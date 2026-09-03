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
`list_notes`, `read_note`, `create_note`, `update_note`, `delete_note`, `capture_markdown`,
`capture_image`, `health`.
See [README.md](README.md#tools) for parameters, the plain-text vs. Markdown note, and how to
insert images (`capture_image`).

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

## 7. Creating grouped / titled sections
To present a titled, visually-grouped block of content, use **`capture_markdown`** with a **callout**:

```
> [!info] Overview
> This whole block shows as one titled, coloured section.
> It can span multiple lines.
```
Callout types: `info` / `note` (blue), `success` (green), `warning` (orange), `tip` (yellow).
You can also group content with headings (`#`, `##`, `###`), fenced code blocks (```), task lists
(`- [ ] item`), and tables (`| a | b |`). Example creating/append­ing to one note:

```
capture_markdown(title="Release notes", markdown="""
## Release 2.3

> [!success] Shipped
> All checks passed.

> [!warning] Follow-up
> Rotate the API key next week.

- [x] build
- [ ] announce
""")
```
(The desktop app also has a manual "titled section" block in its toolbar; over MCP, callouts are the
equivalent grouped section.)

## Notes for the agent
- If `command: "python"` isn't found, try `python3`, or the absolute path to a Python 3.10+ interpreter.
- On Windows, if a virtual environment is used, point `command` at that env's `python.exe`.
- `read_note` returns note text only if the Notes server exposes `PlainText` (recent server build).
- `capture_markdown` content is rendered by the desktop client, so it appears once a client runs.
