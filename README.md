# Story Assistant

FastAPI backend (auth, stories/chapters/characters CRUD, AI-assisted chapter
generation) + a React frontend, backed by Neon Postgres, Redis, and either
OpenAI or a local Ollama model.

## Backend setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env   # fill in your Neon connection string + JWT_SECRET
.venv/bin/uvicorn app.main:app --reload
```

Docs at `http://localhost:8000/docs`.

There's no migration tool — tables are created straight from the current
SQLAlchemy models on startup (`Base.metadata.create_all`, see `app/main.py`'s
`lifespan`). Fine for a single-schema-owner project; add Alembic back only if
this needs versioned migrations against a shared/prod database later.

`DATABASE_URL` should be Neon's **pooled** (`-pooler`) endpoint, using the
`postgresql+asyncpg://` scheme — Neon's dashboard gives you a
`postgresql://...?sslmode=require&channel_binding=require` string; swap the
scheme and drop the query params (asyncpg doesn't parse them the same way
libpq does), then leave `DATABASE_SSL_REQUIRE=true` so the app passes
`ssl="require"` to asyncpg itself.

Needs a reachable Redis (`REDIS_URL`, default `redis://localhost:6379/0`) for
the generation module's session store, and either `LLM_PROVIDER=openai` +
`OPENAI_API_KEY`, or `LLM_PROVIDER=ollama` + a running local Ollama with
`OLLAMA_MODEL` pulled.

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL, default http://localhost:8000
npm run dev
```

Opens at `http://localhost:5173`. The backend's CORS config
(`app/main.py`) allows this origin in dev.

## Tests

`tests/test_smoke.py` runs the full flow (signup → character → story → import
→ chapter → turn reconstruction) against a real Postgres — no mocks, since the
whole point is exercising the DB layer. Point it at any throwaway Postgres:

```bash
export DATABASE_URL=postgresql+asyncpg://user@localhost/storydb_test
export DATABASE_SSL_REQUIRE=false
export JWT_SECRET=test-secret
.venv/bin/python -m tests.test_smoke
```

## Structure

```
app/
  main.py        FastAPI() instance, router registration, table creation on startup
  config.py      Settings (env vars)
  database.py    async engine/session, Base, uuid_pk()
  core/          security (password hashing, JWT), deps (get_db, get_current_user,
                 ownership checks), llm_client (OpenAI / Ollama)
  auth/          signup, login, /me
  users/         User model (no router — auth owns the signup/login workflow)
  characters/    character CRUD, relationships
  stories/       story CRUD, character import
  chapters/      chapter CRUD, reorder, active-character picks, body reconstruction
  generation/    the writing loop — Redis session store, prompt assembly,
                 generate/edit/accept/discard/complete, background summarization
frontend/        React + Vite SPA — auth, stories, characters, the writing room
tests/           smoke test against a real Postgres
```

Chapter body text is never stored as a flat column — it's reconstructed from
`chapter_turns` via `chapters.service.get_chapter_body`. The generation
module's context assembler reuses the same helper.
