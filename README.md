# Disxcel

A small spreadsheet for Ubuntu with a liquid glass look, sibling of [Disctask](https://github.com/discajapon/Disctask). Values only, no formulas.

## Use
- Click a cell and type; Enter/Tab save and move down/right (Shift goes back), Escape cancels, arrows move.
- F2 or double click edits the current text; Delete clears the cell. Ctrl+C / Ctrl+X / Ctrl+V work on the cell.
- Pasting a range copied from Excel, LibreOffice or a web table spreads it over the grid.
- Tabs at the bottom: ＋ adds a sheet, double click renames it, ✕ twice deletes it.
- Columns go A–Z; rows grow as you go.

## Files
- 📂 Abrir reads `.xlsx`, `.xls`, `.ods` or `.csv`; each sheet becomes a new tab (cells keep their place, values come in as displayed text).
- ⬇ CSV saves the current sheet, ⬇ .xls saves the whole book as a real Excel 97–2003 file (plain numbers stay numbers).
- ⬇ Exportar opens an in-app popup with two tabs.
  - 📄 Documento saves the sheet as a self-contained `.html` page (sterile white, opens in any browser): live search that ignores accents, click a column to sort (rows glide into place, `12.500` sorts as a number), long texts folded behind “Ver más” that expand with an animation, “Expandir todo”, clickable links, and a print layout with everything open. The preview in the popup is the real page. Its first non-empty row is the header.
  - 📷 Foto shows a preview of the sheet; tabs switch the style (Normal, the default every time, Liquid glass, Corporativo, Oscuro, Minimal). Long text wraps onto extra lines in the image so nothing is cut (the app grid is unchanged). Save it as PNG or JPG.
- Everything goes to `~/Downloads` and never overwrites an existing file.
- Uses the bundled [SheetJS](https://sheetjs.com) 0.20.3 (`xlsx.full.min.js`, Apache-2.0); nothing touches the network.

## Run
Needs GTK3 + WebKit2GTK (`gir1.2-webkit2-4.1`).

    ./disxcel.py

The book lives in `~/.local/share/disxcel/book.json`, saved on every change. If it is ever unreadable it is kept as `book.json.corrupt` instead of being lost. When something else changes the file (the MCP server below), an open window shows the change within a second. When the app itself is updated (`index.html` changes), an open window reloads within a second, saving the cell being typed first, so it never runs an old version.

Like Disctask, the app forces WebKit's GPU renderer when OpenGL works (`WEBKIT_FORCE_DMABUF_RENDERER=0 ./disxcel.py` to opt out). That renderer leaks one fd per frame, so the launcher raises the fd limit, endless animations pause after 20 s idle or when unfocused, and a dead web process is reloaded.

## MCP server (Claude)
`mcp_server.py` lets Claude read and edit the book: `list_sheets`, `read_sheet` (whole used area or a range like `A1:D20`), `write_cells` (`{"B3": "1200"}`, `""` clears), `write_rows` (a table from a start cell), `add_sheet`, `rename_sheet`, `delete_sheet`. It works whether Disxcel is open or not. Needs the `mcp` Python package (`pip install --user mcp`).

    claude mcp add -s user disxcel -- python3 /path/to/disxcel/mcp_server.py

App and server share a lock for each write; if you type in a cell in the very second Claude writes, the last write wins.

## Tests
`python3 tests/test_app.py` runs the real app on a throwaway data dir and a throwaway `~/Downloads` (needs a display and `python3-openpyxl`, ~50 s), including an MCP write while it is open. `python3 tests/test_mcp.py` checks the MCP tools, also over stdio (a few seconds).

## Font
Anthropic Serif, not in the repo: install it system-wide or drop the `.otf` files into `fonts/` (ignored by git). Falls back to Georgia.

## Launcher
Copy `disxcel.desktop` to `~/.local/share/applications/` and replace `/path/to/disxcel` with the real path.
