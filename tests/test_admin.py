import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend_v2 import create_first_admin
from backend_v2.app.config.database import get_db
from backend_v2.app.config.settings import Settings
from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.dependencies.authentication import get_current_user
from backend_v2.app.main import create_app
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.schemas.usuario import CriarProfessorRequest
from backend_v2.app.services.admin_service import criar_professor


DATABASE_URL = "postgresql+asyncpg://fixture:fixture_password@localhost:5432/codelab_v2"
SECRET_KEY = "fixture-only-not-for-runtime-" + "x" * 32
PROFESSOR = {
    "nome": "Professora Teste",
    "email": "professora@example.com",
    "senha": "SenhaTeste123!",
}


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            _env_file=None, database_url=DATABASE_URL, secret_key=SECRET_KEY
        )
        self.app = create_app(self.settings)
        self.admin = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.ADMIN)

        async def current_user_override():
            return self.admin

        async def db_override():
            yield Mock()

        self.app.dependency_overrides[get_current_user] = current_user_override
        self.app.dependency_overrides[get_db] = db_override

    def test_admin_creates_professor_without_exposing_password(self):
        professor = SimpleNamespace(
            uuid=uuid4(),
            nome=PROFESSOR["nome"],
            email=PROFESSOR["email"],
            matricula=None,
            perfil=PerfilUsuario.PROFESSOR,
            ativo=True,
            senha_hash="hash-privado",
        )
        with (
            patch(
                "backend_v2.app.routes.admin.criar_professor",
                new_callable=AsyncMock,
                return_value=professor,
            ) as create,
            TestClient(self.app) as client,
        ):
            response = client.post("/api/admin/professores", json=PROFESSOR)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["perfil"], "PROFESSOR")
        self.assertIsNone(response.json()["matricula"])
        self.assertNotIn("senha", response.text.lower())
        self.assertNotIn("hash-privado", response.text)
        create.assert_awaited_once_with(ANY, self.admin, ANY)

    def test_request_cannot_select_profile(self):
        with TestClient(self.app) as client:
            response = client.post(
                "/api/admin/professores", json={**PROFESSOR, "perfil": "ADMIN"}
            )
        self.assertEqual(response.status_code, 422)
        self.assertIn("body.perfil", response.json()["campos"])

    def test_service_refuses_non_admin_even_if_route_dependency_is_misused(self):
        professor = SimpleNamespace(perfil=PerfilUsuario.PROFESSOR)
        with self.assertRaisesRegex(CodelabException, "restrito") as error:
            __import__("asyncio").run(
                criar_professor(
                    CriarProfessorRequest(**PROFESSOR), professor, Mock()
                )
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_first_admin_confirmation_is_specific_to_environment_and_email(self):
        args = create_first_admin.parse_args(
            [
                "--nome", "Admin", "--email", "ADMIN@EXAMPLE.COM", "--matricula", "A1",
                "--environment", "development",
                "--confirm", "CREATE-FIRST-ADMIN:development:admin@example.com",
            ]
        )
        create_first_admin.validate_approval(self.settings, args)
        args.confirm = "CREATE-FIRST-ADMIN:development:other@example.com"
        with self.assertRaises(ValueError):
            create_first_admin.validate_approval(self.settings, args)

    def test_first_admin_script_stops_before_password_or_database_on_bad_confirmation(self):
        with (
            patch.object(create_first_admin, "get_settings", return_value=self.settings),
            patch.object(create_first_admin.getpass, "getpass") as get_password,
            patch.object(create_first_admin, "create_first_admin") as create,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = create_first_admin.main(
                [
                    "--nome", "Admin", "--email", "admin@example.com", "--matricula", "A1",
                    "--environment", "development", "--confirm", "errado",
                ]
            )
        self.assertEqual(result, 1)
        get_password.assert_not_called()
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
