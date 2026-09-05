"""
Notes MCP server.

Exposes your self-hosted Notes app (the ASP.NET Core REST API behind the desktop client)
to any MCP-capable agent so it can create, read, list, update and delete notes, attach files,
and manage Kanban boards (columns and cards).

Configuration (environment variables):
  NOTES_API_URL    Base URL of your Notes server, e.g. https://macross.no-ip.info
  NOTES_API_TOKEN  The bearer token your server was configured with (same token the
                   desktop app uses in Settings -> API token).

Run it (stdio transport, which is what Claude Desktop / most MCP clients use):
  NOTES_API_URL=https://macross.no-ip.info NOTES_API_TOKEN=xxxx python -m notes_mcp.server
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import uuid
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
            "archived": n.get("archived", False),
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
            "archived": n.get("archived", False),
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
def archive_note(note_id: str, archived: bool = True) -> dict:
    """Archive a note (hide it from the main list without deleting), or unarchive it by
    passing archived=false. Archived notes remain fully intact and searchable in the desktop
    app's archived view. Returns the note id and its new archived state."""
    with _client() as c:
        action = "archive" if archived else "unarchive"
        r = c.post(f"/api/notes/{note_id}/{action}")
        if r.status_code == 404:
            return {"error": "not found", "id": note_id}
        r.raise_for_status()
        return {"id": note_id, "archived": archived}


@mcp.tool()
def list_attachments(note_id: str) -> list[dict]:
    """List the files attached to a note. Returns each attachment's id, file name, content
    type, size in bytes and creation time (not the file bytes — use download_attachment)."""
    with _client() as c:
        r = c.get(f"/api/notes/{note_id}/attachments")
        r.raise_for_status()
        return [
            {
                "id": a.get("id"),
                "fileName": a.get("fileName"),
                "contentType": a.get("contentType"),
                "size": a.get("size"),
                "createdUtc": a.get("createdUtc"),
            }
            for a in r.json()
        ]


@mcp.tool()
def attach_file(note_id: str, file_path: str = "", file_url: str = "", file_base64: str = "",
                filename: str = "", content_type: str = "") -> dict:
    """Attach a file to a note. Provide the file as exactly ONE of:
      - file_path   : a local file path readable by this MCP process, or
      - file_url    : an http(s) URL (downloaded by this process), or
      - file_base64 : raw base64 (a `data:...;base64,` prefix is accepted and stripped).
    `filename` names the attachment (required for file_base64; otherwise inferred from the path
    or URL). `content_type` is optional and inferred from the filename when omitted. Any file type
    is accepted (PDF, docx, zip, images, …). Returns the new attachment's id, name and size."""
    if file_base64.strip():
        b64 = file_base64.strip()
        if b64.startswith("data:") and "," in b64:
            b64 = b64.split(",", 1)[1]
        data = base64.b64decode(b64)
        name = filename.strip() or "file"
    elif file_path.strip():
        with open(file_path.strip(), "rb") as f:
            data = f.read()
        name = filename.strip() or os.path.basename(file_path.strip()) or "file"
    elif file_url.strip():
        resp = httpx.get(file_url.strip(), timeout=60.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.content
        name = filename.strip() or os.path.basename(file_url.split("?", 1)[0].rstrip("/")) or "file"
    else:
        return {"error": "Provide one of file_path, file_url or file_base64."}

    ct = content_type.strip() or (mimetypes.guess_type(name)[0] or "application/octet-stream")
    with _client() as c:
        r = c.post(
            f"/api/notes/{note_id}/attachments",
            content=data,
            headers={"Content-Type": ct, "X-File-Name": name},
        )
        r.raise_for_status()
        a = r.json()
        return {"id": a.get("id"), "fileName": a.get("fileName"), "size": a.get("size")}


@mcp.tool()
def download_attachment(attachment_id: str, save_path: str) -> dict:
    """Download an attachment (by its id, from list_attachments) and write it to `save_path`
    on this machine. Returns the path written and the number of bytes."""
    with _client() as c:
        r = c.get(f"/api/attachments/{attachment_id}")
        if r.status_code == 404:
            return {"error": "not found", "id": attachment_id}
        r.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(r.content)
        return {"savedTo": save_path, "bytes": len(r.content)}


@mcp.tool()
def delete_attachment(attachment_id: str) -> dict:
    """Permanently delete an attachment by its id. Returns ok."""
    with _client() as c:
        r = c.delete(f"/api/attachments/{attachment_id}")
        r.raise_for_status()
        return {"id": attachment_id, "deleted": True}


# ---------------------------------------------------------------------------
# Kanban boards
#
# A board is one row on the server with a `data` JSON blob holding its columns
# and cards. That blob uses PascalCase keys (Columns, Cards, Title, …) and GUID
# ids — the shape the desktop client reads/writes. These tools hide that: they
# read the board, mutate the parsed structure, and PUT it back with optimistic
# concurrency (rowVersion), retrying if it changed underneath.
# ---------------------------------------------------------------------------

# Column starter sets, mirroring the desktop app's board templates.
_TEMPLATES = {
    "basic": ["To do", "In progress", "In review", "Done"],
    "simple": ["To do", "Doing", "Done"],
    "sprint": ["Backlog", "To do", "In progress", "Review", "Done"],
    "weekly": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "blank": [],
}
# Pleasant colour order for auto-assigning list colours (matches the client).
_CYCLE = ["purple", "orange", "blue", "green", "red", "yellow", "grey"]
# Valid card/column colour keys.
_COLORS = {"red", "orange", "yellow", "green", "blue", "purple", "grey"}


def _iso_due(due: str) -> str | None:
    due = (due or "").strip()
    if not due:
        return None
    return due if "T" in due else due + "T00:00:00"


def _norm_checklist(items: Any) -> list[dict]:
    out = []
    for it in items or []:
        if isinstance(it, dict):
            out.append({"Text": str(it.get("text", it.get("Text", ""))),
                        "Done": bool(it.get("done", it.get("Done", False)))})
        else:
            out.append({"Text": str(it), "Done": False})
    return out


def _new_card(title: str, description: str, color: str, due: str,
              labels: Any, checklist: Any) -> dict:
    card: dict[str, Any] = {
        "Id": str(uuid.uuid4()),
        "Title": title,
        "Description": description or "",
        "Color": color or "",
        "Labels": list(labels or []),
    }
    iso = _iso_due(due)
    if iso:
        card["Due"] = iso
    if checklist:
        card["Checklist"] = _norm_checklist(checklist)
    return card


def _card_out(card: dict) -> dict:
    return {
        "id": card.get("Id"),
        "title": card.get("Title", ""),
        "description": card.get("Description", ""),
        "color": card.get("Color", ""),
        "due": card.get("Due"),
        "labels": card.get("Labels", []),
        "checklist": [{"text": ci.get("Text", ""), "done": bool(ci.get("Done", False))}
                      for ci in card.get("Checklist", [])],
    }


def _parse_board_data(dto: dict) -> dict:
    raw = dto.get("data") or ""
    try:
        obj = json.loads(raw) if raw.strip() else {}
    except Exception:
        obj = {}
    obj.setdefault("Columns", [])
    obj.setdefault("Archived", [])
    return obj


def _find_column(data: dict, key: str) -> dict | None:
    for col in data["Columns"]:
        if col.get("Id") == key:
            return col
    for col in data["Columns"]:
        if str(col.get("Title", "")).strip().lower() == str(key).strip().lower():
            return col
    return None


def _find_card(data: dict, card_id: str):
    for col in data["Columns"]:
        for card in col.get("Cards", []):
            if card.get("Id") == card_id:
                return col, card
    return None, None


def _mutate_board(board_id: str, fn) -> dict:
    """GET the board, let fn(board) mutate {"name","data"} in place, PUT it back with the
    rowVersion. Retries on a 409 (someone else saved in between). fn may raise ValueError to
    abort with a clean error, and may return a dict merged into the result."""
    for _ in range(4):
        with _client() as c:
            r = c.get(f"/api/boards/{board_id}")
            if r.status_code == 404:
                return {"error": "not found", "id": board_id}
            r.raise_for_status()
            dto = r.json()
            board = {"name": dto.get("name", ""), "data": _parse_board_data(dto)}
            try:
                extra = fn(board) or {}
            except ValueError as e:
                return {"error": str(e)}
            payload = {"name": board["name"], "data": json.dumps(board["data"]),
                       "rowVersion": dto.get("rowVersion", "")}
            pr = c.put(f"/api/boards/{board_id}", json=payload)
            if pr.status_code == 409:
                continue   # board changed on the server; re-read and re-apply
            pr.raise_for_status()
            return {"id": board_id, "updated": True, **extra}
    return {"error": "conflict: the board kept changing on the server; try again"}


@mcp.tool()
def list_boards(deleted: bool = False) -> list[dict]:
    """List Kanban boards (id, name, last-updated). Use read_board for a board's columns/cards. Pass
    deleted=True to list trashed boards (restore one with undelete_board)."""
    with _client() as c:
        r = c.get("/api/boards", params={"deleted": "true" if deleted else "false"})
        r.raise_for_status()
        return [{"id": b["id"], "name": b.get("name", ""), "updatedUtc": b.get("updatedUtc")}
                for b in r.json()]


@mcp.tool()
def read_board(board_id: str) -> dict:
    """Read a board's full structure: its columns (id, title, colour) and each column's cards
    (id, title, description, colour, due, labels, checklist). Card/column ids are needed by the
    add/update/move/delete tools."""
    with _client() as c:
        r = c.get(f"/api/boards/{board_id}")
        if r.status_code == 404:
            return {"error": "not found", "id": board_id}
        r.raise_for_status()
        dto = r.json()
        data = _parse_board_data(dto)
        columns = [{
            "id": col.get("Id"),
            "title": col.get("Title", ""),
            "color": col.get("Color", ""),
            "cards": [_card_out(card) for card in col.get("Cards", [])],
        } for col in data["Columns"]]
        return {"id": dto["id"], "name": dto.get("name", ""), "columns": columns,
                "archivedCount": len(data.get("Archived", []))}


@mcp.tool()
def create_board(name: str, template: str = "basic", columns: list[str] | None = None) -> dict:
    """Create a Kanban board. Either pick a `template` (basic, simple, sprint, weekly, blank) or pass
    an explicit `columns` list of column titles (overrides template). Returns the new board id."""
    titles = columns if columns else _TEMPLATES.get(template, _TEMPLATES["basic"])
    data = {
        "Columns": [{"Id": str(uuid.uuid4()), "Title": t, "Color": _CYCLE[i % len(_CYCLE)], "Cards": []}
                    for i, t in enumerate(titles)],
        "Archived": [],
    }
    with _client() as c:
        r = c.post("/api/boards", json={"name": name, "data": json.dumps(data)})
        r.raise_for_status()
        b = r.json()
        return {"id": b["id"], "name": b.get("name", name)}


@mcp.tool()
def rename_board(board_id: str, name: str) -> dict:
    """Rename a board."""
    def _fn(board):
        board["name"] = name
    return _mutate_board(board_id, _fn)


@mcp.tool()
def delete_board(board_id: str) -> dict:
    """Delete a board (moved to Trash, restorable in the desktop app)."""
    with _client() as c:
        r = c.delete(f"/api/boards/{board_id}")
        if r.status_code == 404:
            return {"error": "not found", "id": board_id}
        r.raise_for_status()
        return {"id": board_id, "deleted": True}


@mcp.tool()
def add_column(board_id: str, title: str, color: str = "") -> dict:
    """Add a column (list) to a board. `color` is an optional key: red, orange, yellow, green, blue,
    purple, grey (auto-assigned if omitted). Returns the new column id."""
    def _fn(board):
        cols = board["data"]["Columns"]
        col = {"Id": str(uuid.uuid4()), "Title": title,
               "Color": color if color in _COLORS else _CYCLE[len(cols) % len(_CYCLE)], "Cards": []}
        cols.append(col)
        return {"columnId": col["Id"]}
    return _mutate_board(board_id, _fn)


@mcp.tool()
def delete_column(board_id: str, column: str) -> dict:
    """Delete a column and its cards. `column` is a column id or its exact title."""
    def _fn(board):
        target = _find_column(board["data"], column)
        if target is None:
            raise ValueError(f"column '{column}' not found")
        board["data"]["Columns"].remove(target)
        return {"removedCards": len(target.get("Cards", []))}
    return _mutate_board(board_id, _fn)


@mcp.tool()
def add_card(board_id: str, column: str, title: str, description: str = "", color: str = "",
             due: str = "", labels: list[str] | None = None, checklist: list | None = None) -> dict:
    """Add a card to a column. `column` is a column id or its exact title. Optional: `description`,
    `color` (red/orange/yellow/green/blue/purple/grey), `due` ("YYYY-MM-DD"), `labels` (colour keys),
    and `checklist` (a list of strings, or {"text","done"} dicts). Returns the new card id."""
    def _fn(board):
        target = _find_column(board["data"], column)
        if target is None:
            raise ValueError(f"column '{column}' not found")
        card = _new_card(title, description, color, due, labels, checklist)
        target.setdefault("Cards", []).append(card)
        return {"cardId": card["Id"]}
    return _mutate_board(board_id, _fn)


@mcp.tool()
def update_card(board_id: str, card_id: str, title: str | None = None, description: str | None = None,
                color: str | None = None, due: str | None = None, labels: list[str] | None = None,
                checklist: list | None = None) -> dict:
    """Update a card's fields; anything left null/None is unchanged. `due=""` clears the due date;
    `labels`/`checklist` replace the whole list when provided (checklist items may be strings or
    {"text","done"} dicts)."""
    def _fn(board):
        data = board["data"]
        _, card = _find_card(data, card_id)
        if card is None:
            for c2 in data.get("Archived", []):
                if c2.get("Id") == card_id:
                    card = c2
                    break
        if card is None:
            raise ValueError(f"card {card_id} not found")
        if title is not None:
            card["Title"] = title
        if description is not None:
            card["Description"] = description
        if color is not None:
            card["Color"] = color
        if labels is not None:
            card["Labels"] = list(labels)
        if checklist is not None:
            card["Checklist"] = _norm_checklist(checklist)
        if due is not None:
            if due == "":
                card.pop("Due", None)
            else:
                card["Due"] = _iso_due(due)
        return {"cardId": card_id}
    return _mutate_board(board_id, _fn)


@mcp.tool()
def move_card(board_id: str, card_id: str, to_column: str, position: int | None = None) -> dict:
    """Move a card to another column. `to_column` is a column id or its exact title. `position` is an
    optional 0-based index within the target column (appended to the end if omitted)."""
    def _fn(board):
        data = board["data"]
        col, card = _find_card(data, card_id)
        if card is None:
            raise ValueError(f"card {card_id} not found")
        target = _find_column(data, to_column)
        if target is None:
            raise ValueError(f"column '{to_column}' not found")
        col["Cards"].remove(card)
        cards = target.setdefault("Cards", [])
        if position is None or position < 0 or position > len(cards):
            cards.append(card)
        else:
            cards.insert(position, card)
        return {"cardId": card_id}
    return _mutate_board(board_id, _fn)


@mcp.tool()
def delete_card(board_id: str, card_id: str) -> dict:
    """Delete a card from a board."""
    def _fn(board):
        col, card = _find_card(board["data"], card_id)
        if card is None:
            raise ValueError(f"card {card_id} not found")
        col["Cards"].remove(card)
        return {"cardId": card_id}
    return _mutate_board(board_id, _fn)


@mcp.tool()
def archive_card(board_id: str, card_id: str) -> dict:
    """Archive a card: hide it from the board without deleting it (restorable with unarchive_card, or in
    the desktop app's board archive). Its origin column is remembered. Good for clearing 'Done' cards."""
    def _fn(board):
        data = board["data"]
        col, card = _find_card(data, card_id)
        if card is None:
            raise ValueError(f"card {card_id} not found")
        card["ArchivedFromColumnId"] = col.get("Id")
        col["Cards"].remove(card)
        data.setdefault("Archived", []).append(card)
        return {"cardId": card_id, "archived": True}
    return _mutate_board(board_id, _fn)


@mcp.tool()
def unarchive_card(board_id: str, card_id: str, to_column: str = "") -> dict:
    """Restore an archived card to a column. By default it returns to the column it came from (or the
    first column if that's gone); pass `to_column` (id or title) to place it elsewhere."""
    def _fn(board):
        data = board["data"]
        archived = data.setdefault("Archived", [])
        card = next((c for c in archived if c.get("Id") == card_id), None)
        if card is None:
            raise ValueError(f"archived card {card_id} not found")
        target = _find_column(data, to_column) if to_column else None
        if target is None and card.get("ArchivedFromColumnId"):
            target = _find_column(data, card["ArchivedFromColumnId"])
        if target is None:
            target = data["Columns"][0] if data["Columns"] else None
        if target is None:
            raise ValueError("board has no columns to restore into")
        archived.remove(card)
        card.pop("ArchivedFromColumnId", None)
        target.setdefault("Cards", []).append(card)
        return {"cardId": card_id, "column": target.get("Title", "")}
    return _mutate_board(board_id, _fn)


@mcp.tool()
def move_column(board_id: str, column: str, position: int) -> dict:
    """Reorder a column. `column` is a column id or its exact title; `position` is the 0-based target
    index among the columns."""
    def _fn(board):
        cols = board["data"]["Columns"]
        target = _find_column(board["data"], column)
        if target is None:
            raise ValueError(f"column '{column}' not found")
        cols.remove(target)
        pos = max(0, min(int(position), len(cols)))
        cols.insert(pos, target)
        return {"columnId": target.get("Id")}
    return _mutate_board(board_id, _fn)


@mcp.tool()
def undelete_board(board_id: str) -> dict:
    """Restore a deleted board from Trash. Use `list_boards(deleted=True)` to find a trashed board's id."""
    with _client() as c:
        r = c.post(f"/api/boards/{board_id}/undelete")
        if r.status_code == 404:
            return {"error": "not found", "id": board_id}
        r.raise_for_status()
        return {"id": board_id, "restored": True}


@mcp.tool()
def search_boards(query: str, limit: int = 50) -> list[dict]:
    """Search across all boards for cards matching a term (matches a card's title, description and
    checklist items), returning each hit with its board/column context and card id. Use this to find
    or locate cards; notes are searched separately with `list_notes(query=...)`."""
    q = (query or "").strip().lower()
    if not q:
        return []
    hits: list[dict] = []
    with _client() as c:
        r = c.get("/api/boards", params={"deleted": "false"})
        r.raise_for_status()
        for b in r.json():
            try:
                rr = c.get(f"/api/boards/{b['id']}")
                if rr.status_code != 200:
                    continue
                dto = rr.json()
            except Exception:
                continue
            data = _parse_board_data(dto)
            for col in data["Columns"]:
                for card in col.get("Cards", []):
                    title = card.get("Title", "") or ""
                    desc = card.get("Description", "") or ""
                    checklist = " ".join(ci.get("Text", "") for ci in card.get("Checklist", []))
                    if q in f"{title}\n{desc}\n{checklist}".lower():
                        where = ("title" if q in title.lower()
                                 else "description" if q in desc.lower() else "checklist")
                        hits.append({
                            "boardId": dto["id"], "boardName": dto.get("name", ""),
                            "column": col.get("Title", ""), "cardId": card.get("Id"),
                            "cardTitle": title, "matchedIn": where,
                        })
                        if len(hits) >= max(1, limit):
                            return hits
    return hits


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
