# Notes MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets AI agents **create, read, list,
update and delete notes** in the self‑hosted Notes app (the ASP.NET Core + SQLite service that
backs the desktop client). Notes created via MCP are stored on the server and sync to every
device running the app.

It talks to the app's existing REST API over HTTPS using a bearer token — nothing new to install
on the server.

> **Setting this up (human or AI agent)?** Follow **[AGENTS.md](AGENTS.md)** — step‑by‑step install
> and ready‑to‑paste config for Claude Desktop, Claude Code, Cursor/Windsurf/VS Code, and the Python SDK.

---

## Tools

| Tool | What it does |
|---|---|
| `list_notes(query="", limit=50)` | List notes (pinned first, newest next). `query` filters by title/text/tags. Returns id, title, updated, pinned, notebook, tags. |
| `read_note(note_id)` | Get a note's **plain‑text content** and metadata. |
| `create_note(title, content="", notebook="", tags="")` | Create a note (plain text). Returns the new `id`. |
| `update_note(note_id, title=None, content=None, notebook=None, tags=None)` | Update fields; anything left `None` is unchanged. |
| `delete_note(note_id)` | Delete a note (moved to Trash — restorable in the app). |
| `archive_note(note_id, archived=True)` | Hide a note from the main list without deleting it (or unarchive with `archived=False`). |
| `capture_markdown(markdown, title="", note_id="")` | Append **rich Markdown** (headings, callouts, code, checklists, tables, links) to a note. |
| `capture_image(image_url \| image_path \| image_base64, caption="", title="", note_id="")` | Insert a **real image** into a note (from a URL, local file, or base64). |
| `list_attachments(note_id)` | List a note's file attachments (id, name, content type, size, created). |
| `attach_file(note_id, file_path \| file_url \| file_base64, filename="", content_type="")` | Attach any file to a note (stored directly on the server — no desktop client needed). |
| `download_attachment(attachment_id, save_path)` | Download an attachment to a local path. |
| `delete_attachment(attachment_id)` | Permanently delete an attachment. |
| `list_boards()` | List Kanban boards (id, name, updated). |
| `read_board(board_id)` | A board's columns and cards (with ids). |
| `create_board(name, template="basic", columns=None)` | Create a board (template or explicit columns). |
| `rename_board(board_id, name)` / `delete_board(board_id)` / `undelete_board(board_id)` | Rename / trash / restore a board. |
| `add_column(board_id, title, color="")` / `delete_column(board_id, column)` / `move_column(board_id, column, position)` | Add / remove / reorder a column. |
| `add_card(board_id, column, title, …)` | Add a card (description, color, due, labels, checklist). |
| `update_card(board_id, card_id, …)` | Update a card's fields (null = unchanged). |
| `move_card(board_id, card_id, to_column, position=None)` | Move a card to another column. |
| `archive_card(board_id, card_id)` / `unarchive_card(board_id, card_id, to_column="")` | Archive / restore a card. |
| `delete_card(board_id, card_id)` | Delete a card. |
| `health()` | Check the server is reachable. |

### Inserting images
Use **`capture_image`** to embed an actual picture — pass a URL, a local file path, or base64.
(Plain `![alt](url)` Markdown in `create_note`/`capture_markdown` is treated as text/link, not a
downloaded image.) Like other captures, images are rendered by the desktop client, so a client must
run at least once for them to appear.

### Sections (collapsible titled boxes)
The app's **titled section** — a bordered box with a shaded header (icon + bold title) over a body,
collapsible in the app — is created via `capture_markdown` with a **`:::` fence**:

```python
capture_markdown(title="Trip", markdown="""
::: 📌 Packing list
Take these:

- [ ] passport
- [ ] chargers
:::
""")
```

- Start the line with `:::`, an optional leading **emoji** (becomes the icon), then the **title**;
  close with `:::` on its own line.
- The body is **full Markdown** (bullets, checklists, bold, links, even a table).
- This is the real collapsible section block — different from a callout (which is a coloured strip,
  not collapsible). See [AGENTS.md](AGENTS.md#7-creating-titled-sections-collapsible-boxes) for details.

### Tables
Send a **GitHub-style Markdown table** via `capture_markdown` and the desktop client renders it as a
real bordered table (shaded, bold header row). A table is a header row, a dashes separator row, then
one row per record:

```python
capture_markdown(title="Team roster", markdown="""
| Week | Primary | Backup | Notes                          |
|------|---------|--------|--------------------------------|
| 27   | **Ann** | Bob    | Ann out Fri — Bob covers       |
| 28   | Bob     | Carol  | `oncall@acme` alias            |
| 29   | Carol   | Ann    | [runbook](https://wiki/oncall) |
""")
```

- The **separator row is required** — `| a | b |` on its own (no `|---|---|` under it) is treated as text.
- Outer pipes are optional, cells are trimmed, and alignment colons (`:--:`) are accepted (all columns
  render left-aligned). Short rows are padded; the widest row sets the column count.
- Cells support `**bold**`, `*italic*`, `` `code` `` and `[links](url)`. Escape a literal pipe as `\|`.

### Attaching files
Use **`attach_file`** to add any file (PDF, docx, zip, image, …) to a note — pass a local
`file_path`, an http(s) `file_url`, or `file_base64` (with a `filename`). Attachments are written
**straight to the server**, so (unlike captures) they appear without the desktop client running.
Manage them with `list_attachments`, `download_attachment` and `delete_attachment`.

```python
attach_file(note_id="8f2c…", file_path="/home/me/specs/pricing.xlsx")   # local file
attach_file(note_id="8f2c…", file_url="https://example.com/report.pdf")  # from the web
attach_file(note_id="8f2c…", file_base64="JVBERi0xLjQK…", filename="invoice.pdf")

list_attachments(note_id="8f2c…")
#   → [{"id": "a1b2…", "fileName": "pricing.xlsx", "size": 20481, ...}]
download_attachment(attachment_id="a1b2…", save_path="/tmp/pricing.xlsx")
delete_attachment(attachment_id="a1b2…")
```

### Kanban boards
Boards have **columns** (lists) holding **cards**. Board tools talk directly to the server (no desktop
client needed). Get card/column **ids** from `read_board` before updating, moving, or deleting.

```python
create_board(name="Sprint 42", template="sprint")   # basic|simple|sprint|weekly|blank, or columns=[...]
add_card(board_id="b1…", column="To do", title="Wire up login",
         color="blue", due="2026-09-15", checklist=["design", {"text": "implement", "done": True}])
read_board(board_id="b1…")                            # columns[] -> cards[] with ids
move_card(board_id="b1…", card_id="k3…", to_column="In progress")
```

- Colours: `red, orange, yellow, green, blue, purple, grey`. `due` is `"YYYY-MM-DD"`. `labels` is a list
  of colour keys; `checklist` is strings or `{"text","done"}` dicts.
- Updates use optimistic concurrency and retry on conflicts automatically. See
  [AGENTS.md §11](AGENTS.md#11-kanban-boards-columns--cards) for the full flow.

### Plain vs. rich content
- **`create_note` / `update_note`** store the content as plain text. It appears immediately in the
  app and via `read_note`, no desktop client needed.
- **`capture_markdown`** produces richly‑formatted notes, but captures are rendered by the desktop
  client, so a client must run at least once for the note to materialize. Use a **stable `title`**
  to keep appending to the same running note.

---

## Requirements

- Python 3.10+
- Your Notes server URL and API token (the same token the desktop app uses in
  **Settings → API token**; on the server it's in `token.txt` in the data directory, or whatever
  you set as `NOTES_API_TOKEN` / `Api:Token`).

## Install

```bash
pip install -r requirements.txt
# or, as a package:
pip install .
# or with uv:
uv pip install -e .
```

## Configure

Set two environment variables (or pass them in your MCP client config):

```bash
export NOTES_API_URL=https://macross.no-ip.info
export NOTES_API_TOKEN=your-long-random-api-token
```

## Run

```bash
python -m notes_mcp.server      # stdio transport (what MCP clients use)
# or, if installed as a package:
notes-mcp-server
```

---

## Use it from an MCP client

### Claude Desktop

Add to `claude_desktop_config.json`
(`%APPDATA%\Claude\claude_desktop_config.json` on Windows,
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "notes": {
      "command": "python",
      "args": ["-m", "notes_mcp.server"],
      "env": {
        "NOTES_API_URL": "https://macross.no-ip.info",
        "NOTES_API_TOKEN": "your-long-random-api-token"
      }
    }
  }
}
```

(If you installed the package, you can use `"command": "notes-mcp-server"` with no `args`.)

Restart Claude Desktop; the **notes** tools appear. Try: *"List my notes"*, *"Create a note titled
Groceries with milk, eggs, bread"*, *"Read the note about the deploy log."*

### Claude Code (CLI)

```bash
claude mcp add notes \
  --env NOTES_API_URL=https://macross.no-ip.info \
  --env NOTES_API_TOKEN=your-long-random-api-token \
  -- python -m notes_mcp.server
```

### Cursor / Windsurf / VS Code / other MCP clients

Add the same `mcpServers` block as above to the client's MCP config (e.g. `~/.cursor/mcp.json`,
`.vscode/mcp.json`, or a project `.mcp.json`).

### Claude Agent SDK / programmatic

Any client that speaks MCP over stdio can launch `python -m notes_mcp.server`.
See [`examples/list_and_create.py`](examples/list_and_create.py) for a minimal client.

Full step‑by‑step for every client is in **[AGENTS.md](AGENTS.md)**.

---

## Security

- All calls require the bearer token; keep `NOTES_API_TOKEN` secret (use env vars / your client's
  secret store, not source control).
- The server is expected to be reachable over HTTPS (the reference deployment uses a Caddy TLS
  reverse proxy). Treat note content the agent reads/writes as you would any personal data.

## License

MIT — see [LICENSE](LICENSE).
