#!/usr/bin/env python3
"""Skill Diet 0.1: conservative, dependency-free static audit and review draft."""
import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

MAX_FILE = 2_000_000
MAX_TOTAL = 20_000_000
TEXT_EXT = {'.md', '.txt', '.yaml', '.yml', '.json', '.py', '.sh', '.js', '.ts'}
OPTIONAL = re.compile(r'\b(if|when|optional|only if|unless)\b|如果|当.{0,12}时|可选|仅当', re.I)
BATCH = re.compile(r'\b(read|load|reading|loading)\b.{0,35}\b(all|every|following)\b|全部.{0,12}(阅读|读取|加载)|批量.{0,8}(阅读|读取|加载)|必须.{0,20}(阅读|读取|加载)', re.I)
GUARD = re.compile(r'\b(must|never|validation|verify|safety|permission|approval)\b|必须|禁止|安全|验证|校验|权限|审批', re.I)
LINK = re.compile(r'\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)|`([^`\n]+\.(?:md|py|sh|js|ts|json|ya?ml|txt))`')
CAPS = {'narration': r'narration|voiceover|旁白|配音', 'animation': r'animation|动画', 'charts': r'charts?|图表', 'images': r'image generation|图片生成|图像生成', 'templates': r'templates?|模板', 'export': r'export|导出'}

def inside(path, root):
    return path == root or root in path.parents

def audit(root):
    root = Path(root).resolve()
    if not (root / 'SKILL.md').is_file():
        raise ValueError('目录必须包含 SKILL.md')
    files, issues, texts, total = [], [], {}, 0
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            raise ValueError('拒绝符号链接: ' + rel)
        if not p.is_file():
            continue
        size = p.stat().st_size
        total += size
        if size > MAX_FILE or total > MAX_TOTAL:
            raise ValueError('超出原型大小限制（单文件2MB、总计20MB）')
        raw = p.read_bytes()
        item = {'path': rel, 'bytes': size, 'sha256': hashlib.sha256(raw).hexdigest()}
        if p.suffix.lower() in TEXT_EXT:
            try:
                text = raw.decode('utf-8')
                texts[rel] = text
                item.update(lines=len(text.splitlines()), characters=len(text))
            except UnicodeDecodeError:
                issues.append({'type': 'non_utf8', 'file': rel})
        files.append(item)
    edges, candidates = [], []
    for rel, text in texts.items():
        if not rel.endswith('.md'):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if BATCH.search(line):
                issues.append({'type': 'batch_read_candidate', 'file': rel, 'line': n, 'evidence': line[:500], 'conditional_hint': bool(OPTIONAL.search(line))})
            for m in LINK.finditer(line):
                ref = unquote((m.group(1) or m.group(2)).split('#')[0])
                if not ref or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', ref):
                    continue
                target = (root / rel).parent.joinpath(ref).resolve()
                external = not inside(target, root)
                dest = None if external else target.relative_to(root).as_posix()
                edges.append({'from': rel, 'line': n, 'reference': ref, 'to': dest, 'status': 'outside_root' if external else ('exists' if target.is_file() else 'unresolved'), 'conditional_hint': bool(OPTIONAL.search(line))})
        for cap, pattern in CAPS.items():
            hits = [i for i, line in enumerate(text.splitlines(), 1) if re.search(pattern, line, re.I)]
            if hits:
                candidates.append({'capability': cap, 'file': rel, 'lines': hits[:30], 'decision': 'REVIEW_REQUIRED', 'default': 'preserve', 'reason': '关键词候选不是可关闭能力证明；检查依赖与输出契约。'})
    entry = texts.get('SKILL.md', '')
    if len(entry.splitlines()) > 500:
        issues.append({'type': 'large_entry', 'file': 'SKILL.md', 'lines': len(entry.splitlines())})
    duplicate = {}
    for item in files:
        if item['bytes']:
            duplicate.setdefault(item['sha256'], []).append(item['path'])
    return {'schema_version': 1, 'tool_version': '0.1.0', 'scope': 'static_only', 'files': files, 'summary': {'files': len(files), 'bytes_on_disk': total, 'entry_characters': len(entry), 'markdown_characters': sum(len(v) for k,v in texts.items() if k.endswith('.md'))}, 'references': edges, 'capability_candidates': candidates, 'issues': issues, 'identical_files': [v for v in duplicate.values() if len(v)>1], 'limitations': ['未运行目标 Skill，不执行其脚本。', '磁盘字节/字符不是实际上下文 token 或费用。', 'Markdown 静态引用只覆盖显式链接和部分反引号路径；代码/动态路径/隐式依赖需人工核查。', '条件提示是行级启发式，不证明安全可省略。']}

def report_md(r):
    s = r['summary']
    lines = ['# Skill Diet 静态体检', '', f"文件 {s['files']} 个；磁盘 {s['bytes_on_disk']} bytes；入口 {s['entry_characters']} 字符。", '', '**没有运行任务；不宣称节省 token 或保持行为等价。**', '', '## 体积前十（并非实际加载量）']
    for f in sorted(r['files'], key=lambda x:x['bytes'], reverse=True)[:10]:
        lines.append(f"- `{f['path']}`: {f['bytes']} bytes")
    lines += ['', '## 待核查证据']
    for i in r['issues']:
        lines.append(f"- {i['type']}: `{i['file']}`" + (f":{i['line']} — {i['evidence']}" if 'line' in i else ''))
    for e in r['references']:
        if e['status'] != 'exists':
            lines.append(f"- {e['status']}: `{e['from']}:{e['line']}` → `{e['reference']}`")
    lines += ['', '## 能力候选（默认保留，不能直接关闭）']
    for c in r['capability_candidates']:
        lines.append(f"- {c['capability']}: `{c['file']}`，行 {','.join(map(str,c['lines']))}")
    lines += ['', '## 限制'] + ['- '+x for x in r['limitations']]
    return '\n'.join(lines)+'\n'

def draft(root, out):
    root, out = Path(root).resolve(), Path(out).resolve()
    if inside(out, root) or inside(root, out):
        raise ValueError('输出必须在源目录之外，且不能是源目录的祖先')
    if out.exists():
        raise ValueError('输出已存在；拒绝覆盖')
    r = audit(root)
    out.mkdir(parents=True)
    try:
        shutil.copytree(root, out/'original')
        (out/'audit.json').write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
        (out/'REPORT.md').write_text(report_md(r), encoding='utf-8')
        plan = {'status':'REVIEW_REQUIRED', 'automatic_switching':False, 'original_sha256':next(x['sha256'] for x in r['files'] if x['path']=='SKILL.md'), 'candidates':r['capability_candidates'], 'keep_invariants':['原有安全/权限/事实/格式/质量/交付约束全部保留'], 'next_step':'根据任务人工确认能力、依赖和入口后，才编写精简版本并做回归；此草稿不会自动重写入口。'}
        (out/'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
        (out/'REGRESSION.md').write_text('# 待运行的任务回归\n\n未运行任何目标任务。对原版和候选精简版使用同一模型、宿主、任务和输入。\n\n|任务|版本|实际输入token|延迟|成本|成功|关键约束遗漏|产物验证|\n|---|---|---|---|---|---|---|---|\n\n至少覆盖默认路径、可选能力开启、复杂输入、信息缺失和失败恢复。逐次保存实际 trace。不能用文件字符差代替端到端收益。\n',encoding='utf-8')
    except Exception:
        shutil.rmtree(out)
        raise
    return r

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sp=p.add_subparsers(dest='command', required=True)
    a=sp.add_parser('audit'); a.add_argument('skill'); a.add_argument('--format',choices=['json','markdown'],default='markdown')
    d=sp.add_parser('draft'); d.add_argument('skill'); d.add_argument('--out',required=True)
    args=p.parse_args()
    try:
        if args.command=='audit':
            r=audit(args.skill)
            print(json.dumps(r,ensure_ascii=False,indent=2) if args.format=='json' else report_md(r),end='\n')
        else:
            draft(args.skill,args.out); print('已生成待审查副本；源文件不变；未自动精简或执行。')
        return 0
    except (ValueError, OSError) as e:
        print('错误: '+str(e),file=sys.stderr); return 2

if __name__=='__main__':
    sys.exit(main())
