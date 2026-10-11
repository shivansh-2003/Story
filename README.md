# Story Assistant

Story Assistant is a web app for writing fiction with AI while keeping the writer in control. Build a story bible and cast, organize chapters, generate prose a paragraph at a time, and approve each draft before it enters the manuscript. You can also import existing writing, edit accepted paragraphs, plan scenes, and request targeted AI rewrites.


## Features

- **Story bible:** define the premise, genre, tone, setting, POV, tense, and writing preferences that guide generation.
- **Reusable characters:** maintain character sheets and relationships, reuse characters across stories, and choose the active chapter cast.
- **Chapter management:** create, rename, reorder, archive, complete, lock, unlock, and reopen chapters.
- **Streamed AI writing:** describe what happens next and watch prose arrive, with a choice of approximate response length.
- **Draft review:** keep, rewrite, manually edit, discard, or restore an alternate draft before accepting prose.
- **Draft recovery:** recover pending work after reload and handle conflicting changes from another tab or session.
- **Accepted prose editing:** refine saved paragraphs, browse immutable revision history, and restore earlier text as a new revision.
- **Manuscript import/export:** preview text or Markdown imports, choose the chapters to append, and export accepted writing.
- **Optional planning:** save chapter objectives and ordered scenes with their goals, cast, and POV.
- **AI planning suggestions:** review and edit suggested plans before explicitly saving them.
- **Targeted AI rewriting:** rewrite one paragraph or selection, compare the result, then apply or cancel it.
- **AI memory and retrieval:** refresh chapter summaries and retrieve relevant accepted passages for later generation.
- **Provider choice:** configure OpenAI or local Ollama for prose, summaries, planning, and rewrites.

### Story bible and reusable characters

Each story has a title, premise, genre, tone, point of view, tense, setting, themes, content boundaries, audience, and writing-style notes. Character sheets hold appearance, voice, personality, motivation, flaws, and backstory. Directional relationships describe how characters relate to one another.

Import characters into a story and choose the active cast for each chapter. The Galley also lets you create and activate a character while writing. A cast change affects later generation; it does not rewrite an existing draft.

### Chapter management

Create and rename chapters, reorder them within a story, set a target word count, and archive chapters while retaining their accepted writing. Complete a chapter after resolving its pending draft. Locking protects the prose; unlocking makes it available for further work.

Story status is managed separately from chapter status. Finishing one chapter does not automatically mark the story complete.

**Story status transitions**

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> ongoing: Start story
    draft --> abandoned: Abandon
    ongoing --> on_hold: Pause
    on_hold --> ongoing: Resume
    ongoing --> completed: Finish story
    ongoing --> abandoned: Abandon
    completed --> ongoing: Reopen
    abandoned --> ongoing: Reopen
```

**Chapter status transitions**

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> in_progress: Start writing
    in_progress --> in_review: Draft ready
    in_review --> in_progress: Keep, revise, or discard
    in_review --> draft: Discard with no accepted prose
    in_progress --> draft: Return to draft
    in_progress --> complete: Complete with no pending draft
    in_review --> complete: Complete with no pending draft
    complete --> locked: Lock
    locked --> complete: Unlock
    complete --> in_progress: Edit accepted prose or continue writing
```

Archiving is separate from these status transitions. It hides a chapter from active lists while keeping its stored text.

### Paragraph-by-paragraph writing

Give the AI an instruction and choose a short, standard, or long response. Prose streams into the Galley as it is generated. Review the draft, then:

- **Keep** it to add it to the accepted manuscript.
- **Rewrite** it with another instruction.
- **Edit** it manually and explicitly save your changes.
- **Discard** it and continue experimenting.

```mermaid
flowchart TD
    Instruction["Instruction, length, and optional scene"] --> Prepare["Check access and lock state; prepare context"]
    Prepare --> Stream["Stream AI prose into the Galley"]
    Stream --> Review["Review pending draft"]
    Review --> Decision{"Writer decision"}
    Decision -->|Rewrite| Rewrite["Give another instruction; preserve an alternate"]
    Rewrite --> Prepare
    Decision -->|Manual edit| Edit["Edit text and explicitly save the draft"]
    Edit --> Review
    Decision -->|Discard| Discard["Clear the pending draft"]
    Discard --> Instruction
    Decision -->|Keep| Check{"Draft and source versions current?"}
    Check -->|No| Resolve["Reload, review, or regenerate"]
    Resolve --> Review
    Check -->|Yes| Commit["Atomically save accepted paragraph, revision, and jobs"]
    Commit --> Cleanup["Attempt Redis draft cleanup"]
    Cleanup --> Instruction
```

Explicit Keep adds draft text to the manuscript. If Redis cleanup fails after the database commit, the accepted paragraph remains saved and a retry recovers its existing result.

### Draft recovery and session conflicts

Up to three alternate drafts remain available in the chapter session. Reloading can recover the current draft and its alternatives while the Redis session exists. Sessions expire after 48 hours; accepted writing remains in PostgreSQL.

Draft acceptance uses a stable draft ID. Retrying after an interrupted response cannot add the same draft twice. If accepted text or chapter planning changes while a draft is pending, the app requires review before that draft can be accepted.

```mermaid
sequenceDiagram
    actor Writer
    participant UI as Galley
    participant API as Backend
    participant DB as PostgreSQL
    participant Session as Redis
    Writer->>UI: Open or reload chapter
    UI->>API: Load chapter and draft session
    API->>DB: Read owned chapter and accepted paragraphs
    API->>Session: Read pending draft, alternatives, and session version
    alt Session available
        API->>DB: Check draft source revisions and accepted draft IDs
        API-->>UI: Recover drafts, flag stale sources, and hide already accepted drafts
    else Session missing or expired
        API-->>UI: Accepted prose and an empty draft session
    end
    Writer->>UI: Edit a pending draft
    UI->>API: Save draft with expected session version
    API->>Session: Watch session and compare version
    alt Version matches and transaction succeeds
        API->>Session: Save new draft state and increment version
        API-->>UI: Updated draft
    else Session changed concurrently
        API-->>UI: Conflict, reload before saving again
    end
```

The manuscript and draft session load separately. A lost or expired Redis session does not remove accepted paragraphs or their revision history.

### Accepted prose editing and history

Accepted paragraphs remain editable. **Edit · History** opens the paragraph editor and its immutable revision history. You can save a manual correction or restore an earlier revision; restoring creates a new revision rather than deleting intervening history.

Version checks reject outdated edits from another tab or session. Editing a completed chapter reopens it, invalidates outdated AI memory, and schedules fresh summaries and embeddings. A locked chapter must be unlocked before its prose can change.

```mermaid
flowchart TD
    Open["Open an accepted paragraph and its history"] --> Choice{"Change type"}
    Choice -->|Edit| Edit["Write revised paragraph text"]
    Choice -->|Restore| Restore["Select an earlier revision"]
    Edit --> Submit["Submit with expected paragraph version"]
    Restore --> Submit
    Submit --> Check{"Owned, unlocked, valid, and current?"}
    Check -->|No| Conflict["Show conflict or validation error; preserve manuscript"]
    Conflict --> Reload["Load latest paragraph and review unsaved text"]
    Reload --> Choice
    Check -->|Yes| Changed{"Does the text change?"}
    Changed -->|No| Noop["Return paragraph without another revision"]
    Changed -->|Yes| Commit["Save new paragraph version, history, and memory jobs together"]
    Commit --> Reopen["Reopen a completed chapter and show latest text"]
```

Restoring an earlier version creates a new history entry. Existing revisions remain available.

### Manuscript import and export

Import UTF-8 `.txt` or `.md` files into an existing story. The import preview lets you inspect chapters, rename them, exclude chapters, and choose their order before committing. Imported chapters are appended to the story; its existing prose and bible are preserved.

Parsing rules:

- Blank lines separate paragraphs; line breaks within a paragraph remain.
- Markdown uses `## Chapter title` headings, with an optional initial `# Story title`.
- Plain text uses headings such as `Chapter 1: Arrival`, with an optional initial `Title: Story title`.
- A file without recognized chapter headings becomes one imported chapter.
- Markdown headings inside fenced code blocks are treated as content.

Default bounds are 2,000,000 bytes, 100 chapters, and 2,000 paragraphs per import. An individual paragraph can contain up to 50,000 characters. Previews expire after 30 minutes. Optional AI enrichment can schedule summaries and embeddings after the import commits; enrichment failure does not remove imported writing.

A committed import has a saved receipt. Retrying the same commit recovers its result without creating duplicate chapters. If the response is interrupted, the frontend preserves the commit options for recovery after reload.

Export the accepted manuscript as `.txt` or `.md`, in chapter order. Archived chapters are excluded by default and can be included explicitly. Pending drafts and rewrite suggestions are excluded. These exports contain manuscript text, not the full database or revision history.

```mermaid
flowchart TD
    Action{"Transfer action"}
    Action -->|Import| Upload["Upload UTF-8 text or Markdown"]
    Upload --> Parse["Validate bounds and parse chapters and paragraphs"]
    Parse --> Preview["Preview; rename, exclude, and order chapters"]
    Preview --> Request["Submit selected chapters and commit key"]
    Request --> Receipt{"Matching saved receipt exists?"}
    Receipt -->|Yes| Existing["Return the existing import result"]
    Receipt -->|No| Valid{"Preview and options valid?"}
    Valid -->|No| Correct["Correct options or upload again if expired"]
    Correct --> Preview
    Valid -->|Yes| Commit["Atomically append chapters, revisions, requested jobs, and receipt"]
    Commit --> Imported["Imported manuscript available"]
    Commit -.-> Enrich["Worker performs optional AI enrichment after commit"]
    Action -->|Export| Scope["Choose text or Markdown and archived-chapter option"]
    Scope --> Snapshot["Read accepted paragraphs in chapter order"]
    Snapshot --> Format["Format title, chapter headings, and prose"]
    Format --> Download["Download manuscript"]
```

A receipt prevents duplicate chapters when the same import is retried. Export reads accepted prose and leaves drafts and suggestions out of the downloaded manuscript.

### Optional chapter and scene planning

The **Planning** tab supports a chapter objective, conflict, ending beat, and notes. Add ordered scenes with a title, goal, conflict, outcome, setting, notes, cast, and an optional POV character. The POV character must belong to the selected scene cast.

Planning is optional: write with no plan, a chapter plan alone, or detailed scenes. In the Galley, an optional scene selector supplies that scene's context and cast for the next generation. Without a selected scene, generation uses chapter context and its active cast.

AI planning suggestions are editable proposals. They become saved plans only after the writer explicitly approves them. Planning changes do not alter accepted prose or turn intended events into established story facts.

Accepted paragraphs retain their scene association. Removing a scene archives it and preserves existing paragraph links. Planning and scene edits use version checks to prevent overwriting newer changes.

```mermaid
flowchart TD
    Use{"Use planning?"}
    Use -->|No| Chapter["Use chapter context and active cast"]
    Use -->|Yes| Method{"Planning method"}
    Method -->|Manual| Manual["Write chapter plan and scene details"]
    Method -->|AI suggestion| Suggest["Generate a validated planning proposal"]
    Suggest --> Review["Review and edit the unsaved proposal"]
    Review --> Approve{"Approve proposal?"}
    Approve -->|No| Discard["Discard suggestion; saved planning stays unchanged"]
    Discard --> Chapter
    Approve -->|Yes| Versions{"Save versions valid and chapter unlocked?"}
    Manual --> Versions
    Versions -->|No| Conflict["Load latest planning or regenerate the suggestion"]
    Conflict --> Method
    Versions -->|Yes| Saved["Save chapter plan and ordered scenes"]
    Saved --> Select{"Select a scene for generation?"}
    Select -->|No| Chapter
    Select -->|Yes| Scene["Use selected scene details, cast, and POV"]
    Chapter --> Generate["Generate from current instruction and any saved planning"]
    Scene --> Generate
```

Saved planning describes intended events. Accepted prose establishes what happened in the story. Choosing no scene still allows a saved chapter plan to guide generation.

### Targeted AI rewriting

Choose **AI rewrite** beneath an accepted paragraph. Use the whole paragraph or highlight a smaller range and choose **Use selected text**. Enter an instruction such as “make this more suspenseful while keeping the same events.”

The app displays the original selection beside the AI suggestion. **Apply suggestion** replaces only that selection and records the change in revision history. **Cancel suggestion** leaves the manuscript unchanged. Closing the dialog keeps the saved suggestion available for later review, including after reload.

Rewrite proposals use story context, relevant characters, nearby accepted prose, and optional planning. Applying rechecks the source paragraph, manuscript revision, original selection, and context fingerprint. Changed source material requires regeneration. Repeated application returns the saved receipt without another edit.

Browser selections are converted from UTF-16 offsets to Unicode code-point offsets, so selections after emoji reach the backend correctly. Suggestions expire after 30 minutes. Selections are limited to 12,000 characters, instructions to 2,000, and replacements to 16,000; the resulting paragraph must remain within 50,000 characters.

```mermaid
sequenceDiagram
    actor Writer
    participant UI as Galley
    participant API as Rewrite service
    participant DB as PostgreSQL
    participant AI as Configured model
    Writer->>UI: Select paragraph text and enter an instruction
    UI->>API: Generate with selection, source version, and proposal ID
    API->>DB: Validate source and save generating proposal
    Note over API,AI: Database transaction ends before inference
    API->>AI: Send bounded context, selection, and instruction
    AI-->>API: Return replacement text
    API->>DB: Save validated suggestion
    API-->>UI: Original selection and saved suggestion
    Note over UI,DB: Closing or reloading can recover the saved proposal
    alt Writer cancels
        UI->>API: Cancel proposal
        API->>DB: Mark proposal cancelled
        API-->>UI: Manuscript unchanged
    else Writer applies
        UI->>API: Apply proposal
        API->>DB: Lock and recheck proposal, paragraph, and context
        alt Already applied
            DB-->>API: Existing application receipt
            API-->>UI: Receipt without another edit
            UI->>API: Fetch current paragraph
            API-->>UI: Latest manuscript text
        else Source changed, expired, cancelled, or locked
            API-->>UI: Reject and explain how to reload or regenerate
        else Proposal is current and valid
            API->>DB: Commit selected replacement, revision, jobs, and receipt together
            API-->>UI: Application receipt
            UI->>API: Fetch current paragraph
            API-->>UI: Latest manuscript text
        end
    end
```

Invalid model output or provider failure marks generation failed and leaves accepted prose unchanged. Applying preserves all text outside the selected range.

### AI memory and retrieval

Accepted prose is the source of truth. Chapter summaries and paragraph embeddings are derived from specific content versions. Outdated summaries and vectors are excluded from generation context, and late AI results cannot overwrite memory for newer prose.

Memory refresh and embedding work use durable PostgreSQL jobs with retries and leases. Interrupted work can be reclaimed, while obsolete jobs are marked accordingly. The Galley shows memory refresh status and offers retry when refresh fails. Character summaries use durable jobs when summary inputs change. Updates invalidate the previous summary; jobs release the database connection during inference and save only if their source fields still match.

Semantic retrieval searches accepted paragraphs in other active chapters of the same story. It uses up to three passages with current embeddings and a cosine-distance relevance threshold. If query embedding fails, generation continues using the other available context.

```mermaid
flowchart TD
    Change["Accepted manuscript text changes"] --> Atomic["Commit new content version; invalidate old memory; enqueue jobs"]
    Refresh["Complete chapter or request memory refresh"] --> Queue["Queue job for current source version"]
    Atomic --> Queue
    Queue --> Claim["Worker claims an eligible job with a lease"]
    Interrupted["Interrupted worker lease expires"] --> Claim
    Claim --> Current{"Source version still current?"}
    Current -->|No| Obsolete["Mark job obsolete"]
    Current -->|Yes| Compute["Read source text; release DB connection; call AI provider"]
    Compute --> Success{"Provider call succeeds?"}
    Success -->|No| Budget{"Retry attempts remain?"}
    Budget -->|Yes| Delay["Back off and queue again"]
    Delay --> Queue
    Budget -->|No| Failed["Mark failed; show refresh error"]
    Failed --> Refresh
    Success -->|Yes| Compare{"Conditional write still matches source version?"}
    Compare -->|No| Obsolete
    Compare -->|Yes| Saved["Save current summary or embedding; mark job done"]
```

The worker handles chapter memory, paragraph embedding, and character summary jobs. Provider failures leave accepted writing intact. Only results matching the current source version are saved.

### Provider choice

Configure OpenAI or local Ollama for prose generation, summaries, planning suggestions, and targeted rewrites. Manual editing, planning, and manuscript transfer remain usable without AI inference. Semantic embeddings currently use OpenAI even when prose generation uses Ollama; configuration details are listed below.

## Typical workflow

1. Sign up or log in.
2. Create character sheets and a story bible.
3. Import characters into the story, then create chapters or import an existing manuscript.
4. Optionally plan a chapter and its scenes.
5. Open the Galley, choose a scene if useful, and describe what happens next.
6. Review each streamed draft and keep, rewrite, edit, or discard it.
7. Refine accepted prose using manual editing or AI rewrite proposals.
8. Mark the chapter complete and lock it when ready.
9. Export the accepted manuscript when you want a portable text copy.

Stories support draft, ongoing, on-hold, completed, and abandoned states. Chapters support draft, in-progress, in-review, complete, and locked states. Status transitions are checked by the backend; actions such as completion and locking use dedicated endpoints.

## Tech stack

### Frontend

- React and TypeScript for application components and types.
- Vite for local development and production builds.
- React Router for navigation and TanStack Query for server data.
- Tailwind CSS and Radix UI for styling and interface components.
- Motion, Anime.js, and Three.js for transitions and animation.

### Backend and data

- Python and FastAPI for HTTP APIs and streamed responses.
- Pydantic for request, settings, and structured AI-response validation.
- Asynchronous SQLAlchemy and asyncpg for database access; Alembic for migrations.
- PostgreSQL, with pgvector, for durable records and vector search; Neon is supported as a hosted database.
- Redis for temporary writing sessions and rate-limit state.
- PyJWT and bcrypt for bearer tokens and password hashing.
- OpenAI and Ollama as AI provider integrations.

## Architecture

The browser sends authenticated requests to the API. Ownership and validation checks run before domain services act on stories, chapters, drafts, and proposals. Shared manuscript services coordinate accepted-text changes, history, and memory invalidation.

PostgreSQL owns durable records: accepted paragraphs, revisions, story data, planning, import receipts, rewrite proposals, and jobs. Redis owns temporary generation drafts, alternate attempts, session versions, and inference rate-limit state. The worker claims durable jobs and writes AI-derived memory only if the source version still matches.

```mermaid
flowchart LR
    Browser["Browser application"] -->|Authenticated JSON requests| API["API: ownership and validation"]
    API --> Writing["Writing and manuscript services"]
    API --> Proposals["Planning and rewrite services"]
    API --> Transfers["Import and export services"]
    Writing -->|Durable text, revisions, and jobs| DB[("PostgreSQL")]
    Proposals -->|Plans and rewrite proposals| DB
    Transfers -->|Manuscript and import receipts| DB
    Writing -->|Pending drafts and session versions| Session[("Redis")]
    API -->|Inference rate-limit state| Session
    Writing -->|Generate prose| AI["Configured prose and summary provider"]
    Proposals -->|Generate suggestions| AI
    Writing -.->|Optional query embedding| Embeddings["OpenAI embedding service"]
    Writing -->|Streamed prose through API| Browser
    Worker["Background worker"] -->|Claim jobs and conditionally save results| DB
    Worker -->|Summarize accepted text| AI
    Worker -->|Embed accepted paragraphs| Embeddings
```

JWT bearer tokens are stored in browser `localStorage` and attached by shared API helpers. Accepted manuscript text is reconstructed from ordered paragraph rows, so there is no separate chapter-body field to keep synchronized. Stories, chapters, characters, and scenes are archived while retaining their durable records.

### Generation and performance

The generation service prepares context before streaming starts. Story, cast, relationships, prior summaries, and chapter context share one short-lived read session. Semantic retrieval runs concurrently and opens its own read session only after its query embedding is available. The request database session closes before prose streaming begins.

The system prompt contains the bible, cast, and relationships. The user prompt contains prior summaries, relevant retrieved prose, current chapter context, optional planning, and the writer's instruction.

```mermaid
flowchart LR
    Bible["Story bible"] --> System["System message"]
    Cast["Selected scene cast or active chapter cast"] --> System
    Cast --> Relationships["Relationships within that cast"]
    Relationships --> System
    Prior["Current summaries from prior chapters"] --> User["User message"]
    Retrieved["Relevant accepted passages from other chapters"] --> User
    Accepted["Current chapter context from durable accepted prose"] --> User
    Planning["Optional chapter plan and selected scene"] --> User
    Instruction["Writer instruction and requested length"] --> User
    User --> Trim["Apply context-trimming order"]
    System --> Model["Configured AI provider"]
    Trim --> Model
```

Fresh chapter memory requires only the last two accepted paragraphs. Without a usable current running summary, the fallback reads at most 32 recent paragraphs and supplies at most 24,000 characters of recent prose. Planning is treated as intended events, while accepted prose and current summaries supply established facts.

When the user prompt exceeds its approximate budget, trimming removes older prior summaries first, then retrieved passages, the running summary, and the older raw-tail paragraph. Planning, the current instruction, and the length directive are preserved. Editing a pending draft preserves its text and edit instruction.

```mermaid
flowchart TD
    Budget{"User prompt over approximate budget?"}
    Budget -->|No| Send["Send system and user messages"]
    Budget -->|Yes| Prior{"Older prior summaries remain?"}
    Prior -->|Yes| DropPrior["Remove oldest prior summary"]
    DropPrior --> Budget
    Prior -->|No| Retrieved{"Retrieved passages remain?"}
    Retrieved -->|Yes| DropRetrieved["Remove retrieved-passage block"]
    DropRetrieved --> Budget
    Retrieved -->|No| Summary{"Running summary remains?"}
    Summary -->|Yes| DropSummary["Remove running summary"]
    DropSummary --> Budget
    Summary -->|No| Tail{"More than one raw-tail paragraph?"}
    Tail -->|Yes| DropTail["Remove oldest raw-tail paragraph"]
    DropTail --> Budget
    Tail -->|No| Preserve["Keep latest prose, planning, instruction, and length directive"]
    Preserve --> Send
```

The approximate budget applies to the user message. Protected content can leave it above that target. Pending-draft editing preserves the draft and edit instruction without this trimming ladder.

The provider layer uses OpenAI chat completions or Ollama's native `/api/chat` endpoint. Non-streaming calls have bounded retries; live generation failures are surfaced through the event stream so the writer can decide what to do next. Planning and rewrite responses must pass structured validation before they become usable proposals.

The frontend loads feature pages lazily. The animated landing-page scene has its own Three.js bundle, and the production build checks that it remains isolated from the main application bundle.

### Data integrity

Every child-resource operation checks access through the writer's owned story or chapter. UUIDs identify resources; ownership checks enforce access.

Paragraph and planning edits use expected versions. Redis session writes use optimistic concurrency. Durable acceptance, revision creation, and job scheduling happen together in PostgreSQL; a later Redis failure cannot undo an accepted paragraph. Rewrite application and its receipt also commit in one transaction.

Generation, AI planning, and AI rewriting share a per-user inference rate limiter. Exhausted requests return `429` with `Retry-After`.

## Project structure

```text
app/
  auth/          Signup, login, and current-user endpoints
  users/         User persistence
  characters/    Character sheets, relationships, and summaries
  stories/       Story bible and imported cast
  chapters/      Chapter ordering, status, and active cast
  generation/    Prompt assembly, streaming, drafts, and retrieval
  manuscript/    Accepted prose editing, history, and versioned memory
  planning/      Chapter plans, scenes, and AI planning proposals
  rewriting/     Saved AI rewrite proposals and explicit application
  transfers/     Manuscript parsing, previews, import, and export
  jobs/          Durable memory and embedding jobs
  core/          Authentication, ownership, rate limits, logging, and AI client
  config.py      Environment settings
  database.py    Database engine and session setup
  main.py        Application startup, middleware, and routers

frontend/
  src/features/  Library, characters, chapters, Galley, planning, and transfers
  src/components/ Shared UI components and application shells
  src/hooks/     Streaming, keyboard, and animation hooks
  src/lib/       API helpers, authentication, types, and shared utilities
  src/styles/    Theme, layout, and manuscript styles
  scripts/       Bundle isolation and Unicode selection checks

scripts/         Database migration utilities and embedding backfills
```

Backend domains generally contain their own models, schemas, service, and router. The writing features reuse the manuscript service for accepted-text changes so history and memory invalidation stay consistent.

## Local setup

### Prerequisites

- Python 3.11 or newer.
- Node.js 24 is recommended for the frontend and its TypeScript selection tests.
- PostgreSQL with pgvector support and a database URL.
- Redis for chapter sessions and inference rate limits.
- An OpenAI API key or a running Ollama server with a model available locally.
- The project's Alembic configuration and revision files.

Database migration commands require `alembic.ini` and the `alembic/` revision directory. If either is missing, restore them before applying schema changes. Startup compares the database revision against the application’s required revision in `app/core/schema.py`; it does not load migration scripts or create or change tables automatically.

### Startup and migration checks

```mermaid
flowchart TD
    Install["Install dependencies and configure environment"] --> Files{"Migration configuration and revisions available?"}
    Files -->|No| Restore["Restore required migration files"]
    Restore --> Files
    Files -->|Yes| New{"New empty database?"}
    New -->|Yes| Initialize["Apply versioned migrations"]
    New -->|No| Review["Back up data and verify current database revision"]
    Review --> Upgrade["Apply the appropriate reviewed migrations"]
    Initialize --> Boot["Start backend"]
    Upgrade --> Boot
    Boot --> Check{"Database at expected migration head?"}
    Check -->|No| Blocked["Startup blocked; resolve migration mismatch"]
    Blocked --> Review
    Check -->|Yes| Worker["Start durable background worker and serve API"]
    Worker --> Frontend["Start frontend and connect to API"]
    Frontend --> Ready["Open the application"]
```

Startup checks the migration version before serving requests. Schema changes happen through explicit migrations, and existing data is preserved during reviewed upgrades.

### Backend

From the repository root:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your database URL, JWT secret, Redis connection, and provider settings. Keep `.env` private.

For a new empty database, once the migration files are available:

```bash
python -m alembic upgrade head
```

For an existing database, take a recoverable backup and use the migration utility appropriate to its current revision. Existing unversioned schemas require verification before any baseline stamp; do not stamp an unknown schema or reset its data to make startup pass.

Start the API after migrations finish:

```bash
python -m uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`, with interactive API documentation at `http://localhost:8000/docs`. The backend starts its durable job worker as part of application startup.

### Configuration

Required backend settings:

- `DATABASE_URL` — SQLAlchemy async PostgreSQL URL using the `postgresql+asyncpg://` scheme.
- `JWT_SECRET` — secret used to sign access tokens.

Other settings:

- `DATABASE_SSL_REQUIRE` — defaults to `true`; set to `false` for a local database configured without SSL.
- `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` — both default to `5`.
- `JWT_ALGORITHM` — defaults to `HS256`.
- `ACCESS_TOKEN_EXPIRE_MINUTES` — defaults to `60`.
- `REDIS_URL` — defaults to `redis://localhost:6379/0`.
- `LLM_PROVIDER` — `openai` or `ollama`.
- `OPENAI_API_KEY` and `OPENAI_MODEL` — OpenAI credentials and prose model; the default model is `gpt-4o-mini`.
- `OLLAMA_BASE_URL` — defaults to `http://localhost:11434`, without a `/v1` suffix.
- `OLLAMA_MODEL` — must match an installed model name. The supplied example uses `qwen3.8:27b-mlx`; choose a model available on your machine.
- `IMPORT_MAX_BYTES`, `IMPORT_MAX_CHAPTERS`, `IMPORT_MAX_PARAGRAPHS`, and `IMPORT_PREVIEW_TTL_MINUTES` — import bounds and preview lifetime.
- `ENVIRONMENT` — defaults to `dev`.
- `LOG_LEVEL` — defaults to `INFO`; `DEBUG` includes database query timing.

Settings are loaded from `.env` by `app/config.py`. The settings class defaults to OpenAI, while the supplied environment example selects Ollama.

With Neon, use the pooled endpoint for normal application connections. Use the asyncpg URL scheme and configure SSL through `DATABASE_SSL_REQUIRE` rather than copying driver-specific query parameters from another PostgreSQL client.

Ollama can provide prose, planning, rewrites, and summaries locally. Paragraph embeddings and semantic query embeddings still use OpenAI's `text-embedding-3-small` model. Without an OpenAI key, vector enrichment is unavailable; accepted text remains saved, and generation can continue without retrieved passages.

### Frontend

In a separate terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`.

The frontend uses `http://localhost:8000` as its default API URL. To change it, set `VITE_API_BASE_URL` in the frontend environment and restart Vite. Production builds need that value at build time.

Development uses port `5173` and fails if it is already occupied. Production preview uses port `4173`. These localhost origins are allowed by the backend; using another origin requires updating its CORS configuration.

## API overview

All manuscript and planning actions are scoped to an owned story and chapter. The API documentation provides request schemas and complete endpoint details.

- `/auth` — signup, login, and current user.
- `/characters` — character sheets, archival, and relationships.
- `/stories` — story bible, archival, and imported cast.
- `/stories/{story_id}/chapters` — chapter creation, ordering, metadata, cast, and lock state.
- Chapter `/generate` and `/generate/edit` — streamed generation and pending-draft revision.
- Chapter `/session`, `/session/select`, `/manual-edit`, `/accept`, and `/discard` — draft recovery and decisions.
- Chapter `/turns` — accepted paragraphs, versioned edits, revision history, and restoration.
- Chapter `/memory-status` and `/memory-refresh` — memory status and refresh requests.
- Chapter `/complete` and `/resummarize` — completion and summary refresh.
- Story `/imports/preview`, `/imports/commit`, and `/export` — manuscript transfer.
- Chapter `/plan`, `/scenes`, and `/plan-proposals/save`, plus story `/plan-suggestions` — optional planning.
- Paragraph `/rewrite-proposals` — generate/list/recover suggestions, with `/{proposal_id}/apply` and `/{proposal_id}/cancel` for explicit decisions.
- `/health` — basic API liveness response.

## Development checks

Backend regression checks (Redis concurrency checks start a disposable local Redis and require `redis-server`):

```bash
venv/bin/python -m unittest discover -s tests -v
```

The backend checks do not reset or write to the application database.

Available frontend checks:

```bash
cd frontend
npm run build
npm run lint
npm run test:rewriting
```

The build performs TypeScript checks and validates bundle isolation. The rewrite tests cover Unicode code-point offsets, emoji surrogate boundaries, combining marks, and invalid selection ranges.

Database-dependent backend tests must run against an explicitly separate disposable database. Use isolated schemas and schema-qualified cleanup; never use the application database for test resets. A full backend regression run requires the repository's test suite and development dependencies to be present.

## Logging and troubleshooting

The backend writes to stdout and `logs/app.log`, rotating at 10 MB with five backups. Request timing, operation timing, database connection diagnostics, and background-job failures help identify problems. Logs and private database snapshots should stay outside version control.

Common issues:

- **Missing migration configuration or migration-version mismatch:** restore the migration files and apply the appropriate migration before starting the API. The application deliberately refuses to start against an unexpected schema.
- **Address already in use:** identify the existing process on the API or frontend port before starting another server.
- **Failed to fetch:** check that the API is running, `VITE_API_BASE_URL` is correct, and the frontend origin is allowed by CORS.
- **Ollama generation failure:** confirm that Ollama is running and that `OLLAMA_MODEL` matches a name returned by `ollama list`.
- **Missing draft after a long break:** Redis sessions expire after 48 hours. Accepted manuscript text and revision history are stored separately in PostgreSQL.
- **Edit or proposal conflict:** load the latest paragraph or plan, review the changes, and regenerate or retry with its current version.
- **AI memory refresh failure:** check provider credentials and connectivity, then request another refresh. Accepted prose remains available while memory is stale.
- **Import rejected:** check UTF-8 encoding, supported extension, file size, chapter/paragraph counts, and long paragraphs.

## Current scope

Imports and exports support plain text and Markdown. AI rewrites operate within one accepted paragraph. Chapter planning is optional. The app supplies continuity context through stored character facts, accepted prose, summaries, and retrieval; it does not currently provide an automated contradiction-review panel or guided story-setup wizard.
