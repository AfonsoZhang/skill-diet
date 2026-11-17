#!/usr/bin/env python3
"""Synthetic, bounded review comparison. No model or real host data is used."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import time

SCHEMA = 1
MODEL = 'gpt-6.1-sol'
BUDGET = {'operations': 12, 'characters': 40000, 'seconds': 240}
RULES = ('missing-resource', 'credential-output', 'backend-mismatch', 'stale-cache',
         'source-root-confusion', 'broken-command-path', 'route-conflict')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def digest(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob('*'), key=lambda p: p.relative_to(root).as_posix()):
        if p.is_symlink():
            h.update(p.relative_to(root).as_posix().encode() + b'LINK' + os.readlink(p).encode())
        elif p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + b'\0' + p.read_bytes())
    return h.hexdigest()


def prepare(root, seed=17):
    if root.exists():
        raise ValueError('destination must not exist')
    rng = random.Random(seed)
    names = rng.sample(['amber', 'birch', 'cedar', 'delta', 'elm', 'fern', 'garnet', 'harbor'], 8)
    specs = [
      ('user', 'For invoice summaries, read the required [format guide](references/format.md) before writing.', 'missing-resource'),
      ('project/team', 'For service diagnostics, run the [diagnostic helper](scripts/diagnose.py) and return its output.', 'credential-output'),
      ('plugins/cache/tools/1.0', 'For image export use backend="legacy". The supported backend is "native"; legacy was removed.', 'backend-mismatch'),
      ('user', 'For offline notes read `cache/index.json`; it is authoritative even after the source revision changes.', 'stale-cache'),
      ('project/team', 'For glossary lookup read `references/terms.md` relative to the current working directory, regardless of this skill location.', 'source-root-confusion'),
      ('plugins/cache/tools/2.0', 'For CSV cleanup run `python scripts/normalize.py`.', 'broken-command-path'),
      ('user', 'For invoice summaries always use this skill exclusively; do not run any other invoice summary skill.', 'route-conflict'),
      ('project/team', 'For visual notes use backend="native". If optional references/example.md is absent, proceed with the inline example. Never print SERVICE_TOKEN; show only whether it is set.', None),
    ]
    truth = []
    for i, (folder, instruction, rule) in enumerate(specs):
        rel = Path(folder) / names[i] / 'SKILL.md'
        body = f'---\nname: {names[i]}\ndescription: Assist with a focused document workflow.\n---\n# Workflow\n\n{instruction}\n'
        p = root / 'library' / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding='utf-8', newline='\n')
        if rule:
            truth.append({'rule': rule, 'path': rel.as_posix(), 'lines': [7, 7]})
        if i == 1:
            helper = p.parent / 'scripts/diagnose.py'
            helper.parent.mkdir()
            helper.write_text('# Synthetic fixture; no real service or credential.\nsession_cookie = \"synthetic-session\"\nprint(session_cookie)\n', encoding='utf-8', newline='\n')
            truth[-1]['path'] = helper.relative_to(root / 'library').as_posix()
            truth[-1]['lines'] = [3, 3]
        if i == 3:
            (p.parent / 'cache').mkdir()
            (p.parent / 'cache/index.json').write_text('{"source_revision": 1, "current_revision": 2, "items": []}\n', encoding='utf-8', newline='\n')
        if i == 4:
            (p.parent / 'references').mkdir()
            (p.parent / 'references/terms.md').write_text('A term is a glossary entry.\n', encoding='utf-8', newline='\n')
        if i == 5:
            (p.parent / 'scripts').mkdir()
            (p.parent / 'scripts/clean.py').write_text('# Synthetic inert placeholder.\n', encoding='utf-8', newline='\n')
    # Either conflicting routing instruction is an acceptable location.
    truth[6]['alternate_paths'] = [truth[0]['path']]
    try:
        (root / 'library/user/alias').symlink_to(names[0], target_is_directory=True)
        (root / 'library/project/team/cycle').symlink_to('.', target_is_directory=True)
    except OSError:
        pass
    manifest = {'schema': SCHEMA, 'seed': seed, 'model': MODEL, 'budget': BUDGET,
                'input_hash': digest(root / 'library'), 'rules': RULES}
    write(root / 'manifest.json', manifest)
    write(root / 'private/truth.json', truth)
    (root / 'prompt.txt').write_text(PROMPT, encoding='utf-8', newline='\n')
    return manifest


PROMPT = '''Review this synthetic skill library for actionable defects. Use only the harness action interface; do not read private/, state files, harness/product source code, or use other filesystem/shell access to inspect the library. All content is inert synthetic data. Taxonomy: missing-resource (required resource absent), credential-output (instructs disclosure of a secret), backend-mismatch (requires unsupported backend), stale-cache (uses known obsolete cache as authoritative), source-root-confusion (resolves skill resources from caller working directory), broken-command-path (command references absent executable/script), route-conflict (exclusive overlapping routes). Consider conditional references, symlink aliases and installed cache versions before reporting. Inspect, when available, supplies evidence to verify and may miss semantic issues. Actual ground truth is hidden. Both conditions use gpt-6.1-sol and the same limits: 12 actions including submit, 40000 returned characters, 240 elapsed seconds from first action. Use list/read; inspect is available only in the aided condition. Submit JSON array entries with exactly rule, path (relative file path), line (positive integer), category (defect, benign, or uncertain), explanation. Only actionable defect entries score; uncertain entries do not score as defects. Do not guess findings to inflate recall. No rule aliases are accepted. Tokens and monetary cost are unobserved. End by submitting within the budget.\n'''


def safe(root, value):
    p = (root / value).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError('path escapes library')
    return p


def load(root):
    m = json.loads((root / 'manifest.json').read_text())
    if m.get('schema') != SCHEMA or m.get('budget') != BUDGET or m.get('model') != MODEL or type(m.get('seed')) is not int:
        raise ValueError('invalid manifest or altered budget')
    if digest(root / 'library') != m['input_hash']:
        raise ValueError('synthetic inputs changed')
    # Independently reconstruct the seeded input hash; rejects changed seed/hash pairs.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        expected = prepare(Path(d) / 'reference', m['seed'])
        if expected['input_hash'] != m['input_hash']:
            raise ValueError('manifest does not match seeded dataset')
    return m


def findings(value, library):
    if not isinstance(value, list):
        raise ValueError('submission must be an array')
    for f in value:
        if not isinstance(f, dict) or set(f) != {'rule', 'path', 'line', 'category', 'explanation'}:
            raise ValueError('invalid finding schema')
        if f['rule'] not in RULES or f['category'] not in ('defect', 'benign', 'uncertain') or type(f['line']) is not int or f['line'] < 1 or not isinstance(f['explanation'], str):
            raise ValueError('invalid finding values')
        if not isinstance(f['path'], str) or Path(f['path']).is_absolute() or Path(f['path']).as_posix() != f['path']:
            raise ValueError('path must be relative and normalized')
        if not safe(library, f['path']).is_file():
            raise ValueError('finding path must be an existing library file')
    return value


def action(root, condition, operation, path=None, submission=None):
    if condition not in ('plain', 'aided') or operation not in ('list', 'read', 'inspect', 'submit'):
        raise ValueError('unknown condition or operation')
    m = load(root)
    statepath = root / f'{condition}.json'
    s = json.loads(statepath.read_text()) if statepath.exists() else {
        'schema': SCHEMA, 'condition': condition, 'model': MODEL, 'budget': BUDGET,
        'input_hash': m['input_hash'], 'seed': m['seed'], 'start': time.monotonic(),
        'operations': 0, 'returned_characters': 0, 'read_calls': 0, 'read_characters': 0,
        'tool_calls': 0, 'events': [], 'tokens': None, 'cost': None}
    if s.get('budget') != BUDGET or s.get('condition') != condition or s.get('input_hash') != m['input_hash']:
        raise ValueError('invalid run state')
    elapsed = time.monotonic() - s['start']
    if 'findings' in s or elapsed > BUDGET['seconds'] or s['operations'] >= BUDGET['operations']:
        raise ValueError('run completed or budget exhausted')
    lib = root / 'library'
    if operation == 'list':
        result = '\n'.join(p.relative_to(lib).as_posix() for p in sorted(lib.rglob('*'), key=lambda p: p.relative_to(lib).as_posix()) if p.is_file() or p.is_symlink())
    elif operation == 'read':
        if not path:
            raise ValueError('read requires --path')
        result = '\n'.join(f'{i}: {line}' for i, line in enumerate(safe(lib, path).read_text().splitlines(), 1))
        s['read_calls'] += 1
        s['read_characters'] += len(result)
    elif operation == 'inspect':
        if condition != 'aided':
            raise ValueError('inspect unavailable in plain condition')
        result = json.dumps(inspect(lib), sort_keys=True)
        s['tool_calls'] += 1
    elif operation == 'submit':
        s['findings'] = findings(json.loads(Path(submission).read_text()), lib)
        result = 'Submission recorded.'
    else:
        raise ValueError('unknown operation')
    if s['returned_characters'] + len(result) > BUDGET['characters']:
        raise ValueError('character budget exhausted; request a smaller action')
    elapsed = time.monotonic() - s['start']
    if elapsed > BUDGET['seconds']:
        raise ValueError('elapsed budget exhausted')
    s['operations'] += 1
    s['returned_characters'] += len(result)
    s['elapsed_seconds'] = elapsed
    s['events'].append({'operation': operation, 'path': path, 'characters': len(result), 'elapsed_seconds': elapsed})
    write(statepath, s)
    return result


def inspect(library):
    try:
        from skill_diet.discovery import discover
        from skill_diet import evidence
    except ImportError:
        # Source checkout fallback; this still imports the actual product modules.
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill-diet'))
        import discovery
        import evidence
        discover = discovery.discover
    inventory = discover([library], cache_roots=[library / 'plugins/cache'])
    return evidence.analyze(inventory)


def validate_events(state):
    events = state.get('events')
    if not isinstance(events, list) or not events or events[-1].get('operation') != 'submit':
        raise ValueError('run must end with a submit event')
    previous = 0
    for i, event in enumerate(events):
        operation = event.get('operation')
        if operation not in ('list', 'read', 'inspect', 'submit') or (operation == 'inspect' and state['condition'] != 'aided'):
            raise ValueError('invalid event operation')
        if operation == 'submit' and i != len(events)-1:
            raise ValueError('submit must be the last event')
        chars = event.get('characters')
        elapsed = event.get('elapsed_seconds')
        if type(chars) is not int or chars < 0 or not isinstance(elapsed, (int, float)) or not previous <= elapsed <= BUDGET['seconds']:
            raise ValueError('invalid event counters')
        previous = elapsed
    expected = {
        'operations': len(events),
        'returned_characters': sum(e['characters'] for e in events),
        'read_calls': sum(e['operation'] == 'read' for e in events),
        'read_characters': sum(e['characters'] for e in events if e['operation'] == 'read'),
        'tool_calls': sum(e['operation'] == 'inspect' for e in events),
        'elapsed_seconds': events[-1]['elapsed_seconds'],
        'tokens': None, 'cost': None,
    }
    if any(state.get(key) != value for key, value in expected.items()):
        raise ValueError('aggregate effort disagrees with event log')


def score(root):
    m = load(root)
    truth = json.loads((root / 'private/truth.json').read_text())
    # Regenerate truth as well; edited private answers must not alter scoring.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'reference'
        prepare(p, m['seed'])
        if truth != json.loads((p / 'private/truth.json').read_text()):
            raise ValueError('truth changed')
    scores = {}
    for condition in ('plain', 'aided'):
        s = json.loads((root / f'{condition}.json').read_text())
        if any(s.get(k) != m[k] for k in ('schema', 'model', 'budget', 'input_hash', 'seed')) or s.get('condition') != condition:
            raise ValueError('incomparable run metadata')
        if not 1 <= s['operations'] <= BUDGET['operations'] or not 0 <= s['returned_characters'] <= BUDGET['characters'] or not 0 <= s['elapsed_seconds'] <= BUDGET['seconds']:
            raise ValueError('invalid reported budget usage')
        validate_events(s)
        fs = findings(s['findings'], root / 'library')
        matched, false, seen = set(), 0, set()
        for f in fs:
            if f['category'] != 'defect':
                continue
            canonical = safe(root / 'library', f['path']).relative_to((root / 'library').resolve()).as_posix()
            key = (f['rule'], canonical, f['line'])
            if key in seen:
                continue
            seen.add(key)
            hits = [i for i, t in enumerate(truth) if t['rule'] == f['rule'] and canonical in [t['path'], *t.get('alternate_paths', [])] and t['lines'][0] <= f['line'] <= t['lines'][1]]
            if hits:
                matched.update(hits)
            else:
                false += 1
        tp = len(matched)
        scores[condition] = {'true_positives': tp, 'false_positives': false, 'misses': len(truth)-tp,
          'precision': tp/(tp+false) if tp+false else None, 'recall': tp/len(truth),
          'false_positive_rate': None, 'benign_candidate_denominator': None,
          **{k: s[k] for k in ('elapsed_seconds', 'operations', 'returned_characters', 'read_calls', 'read_characters', 'tool_calls', 'tokens', 'cost')}}
    return {'schema': SCHEMA, 'input_hash': m['input_hash'], 'seed': m['seed'], 'model': MODEL,
            'budget': BUDGET, 'interpretation': 'One descriptive pair; no significance claim. Effort proxies are not human minutes or model tokens.', 'scores': scores}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'action', 'score'])
    p.add_argument('root', type=Path)
    p.add_argument('--seed', type=int, default=17)
    p.add_argument('--condition', choices=['plain', 'aided'])
    p.add_argument('--operation', choices=['list', 'read', 'inspect', 'submit'])
    p.add_argument('--path')
    p.add_argument('--submission', type=Path)
    a = p.parse_args()
    try:
        if a.command == 'prepare':
            result = prepare(a.root, a.seed)
        elif a.command == 'score':
            result = score(a.root)
        else:
            if not a.condition or not a.operation:
                raise ValueError('action requires --condition and --operation')
            result = action(a.root, a.condition, a.operation, a.path, a.submission)
        print(result if isinstance(result, str) else json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as e:
        p.exit(2, f'error: {e}\n')

if __name__ == '__main__':
    main()
