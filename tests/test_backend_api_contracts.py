import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

import httpx

from app.core.deps import get_current_user, rate_limited_user
from app.core.errors import DomainError
from app.database import get_db
from app.generation import router as generation_router
from app.main import app
from app.manuscript import router as manuscript_router
from app.users.models import User


class ApiContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_overrides = app.dependency_overrides.copy()
        self.closed = False
        self.db = Mock()
        self.user = User(id=uuid.uuid4())
        async def db_override():
            try:
                yield self.db
            finally:
                self.closed = True
        async def user_override():
            return self.user
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user] = user_override
        app.dependency_overrides[rate_limited_user] = user_override
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.old_overrides)

    async def test_domain_errors_keep_http_status_and_detail_contract(self):
        with patch.object(manuscript_router, "get_owned_chapter", AsyncMock(side_effect=DomainError(404, "Chapter not found"))):
            response = await self.client.get(f"/stories/{uuid.uuid4()}/chapters/{uuid.uuid4()}/turns")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Chapter not found"})
        self.assertTrue(self.closed)

    async def test_oversize_unicode_password_returns_validation_error(self):
        for endpoint in ("signup", "login"):
            response = await self.client.post(f"/auth/{endpoint}", json={
                "email": "reader@example.com", "password": "é" * 40,
            })
            self.assertEqual(response.status_code, 422)

    async def test_request_database_closes_before_streaming(self):
        async def stream(*_):
            self.assertTrue(self.closed, "Request DB must close before streaming")
            yield "new prose"
        with patch.object(generation_router, "get_owned_chapter", AsyncMock(return_value=Mock())), patch.object(generation_router.service, "prepare_continue", AsyncMock(return_value=("system", "user", {}))), patch.object(generation_router.service, "generate_continue", stream):
            response = await self.client.post(f"/stories/{uuid.uuid4()}/chapters/{uuid.uuid4()}/generate", json={"instruction": "continue"})
        self.assertEqual(response.status_code, 200)
        self.assertIn('"delta": "new prose"', response.text)
        self.assertIn('"done": true', response.text)


if __name__ == "__main__":
    unittest.main()
