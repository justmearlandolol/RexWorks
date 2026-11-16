# RexWorks
 
AI workspace with chat, coding, and web search modes. FastAPI backend on Groq, static HTML frontend, Supabase login.
 
- Web link: https://rexworks-frontend.vercel.app
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
 
 
## Deployment
 
Two Vercel projects from the same repo:
 
- `rexworks-backend`: root directory `Backend`
- `rexworks-frontend`: root directory `Frontend`
Set the environment variables above on the backend project.
 
