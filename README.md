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
| `health()` | Check the server is reachable. |

### Inserting images
Use **`capture_image`** to embed an actual picture — pass a URL, a local file path, or base64.
(Plain `![alt](url)` Markdown in `create_note`/`capture_markdown` is treated as text/link, not a
downloaded image.) Like other captures, images are rendered by the desktop client, so a client must
run at least once for them to appear.

### Attaching files
Use **`attach_file`** to add any file (PDF, docx, zip, image, …) to a note — pass a local
`file_path`, an http(s) `file_url`, or `file_base64`. Attachments are written **straight to the
server**, so (unlike captures) they appear without the desktop client running. Manage them with
`list_attachments`, `download_attachment` and `delete_attachment`.

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
