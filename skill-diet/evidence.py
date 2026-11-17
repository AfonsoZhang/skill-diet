"""Conservative, read-only evidence checks. No target code is executed."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

MAX_TEXT_BYTES = 256 * 1024
MAX_SUPPORT_FILES = 100
BIG_ENTRY_BYTES = 24 * 1024


def analyze(discovery_report, *, host_context=None):
    findings, coverage = [], []
    skills = discovery_report.get('skills', [])
    seen, names, hashes = set(), {}, {}

    def add(skill, path, line, rule, category, evidence, explanation, recommendation,
            confidence='high', context='Static evidence only.', severity='info'):
        identity = f"{skill['id']}:{path}:{line}:{rule}"
        findings.append(dict(id=hashlib.sha256(identity.encode()).hexdigest()[:16],
            skill_id=skill['id'], path=str(path), line=max(1, line), rule=rule,
            category=category, severity=severity, confidence=confidence,
            evidence=evidence[:240], context=context[:500], explanation=explanation,
            recommendation=recommendation))

    for skill in skills:
        entry = Path(skill['canonical_path']).absolute()
        real = entry.resolve()
        if real in seen:
            continue
        seen.add(real)
        root = real.parent
        cov = dict(skill_id=skill['id'], path=str(real), status='audited', files_read=0,
                   skipped=[], usage='unknown')
        coverage.append(cov)
        name = skill.get('name')
        if name and name in names:
            add(skill, real, 1, 'duplicate-name', 'review_candidate', str(name),
                'Different physical skill roots advertise the same name.',
                'Review host routing precedence and intended ownership.')
        elif name:
            names[name] = root
        if skill.get('entry_read', {}).get('state') == 'skipped':
            cov['status'] = 'skipped'
            cov['skipped'].append({'path': str(real), 'reason': skill['entry_read'].get('reason', 'discovery entry skipped')})
            continue
        try:
            size = real.stat().st_size
            if size > MAX_TEXT_BYTES:
                cov['status'] = 'skipped'
                cov['skipped'].append({'path': str(real), 'reason': 'text size limit'})
                continue
            text = real.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as exc:
            cov['status'] = 'skipped'
            cov['skipped'].append({'path': str(real), 'reason': type(exc).__name__})
            continue
        digest = hashlib.sha256(text.encode()).hexdigest()
        if digest in hashes:
            add(skill, real, 1, 'identical-entry', 'review_candidate', 'Identical entry SHA-256',
                'Separate physical roots contain identical entry text.',
                'Review whether shared maintenance or aliases are appropriate.')
        else:
            hashes[digest] = root
        if size >= BIG_ENTRY_BYTES:
            add(skill, real, 1, 'large-entry', 'load_candidate', f'{size} entry bytes',
                'The entry is large; bytes do not establish host loading or token savings.',
                'Review whether supporting detail can be loaded only when needed.')
        pending = [real]
        visited = set()
        while pending:
            path = pending.pop(0)
            if path in visited:
                continue
            if len(visited) >= MAX_SUPPORT_FILES:
                cov['skipped'].append({'path': str(path), 'reason': 'support file count limit'})
                continue
            visited.add(path)
            try:
                if path.stat().st_size > MAX_TEXT_BYTES:
                    cov['skipped'].append({'path': str(path), 'reason': 'text size limit'})
                    continue
                source = text if path == real else path.read_text(encoding='utf-8')
            except (OSError, UnicodeError) as exc:
                cov['skipped'].append({'path': str(path), 'reason': type(exc).__name__})
                continue
            cov['files_read'] += 1
            fenced = False
            lines = source.splitlines()
            for number, line in enumerate(lines, 1):
                if line.lstrip().startswith(('```', '~~~')):
                    fenced = not fenced
                    continue
                if fenced:
                    continue
                context = '\n'.join(lines[max(0, number-2):number+1])
                if re.search(r'\b(?:must|always|first)\b.*\bread\b.*\ball\b.*\b(?:files|references|documents)\b', line, re.I) and not re.search(r'\b(?:if|optional|when needed|only when)\b', line, re.I):
                    add(skill, path, number, 'read-all', 'load_candidate', line,
                        'An unconditional read-all instruction may increase context loading.',
                        'Review whether reads can be scoped to the current task.', context=context)
                if path.suffix.lower() != '.md':
                    continue
                for match in re.finditer(r'(?<!!)\[[^\]]+\]\(([^\s)]+)(?:\s+[^)]*)?\)', line):
                    # Inline code and code examples do not establish resource dependencies.
                    if line[:match.start()].count('`') % 2:
                        continue
                    target = match.group(1).strip('<>')
                    parsed = urlsplit(target)
                    if parsed.scheme or parsed.netloc or not parsed.path or target.startswith(('/', '#')):
                        continue
                    target = unquote(parsed.path)
                    explicit = target.startswith(('./', 'references/', 'scripts/', 'assets/'))
                    if not explicit:
                        continue
                    if re.search(r'[{}<>$*]|\b(?:generated|output|example|placeholder)\b', target, re.I) or re.search(r'\b(?:generate|generated|create|output|example)\b', line, re.I):
                        add(skill, path, number, 'dynamic-reference', 'review_candidate', match.group(0),
                            'This link may name an example or generated resource.',
                            'Verify the resource lifecycle before treating it as missing.', 'low', context)
                        continue
                    destination = (path.parent / target).resolve()
                    if not destination.is_relative_to(root):
                        cov['skipped'].append({'path': str(path.parent / target), 'reason': 'outside skill root; not read'})
                        add(skill, path, number, 'outside-root-reference', 'review_candidate', match.group(0),
                            'The link resolves outside the physical skill root.',
                            'Review the intended boundary; the destination was not read.', context=context)
                        continue
                    if not destination.exists():
                        add(skill, path, number, 'missing-local-resource', 'defect', match.group(0),
                            'An explicitly linked local resource does not exist.',
                            'Repair the link or restore the intended resource.', context=context, severity='warning')
                    elif destination.is_file() and destination.suffix.lower() in ('.md', '.py', '.js'):
                        pending.append(destination)
                    else:
                        cov['skipped'].append({'path': str(destination), 'reason': 'non-text support resource'})
            if path.suffix.lower() == '.py':
                try:
                    tree = ast.parse(source)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'print':
                        expression = ast.get_source_segment(source, node) or ''
                        identifiers = [n.id.lower() for n in ast.walk(node) if isinstance(n, ast.Name)]
                        suspicious = any(re.search(r'password|passwd|session_cookie', n) for n in identifiers)
                        suspicious |= 'sid' in identifiers and 'cookie' in source.lower()
                        if suspicious:
                            add(skill, path, node.lineno, 'credential-print', 'review_candidate',
                                'print(...) references a credential-like variable; values omitted',
                                'Python AST shows a print call with a credential-like identifier.',
                                'Review whether sensitive values can reach output; redact them if so.',
                                'medium', 'Static AST only; literal values and source snippets omitted.', 'warning')
        if host_context:
            commands = host_context.get('commands', {})
            for command, observed in commands.items():
                if observed is False:
                    for number, line in enumerate(text.splitlines(), 1):
                        if re.search(r'\b(?:requires?|must|prerequisite|install)\b', line, re.I) and re.search(r'(?<![\w-])' + re.escape(command) + r'(?![\w-])', line):
                            add(skill, real, number, 'host-command-prerequisite', 'host_prerequisite', line,
                                f'Provided host context explicitly reports {command!r} unavailable.',
                                'Check the documented prerequisite on the target host.', context='Host context supplied by caller; source: ' + str(host_context.get('source', 'unspecified')))
    return dict(schema_version=1, findings=findings, coverage=coverage,
                discovery_summary=discovery_report.get('summary', {}),
                discovery_issues=discovery_report.get('issues', []),
                host_context_coverage=dict(source=(host_context or {}).get('source'),
                    supported_checks=['commands'],
                    supplied_unchecked_fields=[key for key in ('tool_names', 'model_names') if key in (host_context or {})]),
                summary=dict(skills_considered=len(coverage),
                    skills_audited=sum(c['status'] == 'audited' for c in coverage),
                    skills_skipped=sum(c['status'] == 'skipped' for c in coverage),
                    findings=len(findings), usage_status='unknown'),
                limitations=['Conservative static checks, not comprehensive semantic lint.',
                    'No target code, commands, APIs, or activity logs executed or inspected.',
                    'Usage is unknown; file timestamps do not establish use.',
                    'Only explicit local Markdown links outside code examples are checked; bare and backtick references are not dependencies.',
                    'Only linked .md, .py and .js text within the physical skill root is read, with size and count limits.',
                    'Tool and model availability is not inferred from this engine or from incomplete host lists.'])


def render_markdown(report):
    def safe(value):
        return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('`', "'")
    rows = ['# Static evidence review', '', f"Findings: {len(report.get('findings', []))}. Usage: unknown.", '']
    for finding in report.get('findings', []):
        rows.extend([f"- **{safe(finding['category'])}: {safe(finding['rule'])}** — {safe(finding['path'])}:{finding['line']}",
                     f"  {safe(finding['explanation'])} {safe(finding['recommendation'])}"])
    rows.extend(['', 'Coverage:', ''])
    summary = report.get('summary', {})
    rows.append(f"- Skills considered: {summary.get('skills_considered', 0)}; audited: {summary.get('skills_audited', 0)}; skipped: {summary.get('skills_skipped', 0)}.")
    rows.append('- Discovery summary: ' + safe(json.dumps(report.get('discovery_summary', {}), ensure_ascii=False)))
    for issue in report.get('discovery_issues', []):
        rows.append('- Discovery issue: ' + safe(json.dumps(issue, ensure_ascii=False)))
    for item in report.get('coverage', []):
        rows.append(f"- {safe(item['path'])}: {safe(item['status'])}; {item['files_read']} text files read.")
        for skipped in item.get('skipped', []):
            rows.append(f"  Skipped {safe(skipped['path'])}: {safe(skipped['reason'])}.")
    host = report.get('host_context_coverage', {})
    rows.append('- Host checks: commands only; source: ' + safe(host.get('source') or 'not supplied') +
                '; supplied fields not checked: ' + safe(', '.join(host.get('supplied_unchecked_fields', [])) or 'none') + '.')
    rows.extend(['', 'Limits:', ''])
    rows.extend('- ' + safe(item) for item in report.get('limitations', []))
    return '\n'.join(rows) + '\n'
