#!/usr/bin/env python3
"""End-to-end check of the real app (needs a display). Runs it on a throwaway data dir and
a throwaway ~/Downloads, driving it with DOM events inside the page (never xdotool).

    python3 tests/test_app.py          # ~50 s, exit code 1 on any failure
"""
import os, sys, tempfile, json, base64, io, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='disxcel-test-')
os.environ['DISXCEL_DATA'] = TMP + '/data'
os.makedirs(TMP + '/Downloads')
os.makedirs(TMP + '/data')
open(TMP + '/data/book.json', 'w').write('{broken')  # the app must keep a copy, not lose it
sys.path.insert(0, ROOT)
import mcp_server
import gi
gi.require_version('Gtk', '3.0'); gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib
import runpy, resource, openpyxl, subprocess
from PIL import Image
# a desktop launcher starts apps with a 1024 soft fd limit; mimic it (the app must raise it itself)
resource.setrlimit(resource.RLIMIT_NOFILE, (1024, resource.getrlimit(resource.RLIMIT_NOFILE)[1]))
fails, wv, checks = [], None, [0]

def check(name, ok, info=''):
    checks[0] += 1
    print(('PASS ' if ok else 'FAIL ') + name, info, flush=True)
    if not ok: fails.append(name)
def js(code, cb=lambda r: None):
    def done(v, res):
        try: cb(v.run_javascript_finish(res).get_js_value().to_string())
        except Exception as e: check('script ran', False, e)
    wv.run_javascript(code, None, done)
def jsj(code, cb): js('JSON.stringify(' + code + ')', lambda r: cb(json.loads(r)))
def at(ms, f): GLib.timeout_add(ms, lambda: (f(), False)[1])
def web_pid():
    me = os.getpid()
    for p in os.listdir('/proc'):
        if p.isdigit():
            try:
                if int(open(f'/proc/{p}/stat').read().rsplit(')', 1)[1].split()[1]) == me and b'WebKitWebProcess' in open(f'/proc/{p}/cmdline', 'rb').read(): return int(p)
            except OSError: pass
def syncs(pid): return sum(1 for f in os.listdir(f'/proc/{pid}/fd') if os.path.islink(f'/proc/{pid}/fd/{f}') and 'sync_file' in os.readlink(f'/proc/{pid}/fd/{f}'))

def xlsx_b64():  # data starting at B3, as real files often do
    b = openpyxl.Workbook(); s = b.active; s.title = 'Gastos'
    s['B3'] = 'Año'; s['C3'] = 'Total'; s['B4'] = 2026; s['C4'] = 12.5
    b.create_sheet('Ingresos')['A1'] = 'Sueldo'
    f = io.BytesIO(); b.save(f); return base64.b64encode(f.getvalue()).decode()

EDIT = """(()=>{const kd=(k,o={})=>ed.dispatchEvent(new KeyboardEvent('keydown',{key:k,bubbles:true,cancelable:true,...o}));
 ed.value='hola';ed.dispatchEvent(new InputEvent('input',{bubbles:true}));const editing=ed.classList.contains('on');kd('Enter');
 const after={editing,R,C,a1:sheet().cells.A1};
 kd('ArrowRight');kd('F2');const f2=mode;kd('Escape');
 const dt=new DataTransfer();dt.setData('text/plain','1\\t2\\r\\n3\\t,5\\r\\n');
 ed.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));
 R=0;C=0;place();kd('Delete');const del=sheet().cells.A1;kd('z');ed.value='z';ed.dispatchEvent(new InputEvent('input',{bubbles:true}));kd('Tab');
 return{...after,f2,cells:sheet().cells,del,num:cell(2,2).className,ref:$('ref').textContent}})()"""
SHEETS = """(()=>{$('add').click();const n1=wb.sheets.length,a1=wb.active;R=0;C=0;place();setCell(0,0,'otra');
 const t=document.querySelector('#tabs .sel');t.dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));
 const inp=document.querySelector('#tabs input');inp.value='Mía';inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));
 document.querySelector('#tabs [data-i="0"]').click();const back=cell(0,0).textContent;
 return{n1,a1,back,names:wb.sheets.map(s=>s.name),active:wb.active}})()"""
DELETE = """(()=>{document.querySelector('#tabs [data-i="1"]').click();const x=()=>document.querySelector('#tabs .x');
 x().click();const armed=wb.sheets.length;x().click();return{armed,after:wb.sheets.map(s=>s.name),active:wb.active}})()"""
IMPORT = """(()=>{const b=Uint8Array.from(atob('%s'),c=>c.charCodeAt(0)),dt=new DataTransfer();
 dt.items.add(new File([b],'libro.xlsx'));$('fi').files=dt.files;$('fi').dispatchEvent(new Event('change'));return 1})()"""
EXPORT = "$('xc').click();setTimeout(()=>$('xx').click(),600);1"
STATE = "{names:wb.sheets.map(s=>s.name),sheets:wb.sheets.map(s=>s.cells),active:wb.active,shown:cell(2,1).textContent}"

def phase2():
    def first(o):
        check('corrupt book survives as a copy', open(TMP + '/data/book.json.corrupt').read() == '{broken')
        check('app boots with one empty sheet', o['names'] == ['Hoja 1'] and o['sheets'] == [{}], o)
    jsj(STATE, first)
    def edit(o):
        check('typing opens the editor', o['editing'])
        check('Enter saves the cell and moves down', o['a1'] == 'hola' and o['R'] == 1 and o['C'] == 0, o)
        check('F2 edits in place', o['f2'] == 'edit')
        check('pasted rows/columns spread over the grid', all(o['cells'].get(k) == v for k, v in {'B2': '1', 'C2': '2', 'B3': '3', 'C3': ',5'}.items()), o['cells'])
        check('Delete clears, typing then Tab saves and moves right', o.get('del') is None and o['cells'].get('A1') == 'z' and o['ref'] == 'B1', o)
        check('numbers are right aligned', o['num'] == 'num', o['num'])
    jsj(EDIT, edit)
    def sheets(o):
        check('＋ adds and opens a sheet', o['n1'] == 2 and o['a1'] == 1, o)
        check('double click renames a tab', o['names'] == ['Hoja 1', 'Mía'], o['names'])
        check('switching sheets shows that sheet', o['back'] == 'z' and o['active'] == 0, o)
    at(300, lambda: jsj(SHEETS, sheets))
    def delete(o):
        check('first ✕ click only asks', o['armed'] == 2)
        check('second ✕ click deletes the sheet', o['after'] == ['Hoja 1'] and o['active'] == 0, o)
    at(700, lambda: jsj(DELETE, delete))
    at(1100, lambda: js(IMPORT % xlsx_b64()))
    def imported(o):
        check('xlsx sheets become tabs', o['names'] == ['Hoja 1', 'Gastos', 'Ingresos'] and o['active'] == 1, o['names'])
        check('imported cells keep their position', o['sheets'][1] == {'B3': 'Año', 'C3': 'Total', 'B4': '2026', 'C4': '12.5'} and o['shown'] == 'Año', o['sheets'][1:])
    at(2500, lambda: jsj(STATE, imported))
    def export():
        os.environ['HOME'] = TMP  # downloads go to the throwaway ~/Downloads
        js(EXPORT)
    at(2800, export)
    at(3400, lambda: js("$('sh').click();1"))
    def popup(o):
        check('📷 Foto opens the in-app popup with a preview', o['open'] and o['src'] == 'data:image/png;base64,', o)
        js("$('pp').click();setTimeout(()=>$('sh').click(),300);setTimeout(()=>$('pj').click(),1200);1")
    at(4400, lambda: jsj("{open:$('ph').open,src:$('pv').src.slice(0,22)}", popup))
    at(6500, exported)
    at(7000, lambda: mcp_server.write_cells('Hoja 1', {'A1': 'desde Claude', 'D9': 'x'}))
    def live(o):
        check('an MCP write shows up in the open app', o['sheets'][0].get('A1') == 'desde Claude' and o['sheets'][0].get('D9') == 'x'
              and o['names'] == ['Hoja 1', 'Gastos', 'Ingresos'] and o['active'] == 1, o['sheets'][0])
    at(9000, lambda: jsj(STATE, live))
    pid = web_pid(); lim = [l for l in open(f'/proc/{pid}/limits') if l.startswith('Max open files')][0].split()
    check('web process has a high fd limit', int(lim[3]) >= 65536, lim[3]); limit[0] = int(lim[3])
    for t in range(30000, 43000, 3000): at(t, lambda: samples.append(syncs(pid)))  # animations pause after 20 s idle
    at(43000, lambda: wv.reload())
def exported():
    csv = glob.glob(TMP + '/Downloads/*.csv'); x = glob.glob(TMP + '/Downloads/*.xls')
    check('CSV of the active sheet lands in Downloads', [os.path.basename(p) for p in csv] == ['Gastos.csv'] and
          open(csv[0], encoding='utf-8-sig').read().splitlines()[2:4] == [',Año,Total', ',2026,12.5'], csv and open(csv[0], encoding='utf-8-sig').read())
    if x:
        check('.xls is a real Excel 97-2003 file', open(x[0], 'rb').read(8) == bytes.fromhex('d0cf11e0a1b11ae1'))  # OLE2, not renamed xlsx
        o = json.loads(subprocess.run(['node', '-e', "const X=require(process.argv[1]),b=X.read(require('fs').readFileSync(process.argv[2])),g=b.Sheets.Gastos;"
            "console.log(JSON.stringify({names:b.SheetNames,b4:g.B4.v,t:g.B4.t,c3:b.Sheets['Hoja 1'].C3.v}))", ROOT + '/xlsx.full.min.js', x[0]],
            capture_output=True, text=True).stdout or 'null')
        check('.xls holds every sheet with typed numbers', o == {'names': ['Hoja 1', 'Gastos', 'Ingresos'], 'b4': 2026, 't': 'n', 'c3': ',5'}, o)
    else: check('.xls export lands in Downloads', False)
    for ext, fmt in (('png', 'PNG'), ('jpg', 'JPEG')):
        try: im = Image.open(TMP + '/Downloads/Gastos.' + ext); ok = im.format == fmt and im.width > 400 and len(set(im.convert('L').getdata())) > 20
        except OSError as e: ok, im = False, e
        check('photo saved as ' + ext.upper(), ok, im)
samples, limit = [], [0]
def finish():
    def persisted(o):
        check('everything survives a reload', o['names'] == ['Hoja 1', 'Gastos', 'Ingresos'] and o['sheets'][0].get('A1') == 'desde Claude' and o['active'] == 1, o['names'])
        last = samples[-3:]  # once idle the count must hold still
        check('no fence fds leak while idle', max(last) - min(last) <= 5, samples)
        check('fd count stays far from the limit', max(samples) < limit[0] // 16, (max(samples), limit[0]))
        if checks[0] < 20: fails.append('only %d checks ran' % checks[0])
        print('FAILED: ' + ', '.join(fails) if fails else 'ALL PASSED'); Gtk.main_quit()
    jsj(STATE, persisted)

orig, state = WebKit2.WebView.load_uri, [0]
def lu(self, uri):
    global wv; wv = self
    def done(v, e):
        if e != WebKit2.LoadEvent.FINISHED: return
        state[0] += 1
        if state[0] == 1: at(800, phase2)
        elif state[0] == 2: at(800, finish)
    self.connect('load-changed', done)
    orig(self, uri)
WebKit2.WebView.load_uri = lu
at(80000, lambda: (print('TIMEOUT'), sys.exit(1)))
sys.argv = ['disxcel.py']
runpy.run_path(os.path.join(ROOT, 'disxcel.py'), run_name='__main__')
sys.exit(1 if fails else 0)
