import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import Depends
from fastapi.testclient import TestClient
from jose import jwt

from backend_v2.app.config.database import get_db
from backend_v2.app.config.settings import Settings
from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.core.security import create_access_token
from backend_v2.app.dependencies.authentication import get_current_user
from backend_v2.app.main import create_app
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.services.auth_service import autenticar_usuario


DATABASE_URL = "postgresql+asyncpg://fixture:fixture_password@localhost:5432/codelab_v2"
SECRET_KEY = "fixture-only-not-for-runtime-" + "x" * 32


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            _env_file=None, database_url=DATABASE_URL, secret_key=SECRET_KEY
        )
        self.app = create_app(self.settings)

    def test_login_returns_bearer_token_without_user_or_password(self):
        user = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.ALUNO)
        with (
            patch(
                "backend_v2.app.routes.auth.autenticar_usuario",
                new_callable=AsyncMock,
                return_value=user,
            ) as authenticate,
            patch(
                "backend_v2.app.routes.auth.create_access_token",
                return_value="token-de-teste",
            ),
            TestClient(self.app) as client,
        ):
            response = client.post(
                "/api/auth/login",
                data={"username": "ALUNO@EXAMPLE.COM", "password": "SenhaTeste123!"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"accessToken": "token-de-teste", "tokenType": "bearer"},
        )
        self.assertNotIn("SenhaTeste123", response.text)
        authenticate.assert_awaited_once_with("ALUNO@EXAMPLE.COM", "SenhaTeste123!", ANY)

    def test_authentication_normalizes_email_and_checks_password_hash(self):
        from backend_v2.app.core.security import get_password_hash

        user = SimpleNamespace(
            email="aluno@example.com", senha_hash=get_password_hash("SenhaTeste123!")
        )
        db = Mock()
        db.scalar = AsyncMock(return_value=user)
        authenticated = __import__("asyncio").run(
            autenticar_usuario(" ALUNO@EXAMPLE.COM ", "SenhaTeste123!", db)
        )
        self.assertIs(authenticated, user)
        db.scalar.assert_awaited_once()

    def test_login_rejects_invalid_credentials(self):
        with (
            patch(
                "backend_v2.app.routes.auth.autenticar_usuario",
                new_callable=AsyncMock,
                side_effect=CodelabException("E-mail ou senha inválidos.", 401),
            ),
            TestClient(self.app) as client,
        ):
            response = client.post(
                "/api/auth/login", data={"username": "x@example.com", "password": "errada"}
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"erro": "E-mail ou senha inválidos."})

    def test_current_user_uses_token_subject_and_database_profile(self):
        user_id = uuid4()
        database_user = SimpleNamespace(uuid=user_id, perfil=PerfilUsuario.PROFESSOR)
        fake_db = Mock()
        fake_db.get = AsyncMock(return_value=database_user)

        async def db_override():
            yield fake_db

        self.app.dependency_overrides[get_db] = db_override

        @self.app.get("/api/_teste/autenticado")
        async def authenticated(user=Depends(get_current_user)):
            return {"perfil": user.perfil.value}

        token = create_access_token(
            {"sub": str(user_id), "perfil": "ADMIN"}, settings=self.settings
        )
        with TestClient(self.app) as client:
            response = client.get(
                "/api/_teste/autenticado", headers={"Authorization": f"Bearer {token}"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"perfil": "PROFESSOR"})
        fake_db.get.assert_awaited_once_with(unittest.mock.ANY, user_id)

    def test_invalid_or_expired_token_is_rejected(self):
        @self.app.get("/api/_teste/autenticado")
        async def authenticated(user=Depends(get_current_user)):
            return {"uuid": str(user.uuid)}

        expired = create_access_token(
            {"sub": str(uuid4())},
            expires_delta=timedelta(seconds=-1),
            settings=self.settings,
        )
        malformed_subject = jwt.encode(
            {"sub": "nao-e-uuid"},
            self.settings.secret_key.get_secret_value(),
            algorithm=self.settings.algorithm,
        )
        with TestClient(self.app) as client:
            no_token = client.get("/api/_teste/autenticado")
            expired_token = client.get(
                "/api/_teste/autenticado", headers={"Authorization": f"Bearer {expired}"}
            )
            invalid_subject = client.get(
                "/api/_teste/autenticado",
                headers={"Authorization": f"Bearer {malformed_subject}"},
            )
        for response in (no_token, expired_token, invalid_subject):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["www-authenticate"], "Bearer")
            self.assertEqual(response.json(), {"erro": "Não autenticado."})


if __name__ == "__main__":
    unittest.main()
