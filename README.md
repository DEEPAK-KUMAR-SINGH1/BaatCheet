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

## Tests

Run the backend safety tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
