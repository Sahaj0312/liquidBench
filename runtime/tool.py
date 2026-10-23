"""Trusted container-side tools. This file is never writable by the agent."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path('/workspace')
MAX_FILE = 64_000
MAX_TOTAL = 512_000


def path(value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError('Use a relative workspace path')
    parts = Path(value).parts
    if '..' in parts:
        raise ValueError('Parent traversal is forbidden')
    target = ROOT.joinpath(value)
    for item in [target, *target.parents]:
        if item == ROOT:
            break
        if item.is_symlink():
            raise ValueError('Symlinks are forbidden')
    if not target.resolve().is_relative_to(ROOT):
        raise ValueError('Path escapes workspace')
    return target


def snapshot():
    files = {}
    size = 0
    for base, dirs, names in os.walk(ROOT, followlinks=False):
        for name in dirs + names:
            p = Path(base, name)
            mode = p.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError('Workspace must contain regular files and directories only')
        for name in sorted(names):
            p = Path(base, name)
            if p.stat().st_size > MAX_FILE:
                raise ValueError('File exceeds 64 KB limit')
            content = p.read_text()
            size += len(content.encode())
            if size > MAX_TOTAL or len(files) >= 128:
                raise ValueError('Workspace exceeds snapshot limits')
            files[str(p.relative_to(ROOT))] = content
    return files


def analyze(source):
    proc = subprocess.run(['node', '/opt/liquidbench/analyze.mjs'],
                          input=json.dumps({'source': source}),
                          capture_output=True, text=True, timeout=10)
    if proc.returncode:
        raise RuntimeError('Liquid analysis runtime failed: ' + proc.stderr[:1000])
    return json.loads(proc.stdout)


def execute(request):
    tool = request['tool']
    args = request.get('args', {})
    if tool == '_snapshot':
        return snapshot()
    if tool == '_initialize':
        for name, content in args['files'].items():
            p = path(name)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        return {'ok': True}
    if tool == 'list_files':
        return {'files': sorted(snapshot())}
    if tool == 'read_file':
        p = path(args['path'])
        if p.stat().st_size > MAX_FILE:
            raise ValueError('File exceeds 64 KB limit')
        return {'content': p.read_text()}
    if tool == 'write_file':
        content = args['content']
        if not isinstance(content, str) or len(content.encode()) > MAX_FILE:
            raise ValueError('Content must be text of at most 64 KB')
        p = path(args['path'])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return {'ok': True}
    if tool == 'search':
        needle = args['text']
        if not isinstance(needle, str) or not needle:
            raise ValueError('Search text must be nonempty')
        matches = []
        for name, content in sorted(snapshot().items()):
            for number, line in enumerate(content.splitlines(), 1):
                if needle in line:
                    matches.append({'path': name, 'line': number, 'text': line[:300]})
        return {'matches': matches[:50], 'truncated': len(matches) > 50}
    if tool == 'check':
        proc = subprocess.run(['node', '/opt/liquidbench/theme-check.mjs'],
                              capture_output=True, text=True, timeout=15)
        if proc.returncode:
            raise RuntimeError('Theme Check runtime failed: ' + proc.stderr[:1000])
        return {'offenses': json.loads(proc.stdout)}
    if tool == 'analyze':
        return analyze(path(args['path']).read_text())
    if tool == 'render':
        source = path(args['path']).read_text()
        if args.get('strip_schema', False):
            parsed = analyze(source)
            if not parsed['ok']:
                return parsed
            if len(parsed['schemas']) != 1 or not parsed['schemas'][0]['top_level']:
                raise ValueError('Expected exactly one top-level schema block')
            source = parsed['body_source']
        proc = subprocess.run(['ruby', '/opt/liquidbench/render.rb'],
                              input=json.dumps({'source': source, 'variables': args['variables']}),
                              capture_output=True, text=True, timeout=10)
        if proc.returncode:
            raise RuntimeError('Liquid runtime failed: ' + proc.stderr[:1000])
        return json.loads(proc.stdout)
    raise ValueError('Unknown tool')


try:
    print(json.dumps({'ok': True, 'result': execute(json.load(sys.stdin))}))
except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as error:
    print(json.dumps({'ok': False, 'error': str(error)[:1000]}))
except RuntimeError as error:
    print(json.dumps({'ok': False, 'infrastructure_error': str(error)[:1000]}))
