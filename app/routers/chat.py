import os
import time
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.connection_manager import manager
from app.database import get_db  # adjust import path to match your project
from app.models import User

router = APIRouter(tags=["chat"])

TRANSFER_DIR = Path(settings.file_transfer_dir)
TRANSFER_DIR.mkdir(parents=True, exist_ok=True)

# In-memory index only: maps a one-time file_id -> (path, expiry).
# Never touches the database. Cleared once downloaded or expired.
_file_index: dict[str, dict] = {}


def _purge_expired():
    now = time.time()
    expired = [fid for fid, meta in _file_index.items() if meta["expires_at"] < now]
    for fid in expired:
        meta = _file_index.pop(fid, None)
        if meta:
            try:
                os.remove(meta["path"])
            except OSError:
                pass


async def get_current_user_ws_by_username(websocket: WebSocket, db: Session) -> User | None:
    """
    Resolves the connecting user directly from a `?username=` query param
    instead of a bearer token. No token/signature is verified here — this
    trusts whatever username is passed on the connection string.

    SECURITY NOTE: this removes token-based authentication entirely. Anyone
    who can reach this endpoint can connect *as* any existing username with
    no proof of identity. Only use this if the WS endpoint sits behind some
    other access control (e.g. a private network, VPN, or reverse proxy that
    already authenticates the caller) — otherwise this allows impersonation
    and reading/sending messages as any user.
    """
    username = websocket.query_params.get("username")
    if not username:
        return None

    user = db.query(User).filter(User.username == username).first()
    return user


# ---------------------------------------------------------------------------
# Live chat: direct WebSocket relay between two logged-in users.
# Messages are forwarded in-memory to the recipient's open socket and are
# never written anywhere. If the recipient is offline the message is
# dropped (for text) — for files, use the REST fallback below instead.
# ---------------------------------------------------------------------------
@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    # Auth is now based purely on the `username` query param
    # (ws://.../ws/chat?username=<username>) instead of a token.
    user = await get_current_user_ws_by_username(websocket, db)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(user.username, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            print(f"data received ----------- {data}")
            # Expected shape: {"to": "other_username", "type": "message"|"file",
            #                  "text": "...", "filename": "...", "file_id": "..."}
            to_user = data.get("to")
            if not to_user:
                await websocket.send_json({"type": "error", "detail": "'to' is required"})
                continue

            outgoing = {
                "type": data.get("type", "message"),
                "from": user.username,
                "text": data.get("text"),
                "filename": data.get("filename"),
                "file_id": data.get("file_id"),
            }
            delivered = await manager.send_json_to(to_user, outgoing)
            await websocket.send_json(
                {
                    "type": "ack",
                    "to": to_user,
                    "delivered": delivered,
                }
            )
    except WebSocketDisconnect:
        manager.disconnect(user.username)


# ---------------------------------------------------------------------------
# File transfer fallback (also used by the WS flow: upload -> get file_id ->
# send file_id over the socket -> recipient downloads once -> file deleted).
# Files sit on disk only briefly (TTL) and are removed after first download
# or expiry. No file ever gets a row in Postgres.
# ---------------------------------------------------------------------------
@router.post("/chat/files/upload")
async def upload_file(
    to: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    _purge_expired()

    file_id = str(uuid.uuid4())
    dest_path = TRANSFER_DIR / file_id

    with open(dest_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    _file_index[file_id] = {
        "path": str(dest_path),
        "filename": file.filename,
        "from": user.username,
        "to": to,
        "expires_at": time.time() + settings.file_ttl_seconds,
    }

    # If the recipient is online right now, ping them immediately.
    await manager.send_json_to(
        to,
        {
            "type": "file",
            "from": user.username,
            "filename": file.filename,
            "file_id": file_id,
        },
    )

    return {"file_id": file_id, "filename": file.filename, "expires_in": settings.file_ttl_seconds}


@router.get("/chat/files/{file_id}")
def download_file(file_id: str, user: User = Depends(get_current_user)):
    _purge_expired()

    meta = _file_index.get(file_id)
    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found or expired")

    if user.username not in (meta["from"], meta["to"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this file")

    path = meta["path"]
    filename = meta["filename"]

    def _cleanup():
        _file_index.pop(file_id, None)
        try:
            os.remove(path)
        except OSError:
            pass

    # One-time download: remove from disk + index right after serving.
    return FileResponse(
        path,
        filename=filename,
        media_type="application/octet-stream",
        background=BackgroundTask(_cleanup),
    )