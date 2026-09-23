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

## Google Connectors

Create one Google OAuth Web client in Google Cloud Console, enable the Google
APIs you want the chatbot to use, and put that single client ID and client secret
in `.env`:

```env
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
```

Add every Google connector callback URL to the same OAuth client's authorized
redirect URIs:

```text
http://localhost:8000/connectors/gmail/callback
http://localhost:8000/connectors/google_drive/callback
http://localhost:8000/connectors/youtube/callback
```

After the backend and frontend are running, use the Connectors menu to connect or
disconnect Gmail, Google Drive, and YouTube. Each connector asks for only its own
required scopes during the Google consent flow.

## Additional Connectors

The Connectors menu also supports LinkedIn, Telegram, Notion, and Trello.
OAuth connectors use these callback URLs:

```text
http://localhost:8000/connectors/linkedin/callback
http://localhost:8000/connectors/notion/callback
```

LinkedIn and Notion use their provider app `CLIENT_ID` / `CLIENT_SECRET` values.
Telegram connects with `TELEGRAM_BOT_TOKEN` from BotFather. Trello connects
through its authorization page using `TRELLO_API_KEY` from a Trello Power-Up/API
key.

## Tests

Run the backend safety tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
