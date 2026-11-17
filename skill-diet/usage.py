#!/usr/bin/env python3
"""Skill Diet 0.2: explicit local usage inventory, no host log discovery."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3
import sys


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('时间必须是带时区的字符串')
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('时间必须带时区')
    return d.astimezone(timezone.utc).isoformat(timespec='microseconds')


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS inventory(id TEXT PRIMARY KEY,path TEXT NOT NULL,keep INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS windows(skill TEXT REFERENCES inventory(id),source TEXT,start TEXT,end TEXT,PRIMARY KEY(skill,source,start,end));
    CREATE TABLE IF NOT EXISTS events(source TEXT,event_id TEXT,skill TEXT REFERENCES inventory(id),at TEXT,PRIMARY KEY(source,event_id));
    ''')
    return db


def add(db, skill, path):
    if not skill.strip():
        raise ValueError('Skill ID 不能为空')
    p = Path(path).resolve()
    if not (p/'SKILL.md').is_file():
        raise ValueError('路径必须包含 SKILL.md；只登记，不扫描日志')
    with db:
        db.execute('INSERT INTO inventory(id,path) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET path=excluded.path', (skill,str(p)))


def import_usage(db, data):
    """Windows are importer assertions of complete coverage for that source ONLY."""
    source = data['source']
    if not isinstance(source,str) or not source.strip():
        raise ValueError('必须声明非空来源')
    windows = []
    events = []
    for w in data['windows']:
        start, end = timestamp(w['start']), timestamp(w['end'])
        if start > end:
            raise ValueError('窗口起点晚于终点')
        windows.append((w['skill'],source,start,end))
    for e in data['events']:
        at = timestamp(e['at'])
        if not isinstance(e['id'],str) or not e['id']:
            raise ValueError('事件 ID 必须是非空字符串')
        if not any(s == e['skill'] and a <= at <= b for s,_,a,b in windows):
            raise ValueError('每个事件必须位于本次导入声明的观测窗口内')
        events.append((source,e['id'],e['skill'],at))
    # Atomic batch; same event ID is idempotent, conflicting payload is rejected.
    with db:
        for row in windows:
            db.execute('INSERT OR IGNORE INTO windows VALUES(?,?,?,?)',row)
        for row in events:
            old = db.execute('SELECT * FROM events WHERE source=? AND event_id=?',row[:2]).fetchone()
            if old and tuple(old) != row:
                raise ValueError('相同来源/事件 ID 的内容冲突')
            db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?)',row)
    return {'source':source,'input_events':len(events),'input_windows':len(windows),'note':'重复事件不累计；来源完整性由导入者声明，工具未独立验证'}


def covered(windows, start, end):
    cursor = start
    for a,b in sorted(windows):
        if b < cursor:
            continue
        if a > cursor:
            return False
        cursor = max(cursor,b)
        if cursor >= end:
            return True
    return False


def inventory(db, as_of, days):
    if days <= 0:
        raise ValueError('days 必须大于 0')
    end = timestamp(as_of)
    start = (datetime.fromisoformat(end)-timedelta(days=days)).isoformat(timespec='microseconds')
    result = []
    for item in db.execute('SELECT * FROM inventory ORDER BY id').fetchall():
        skill = item['id']
        events = db.execute('SELECT * FROM events WHERE skill=? AND at<=? ORDER BY at',(skill,end)).fetchall()
        windows = db.execute('SELECT * FROM windows WHERE skill=? AND start<=? ORDER BY source,start',(skill,end)).fetchall()
        sources = []
        for source in sorted({w['source'] for w in windows}):
            ws = [w for w in windows if w['source']==source]
            es = [e for e in events if e['source']==source]
            full = covered([(w['start'],w['end']) for w in ws],start,end)
            recent = sum(e['at'] >= start for e in es)
            status = 'used' if recent else ('not_observed_in_window' if full else 'insufficient_coverage')
            sources.append({'source':source,'status':status,'complete_lookback':full,'count':len(es),'recent_count':recent,'last_used':es[-1]['at'] if es else None,'windows':[{'start':w['start'],'end':w['end']} for w in ws]})
        recent = any(e['at'] >= start for e in events)
        # Conservative across ALL declared sources, not all possible host sources.
        stale = bool(sources) and all(s['complete_lookback'] for s in sources) and not recent
        status = 'used' if recent else ('stale_candidate' if stale else ('insufficient_coverage' if sources else 'unknown'))
        result.append({'id':skill,'path':item['path'],'keep':bool(item['keep']),'status':status,'stale_candidate':stale,'actionable_candidate':stale and not item['keep'],'count':len(events),'last_used':events[-1]['at'] if events else None,'lookback':{'start':start,'end':end},'sources':sources})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',required=True,help='本地 SQLite 文件；不要放在待审计 Skill 内')
    sp=p.add_subparsers(dest='command',required=True)
    a=sp.add_parser('add');a.add_argument('id');a.add_argument('path')
    i=sp.add_parser('import');i.add_argument('file')
    k=sp.add_parser('keep');k.add_argument('id');k.add_argument('value',choices=['on','off'])
    for command in ['list','stale']:
        q=sp.add_parser(command);q.add_argument('--days',type=int,default=30);q.add_argument('--as-of',default=datetime.now(timezone.utc).isoformat())
    args=p.parse_args()
    try:
        with connect(args.db) as db:
            if args.command=='add':
                add(db,args.id,args.path);out={'registered':args.id}
            elif args.command=='import':
                out=import_usage(db,json.loads(Path(args.file).read_text(encoding='utf-8')))
            elif args.command=='keep':
                c=db.execute('UPDATE inventory SET keep=? WHERE id=?',(int(args.value=='on'),args.id))
                if not c.rowcount: raise ValueError('未登记的 Skill ID')
                out={'id':args.id,'keep':args.value=='on'}
            else:
                out=inventory(db,args.as_of,args.days)
                if args.command=='stale': out=[x for x in out if x['actionable_candidate']]
            print(json.dumps(out,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as e:
        print('错误: '+str(e),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
