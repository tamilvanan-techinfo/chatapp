from fastapi import WebSocket


class ConnectionManager:
    """
    Holds active WebSocket connections in memory only, keyed by username.
    Nothing here is ever written to the database - if a message can't be
    delivered live (recipient offline), it is simply dropped (or, for
    files, briefly spooled to disk via the REST fallback - see routers/chat.py).
    """

    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active[username] = websocket

    def disconnect(self, username: str):
        self.active.pop(username, None)

    def is_online(self, username: str) -> bool:
        return username in self.active

    async def send_json_to(self, username: str, payload: dict) -> bool:
        ws = self.active.get(username)
        if ws is None:
            return False
        await ws.send_json(payload)
        return True


manager = ConnectionManager()
