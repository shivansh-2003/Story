import asyncio
import copy
import json
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from redis import Redis as SyncRedis
from redis.asyncio import Redis

from app.core import rate_limit
from app.generation import session_store


class RedisConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    """Exercise actual Lua and WATCH against a disposable, nonpersistent Redis."""

    @classmethod
    def setUpClass(cls):
        executable = shutil.which("redis-server")
        if executable is None:
            raise unittest.SkipTest("redis-server is required for concurrency tests")
        cls.directory = tempfile.TemporaryDirectory(prefix="story-redis-", dir="/tmp")
        cls.socket = str(Path(cls.directory.name) / "redis.sock")
        cls.server = subprocess.Popen(
            [executable, "--port", "0", "--unixsocket", cls.socket,
             "--save", "", "--appendonly", "no", "--dir", cls.directory.name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            try:
                with SyncRedis(unix_socket_path=cls.socket) as client:
                    if client.ping():
                        return
            except Exception:
                time.sleep(0.05)
        cls.server.terminate()
        cls.server.wait(timeout=5)
        cls.directory.cleanup()
        raise RuntimeError("Disposable Redis did not start")

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=5)
        cls.directory.cleanup()

    async def asyncSetUp(self):
        self.redis = Redis(unix_socket_path=self.socket, decode_responses=True)
        self.rate_patch = patch.object(rate_limit, "redis_client", return_value=self.redis)
        self.session_patch = patch.object(session_store, "redis_client", return_value=self.redis)
        self.rate_patch.start()
        self.session_patch.start()

    async def asyncTearDown(self):
        self.rate_patch.stop()
        self.session_patch.stop()
        await self.redis.aclose()

    async def test_concurrent_requests_cannot_consume_the_same_token(self):
        user_id = uuid.uuid4()
        seconds, micros = await self.redis.time()
        await self.redis.hset(rate_limit._bucket_key(user_id, "generate"), mapping={
            "tokens": 1, "last_refill_at": seconds + micros / 1_000_000,
        })
        results = await asyncio.gather(*[
            rate_limit.check_and_consume(user_id) for _ in range(40)
        ])
        self.assertEqual(sum(allowed for allowed, _ in results), 1)
        self.assertTrue(all(retry > 0 for allowed, retry in results if not allowed))

    async def test_burst_and_refill_and_expiry(self):
        user_id = uuid.uuid4()
        results = await asyncio.gather(*[
            rate_limit.check_and_consume(user_id) for _ in range(30)
        ])
        self.assertEqual(sum(allowed for allowed, _ in results), rate_limit.BUCKET_SIZE)
        key = rate_limit._bucket_key(user_id, "generate")
        self.assertGreater(await self.redis.ttl(key), 0)
        seconds, micros = await self.redis.time()
        await self.redis.hset(key, mapping={
            "tokens": 0, "last_refill_at": seconds + micros / 1_000_000 - 7,
        })
        self.assertTrue((await rate_limit.check_and_consume(user_id))[0])

    async def test_legacy_session_cleanup_preserves_drafts_and_version(self):
        chapter_id = uuid.uuid4()
        draft = {"content": "unsaved writing", "draft_id": str(uuid.uuid4())}
        legacy = {"pending_turn": draft, "sibling_attempts": [draft], "version": 4,
                  "raw_tail": ["old accepted prose"], "running_summary": "old summary",
                  "word_count_since_compaction": 100}
        await self.redis.set(session_store._key(chapter_id), json.dumps(legacy))
        state = await session_store.get_session(chapter_id)
        self.assertEqual(state["pending_turn"], draft)
        self.assertEqual(state["sibling_attempts"], [draft])
        self.assertEqual(state["version"], 4)
        await session_store.save_session(chapter_id, state)
        persisted = json.loads(await self.redis.get(session_store._key(chapter_id)))
        self.assertEqual(persisted["version"], 5)
        self.assertNotIn("raw_tail", persisted)
        self.assertNotIn("running_summary", persisted)
        self.assertNotIn("word_count_since_compaction", persisted)

    async def test_concurrent_draft_saves_preserve_winner(self):
        chapter_id = uuid.uuid4()
        first = await session_store.get_session(chapter_id)
        second = copy.deepcopy(first)
        first["pending_turn"] = {"content": "first"}
        second["pending_turn"] = {"content": "second"}
        results = await asyncio.gather(
            session_store.save_session(chapter_id, first),
            session_store.save_session(chapter_id, second), return_exceptions=True,
        )
        self.assertEqual(sum(isinstance(r, session_store.SessionConflict) for r in results), 1)
        saved = await session_store.get_session(chapter_id)
        self.assertEqual(saved["version"], 1)
        loser = second if results[1] is not None else first
        self.assertEqual(loser["version"], 0)
        winner = first if results[0] is None else second
        self.assertEqual(saved["pending_turn"], winner["pending_turn"])
