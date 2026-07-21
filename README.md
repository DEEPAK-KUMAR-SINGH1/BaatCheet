# AI Chatbot

FastAPI backend, React/Vite frontend, and local SQLite storage.

## Setup

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Then fill in the API keys, email settings, `JWT_SECRET`, and admin bootstrap values. Use
`ADMIN_BOOTSTRAP_PASSWORD` only for first setup; after the admin account exists, remove it
from `.env` and use the forgot-password flow to set a private password.

Install backend dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend-react
npm install
```

## Run Locally

Start the FastAPI backend in one terminal:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```powershell
cd frontend-react
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies API requests to `http://localhost:8000`.

The default SQLite database is `backend/chatbot.db`. You can override it with `DATABASE_PATH` in `.env`.

## Gmail MCP Connector

Create a Google OAuth client in Google Cloud Console and save its JSON secret as
`backend/MCP/gmail/credentials.json`, or set `GMAIL_CLIENT_SECRETS_FILE` in `.env`.
The redirect URI in Google Cloud must match `GMAIL_REDIRECT_URI`; for local dev that is:

```text
http://localhost:8000/mcp/gmail/callback
```

After the backend and frontend are running, use the Gmail button in the chat header
to connect or disconnect the account. Once connected, the chatbot can search, read,
label/archive, and send Gmail messages through MCP tools.

## Additional MCP Connectors

The MCP menu also supports Google Drive, YouTube, LinkedIn, Telegram, Notion, and Trello.
OAuth connectors use these callback URLs:

```text
http://localhost:8000/mcp/google_drive/callback
http://localhost:8000/mcp/youtube/callback
http://localhost:8000/mcp/linkedin/callback
http://localhost:8000/mcp/notion/callback
```

Telegram connects from a configured bot token file (`TELEGRAM_BOT_TOKEN_FILE`).
Trello connects from `TRELLO_API_KEY` and `TRELLO_TOKEN`, or the matching values in
`backend/MCP/trello/credentials.json`.

## Tests

Run the backend safety tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
