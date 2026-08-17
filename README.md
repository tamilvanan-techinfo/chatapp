# Chat Auth + Relay API

FastAPI service that handles:
- **Register** (`POST /auth/register`) — stored in PostgreSQL
- **Login** (`POST /auth/login`) — returns a JWT, checked against PostgreSQL
- **Chat** (`WS /ws/chat`, `POST /chat/files/upload`, `GET /chat/files/{id}`) — **not stored in the database at all**

## Why chat isn't in the DB
There is only one table: `users`. Text messages sent over the WebSocket are
relayed directly, in-memory, to the recipient's open socket and then
discarded. Files are written briefly to a temp folder on disk (not Postgres),
pushed to the recipient if they're online, and deleted the moment they're
downloaded or after a TTL expires (default 1 hour). Nothing chat-related is
ever modeled in SQLAlchemy or written to Postgres.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DATABASE_URL to your Postgres instance, and set a real SECRET_KEY

# create the database first, e.g.:
# createdb chatapp

uvicorn app.main:app --reload
```

Docs at `http://localhost:8000/docs`.

## Usage

### 1. Register
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","password":"supersecret1"}'
```

### 2. Login (OAuth2 form body, not JSON)
```bash
curl -X POST http://localhost:8000/auth/login \
  -d "username=alice&password=supersecret1"
```
Returns `{"access_token": "...", "token_type": "bearer"}`.

### 3. Chat over WebSocket
Connect with the JWT as a query param (browsers can't send WS headers):
```
ws://localhost:8000/ws/chat?token=<access_token>
```
Send JSON frames:
```json
{"to": "bob", "type": "message", "text": "hey!"}
```
The server relays it live to `bob`'s socket if `bob` is connected, and sends
you back an `{"type": "ack", "delivered": true/false}`.

### 4. Send a file
Either:
- Upload via REST, then tell the recipient the `file_id` over the WebSocket:
  ```bash
  curl -X POST http://localhost:8000/chat/files/upload \
    -H "Authorization: Bearer <token>" \
    -F "to=bob" -F "file=@photo.png"
  ```
  This immediately notifies `bob` over WS if online (`{"type":"file", "file_id": "..."}`).
- Recipient downloads it once (auto-deleted from disk right after):
  ```bash
  curl -H "Authorization: Bearer <token>" \
    http://localhost:8000/chat/files/<file_id> -o photo.png
  ```

## Project layout
```
app/
  config.py       # settings (.env)
  database.py     # Postgres engine/session (users only)
  models.py       # single User model
  schemas.py      # Pydantic request/response models
  auth.py         # password hashing + JWT
  connection_manager.py  # in-memory WebSocket registry
  routers/
    auth.py       # /auth/register, /auth/login
    chat.py       # /ws/chat, /chat/files/*
  main.py         # app assembly
```
