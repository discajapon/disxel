"""The workbook file shared by the app and the MCP server: {"active": n, "sheets": [{"name", "cells": {"A1": "text"}}]}."""
import fcntl, json, os, shutil
from contextlib import contextmanager

DIR = os.environ.get('DISXCEL_DATA') or os.path.expanduser('~/.local/share/disxcel')  # override for tests
PATH = os.path.join(DIR, 'book.json')

def valid(b): return isinstance(b, dict) and isinstance(b.get('sheets'), list)

def read():
    """Text of the book, or None if there is none yet. Unreadable data is kept as book.json.corrupt, never lost."""
    try: text = open(PATH, encoding='utf-8').read()
    except FileNotFoundError: return None
    try:
        if valid(json.loads(text)): return text
    except ValueError: pass
    shutil.copyfile(PATH, PATH + '.corrupt')
    return None

def write(text):  # atomic: a reader sees the old book or the new one, never half
    os.makedirs(DIR, exist_ok=True)
    tmp = PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: f.write(text)
    os.replace(tmp, PATH)

@contextmanager
def locked():
    """Serialise read-modify-write between the app and the MCP server."""
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(DIR, 'book.lock'), 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
