# Notes MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets AI agents **create, read, list,
update and delete notes** in the self‑hosted Notes app (the ASP.NET Core + SQLite service that
backs the desktop client). Notes created via MCP are stored on the server and sync to every
device running the app.

It talks to the app's existing REST API over HTTPS using a bearer token — nothing new to install
on the server.

---

## Tools

| Tool | What it does |
|---|---|
| `list_notes(query="", limit=50)` | List notes (pinned first, newest next). `query` filters by title/text/tags. Returns id, title, updated, pinned, notebook, tags. |
| `read_note(note_id)` | Get a note's **plain‑text content** and metadata. |
| `create_note(title, content="", notebook="", tags="")` | Create a note (plain text). Returns the new `id`. |
| `update_note(note_id, title=None, content=None, notebook=None, tags=None)` | Update fields; anything left `None` is unchanged. |
| `delete_note(note_id)` | Delete a note (moved to Trash — restorable in the app). |
| `capture_markdown(markdown, title="", note_id="")` | Append **rich Markdown** (headings, callouts, code, checklists, tables, links) to a note. |
| `health()` | Check the server is reachable. |

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

### Claude Agent SDK / other MCP clients

Any client that speaks MCP over stdio can launch `python -m notes_mcp.server` the same way.
See [`examples/`](examples/) for a minimal programmatic client.

---

## Security

- All calls require the bearer token; keep `NOTES_API_TOKEN` secret (use env vars / your client's
  secret store, not source control).
- The server is expected to be reachable over HTTPS (the reference deployment uses a Caddy TLS
  reverse proxy). Treat note content the agent reads/writes as you would any personal data.

## License

MIT — see [LICENSE](LICENSE).
