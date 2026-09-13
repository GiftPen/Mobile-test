#!/usr/bin/env python3
"""Syntax-check the JavaScript every suite injects into the page.

A suite works by appending a <script> to index.html. If that script does not parse, NOTHING
runs -- no error, no result, just the page's own title coming back. The suite reports
"NO RESULT" and you go looking in the game for a bug that is in the test. This has happened
twice (a duplicated const, a duplicated function), so it gets caught here instead: the
scripts are pulled out of the tools and handed to `node --check`."""
import os, re, subprocess, sys, glob, tempfile

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
if subprocess.run(['node', '--version'], capture_output=True).returncode != 0:
    print('js-check: node 없음 — 건너뜀'); sys.exit(0)

# Read the tools with ast and take the string literals' VALUES, not their source text: a
# non-raw Python string writes \\( for a JavaScript \\(, and scraping the source would hand the
# checker an escape that was never meant for it. It also skips the short '<script>' fragments
# the tools use for splicing, which are not scripts.
import ast
bad, n = [], 0
for f in sorted(glob.glob('tools/*.py')):
    try:
        tree = ast.parse(open(f, encoding='utf-8').read())
    except SyntaxError as e:
        bad.append(f'{os.path.basename(f)}: 파이썬 문법 오류 {e}'); continue
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)): continue
        v = node.value
        if '<script>' not in v or '</script>' not in v or len(v) < 200: continue
        body = re.sub(r'%s\b', 'null', v[v.index('<script>') + 8:v.rindex('</script>')])
        n += 1
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as t:
            t.write(body); path = t.name
        r = subprocess.run(['node', '--check', path], capture_output=True, text=True)
        os.unlink(path)
        if r.returncode:
            err = [l.strip() for l in r.stderr.splitlines() if 'Error:' in l]
            bad.append(f'{os.path.basename(f)} 줄 {node.lineno}: ' + (err[0] if err else r.stderr[:80]))

print(f'js-check: 주입 스크립트 {n}개')
for b in bad: print('   !', b)
print('PASS' if not bad else 'FAIL')
sys.exit(1 if bad else 0)
