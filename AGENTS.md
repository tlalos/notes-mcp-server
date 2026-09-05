# Setup instructions (for humans and AI agents)

This file tells an agent exactly how to install and configure the Notes MCP server. Follow the
steps in order. Everything you need is in this repository.

## 0. Prerequisites
- Python **3.10+** on the machine that will run the MCP server.
- Two secrets from the note owner:
  - `NOTES_API_URL` — the Notes server base URL, e.g. `https://macross.no-ip.info`
  - `NOTES_API_TOKEN` — the bearer token (same one the desktop app uses in Settings → API token).
  Never hard-code the token in files that get committed; put it in the client config `env` block or
  an environment variable.

## 1. Install
From the repository root:
```bash
pip install -r requirements.txt      # or:  pip install .
```
Verify it loads (optional):
```bash
python -c "import notes_mcp.server; print('ok')"
```

## 2. Choose the launch command
The server speaks MCP over **stdio**. The launch command is:
```
python -m notes_mcp.server
```
(If you ran `pip install .`, the equivalent console command is `notes-mcp-server`.)
It requires the two environment variables from step 0.

## 3. Register it with your MCP client
Pick the block that matches your client. Replace the URL/token with the real values.

### Claude Desktop
Edit the config file:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

Merge this into the top-level `"mcpServers"` object (create it if missing), then restart Claude Desktop:
```json
{
  "mcpServers": {
    "notes": {
      "command": "python",
      "args": ["-m", "notes_mcp.server"],
      "env": {
        "NOTES_API_URL": "https://macross.no-ip.info",
        "NOTES_API_TOKEN": "REPLACE_WITH_TOKEN"
      }
    }
  }
}
```

### Claude Code (CLI)
One command (run from anywhere; use `-s user` for a global install):
```bash
claude mcp add notes \
  --env NOTES_API_URL=https://macross.no-ip.info \
  --env NOTES_API_TOKEN=REPLACE_WITH_TOKEN \
  -- python -m notes_mcp.server
```
Or commit a project-scoped `.mcp.json` at the repo root with the same shape as the generic block below.

### Cursor / Windsurf / VS Code (and most other MCP clients)
Add to the client's MCP config file (e.g. `~/.cursor/mcp.json`, or the project's `.mcp.json` /
`.vscode/mcp.json`):
```json
{
  "mcpServers": {
    "notes": {
      "command": "python",
      "args": ["-m", "notes_mcp.server"],
      "env": {
        "NOTES_API_URL": "https://macross.no-ip.info",
        "NOTES_API_TOKEN": "REPLACE_WITH_TOKEN"
      }
    }
  }
}
```

### Programmatic (MCP Python SDK)
See [`examples/list_and_create.py`](examples/list_and_create.py) — it launches
`python -m notes_mcp.server` over stdio and calls the tools.

## 4. Confirm it works
After registering, ask the agent to run the `health` tool (should return `{"ok": true}`), then
`list_notes`. If `health` fails, re-check `NOTES_API_URL`/`NOTES_API_TOKEN` and that the machine can
reach the server over HTTPS.

## 5. Available tools
**Notes:** `list_notes`, `read_note`, `create_note`, `update_note`, `delete_note`, `archive_note`,
`capture_markdown`, `capture_image`.
**Attachments:** `list_attachments`, `attach_file`, `download_attachment`, `delete_attachment`.
**Kanban boards:** `list_boards`, `read_board`, `search_boards`, `create_board`, `rename_board`,
`delete_board`, `undelete_board`, `add_column`, `delete_column`, `move_column`, `add_card`,
`update_card`, `move_card`, `archive_card`, `unarchive_card`, `delete_card`.

**Searching:** notes → `list_notes(query="…")` (matches title, text, tags); board cards →
`search_boards(query="…")` (matches card title, description, checklist).
**Misc:** `health`.
See [README.md](README.md#tools) for parameters, the plain-text vs. Markdown note, how to
insert images (`capture_image`), attach files (`attach_file`), and manage boards (§10).

## 6. Inserting images
There are two ways to put a **real image** into a note:

1. **`capture_image`** — pass the image as exactly one of:
   - `image_url`    — an http(s) URL (downloaded), e.g. `capture_image(image_url="https://…/pic.png", title="Trip", caption="Sunset")`
   - `image_path`   — a local file path readable by the MCP process
   - `image_base64` — raw base64 (a `data:image/…;base64,…` prefix is accepted and stripped)
   Optional `caption` (text above the image), and target with `note_id` or `title`.

2. **`capture_markdown`** with Markdown image syntax — these now render as embedded pictures:
   - `![alt](https://example.com/pic.png)` (downloaded), or
   - `![alt](data:image/png;base64,iVBOR…)` (inline data URI).

Do **not** expect `![](…)` inside `create_note` to become an image — `create_note` stores plain text.
Use `capture_image` or `capture_markdown` for images. Images are materialized by the desktop client,
so a client must run at least once for them to appear.

## 7. Creating titled "sections" (collapsible boxes)
The desktop app has a **titled section** block — a bordered box with a shaded header (an optional icon
+ a bold title) over a body, which the reader can collapse/expand. To create one over MCP, send
**`capture_markdown`** with a **`:::` fence**. This is the real section block, not a callout.

Syntax — an opening `:::` line with an optional leading emoji and a title, the body lines, then a
closing `:::`:

```
::: 📌 Packing list
Take these on the trip:

- passport
- charger
- power bank
:::
```

Rules the renderer follows:
- The line **must start with `:::`** (an optional `section` keyword is allowed: `::: section 📌 Title`).
- A **leading emoji** right after `:::` becomes the section's icon; the rest of the line is the bold
  title. No emoji is fine — then the whole line is the title. An empty title defaults to "Section".
- Everything until the **closing `:::`** is the body, and the body is **full Markdown** — use headings,
  bullets, `- [ ]` checklists, `**bold**`, links, even a table inside the section.
- Always close the fence with `:::` on its own line. (If you forget, everything to the end of the note
  becomes the body.)
- Sections are collapsible in the app via the ▾/▸ chevron in the header; MCP-created ones already
  include it.

Full example with several sections in one note:
```
capture_markdown(title="Trip to Rotterdam", markdown="""
# Rotterdam 2026

::: 🧳 To pack
- [ ] passport
- [ ] chargers + power bank
- [ ] meds
:::

::: 📄 Documents
Print these and keep a PDF copy on the phone:

- hotel booking
- train tickets
:::

::: ℹ️ Notes
Weather looks rainy — **bring a jacket**. Contact: [hotel](https://example.com).
:::
""")
```

### Callouts (a lighter alternative)
If you just want a coloured, titled highlight (not a collapsible box), use a **callout** instead:
```
> [!info] Overview
> This whole block shows as one titled, coloured strip.
```
Callout types: `info` / `note` (blue), `success` (green), `warning` (orange), `tip` (yellow).

You can also group content with headings (`#`, `##`, `###`), fenced code blocks (```` ``` ````), task
lists (`- [ ] item`), and tables (see §8). Use a stable `title` on `capture_markdown` to keep appending
to the same note. Captures are materialized by the desktop client, so a client must run at least once
for the note to appear.

## 8. Tables in notes
Use **`capture_markdown`** with a **GitHub-style Markdown table** — the desktop client renders it as a
real bordered table (shaded, bold header row), not as text. The shape is a header row, a separator row
of dashes, then one row per record. Outer pipes are optional; cells are trimmed.

```
| Name  | Role | Location |
|-------|------|----------|
| Ann   | Lead | Berlin   |
| Bob   | Dev  | Lisbon   |
```

Rules the renderer follows:
- A table is recognised only when a row of `|`-separated cells is **immediately followed by a separator
  line** (dashes, pipes, optional colons/spaces), e.g. `|---|---|` or `---|:--:|---`. Without that
  separator line the row is treated as plain text.
- Alignment colons (`:---`, `:--:`, `---:`) are accepted but not visually applied — every column renders
  left-aligned. The separator just has to be present.
- Ragged rows are fine: short rows are padded with empty cells, and the column count is the widest row.
- Cell text supports the usual inline formatting: `**bold**`, `*italic*`, `` `code` ``, and `[links](https://…)`.
- Escape a literal pipe inside a cell as `\|`.

Full example creating (or appending to) a note with a table:
```
capture_markdown(title="Team roster", markdown="""
## Q3 on-call roster

| Week | Primary   | Backup   | Notes                    |
|------|-----------|----------|--------------------------|
| 27   | **Ann**   | Bob      | Ann out Fri — Bob covers |
| 28   | Bob       | Carol    | `oncall@acme` alias      |
| 29   | Carol     | Ann      | [runbook](https://wiki/oncall) |
""")
```
Tables, like other `capture_markdown` content, are materialized by the desktop client, so a client must
run at least once for the note to appear. Use a stable `title` to keep appending to the same note.

## 9. Attaching files to a note
Notes can carry arbitrary file attachments (PDFs, docx, zips, images, anything). Unlike
`capture_markdown`/`capture_image`, attachments are stored **directly** on the server — they do
**not** need the desktop client to run to appear.

- **`attach_file`** — pass the file as exactly one of:
  - `file_path`   — a local file readable by the MCP process
  - `file_url`    — an http(s) URL (downloaded by the MCP process)
  - `file_base64` — raw base64 (a `data:…;base64,…` prefix is accepted and stripped); pass `filename` with this form
  Optional `filename` (overrides the inferred name) and `content_type` (inferred from the name when omitted).
- **`list_attachments(note_id)`** — list a note's attachments (id, file name, content type, size, created time).
- **`download_attachment(attachment_id, save_path)`** — download one to a local path.
- **`delete_attachment(attachment_id)`** — permanently remove one.

Examples (get a `note_id` from `list_notes`/`create_note` first):
```
# 1. Attach a local file (name + content type inferred from the path)
attach_file(note_id="8f2c…", file_path="/home/me/specs/pricing.xlsx")

# 2. Attach a file straight from the web
attach_file(note_id="8f2c…", file_url="https://example.com/report.pdf")

# 3. Attach from base64 (filename is required here; content type inferred from it)
attach_file(note_id="8f2c…", file_base64="JVBERi0xLjQK…", filename="invoice.pdf")

# 4. List, download, and delete
list_attachments(note_id="8f2c…")
#   → [{"id": "a1b2…", "fileName": "pricing.xlsx", "contentType": "application/…", "size": 20481, "createdUtc": "…"}]
download_attachment(attachment_id="a1b2…", save_path="/tmp/pricing.xlsx")
delete_attachment(attachment_id="a1b2…")
```

## 10. Archiving notes
Use **`archive_note(note_id, archived=True)`** to hide a note from the main list without deleting it,
and `archive_note(note_id, archived=False)` to bring it back. Archived notes stay intact and are
listed in the desktop app's archived view (the 🗄 toggle). `read_note` reports each note's `archived`
flag. This is distinct from `delete_note`, which moves a note to Trash.

## 11. Kanban boards (columns & cards)
Boards are separate from notes. Each board has **columns** (lists) that hold **cards**. Board tools
talk **directly** to the server (no desktop client needed to materialize). Every card and column has a
stable **id** — get ids from `read_board` before you update / move / delete.

Typical flow:
```
list_boards()                                             # -> [{"id","name","updatedUtc"}, …]
create_board(name="Sprint 42", template="sprint")        # -> {"id": "b1…"}
#   templates: basic | simple | sprint | weekly | blank   (or pass columns=["A","B","C"])

add_column(board_id="b1…", title="Blocked", color="red") # -> {"columnId": "c9…"}

add_card(board_id="b1…", column="To do", title="Wire up login",
         description="OAuth + session", color="blue", due="2026-09-15",
         labels=["blue"], checklist=["design", {"text": "implement", "done": True}])
#   column = a column id OR its exact title            -> {"cardId": "k3…"}

read_board(board_id="b1…")   # full structure: columns[] each with cards[] (ids, title, desc, colour, due, labels, checklist)

update_card(board_id="b1…", card_id="k3…", color="green", due="")   # due="" clears the date
move_card(board_id="b1…", card_id="k3…", to_column="In progress")   # optional position=<0-based index>
move_column(board_id="b1…", column="Blocked", position=0)           # reorder a column
archive_card(board_id="b1…", card_id="k3…")                         # hide a done card (restorable)
unarchive_card(board_id="b1…", card_id="k3…", to_column="To do")    # bring it back (defaults to origin)
delete_card(board_id="b1…", card_id="k3…")
delete_column(board_id="b1…", column="Blocked")
rename_board(board_id="b1…", name="Sprint 42 (final)")
delete_board(board_id="b1…")                                        # -> Trash
list_boards(deleted=True); undelete_board(board_id="b1…")           # find & restore a trashed board
```

Notes:
- **Colours** are keys: `red`, `orange`, `yellow`, `green`, `blue`, `purple`, `grey` (used for a card's
  accent and a column's header; auto-assigned to new columns when omitted).
- **`due`** is a date string `"YYYY-MM-DD"`.
- **`labels`** is a list of colour keys; **`checklist`** is a list of strings, or `{"text","done"}` dicts.
  On `update_card`, passing `labels`/`checklist` replaces the whole list.
- **Archive vs delete:** `archive_card` hides a card (restorable, kept in the board's archive);
  `delete_card` removes it. `delete_board` trashes a board; `undelete_board` restores it.
- Updates use optimistic concurrency and retry automatically if the board changed on the server; a
  persistent clash returns `{"error": "conflict: …"}`.

### Instructing your agent to use boards
Drop something like this into your agent's system prompt / instructions so it knows the capability
exists:

> You can manage the user's Kanban boards through the Notes MCP server. Use `list_boards` /
> `read_board` to see boards, columns and cards (always read a board first to get the column and card
> **ids** you'll need). Create boards with `create_board` (templates: basic, simple, sprint, weekly,
> blank). Add work with `add_card` (title, description, colour, `due` as YYYY-MM-DD, labels, checklist)
> and organise it with `move_card` between columns, `add_column` / `move_column`, `update_card` to edit
> a card, `archive_card` when work is done, and `delete_card` / `delete_board` to remove things. Prefer
> archiving finished cards over deleting them. Board changes apply immediately — no desktop app needed.

## Notes for the agent
- If `command: "python"` isn't found, try `python3`, or the absolute path to a Python 3.10+ interpreter.
- On Windows, if a virtual environment is used, point `command` at that env's `python.exe`.
- `read_note` returns note text only if the Notes server exposes `PlainText` (recent server build).
- `capture_markdown` content is rendered by the desktop client, so it appears once a client runs.
- Board tools apply immediately server-side (no client needed); notes captures need a client to render.
