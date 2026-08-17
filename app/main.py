from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth, chat, users

# Creates only the `users` table. Chat data is intentionally never modeled
# here, so there is nothing for the DB to store for messages/files.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Chat Auth + Relay API",
    description=(
        "Register/login are backed by PostgreSQL. Chat messages and files "
        "are relayed live over WebSocket / briefly spooled to disk and are "
        "never written to the database."
    ),
    version="1.0.0",
)

# Allow the frontend dev server(s) to call this API from the browser.
# Add your deployed frontend origin here too once you have one.
origins = [
    "http://localhost:3000",   # Create React App default
    "http://localhost:5173",  # Vite default
    "http://localhost:1029",  # Vite default
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:1029",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}