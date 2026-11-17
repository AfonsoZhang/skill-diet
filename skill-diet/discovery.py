"""Bounded, read-only discovery of explicitly supplied skill roots.

HostObservation is a trusted caller interface, not authentication. No verified
host adapter is bundled. Filesystem location and absence never prove inactivity.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re

EXCLUDED_DIRECTORIES = frozenset({'.git', 'node_modules', '.venv', '__pycache__'})
METADATA_BYTES = 65536


@dataclass(frozen=True)
class HostObservation:
    """Observation supplied programmatically by a verified host adapter.

    Callers must verify their adapter's provenance before constructing this value.
    Neither a user manifest nor a cache listing constitutes verified observation.
    """
    host: str
    source: str
    active_paths: tuple[str, ...] = ()
    inactive_paths: tuple[str, ...] = ()
    observed_at: str = ''


def _absolute(path):
    return os.path.abspath(os.path.expanduser(os.fspath(path)))


def _canonical(path):
    return os.path.realpath(_absolute(path))


def _entry_path(path):
    return path if Path(path).name == 'SKILL.md' else os.path.join(path, 'SKILL.md')


def _name(text, fallback):
    # Deliberately a scalar-only subset. Unsupported YAML is not an error.
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return fallback
    for line in lines[1:]:
        if line.strip() in {'---', '...'}:
            break
        match = re.fullmatch(r'name:\s*(.*?)\s*', line)
        if match:
            value = match.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            elif any(c in value for c in '{}[]#&*!>|'):
                continue
            if value:
                return value
    return fallback


def discover(roots, *, cache_roots=(), host_observation=None,
             max_directories=20000, max_skills=10000, max_entry_bytes=2_000_000):
    """Discover entries without running code or reading host logs.

    Budgets count visited logical directories and unique canonical entries.
    Symlink aliases are traversed independently with ancestor cycle protection.
    """
    if not isinstance(max_directories, int) or max_directories < 1:
        raise ValueError('max_directories must be a positive integer')
    if not isinstance(max_skills, int) or max_skills < 1:
        raise ValueError('max_skills must be a positive integer')
    if host_observation is not None and not isinstance(host_observation, HostObservation):
        raise TypeError('host_observation must be a HostObservation from a verified adapter')
    if not isinstance(max_entry_bytes, int) or max_entry_bytes < 1:
        raise ValueError('max_entry_bytes must be a positive integer')
    if host_observation is not None and not all(
            isinstance(value, str) and value.strip()
            for value in (host_observation.host, host_observation.source, host_observation.observed_at)):
        raise ValueError('host observation requires nonempty host, source, and observed_at provenance')
    root_paths = list(dict.fromkeys(_absolute(p) for p in roots))
    caches = [_canonical(p) for p in cache_roots]
    issues, entries, visited = [], {}, set()
    exhausted = set()

    def issue(code, path, detail):
        issues.append({'code': code, 'path': str(path), 'detail': detail})

    def source(path, canonical):
        for candidate in (path, canonical):
            if '/plugins/cache/' in candidate.replace('\\', '/'):
                return 'plugin_cache'
            for cache in caches:
                try:
                    if os.path.commonpath([candidate, cache]) == cache:
                        return 'plugin_cache'
                except ValueError:
                    pass
        return 'local'

    def entry(path):
        canonical = _canonical(path)
        alias = {'path': path, 'is_alias': path != canonical,
                 'source_kind': source(path, canonical)}
        if canonical in entries:
            if alias not in entries[canonical]['paths']:
                entries[canonical]['paths'].append(alias)
            return
        if len(entries) >= max_skills:
            if 'skills' not in exhausted:
                issue('skill_budget', path, 'Unique skill limit reached; inventory is incomplete')
                exhausted.add('skills')
            return
        try:
            digest, prefix = hashlib.sha256(), bytearray()
            size = os.stat(path).st_size
            skipped = size > max_entry_bytes
            read_bytes = 0
            if not skipped:
                with open(path, 'rb') as stream:
                    while chunk := stream.read(min(65536, max_entry_bytes + 1 - read_bytes)):
                        read_bytes += len(chunk)
                        if read_bytes > max_entry_bytes:
                            skipped = True
                            size = max(size, read_bytes)
                            break
                        digest.update(chunk)
                        if len(prefix) < METADATA_BYTES:
                            prefix.extend(chunk[:METADATA_BYTES - len(prefix)])
                if not skipped:
                    size = read_bytes
            if skipped:
                prefix.clear()
                exhausted.add('entry_bytes')
                issue('entry_byte_budget', path,
                      'Entry exceeds byte budget; content and metadata skipped, hash unknown')
            if not skipped and size > METADATA_BYTES:
                issue('metadata_truncated', path, 'Name parsing limited to first 65536 bytes')
            try:
                text = bytes(prefix).decode('utf-8')
            except UnicodeDecodeError:
                text = bytes(prefix).decode('utf-8', errors='replace')
                issue('utf8_decode', path, 'Metadata contains invalid or truncated UTF-8; replacement used')
        except OSError as exc:
            issue('read_error', path, str(exc))
            return
        entries[canonical] = {
            'id': hashlib.sha256(os.fsencode(canonical)).hexdigest(),
            'name': _name(text, Path(canonical).parent.name),
            'canonical_path': canonical, 'paths': [alias], 'entry_bytes': size,
            'entry_sha256': None if skipped else digest.hexdigest(),
            'entry_read': {'state': 'skipped' if skipped else 'complete',
                           'reason': 'entry_byte_budget' if skipped else None},
            'host_activity': {'state': 'unknown', 'evidence': None}}

    pending = [(root, set()) for root in reversed(root_paths)]
    while pending:
        path, ancestors = pending.pop()
        if path in visited:
            continue
        try:
            if not os.path.exists(path):
                issue('broken_link' if os.path.islink(path) else 'missing_path', path, 'Path does not exist')
                continue
            if os.path.isfile(path):
                if Path(path).name == 'SKILL.md':
                    entry(path)
                else:
                    issue('unsupported_root', path, 'Expected directory or SKILL.md')
                continue
            canonical = _canonical(path)
            if canonical in ancestors:
                issue('symlink_cycle', path, 'Directory resolves to an ancestor')
                continue
            if len(visited) >= max_directories:
                if 'directories' not in exhausted:
                    issue('directory_budget', path, 'Directory limit reached; inventory is incomplete')
                    exhausted.add('directories')
                continue
            visited.add(path)
            with os.scandir(path) as scan:
                children = sorted(scan, key=lambda item: item.name)
            for child in reversed(children):
                if child.name in EXCLUDED_DIRECTORIES and child.is_dir(follow_symlinks=True):
                    issue('excluded_directory', child.path, 'Excluded by discovery policy')
                elif child.name == 'SKILL.md' or child.is_dir(follow_symlinks=True) or child.is_symlink():
                    pending.append((child.path, ancestors | {canonical}))
        except OSError as exc:
            issue('filesystem_error', path, str(exc))
    if host_observation is not None:
        active = {_canonical(_entry_path(p)) for p in host_observation.active_paths}
        inactive = {_canonical(_entry_path(p)) for p in host_observation.inactive_paths}
        for canonical, item in entries.items():
            if canonical in active & inactive:
                issue('conflicting_host_observation', canonical, 'Adapter reports both active and inactive; state unknown')
            elif canonical in active | inactive:
                item['host_activity'] = {
                    'state': 'confirmed_active' if canonical in active else 'confirmed_inactive',
                    'evidence': {'host': host_observation.host, 'source': host_observation.source,
                                 'observed_at': host_observation.observed_at}}
    skills = sorted(entries.values(), key=lambda item: item['canonical_path'])
    for item in skills:
        item['paths'].sort(key=lambda alias: alias['path'])
    return {'schema_version': 1, 'roots': root_paths, 'skills': skills, 'issues': issues,
            'summary': {'skills': len(skills), 'directories_visited': len(visited),
                        'paths': sum(len(s['paths']) for s in skills),
                        'truncated': bool(exhausted), 'issues': len(issues)},
            'limitations': ['Only explicitly supplied roots are inspected.',
                            'No verified host adapter is bundled; host activity defaults to unknown.',
                            'HostObservation is a trusted caller interface, not authentication.',
                            'Cache location and missing observations do not establish inactivity.',
                            'Name parsing supports a conservative scalar frontmatter subset.']}
