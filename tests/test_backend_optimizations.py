import asyncio
import copy
import threading
import unittest
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.auth import service as auth
from app.auth.schemas import LoginRequest, SignupRequest
from app.characters import service as characters
from app.characters import summarizer
from app.characters.models import Character
from app.characters.queries import chapter_cast, scene_cast
from app.core import llm_client, security
from app.core.errors import DomainError
from app.database import _measure_checkout
from app.generation import service as generation
from app.generation.assembler import _format_characters
from app.generation.session_store import DEFAULT_STATE
from app.manuscript import memory, service as manuscript
from app.chapters.models import ChapterStatus
from app.users.models import User


def character(**fields):
    return Character(id=uuid.uuid4(), user_id=uuid.uuid4(), name="Mira",
                     is_archived=False, **fields)


def sql(statement):
    return str(statement.compile(dialect=postgresql.dialect()))


class PasswordTests(unittest.TestCase):
    def test_unicode_limit_is_in_bytes_for_both_requests(self):
        for model in (SignupRequest, LoginRequest):
            with self.subTest(model=model):
                accepted = model(email="reader@example.com", password="é" * 36)
                self.assertEqual(len(accepted.password.encode()), 72)
                with self.assertRaises(ValidationError):
                    model(email="reader@example.com", password="é" * 40)

    def test_signup_minimum_is_preserved(self):
        with self.assertRaises(ValidationError):
            SignupRequest(email="reader@example.com", password="short")
        LoginRequest(email="reader@example.com", password="short")


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_password_round_trip_at_unicode_byte_limit(self):
        hashed = await security.hash_password_async("é" * 36)
        self.assertTrue(await security.verify_password_async("é" * 36, hashed))
        self.assertFalse(await security.verify_password_async("wrong password", hashed))

    async def test_hashing_runs_off_event_loop(self):
        loop_thread = threading.get_ident()
        with patch.object(security, "hash_password", side_effect=lambda _: str(threading.get_ident())):
            hashed = await security.hash_password_async("password")
        self.assertNotEqual(int(hashed), loop_thread)

    async def test_verification_runs_off_event_loop(self):
        loop_thread = threading.get_ident()
        with patch.object(security, "verify_password", side_effect=lambda *_: threading.get_ident()):
            thread = await security.verify_password_async("password", "hash")
        self.assertNotEqual(thread, loop_thread)

    async def test_signup_releases_read_before_hashing(self):
        db = Mock(scalar=AsyncMock(return_value=None), rollback=AsyncMock(),
                  commit=AsyncMock(), refresh=AsyncMock())
        async def hashing(_):
            db.rollback.assert_awaited_once()
            return "hash"
        with patch.object(auth, "hash_password_async", side_effect=hashing):
            user = await auth.create_user(db, "reader@example.com", "password")
        self.assertEqual(user.hashed_password, "hash")
        db.commit.assert_awaited_once()

    async def test_racing_duplicate_signup_returns_conflict_result(self):
        db = Mock(scalar=AsyncMock(side_effect=[None, uuid.uuid4()]),
                  rollback=AsyncMock(), commit=AsyncMock(side_effect=IntegrityError(
                      "INSERT", {}, Exception("duplicate email")
                  )), refresh=AsyncMock())
        with patch.object(auth, "hash_password_async", AsyncMock(return_value="hash")):
            self.assertIsNone(await auth.create_user(db, "reader@example.com", "password"))
        self.assertEqual(db.rollback.await_count, 2)

    async def test_unrelated_integrity_error_is_not_hidden(self):
        error = IntegrityError("INSERT", {}, Exception("other constraint"))
        db = Mock(scalar=AsyncMock(return_value=None), rollback=AsyncMock(),
                  commit=AsyncMock(side_effect=error))
        with patch.object(auth, "hash_password_async", AsyncMock(return_value="hash")):
            with self.assertRaises(IntegrityError):
                await auth.create_user(db, "reader@example.com", "password")

    async def test_login_releases_connection_before_checking_password(self):
        user = User(id=uuid.uuid4(), email="reader@example.com", hashed_password="hash")
        db = Mock(scalar=AsyncMock(return_value=user), rollback=AsyncMock())
        async def verify(*_):
            db.expunge.assert_called_once_with(user)
            db.rollback.assert_awaited_once()
            return True
        with patch.object(auth, "verify_password_async", side_effect=verify):
            self.assertIs(await auth.authenticate_user(db, user.email, "password"), user)


class CharacterSummaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_releases_read_session_and_compares_every_source_field(self):
        c = character(backstory="old source")
        source = summarizer.summary_source(c)
        db = Mock(get=AsyncMock(return_value=c), execute=AsyncMock(return_value=Mock(rowcount=0)),
                  commit=AsyncMock())
        active = []
        @asynccontextmanager
        async def session():
            active.append(True)
            try:
                yield db
            finally:
                active.pop()
        async def infer(*_, **__):
            self.assertFalse(active, "Inference must not hold a DB session")
            return "summary"
        with patch.object(summarizer, "async_session", session), patch.object(summarizer, "call_model", side_effect=infer):
            self.assertFalse(await summarizer.summarize_character(c.id, summarizer.source_revision(source)))
        statement = db.execute.call_args.args[0]
        query = sql(statement)
        for field in source:
            self.assertIn(f"characters.{field} IS NOT DISTINCT FROM", query)
        self.assertIn("characters.is_archived IS false", query)

    async def test_obsolete_and_archived_jobs_do_not_call_provider(self):
        for archived, revision in [(False, -1), (True, 0)]:
            c = character()
            c.is_archived = archived
            db = Mock(get=AsyncMock(return_value=c))
            @asynccontextmanager
            async def session():
                yield db
            with patch.object(summarizer, "async_session", session), patch.object(summarizer, "call_model", AsyncMock()) as infer:
                self.assertFalse(await summarizer.summarize_character(c.id, revision))
                infer.assert_not_awaited()

    async def test_edit_invalidates_summary_and_saves_job_in_same_commit(self):
        c = character(backstory="old", condensed_summary="outdated")
        db = Mock(commit=AsyncMock(), refresh=AsyncMock())
        from app.characters.schemas import CharacterUpdate
        with patch.object(characters, "get_owned_character", AsyncMock(return_value=c)):
            await characters.update_character(db, Mock(), c.id, CharacterUpdate(backstory="new"))
        self.assertIsNone(c.condensed_summary)
        job = db.add.call_args.args[0]
        self.assertEqual(job.kind, "character_summary")
        self.assertEqual(job.target_id, c.id)
        self.assertEqual(job.target_revision, summarizer.source_revision(summarizer.summary_source(c)))
        db.commit.assert_awaited_once()

    async def test_unchanged_summary_fields_do_not_schedule_work(self):
        c = character(backstory="same")
        db = Mock(commit=AsyncMock(), refresh=AsyncMock())
        from app.characters.schemas import CharacterUpdate
        with patch.object(characters, "get_owned_character", AsyncMock(return_value=c)):
            await characters.update_character(db, Mock(), c.id, CharacterUpdate(backstory="same"))
        db.add.assert_not_called()

    def test_name_and_role_invalidate_and_pending_summary_has_current_facts(self):
        self.assertTrue(summarizer.should_resummarize({"name"}))
        self.assertTrue(summarizer.should_resummarize({"role"}))
        c = character(motivation="Find the missing map")
        self.assertIn(c.motivation, _format_characters([c]))


class ContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_context_retains_summary_and_order(self):
        result = Mock(all=Mock(return_value=[(5, 5, "summary", "older"), (5, 5, "summary", "newer")]))
        db = Mock(execute=AsyncMock(return_value=result))
        context = await memory.accepted_context(uuid.uuid4(), db)
        self.assertEqual(context, {"manuscript_revision": 5, "running_summary": "summary",
                                   "raw_tail": ["older", "newer"]})
        query = sql(db.execute.call_args.args[0])
        self.assertIn("LATERAL", query)
        self.assertIn("LIMIT CASE", query)
        db.execute.assert_awaited_once()

    async def test_stale_context_is_bounded_and_keeps_latest_text(self):
        result = Mock(all=Mock(return_value=[(6, None, "old summary", "a" * 20000),
                                            (6, None, "old summary", "b" * 20000)]))
        db = Mock(execute=AsyncMock(return_value=result))
        context = await memory.accepted_context(uuid.uuid4(), db)
        self.assertEqual(context["running_summary"], "")
        self.assertLessEqual(len("\n\n".join(context["raw_tail"])), memory.MAX_STALE_CONTEXT_CHARS)
        self.assertTrue(context["raw_tail"][-1].endswith("b" * 20000))

    async def test_missing_chapter_has_domain_error(self):
        db = Mock(execute=AsyncMock(return_value=Mock(all=Mock(return_value=[]))))
        with self.assertRaises(DomainError) as error:
            await memory.accepted_context(uuid.uuid4(), db)
        self.assertEqual(error.exception.status_code, 404)

    async def test_shared_cast_queries_exclude_archived_and_other_owner(self):
        for query_func, args in [(chapter_cast, [uuid.uuid4()]),
                                 (scene_cast, [uuid.uuid4(), uuid.uuid4()])]:
            db = Mock(scalars=AsyncMock(return_value=Mock(all=Mock(return_value=[]))))
            await query_func(db, *args)
            query = sql(db.scalars.call_args.args[0])
            self.assertIn("characters.is_archived IS false", query)
            self.assertIn("characters.user_id = stories.user_id", query)

    async def test_manual_draft_reuses_read_and_preserves_scene(self):
        state = copy.deepcopy(DEFAULT_STATE)
        state["pending_turn"] = {"scene_id": str(uuid.uuid4())}
        with patch.object(generation.session_store, "get_session", AsyncMock()) as read, patch.object(generation.session_store, "save_session", AsyncMock()):
            draft = await generation.apply_manual_edit(uuid.uuid4(), "revised", state=state)
            read.assert_not_awaited()
            self.assertEqual(draft["scene_id"], state["pending_turn"]["scene_id"])

    async def test_session_hides_accepted_drafts_and_flags_stale_sources(self):
        accepted_id, pending_id = str(uuid.uuid4()), str(uuid.uuid4())
        state = {"pending_turn": {"draft_id": pending_id, "base_revision": 0},
                 "sibling_attempts": [{"draft_id": accepted_id}], "version": 2}
        db = Mock(scalars=AsyncMock(return_value=Mock(all=Mock(return_value=[accepted_id]))))
        chapter = SimpleNamespace(id=uuid.uuid4(), manuscript_revision=3, planning_revision=0)
        with patch.object(generation.session_store, "get_session", AsyncMock(return_value=state)):
            recovered = await generation.read_session(db, chapter)
        self.assertEqual(recovered["sibling_attempts"], [])
        self.assertTrue(recovered["stale_draft"])


class ClientAndMetricsTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_cleanup_closes_and_resets_cached_clients(self):
        openai_client = Mock(close=AsyncMock())
        ollama_client = Mock(aclose=AsyncMock())
        llm_client._openai_client.cache_clear()
        llm_client._ollama_client.cache_clear()
        with patch.object(llm_client, "AsyncOpenAI", return_value=openai_client), patch.object(llm_client.httpx, "AsyncClient", return_value=ollama_client):
            self.assertIs(llm_client._openai_client(), llm_client._openai_client())
            self.assertIs(llm_client._ollama_client(), llm_client._ollama_client())
            await llm_client.close_model_clients()
        openai_client.close.assert_awaited_once()
        ollama_client.aclose.assert_awaited_once()
        self.assertEqual(llm_client._openai_client.cache_info().currsize, 0)
        self.assertEqual(llm_client._ollama_client.cache_info().currsize, 0)

    async def test_disconnecting_closes_provider_without_saving_partial_draft(self):
        closed = []
        async def provider(*_, **__):
            try:
                yield "partial"
                yield "complete"
            finally:
                closed.append(True)
        with patch.object(generation, "stream_model", provider), patch.object(generation.session_store, "save_session", AsyncMock()) as save:
            stream = generation.generate_continue("system", "user", {}, uuid.uuid4(), "continue", "short")
            self.assertEqual(await anext(stream), "partial")
            await stream.aclose()
            self.assertEqual(closed, [True])
            save.assert_not_awaited()

    async def test_permanent_provider_failure_is_not_retried(self):
        with patch.object(llm_client, "_call_openai", AsyncMock(side_effect=ValueError("invalid config"))) as provider, patch.object(llm_client, "get_settings", return_value=SimpleNamespace(llm_provider="openai")):
            with self.assertRaises(ValueError):
                await llm_client.call_model("input", 10)
            provider.assert_awaited_once()

    async def test_transient_provider_failure_is_retried(self):
        with patch.object(llm_client, "_call_openai", AsyncMock(side_effect=[httpx.ConnectError("temporary"), "ok"])) as provider, patch.object(llm_client, "get_settings", return_value=SimpleNamespace(llm_provider="openai")), patch.object(llm_client.asyncio, "sleep", AsyncMock()):
            self.assertEqual(await llm_client.call_model("input", 10), "ok")
            self.assertEqual(provider.await_count, 2)

    async def test_shared_embedding_client(self):
        client = Mock(embeddings=Mock(create=AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(embedding=[1.0])]))))
        with patch.object(llm_client, "_openai_client", return_value=client) as factory:
            self.assertEqual(await llm_client.embed_text("text"), [1.0])
            factory.assert_called_once()

    async def test_checkout_is_measured_before_first_read(self):
        session = Mock(in_transaction=Mock(return_value=False), connection=AsyncMock())
        async def query(db):
            db.connection.assert_awaited_once()
            return "result"
        self.assertEqual(await _measure_checkout(query)(session), "result")
        session.in_transaction.return_value = True
        session.connection.reset_mock()
        async def existing_query(db):
            db.connection.assert_not_awaited()
        await _measure_checkout(existing_query)(session)


class ManuscriptTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_staged_edit_records_history_without_committing(self):
        chapter = SimpleNamespace(id=uuid.uuid4(), status=ChapterStatus.complete,
                                  manuscript_revision=3, memory_revision=3,
                                  chapter_summary="summary", running_summary_cache="running")
        turn = SimpleNamespace(id=uuid.uuid4(), version=2, content="original",
                               source="ai", embedding=[1.0], embedding_version=2)
        db = Mock(scalar=AsyncMock(return_value=uuid.uuid4()), flush=AsyncMock(), commit=AsyncMock())
        with patch.object(manuscript, "lock_chapter", AsyncMock(return_value=chapter)), patch.object(manuscript, "get_turn", AsyncMock(return_value=turn)):
            result = await manuscript.stage_turn_edit(db, chapter, turn.id, "revised", 2, uuid.uuid4())
        self.assertIs(result, turn)
        self.assertEqual(turn.version, 3)
        self.assertEqual(chapter.manuscript_revision, 4)
        self.assertEqual(chapter.status, ChapterStatus.in_progress)
        self.assertIsNone(chapter.memory_revision)
        self.assertIsNone(turn.embedding)
        self.assertEqual(db.add.call_count, 3)  # Revision and unchanged memory/embedding jobs.
        db.flush.assert_awaited_once()
        db.commit.assert_not_awaited()


    async def test_stale_edit_rejects_before_mutation_or_jobs(self):
        chapter = SimpleNamespace(id=uuid.uuid4())
        turn = SimpleNamespace(version=3, content="current")
        db = Mock(commit=AsyncMock())
        with patch.object(manuscript, "lock_chapter", AsyncMock(return_value=chapter)), patch.object(manuscript, "get_turn", AsyncMock(return_value=turn)):
            with self.assertRaises(DomainError) as error:
                await manuscript.stage_turn_edit(db, chapter, uuid.uuid4(), "revised", 2, uuid.uuid4())
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(turn.content, "current")
        db.add.assert_not_called()
        db.commit.assert_not_awaited()


class PlanningAndWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_combined_proposal_never_commits_partial_plan(self):
        from app.planning import service
        chapter = SimpleNamespace(planning_revision=1, manuscript_revision=2)
        body = SimpleNamespace(expected_planning_revision=1, expected_manuscript_revision=2,
                               expected_plan_version=1, plan=Mock(model_dump=Mock(return_value={})),
                               scenes=[Mock()])
        db = Mock(commit=AsyncMock())
        with patch.object(service, "lock_chapter", AsyncMock(return_value=chapter)), patch.object(service, "stage_plan", AsyncMock()) as plan, patch.object(service, "stage_scene", AsyncMock(side_effect=DomainError(422, "invalid scene"))):
            with self.assertRaises(DomainError):
                await service.save_proposal(db, chapter, body)
            plan.assert_awaited_once()
            db.commit.assert_not_awaited()

    async def test_worker_dispatches_durable_character_jobs_and_marks_obsolete(self):
        from app.jobs import worker
        job = SimpleNamespace(id=uuid.uuid4(), kind="character_summary", attempts=0,
                              target_id=uuid.uuid4(), target_revision=123, status="queued")
        db = Mock(scalar=AsyncMock(return_value=job), commit=AsyncMock(), execute=AsyncMock())
        @asynccontextmanager
        async def session():
            yield db
        with patch.object(worker, "async_session", session), patch.object(worker, "summarize_character", AsyncMock(return_value=False)) as infer:
            self.assertTrue(await worker.run_one())
            infer.assert_awaited_once_with(job.target_id, job.target_revision)
        self.assertEqual(db.commit.await_count, 2)
        self.assertEqual(db.execute.call_args.args[0].compile().params["status"], "obsolete")



if __name__ == "__main__":
    unittest.main()
