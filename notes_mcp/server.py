"""
Notes MCP server.

Exposes your self-hosted Notes app (the ASP.NET Core REST API behind the desktop client)
to any MCP-capable agent so it can create, read, list, update and delete notes.

Configuration (environment variables):
  NOTES_API_URL    Base URL of your Notes server, e.g. https://macross.no-ip.info
  NOTES_API_TOKEN  The bearer token your server was configured with (same token the
                   desktop app uses in Settings -> API token).

Run it (stdio transport, which is what Claude Desktop / most MCP clients use):
  NOTES_API_URL=https://macross.no-ip.info NOTES_API_TOKEN=xxxx python -m notes_mcp.server
"""
from __future__ import annotations

import base64
import os
from typing import Any

import httpx

# The MCP Python SDK renamed FastMCP -> MCPServer in v2; support both.
try:
    from mcp.server.mcpserver import MCPServer as _Server  # mcp >= 2.0
except ModuleNotFoundError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Server      # mcp 1.x

mcp = _Server("notes")


def _base_url() -> str:
    url = os.environ.get("NOTES_API_URL", "").strip().rstrip("/")
    if not url:
        raise RuntimeError("NOTES_API_URL is not set (e.g. https://macross.no-ip.info)")
    return url


def _client() -> httpx.Client:
    token = os.environ.get("NOTES_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("NOTES_API_TOKEN is not set")
    return httpx.Client(
        base_url=_base_url(),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )


def _summary(n: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": n.get("id"),
        "title": n.get("title") or "(untitled)",
        "updatedUtc": n.get("updatedUtc"),
        "pinned": n.get("pinned", False),
        "notebook": n.get("notebook", ""),
        "tags": n.get("tags", ""),
    }


@mcp.tool()
def list_notes(query: str = "", limit: int = 50) -> list[dict]:
    """List notes (most-recent first, pinned on top). Optionally filter by a search
    term that matches the title, text or tags. Returns id, title, updated time,
    pinned flag, notebook and tags — not the note body (use read_note for that)."""
    with _client() as c:
        params = {"deleted": "false"}
        if query.strip():
            params["q"] = query.strip()
        r = c.get("/api/notes", params=params)
        r.raise_for_status()
        return [_summary(n) for n in r.json()[: max(1, limit)]]


@mcp.tool()
def read_note(note_id: str) -> dict:
    """Read a single note's plain-text content and metadata by its id."""
    with _client() as c:
        r = c.get(f"/api/notes/{note_id}")
        if r.status_code == 404:
            return {"error": "not found", "id": note_id}
        r.raise_for_status()
        n = r.json()
        return {
            "id": n["id"],
            "title": n.get("title") or "(untitled)",
            "text": n.get("plainText", ""),
            "notebook": n.get("notebook", ""),
            "tags": n.get("tags", ""),
            "pinned": n.get("pinned", False),
            "updatedUtc": n.get("updatedUtc"),
        }


@mcp.tool()
def create_note(title: str, content: str = "", notebook: str = "", tags: str = "") -> dict:
    """Create a new note with a title and plain-text content. `tags` is a comma-separated
    string. Returns the new note's id. The note is stored immediately and shows up in the
    desktop app (and syncs to every device). For richly-formatted notes (headings, callouts,
    checklists, images) use capture_markdown instead."""
    body_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    payload = {
        "title": title,
        "body": body_b64,        # stored as-is; the client renders it as text
        "plainText": content,
        "notebook": notebook,
        "tags": tags,
        "pinned": False,
    }
    with _client() as c:
        r = c.post("/api/notes", json=payload)
        r.raise_for_status()
        n = r.json()
        return {"id": n["id"], "title": n.get("title", title)}


@mcp.tool()
def update_note(note_id: str, title: str | None = None, content: str | None = None,
                notebook: str | None = None, tags: str | None = None) -> dict:
    """Update a note. Any argument left as null/None is kept unchanged. Returns the note id."""
    with _client() as c:
        cur = c.get(f"/api/notes/{note_id}")
        if cur.status_code == 404:
            return {"error": "not found", "id": note_id}
        cur.raise_for_status()
        n = cur.json()

        new_title = n.get("title", "") if title is None else title
        if content is None:
            body_b64 = n.get("body", "")          # already base64 from the API
            plain = n.get("plainText", "")
        else:
            body_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            plain = content

        payload = {
            "title": new_title,
            "body": body_b64,
            "plainText": plain,
            "rowVersion": n.get("rowVersion", ""),
            "pinned": n.get("pinned", False),
            "tags": n.get("tags", "") if tags is None else tags,
            "notebook": n.get("notebook", "") if notebook is None else notebook,
            "reminderUtc": n.get("reminderUtc"),
        }
        r = c.put(f"/api/notes/{note_id}", json=payload)
        if r.status_code == 409:
            return {"error": "conflict: the note changed on the server; read it again and retry"}
        r.raise_for_status()
        return {"id": note_id, "updated": True}


@mcp.tool()
def delete_note(note_id: str) -> dict:
    """Delete a note (moved to Trash, restorable from the desktop app). Returns ok."""
    with _client() as c:
        r = c.delete(f"/api/notes/{note_id}")
        if r.status_code == 404:
            return {"error": "not found", "id": note_id}
        r.raise_for_status()
        return {"id": note_id, "deleted": True}


@mcp.tool()
def capture_markdown(markdown: str, title: str = "", note_id: str = "") -> dict:
    """Append richly-formatted content (Markdown) to a note. Markdown is rendered into real
    blocks — headings, callouts (`> [!info]`), code fences, checklists (`- [ ]`), tables,
    bold/italic, links. Provide `note_id` to append to a specific note, or `title` to append
    to (or create) a note with that title. NOTE: captures are materialized by the desktop
    client, so a client must run at least once for the note to appear."""
    payload: dict[str, Any] = {"text": markdown}
    if note_id.strip():
        payload["noteId"] = note_id.strip()
    if title.strip():
        payload["title"] = title.strip()
    with _client() as c:
        r = c.post("/api/inbox", json=payload)
        r.raise_for_status()
        return {"queued": True, "captureId": r.json().get("id")}


@mcp.tool()
def capture_image(image_url: str = "", image_path: str = "", image_base64: str = "",
                  caption: str = "", title: str = "", note_id: str = "") -> dict:
    """Insert a **real image** into a note. Provide the image as exactly ONE of:
      - image_url    : an http(s) URL (the server downloads it), or
      - image_path   : a local file path readable by this MCP process, or
      - image_base64 : raw base64 (a `data:image/...;base64,` prefix is accepted and stripped).
    Optional: `caption` (text placed above the image), and a target via `note_id` (append to that
    note) or `title` (append to / create a note with that title). PNG/JPEG/GIF/BMP are supported.
    Like all captures, the image is materialized by the desktop client, so a client must run at
    least once for it to appear."""
    if image_base64.strip():
        b64 = image_base64.strip()
        if b64.startswith("data:") and "," in b64:
            b64 = b64.split(",", 1)[1]
    elif image_path.strip():
        with open(image_path.strip(), "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    elif image_url.strip():
        resp = httpx.get(image_url.strip(), timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        b64 = base64.b64encode(resp.content).decode("ascii")
    else:
        return {"error": "Provide one of image_url, image_path or image_base64."}

    payload: dict[str, Any] = {"image": b64}
    if caption.strip():
        payload["text"] = caption
    if note_id.strip():
        payload["noteId"] = note_id.strip()
    if title.strip():
        payload["title"] = title.strip()
    with _client() as c:
        r = c.post("/api/inbox", json=payload)
        r.raise_for_status()
        return {"queued": True, "captureId": r.json().get("id")}


@mcp.tool()
def health() -> dict:
    """Check that the Notes server is reachable."""
    with httpx.Client(base_url=_base_url(), timeout=10.0) as c:
        r = c.get("/api/health")
        return {"ok": r.status_code == 200, "status": r.status_code}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
