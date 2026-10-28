#!/usr/bin/env python3
import gi, os, resource, json
import book
gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1')
from gi.repository import Gtk, WebKit2, GLib
# WebKit's forced GPU renderer leaks one sync_file fd per presented frame (~15/s while
# animating); at the default 1024 limit the web process wedges at 100% CPU. Children inherit this.
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
GLib.set_prgname('disxcel')  # Wayland app id; must match disxcel.desktop for the dock icon
def gl_ok():  # forcing the GPU renderer aborts the app when GDK has no OpenGL, so probe first
    t = Gtk.Window(); t.realize()
    try: t.get_window().create_gl_context().realize(); return True
    except Exception: return False
    finally: t.destroy()
# WebKitGTK falls back to CPU painting on some GPUs (NVIDIA here: ~12 fps with the glass
# effects); force the GPU renderer. WEBKIT_FORCE_DMABUF_RENDERER=0 ./disxcel.py to opt out.
if gl_ok(): os.environ.setdefault('WEBKIT_FORCE_DMABUF_RENDERER', '1')
d = book.DIR
ctx = WebKit2.WebContext.new_with_website_data_manager(
    WebKit2.WebsiteDataManager(base_data_directory=d, base_cache_directory=d))
def save(dl, name):  # exports land in ~/Downloads, never overwriting
    dst, i = os.path.expanduser('~/Downloads/' + name), 1
    while os.path.exists(dst):
        dst, i = os.path.expanduser('~/Downloads/%s (%d)%s' % (*os.path.splitext(name)[:1], i, os.path.splitext(name)[1])), i + 1
    dl.set_destination('file://' + dst)
    return True
ctx.connect('download-started', lambda c, dl: dl.connect('decide-destination', save))
v = WebKit2.WebView.new_with_context(ctx)
v.get_settings().set_allow_file_access_from_file_urls(True)  # so the photo export can paint bg.jpg on a canvas without tainting it
def policy(v, dec, kind):  # web links open in the default browser, not inside the app
    if kind in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION, WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
        uri = dec.get_navigation_action().get_request().get_uri()
        if uri.startswith(('http:', 'https:')):
            Gtk.show_uri_on_window(w, uri, Gtk.get_current_event_time())
            dec.ignore()
            return True
    return False
v.connect('decide-policy', policy)
v.connect('web-process-terminated', lambda v, why: v.reload())  # the book is saved on every change, a reload loses nothing
m = v.get_user_content_manager()
def inject(text):  # the page reads the book from window.__book when it loads (also after a crash reload)
    m.remove_all_scripts()
    m.add_script(WebKit2.UserScript('window.__book=' + json.dumps(text), WebKit2.UserContentInjectedFrames.TOP_FRAME,
                                    WebKit2.UserScriptInjectionTime.START, None, None))
last = [book.read(), None]  # [text we last wrote or showed, mtime we last saw]
inject(last[0])
def saved(m, res):
    text = res.get_js_value().to_string()
    with book.locked(): book.write(text)
    last[0] = text; inject(text)
m.register_script_message_handler('book')
m.connect('script-message-received::book', saved)
# ponytail: last writer wins inside the 1 s poll window (typing in the same second as an MCP write); merge per cell if that ever bites
def poll():  # book.json changed outside the app (the MCP server): show it
    try: mt = os.stat(book.PATH).st_mtime_ns
    except FileNotFoundError: return True
    if mt != last[1]:
        last[1] = mt; t = book.read()
        if t is not None and t != last[0]:
            last[0] = t; inject(t); v.run_javascript('external(%s)' % json.dumps(t), None, None)
    return True
GLib.timeout_add(1000, poll)
v.load_uri('file://' + os.path.join(os.path.dirname(os.path.realpath(__file__)), 'index.html'))
w = Gtk.Window(title='Disxcel', default_width=1100, default_height=720)
w.set_icon_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'icon.png'))
w.add(v); w.connect('destroy', Gtk.main_quit); w.show_all(); Gtk.main()
