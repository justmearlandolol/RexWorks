# RexWorks
 
AI workspace with chat, coding, and web search modes. FastAPI backend on Groq, static HTML frontend, Supabase login.
 
- Frontend: https://rexworks-frontend.vercel.app
- Backend: https://rexworks-backend.vercel.app
## Features
 
- Chat mode: general conversation, web search, image input
- Coding mode: sandboxed bash tool to run and verify code (max 6 steps per message, sandbox reset on every message)
- Canvas actions on pasted content
- File upload and audio transcription (Whisper)
- Streaming responses (SSE)
- Round-robin Groq API key pool with per-key cooldown and secret redaction
- Auth via Supabase JWT or `X-App-Token`
## Structure
 
```
RexWorks/
├── Backend/
│   ├── main.py            FastAPI app, middleware, error handlers
│   ├── api/index.py       Vercel entrypoint
│   ├── core/              config, security, modes, provider, chat, agent, uploads, routes
│   ├── tests/
│   ├── requirements.txt
│   └── vercel.json
├── Frontend/
│   ├── index.html         main app
│   ├── Main.html          login page
│   └── greet.js
└── assets/
```
 
## Setup
 
Backend:
 
```
cd Backend
pip install -r requirements.txt
uvicorn main:app --reload
```
 
Frontend: serve `Frontend/` with any static server, or open it through the backend at `/`. Set the `rexwork-api` meta tag in `index.html` to the backend URL.
 
Tests:
 
```
cd Backend
pytest
```
 
 
## API
 
All `/api/*` routes require `Authorization: Bearer <supabase_jwt>` or `X-App-Token`, except `/api/status`, `/api/health`, and `/api/index`.
 
| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/chat` | Chat and coding, streamed |
| POST | `/api/search` | Web search answer |
| POST | `/api/canvas` | Transform content with a canvas action |
| POST | `/api/upload` | Upload a file |
| POST | `/api/transcribe` | Transcribe audio |
| GET | `/api/models` | Available modes and models |
| GET | `/api/status` | App status |
| GET | `/api/health` | Health check |
 
## Deployment
 
Two Vercel projects from the same repo:
 
- `rexworks-backend`: root directory `Backend`
- `rexworks-frontend`: root directory `Frontend`
Set the environment variables above on the backend project.
 
