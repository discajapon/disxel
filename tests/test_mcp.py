#!/usr/bin/env python3
"""Checks the MCP server on a throwaway data dir, directly and over stdio like Claude talks to it.

    python3 tests/test_mcp.py          # a few seconds, no display needed
"""
import asyncio, json, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['DISXCEL_DATA'] = tempfile.mkdtemp(prefix='disxcel-mcp-test-')
sys.path.insert(0, ROOT)
import book, mcp_server as m

assert m.list_sheets() == [{'name': 'Hoja 1', 'cells': 0, 'range': None}]  # no book yet
m.write_rows('Hoja 1', 'B2', [['Mes', 'Monto'], ['Octubre', '450000']])
m.write_cells('Hoja 1', {'a1': ' Gastos ', 'C3': ''})
assert m.read_sheet('Hoja 1') == {'range': 'A1:C3', 'rows': [['Gastos', '', ''], ['', 'Mes', 'Monto'], ['', 'Octubre', '']]}
assert m.read_sheet('Hoja 1', 'C2:B3')['rows'] == [['Mes', 'Monto'], ['Octubre', '']]
assert m.list_sheets() == [{'name': 'Hoja 1', 'cells': 4, 'range': 'A1:C3'}]
assert m.add_sheet('Ideas') == 'Ideas' and m.add_sheet('Ideas') == 'Ideas (2)'
assert m.rename_sheet('Ideas (2)', 'Hoja 1') == 'Hoja 1 (2)'
m.delete_sheet('Hoja 1 (2)')
assert [s['name'] for s in m.list_sheets()] == ['Hoja 1', 'Ideas']
for bad in (lambda: m.write_cells('Hoja 1', {'AA1': 'x', 'A1': 'y'}), lambda: m.read_sheet('Nope'),
            lambda: m.write_rows('Ideas', 'Z1', [['a', 'b']])):
    try: bad(); raise AssertionError('should have failed')
    except ValueError: pass
assert m.read_sheet('Hoja 1')['rows'][0][0] == 'Gastos'  # a rejected write changes nothing
open(book.PATH, 'w').write('{broken')
assert m.list_sheets()[0]['name'] == 'Hoja 1' and open(book.PATH + '.corrupt').read() == '{broken'

async def over_stdio():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    p = StdioServerParameters(command=sys.executable, args=[os.path.join(ROOT, 'mcp_server.py')], env=dict(os.environ))
    async with stdio_client(p) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        names = sorted(t.name for t in (await s.list_tools()).tools)
        assert names == ['add_sheet', 'delete_sheet', 'list_sheets', 'read_sheet', 'rename_sheet', 'write_cells', 'write_rows'], names
        await s.call_tool('write_cells', {'sheet': 'Hoja 1', 'cells': {'A1': 'por stdio'}})
        res = await s.call_tool('read_sheet', {'sheet': 'Hoja 1', 'range': 'A1'})
        assert json.loads(res.content[0].text)['rows'] == [['por stdio']], res
asyncio.run(over_stdio())
print('ALL PASSED')
