import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend_v2.app.config.settings import Settings
from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.main import create_app
from backend_v2.app.models.usuario import PerfilUsuario


DATABASE_URL = "postgresql+asyncpg://fixture:fixture_password@localhost:5432/codelab_v2"
SECRET_KEY = "fixture-only-not-for-runtime-" + "x" * 32

CADASTRO = {
    "nome": "Aluno Teste",
    "email": "aluno.teste@example.com",
    "matricula": "TESTE001",
    "senha": "SenhaTeste123!",
}


class CadastroAlunoTests(unittest.TestCase):
    def setUp(self):
        settings = Settings(
            _env_file=None,
            database_url=DATABASE_URL,
            secret_key=SECRET_KEY,
        )
        self.app = create_app(settings)

    def test_cadastro_retorna_201_sem_expor_senha(self):
        aluno = SimpleNamespace(
            uuid=uuid4(),
            nome=CADASTRO["nome"],
            email=CADASTRO["email"],
            matricula=CADASTRO["matricula"],
            perfil=PerfilUsuario.ALUNO,
        )

        with (
            patch(
                "backend_v2.app.routes.auth.cadastrar_aluno",
                new_callable=AsyncMock,
                return_value=aluno,
            ) as cadastrar,
            patch(
                "backend_v2.app.routes.auth.create_access_token",
                return_value="token-de-teste",
            ),
            TestClient(self.app) as client,
        ):
            response = client.post("/api/auth/cadastro", json=CADASTRO)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["usuario"]["perfil"], "ALUNO")
        self.assertEqual(response.json()["accessToken"], "token-de-teste")
        self.assertEqual(response.json()["tokenType"], "bearer")
        self.assertNotIn("senha", response.text)
        self.assertNotIn("senhaHash", response.text)
        cadastrar.assert_awaited_once()

    def test_cadastro_duplicado_retorna_409(self):
        with (
            patch(
                "backend_v2.app.routes.auth.cadastrar_aluno",
                new_callable=AsyncMock,
                side_effect=CodelabException(
                    "E-mail ou matrícula já cadastrado(a).",
                    status_code=409,
                ),
            ),
            TestClient(self.app) as client,
        ):
            response = client.post("/api/auth/cadastro", json=CADASTRO)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"erro": "E-mail ou matrícula já cadastrado(a)."},
        )

    def test_cadastro_nao_aceita_perfil_enviado(self):
        with (
            patch(
                "backend_v2.app.routes.auth.cadastrar_aluno",
                new_callable=AsyncMock,
            ) as cadastrar,
            TestClient(self.app) as client,
        ):
            response = client.post(
                "/api/auth/cadastro",
                json={**CADASTRO, "perfil": "ADMIN"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("body.perfil", response.json()["campos"])
        cadastrar.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()