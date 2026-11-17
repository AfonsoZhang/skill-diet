"""Manage a local Agent Skill inventory without changing installed skills."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import shutil
import sys

if __package__:
    from . import diet, usage, discovery, evidence
else:
    import diet
    import usage
    import discovery
    import evidence


def scan(path):
    """Discover a skill itself, or the immediate children of a skills directory.

    Directory symlinks are listed for inventory purposes. The static auditor has
    its own stricter policy. No target code or host session logs are executed/read.
    """
    root = Path(path).expanduser()
    if not root.is_dir():
        raise ValueError('Scan path must be an existing directory')
    candidates = [root] if (root / 'SKILL.md').is_file() else sorted(root.iterdir())
    result = []
    for item in candidates:
        entry = item / 'SKILL.md'
        if item.is_dir() and entry.is_file():
            result.append({
                'suggested_id': item.name,
                'path': str(item.absolute()),
                'resolved_path': str(item.resolve()),
                'symlink': item.is_symlink(),
                'entry_bytes': entry.stat().st_size,
            })
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', action='version', version='%(prog)s 0.4.0')
    p.add_argument('--db', default=str(Path.home() / '.skill-diet' / 'inventory.sqlite'),
                   help='Local inventory database (default: ~/.skill-diet/inventory.sqlite)')
    commands = p.add_subparsers(dest='command', required=True)
    s = commands.add_parser('scan', help='List skills in an explicitly chosen directory; no registration')
    s.add_argument('path')
    for command in ('discover', 'inspect'):
        q = commands.add_parser(command, help='Discover nested skills and aliases' if command == 'discover'
                                else 'Review skills with categorized, source-located findings')
        q.add_argument('paths', nargs='+', help='Explicit skill, collection, or plugin roots')
        q.add_argument('--cache-root', action='append', default=[], help='Label paths under this root as cache; repeatable')
        q.add_argument('--max-directories', type=int, default=20000)
        q.add_argument('--max-skills', type=int, default=10000)
        if command == 'inspect':
            q.add_argument('--format', choices=('json', 'markdown'), default='json')
            q.add_argument('--check-host', action='store_true', help='Check common executable names on the current PATH')
            q.add_argument('--host-context', help='Operator-reported command/tool/model availability JSON; does not prove activation')
    a = commands.add_parser('add', help='Register or update an ID and its location')
    a.add_argument('id')
    a.add_argument('path')
    for command in ('list', 'stale'):
        q = commands.add_parser(command, help='Show inventory' if command == 'list' else 'Show unused candidates with sufficient coverage')
        q.add_argument('--days', type=int, default=30)
        q.add_argument('--as-of', default=None)
    i = commands.add_parser('import', help='Import explicitly exported usage events')
    i.add_argument('file')
    k = commands.add_parser('keep', help='Mark an inventory item to retain')
    k.add_argument('id')
    k.add_argument('value', choices=('on', 'off'))
    a = commands.add_parser('audit', help='Audit a skill directory without executing it')
    a.add_argument('path')
    a.add_argument('--format', choices=('json', 'markdown'), default='markdown')
    d = commands.add_parser('draft', help='Copy a skill into a new review directory')
    d.add_argument('path')
    d.add_argument('--out', required=True)
    return p


def main(argv=None):
    # Reports contain Unicode source excerpts. Keep redirected output portable
    # on Windows and other hosts whose default pipe encoding is not UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = parser().parse_args(argv)
    try:
        if args.command in ('discover', 'inspect'):
            result = discovery.discover(args.paths, cache_roots=args.cache_root,
                                        max_directories=args.max_directories, max_skills=args.max_skills)
            if args.command == 'inspect':
                context = None
                if args.host_context:
                    context = json.loads(Path(args.host_context).expanduser().read_text(encoding='utf-8'))
                    if not isinstance(context, dict):
                        raise ValueError('Host context must be a JSON object')
                    commands = context.get('commands', {})
                    if not isinstance(commands, dict) or any(not isinstance(k, str) or not isinstance(v, bool) for k, v in commands.items()):
                        raise ValueError('Host context commands must map names to observed booleans')
                    for field in ('tool_names', 'model_names'):
                        if field in context and (not isinstance(context[field], list) or any(not isinstance(v, str) for v in context[field])):
                            raise ValueError(field + ' must be a list of names')
                    context['source'] = 'operator_reported_file'
                if args.check_host:
                    context = dict(context or {})
                    context['commands'] = dict(context.get('commands', {}))
                    context['commands'].update({name: shutil.which(name) is not None for name in
                                               ('python', 'python3', 'node', 'soffice', 'pdftoppm', 'markitdown', 'codex', 'claude')})
                    context['command_observation'] = 'current_process_PATH'
                result = evidence.analyze(result, host_context=context)
                if args.format == 'markdown':
                    print(evidence.render_markdown(result), end='')
                    return 0
        elif args.command == 'scan':
            result = scan(args.path)
        elif args.command == 'audit':
            result = diet.audit(Path(args.path).expanduser())
            if args.format == 'markdown':
                print(diet.report_md(result), end='')
                return 0
        elif args.command == 'draft':
            diet.draft(Path(args.path).expanduser(), Path(args.out).expanduser())
            result = {'review_directory': str(Path(args.out).expanduser().resolve()),
                      'automatic_optimization': False}
        else:
            # Validate query arguments before creating a database.
            if args.command in ('list', 'stale'):
                if args.days <= 0:
                    raise ValueError('days must be greater than zero')
                as_of = usage.timestamp(args.as_of or datetime.now(timezone.utc).isoformat())
            db_path = Path(args.db).expanduser()
            # Viewing an inventory that does not exist is an empty, read-only operation.
            if args.command in ('list', 'stale') and not db_path.exists():
                result = []
            else:
                if args.command != 'add' and not db_path.exists():
                    raise ValueError('Inventory does not exist; register a skill with add first')
                if args.command == 'add':
                    target = Path(args.path).expanduser()
                    if not args.id.strip() or not (target / 'SKILL.md').is_file():
                        raise ValueError('add requires a nonempty ID and a directory containing SKILL.md')
                    db_path.parent.mkdir(parents=True, exist_ok=True)
                db = usage.connect(str(db_path))
                try:
                    if args.command == 'add':
                        usage.add(db, args.id, target)
                        result = {'registered': args.id}
                    elif args.command == 'import':
                        data = json.loads(Path(args.file).expanduser().read_text(encoding='utf-8'))
                        result = usage.import_usage(db, data)
                    elif args.command == 'keep':
                        with db:
                            changed = db.execute('UPDATE inventory SET keep=? WHERE id=?',
                                                 (int(args.value == 'on'), args.id))
                            if not changed.rowcount:
                                raise ValueError('Unknown skill ID')
                        result = {'id': args.id, 'keep': args.value == 'on'}
                    else:
                        result = usage.inventory(db, as_of, args.days)
                        for item in result:
                            item['entry_exists'] = (Path(item['path']) / 'SKILL.md').is_file()
                        if args.command == 'stale':
                            result = [item for item in result if item['actionable_candidate']]
                finally:
                    db.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OverflowError, OSError, sqlite3.Error) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
