#!/usr/bin/env python3
"""MCP server that lets Claude read and edit the Disxcel workbook. Writes go to book.json, which an open
Disxcel window picks up within a second.

    claude mcp add -s user disxcel -- python3 /path/to/disxcel/mcp_server.py
"""
import builtins, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import book
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('disxcel', instructions='Disxcel is the user\'s personal spreadsheet: sheets of plain text values (no formulas), '
              'columns A-Z, rows from 1. Cells are addressed like "B3". Read before you overwrite.')
REF = re.compile(r'^([A-Z])([1-9]\d*)$')

def load():
    b = json.loads(book.read() or 'null') or {'active': 0, 'sheets': [{'name': 'Hoja 1', 'cells': {}}]}
    for s in b['sheets']: s.setdefault('cells', {})
    return b
def find(b, name):
    for s in b['sheets']:
        if s.get('name') == name: return s
    raise ValueError('No sheet named %r. Sheets: %s' % (name, ', '.join(s.get('name', '') for s in b['sheets'])))
def ref(r):
    m = REF.match(r.strip().upper())
    if not m: raise ValueError('%r is not a cell like A1 (columns A-Z only)' % r)
    return ord(m[1]) - 65, int(m[2]) - 1
def edit(fn):  # read-modify-write under the lock shared with the app
    with book.locked():
        b = load(); out = fn(b); book.write(json.dumps(b, ensure_ascii=False))
    return out

@mcp.tool()
def list_sheets() -> list[dict]:
    """List the sheets with how many cells each one uses and the range they span."""
    out = []
    for s in load()['sheets']:
        refs = [ref(k) for k in s['cells']]
        span = '%s1:%s%d' % ('A', chr(65 + max(c for c, _ in refs)), max(r for _, r in refs) + 1) if refs else None
        out.append({'name': s['name'], 'cells': len(refs), 'range': span})
    return out

@mcp.tool()
def read_sheet(sheet: str, range: str | None = None) -> dict:
    """Read a sheet as rows of strings ('' for empty cells). range like "A1:D20" limits it; default is the used area from A1."""
    cells = find(load(), sheet)['cells']
    if range:
        (c0, r0), (c1, r1) = (ref(x) for x in range.split(':')) if ':' in range else (ref(range),) * 2
    else:
        refs = [ref(k) for k in cells] or [(0, 0)]
        c0, r0, c1, r1 = 0, 0, max(c for c, _ in refs), max(r for _, r in refs)
    rows = [[cells.get('%s%d' % (chr(65 + c), r + 1), '') for c in range_(c0, c1)] for r in range_(r0, r1)]
    return {'range': '%s%d:%s%d' % (chr(65 + c0), r0 + 1, chr(65 + c1), r1 + 1), 'rows': rows}
def range_(a, b): return builtins.range(min(a, b), max(a, b) + 1)  # read_sheet's `range` argument shadows the builtin

if __name__ == '__main__':
    mcp.run()
