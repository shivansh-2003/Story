# Backend Latency Optimization — Report

Measured against the real Neon Postgres instance and Redis used by this app's dev environment, using the `@log_execution` instrumentation added in the logging pass (`app/core/logging_utils.py`) plus live request traces. All numbers below are real measurements taken during implementation and verification — none are estimates unless explicitly marked as such.

## Bottom line

**Yes, for the code paths this work touched — no, for the app's overall felt latency.** Every fix below is real and verified: 2.61x faster prompt assembly (Table 1), −18.8% on `/accept` (Table 5), ~99.5% faster cached chapter reads (Table 3), redundant round trips eliminated for good (Tables 5–6). But all of it shaves milliseconds-to-low-seconds off requests still dominated by something none of it touches: Neon's compute waking from auto-suspend, which costs 1.5–3s **per request** after any idle gap. Item 8's diagnostic confirms this is compute-level, not a connection-pool or query-design problem — `list_stories`, for example, shows no real average improvement across this whole effort (Table 8) because its cost was never query design to begin with. Everything that was ours to fix in code is fixed; the dominant remaining cost is a Neon plan/keep-alive decision, not an engineering one (see "Current status and open decision" at the end).

## Method

Two measurement approaches were used, and each table below states which one produced its numbers:

- **Controlled A/B benchmark**: same code path, same data, run back-to-back in the same process against the live Neon DB (used for Issue B and the cache).
- **Live trace comparison**: real `/generate`, `/accept`, and read-endpoint requests captured before and after a change, from the running dev server's own logs. These are *not* a controlled A/B — Neon's live network/compute latency visibly drifts by seconds between traces taken minutes apart (its serverless compute auto-suspends after ~5 min idle, so a request after any gap pays a 2–3s cold-start tax). Where this matters, it's called out.

## 1. Parallel prompt-assembly reads (`app/generation/assembler.py`)

**Problem**: `build_continue_prompt` fetched story, active characters, and prior-chapter summaries as three sequential `await`s, each paying a full Neon round trip, when none of the three depend on each other's output.

**Fix**: `asyncio.gather()` runs all three concurrently on separate DB sessions (`AsyncSession` isn't safe for concurrent use, so each branch opens its own). `relationships` is fetched afterward since it genuinely depends on the characters result — verified via the actual query before assuming it was independent.

**Table 1.** Prompt-assembly reads, sequential vs. parallel.

| | Sequential (before) | Parallel (after) | Change |
|---|---|---|---|
| Prompt-assembly reads (controlled A/B, 20 runs, real Neon) | 6358.6ms avg | 2431.9ms avg | **2.61x faster (−61.8%)** |

## 2. Overlap the status write with prompt assembly (`app/generation/service.py`)

**Problem**: `prepare_continue`/`prepare_edit` ran a lock-check-and-mark-`in_progress` guard *before* starting the prompt-assembly gather, serializing the status UPDATE's full round trip in front of independent read work.

**Fix**: the status write and the prompt-assembly gather touch unrelated data, so they now run concurrently via `asyncio.gather`. The write's duration is only "free" up to the length of the longer-running gather it's hidden inside.

**Table 2.** Status write before vs. after overlapping it with prompt assembly.

| | Before (live trace) | After (live trace) |
|---|---|---|
| Lock-check + status write | 1126.3ms, fully serial in front of the gather | Status write (855.1ms) overlaps entirely inside the 3074.2ms gather — **contributes 0ms to the total** |
| `PREPARE_PHASE` total | 3556.4ms | 3360.9ms |

Confirmed via real timestamps, not inferred: `set_chapter_status` START/DONE fell entirely within the `_fetch_*` calls' START/DONE window in the trace.

## 3. Chapter body Redis cache (`app/generation/session_store.py`, `app/chapters/service.py`)

**Problem**: `get_chapter_body` reconstructed the full chapter text from `chapter_turns` on every read (a `SELECT` + string join), even though the result only changes when a turn is accepted.

**Fix**: cached in Redis, invalidated explicitly in `accept_pending` right after the new turn commits — not a TTL-only cache.

**Table 3.** Chapter body reconstruction, cache miss vs. hit.

| | Before / cache miss | Cache hit | Change |
|---|---|---|---|
| `get_chapter_body` (live trace) | ~570–590ms | ~1–4ms | **~99.5% reduction** on every read after the first |

Full sample set across all three traces: **cache miss**, real content (n=3): 590.8ms, 570.6ms, 585.9ms → avg 582.4ms. **Cache hit** (n=13): 1.3–8.7ms → avg 2.88ms. (A 4th miss sample, 9.4ms, was the very first-ever read of an empty chapter with zero turns — trivial by construction, excluded from the average above as not representative of a real reconstruction.)

## 4. Connection pool sizing (`app/config.py`, `app/database.py`)

**Fix**: `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` made configurable (defaults 5/5), plus a >50ms connection-acquisition warning in `get_db()`.

**Table 4.** Connection pool sizing impact.

| | Impact |
|---|---|
| Per-request latency | None measured — this is capacity headroom, not a speed change |
| What it actually does | Prevents pool-exhaustion stalls under concurrent load; no single-request millisecond delta to report |

## 5. Collapse `get_owned_chapter` into one joined query (`app/core/deps.py`)

**Problem**: every chapter-scoped route (`generate`, `edit`, `accept`, `discard`, `complete`, `lock`/`unlock`, chapter detail) resolved ownership via two sequential round trips — `get_owned_story` (fetch `Story`, check ownership) then a separate `db.get(Chapter)`.

**Fix**: one `select(Chapter).join(Story).where(...)` query checking both ownership and IDs at once.

## 6. Stop re-fetching the chapter the router already fetched (`app/generation/service.py`, `app/chapters/service.py`)

**Problem**: `get_owned_chapter` already returns a validated `Chapter` object, but it was discarded — `prepare_continue`/`prepare_edit` re-fetched it again for the lock check, and `set_chapter_status` re-fetched it *again* internally. Up to **4 round trips to resolve one `Chapter` row** before any real work started.

**Fix**: the `Chapter` object is threaded through from the router into `prepare_continue`, `prepare_edit`, `accept_pending`, `discard_pending`, `complete_chapter`, `lock_chapter`, and `unlock_chapter`; `set_chapter_status` now accepts an optional pre-fetched `chapter` and only queries if one isn't given.

### Combined effect of #5 and #6 (live trace comparison)

**Table 5.** Combined effect of the join-collapse and re-fetch elimination.

| | Before | After | Change |
|---|---|---|---|
| `PREPARE_PHASE`'s redundant lock-check round trip | 277.3ms (separate `db.get(Chapter)`) | **0ms — the round trip no longer exists** | removed entirely |
| `POST /accept` endpoint total | 6409.6ms | 5206.9ms | **−1202.7ms (−18.8%)** |
| — of which: `accept_pending`'s own span | 4051.5ms | 3401.3ms | −650.2ms (redundant internal chapter re-fetch removed) |
| — of which: time outside `accept_pending` (auth + ownership, 3 round trips → 2) | 2358.1ms | 1805.6ms | −552.5ms (join collapse) |
| `GET /chapters/{id}` (cache hit), avg of 3 samples | 3246.9ms | 2479.5ms | **−767.4ms (−23.6%)** |

## 7. Collapse `list_chapters`' ownership check into its own query (`app/chapters/service.py`)

**Problem**: flagged as a candidate in this report's first draft — `list_chapters` still paid `get_owned_story` (fetch `Story`, check ownership) as a separate round trip in front of its own `select(Chapter)`, the same shape of redundancy #5 fixed for `get_owned_chapter`.

**Fix**: one `LEFT JOIN` from `Story` to `Chapter`, so a valid-but-empty story still returns exactly one row (chapter columns `NULL`) instead of collapsing to the same zero-row result a missing/forbidden story produces — the join has to preserve that distinction or a real empty chapter list would silently 404. Verified directly against six cases before trusting it: empty-but-owned story (200 + `[]`), populated + correctly ordered, archived-chapter exclusion without losing sibling chapters, nonexistent story (404), story owned by someone else (404), and a soft-archived story (404) — all six passed.

**Table 6.** `list_chapters` before vs. after the join-collapse.

| | Before (pooled appendix avg, n=14) | After (live trace, n=2) | Change |
|---|---|---|---|
| `list_chapters` | 1718.9ms | 1562.2ms, 532.1ms (avg 1047.2ms) | Directionally consistent with the fix, but **not confirmed** — 2 samples in one trace isn't enough to claim on its own, and item 8 below shows Neon's own variability is large enough to produce swings this size without any code change |

## 8. Pool-contention vs. compute cold-start diagnostic (`app/database.py`)

**Why**: every prior trace showed the same ambiguous symptom — a query costing 250ms sitting next to one costing 2.5s moments later — with two plausible causes that look identical from the outside: Neon's serverless compute waking from auto-suspend, or the connection pool getting squeezed by concurrent requests (e.g. the duplicate frontend fetches in #9). The existing >50ms connection-acquisition warning couldn't distinguish them.

**Fix**: extended that warning to also log `checked_out`/`overflow` (pool contention signal) and `idle_gap` — seconds since the last DB session was released (cold-start signal) — whenever acquisition exceeds 50ms.

**Result, from a live trace after deployment**: **zero acquisition warnings fired**, anywhere in a trace containing `list_stories` at 2350.6ms, `authenticate_user` at 2408.1ms, and `list_active_characters` at 1674.0ms. This is a conclusive negative result, not an inconclusive one:

- Every connection was checked out from the pool in under 50ms, every time — **pool contention from the duplicate frontend fetches is ruled out** as a cause of the multi-second numbers, not merely deprioritized.
- The slowness is entirely inside query execution on an already-acquired connection. This matches Neon's proxy/compute split: the client's connection to Neon's proxy is fast and warm, but the compute node executing the query can still be suspended — the wake delay shows up as query-execution time, invisible to any client-side pool instrumentation.
- **Conclusion, now diagnosed rather than assumed**: the remaining multi-second latency is Neon compute cold-start/resume. It is not fixable in application code. The only two real levers are a scheduled keep-alive query (real cost — paying to defeat scale-to-zero) or a Neon plan/tier change with faster resume or no auto-suspend. Neither has been implemented; both are cost decisions, not engineering ones.

## 9. Frontend `AbortController` cleanup (`apiFetch.ts` + the two duplicate-fetching pages) — fixed, impact corrected

**Problem** (from the investigation phase of this report): React 18 `StrictMode` double-invokes `useEffect` in dev, and the data-fetching hooks in `StoryDetailPage.tsx`/`CharactersPage.tsx` had no cancellation, so the remount fired a second real request.

**Fix implemented**: `AbortController` threaded through `apiFetch` and the three read calls (`getStory`, `listChapters`, `listCharacters`), aborted on effect cleanup.

**Impact — corrected after measurement, not as originally framed**: this report's earlier draft implied the fix would reduce duplicate backend load. A post-fix trace shows that's not reliably true: five separate `list_stories` calls still landed within 11 seconds of each other. The reason is timing, not a broken fix — `StrictMode`'s cleanup calls `abort()` *after* the first effect's `fetch()` has usually already dispatched the request (including its CORS preflight) and the backend has already started processing it. Aborting a request already in flight stops the client from acting on the stale response; it does not reliably stop the server from doing the work. **Net effect: real (fewer stale re-renders, no wasted state updates, cleaner console), but client-side only** — it should not be counted as a backend-load or latency reduction, correcting the impact claim made when this was first proposed.

## Combined `PREPARE_PHASE` total across all fixes (live trace, 3 points in time)

**Table 7.** Combined `PREPARE_PHASE` total across all fixes.

| Stage | Total |
|---|---|
| No optimizations | 3556.4ms |
| + status-write overlap only | 3360.9ms |
| + all fixes (parallel gather, overlap, join, re-fetch elimination) | 2820.3ms |

**Net: 3556.4ms → 2820.3ms, −736.1ms (−20.7%)** in this specific live-trace comparison. Caveat: these three traces were taken minutes apart against a live, non-deterministic Neon connection, so this isn't a clean controlled A/B like the Issue B benchmark — Neon's own baseline moved between samples. The individually-verified pieces (2.61x on the gather, the fully-eliminated 277ms round trip, the −18.8% on `/accept`) are the reliable numbers; this combined total is directionally solid but not lab-controlled.

## Appendix: full functional-operation latency data

Every timed operation observed across the three live traces captured during this work (baseline → guard-overlap-only → all fixes applied), pooled by operation. These are real production-code timings from a running dev server against live Neon + Redis, not a synthetic load test — sample counts are small and Neon's own baseline drifts between traces (see Method), so treat the spread (min–max) as more informative than the average alone.

### Read/list endpoints (service-layer span, `DONE` time)

**Table 8.** Read/list endpoint latency, pooled across all traces.

| Operation | n | Min | Avg | Max |
|---|---|---|---|---|
| `list_stories` | 19 | 264.3ms | 1141.1ms | 3044.0ms |
| `list_characters` | 21 | 263.0ms | 795.3ms | 2515.5ms |
| `list_chapters` | 14 | 524.7ms | 1718.9ms | 3887.3ms |
| `imported_characters` (nested in story detail) | 14 | 2.0ms | 525.0ms | 1284.9ms |
| `get_chapter_body` — cache hit | 13 | 1.3ms | 2.88ms | 8.7ms |
| `get_chapter_body` — cache miss (real content) | 3 | 570.6ms | 582.4ms | 590.8ms |

`list_chapters` runs consistently higher than `list_stories`/`list_characters` (avg 1719ms vs ~800–1140ms) because it still carries the unmerged `get_owned_story` round trip on top of its own query — the one CRUD-listing endpoint in this set that the `get_owned_chapter` join fix doesn't reach, since it authorizes via story ownership, not chapter ownership. This has since been fixed — see item 7 above for the after numbers (directionally positive, not yet statistically confirmed given the small sample).

### Auth and generation-flow operations

**Table 9.** Auth and generation-flow operation latency across the three traces.

| Operation | Trace samples (ms) | Notes |
|---|---|---|
| `authenticate_user` (login) | 2358.3, 2402.2, 2415.1 (avg 2391.9) | Consistently ~2.4s across all three traces — this is Neon compute cold-start after the idle gap that precedes every pasted trace, not a query-design issue |
| `PREPARE_PHASE` (`prepare_continue`) | 3556.4 → 3360.9 → 2820.3 | See main tables above — the −20.7% combined trend |
| `accept_pending` (service span) | 4051.5 → 4107.9 → 3401.3 | Improves only on the third trace, after the re-fetch elimination landed |
| `POST /accept` (endpoint total) | 6409.6 → 6123.7 → 5206.9 | Same pattern — flat until the join/re-fetch fix, then −18.8% |

### CRUD operations (warm baseline, single-session samples from the first trace)

These were captured on a freshly warm connection within one continuous browser session, before any cold-start gap — they're the closest thing to a "latency floor" observed for simple, single-row writes, and are included to show that Neon itself is fast when its compute is already awake:

**Table 10.** CRUD operation latency, warm-connection baseline.

| Operation | Time |
|---|---|
| `create_user` (signup) | 319.7ms, 286.7ms |
| `create_character` | 18.4ms |
| `create_story` | 11.4ms |
| `import_character` (activate existing character) | 6.0ms |
| `create_chapter` | 13.4ms |

The gap between these (single-digit-to-low-hundreds ms) and the multi-second numbers seen elsewhere in this report is entirely explained by Neon's cold-start behavior after an idle gap — not by anything these operations do differently. It's the strongest evidence in this dataset that the remaining multi-second latency is an infrastructure characteristic, not application code.

### LLM streaming (reference only — explicitly out of scope, not touched by any fix in this report)

**Table 11.** LLM streaming latency across the three traces (reference only).

| Trace | `STREAM_TTFT` | `STREAM_TOTAL` (full generate wrapper) |
|---|---|---|
| Baseline | 10992.3ms | 16332.5ms |
| Guard-overlap only | 11402.9ms | 18441.6ms |
| All fixes applied | 1151.2ms | 6550.4ms |

The dramatic drop on the third trace is Ollama/qwen3.6 variance (likely a warm model already in memory, or a shorter completion) — not attributable to any backend change in this report. Included here only so the full request timeline (`PREPARE_PHASE` + `GENERATE`) is traceable end-to-end.

## What's explicitly out of scope / unaffected

**Table 12.** Endpoints and factors explicitly out of scope or unaffected.

| Endpoint | Status | Why |
|---|---|---|
| `GET /stories` (list) | Unaffected (already minimal) | Only 2 round trips to begin with — no `get_owned_*` chain to collapse |
| `GET /stories/{id}` (detail) | Unaffected | Uses `get_owned_story` directly; the `imported_characters` query inside it is a separate concern from the join-collapse pattern and wasn't judged worth the added complexity (see item 7 for why `list_chapters` was, and story-detail wasn't) |
| `GET /stories/{id}/chapters` (list) | **Fixed** (item 7) | Previously unaffected for the same reason as story detail; now uses the same join-collapse pattern as `get_owned_chapter` |
| LLM generation (`STREAM_TTFT`/`STREAM_TOTAL`) | Not touched | Ollama/model latency, 1.1–17s observed across runs — pure LLM-side variance, unrelated to any backend code in this report |
| Neon compute cold-start | **Diagnosed, not fixed** (item 8) | Confirmed via pool instrumentation to be compute-level, not connection-pool contention — the only remaining levers are a keep-alive ping or a Neon plan/tier change, both cost decisions outside application code |

## Frontend duplicate GETs — see item 9

Superseded by item 9 above: the `AbortController` fix was implemented after all, on the judgment that dev-loop iteration speed has real value mid-optimization-sprint even though the mechanism is dev-only. Its actual measured impact turned out to be narrower than first assumed — see item 9 for the corrected claim.

## Current status and open decision

Everything code-addressable in this investigation has been implemented and verified: parallel prompt assembly, the status-write overlap, the chapter-body cache, pool sizing, the `get_owned_chapter` and `list_chapters` join-collapses, the redundant-refetch elimination, and the frontend cancellation cleanup. Item 8's diagnostic closed the one open question from earlier drafts of this report — Neon compute cold-start, not connection-pool contention, is confirmed as the dominant remaining source of multi-second latency, and it sits outside what application code can fix. The only next step is a decision, not a code change: whether to accept the current behavior, add a scheduled keep-alive query (a real, ongoing cost to defeat scale-to-zero), or move to a Neon plan/tier with faster compute resume.
