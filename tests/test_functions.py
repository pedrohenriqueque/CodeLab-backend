import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend_v2.app.config.database import get_db
from backend_v2.app.config.settings import Settings
from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.dependencies.authentication import get_current_user
from backend_v2.app.main import create_app
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.routes.functions import to_response
from backend_v2.app.schemas.funcao import AtualizarFuncaoRequest, CriarFuncaoRequest
from backend_v2.app.services.function_service import atualizar_funcao, criar_funcao, obter_funcao

DATABASE_URL = "postgresql+asyncpg://fixture:fixture_password@localhost:5432/codelab_v2"
SECRET_KEY = "fixture-only-not-for-runtime-" + "x" * 32
FUNCTION = {
    "nome": "contarPares", "enunciado": "Conte os valores pares.",
    "tipoRetorno": "int",
    "parametros": [{"nome": "valores", "tipo": "int[]"}, {"nome": "ativo", "tipo": "bool"}],
    "dificuldade": "MEDIO", "compartilhada": True,
}


class FunctionTests(unittest.TestCase):
    def setUp(self):
        settings = Settings(_env_file=None, database_url=DATABASE_URL, secret_key=SECRET_KEY)
        self.app = create_app(settings)
        self.professor = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)

        async def user_override(): return self.professor
        async def db_override(): yield Mock()
        self.app.dependency_overrides[get_current_user] = user_override
        self.app.dependency_overrides[get_db] = db_override

    def test_signature_accepts_scalar_boolean_string_and_vector_parameters(self):
        request = CriarFuncaoRequest(
            **{**FUNCTION, "tipoRetorno": "string", "parametros": [
                {"nome": "texto", "tipo": "string"}, {"nome": "marcas", "tipo": "bool[]"},
            ]}
        )
        self.assertEqual(request.tipo_retorno, "string")
        self.assertEqual(request.parametros[1].tipo, "bool[]")

    def test_signature_rejects_vector_return_and_unknown_types(self):
        with self.assertRaises(ValidationError):
            CriarFuncaoRequest(**{**FUNCTION, "tipoRetorno": "int[]"})
        with self.assertRaises(ValidationError):
            CriarFuncaoRequest(**{**FUNCTION, "parametros": [{"nome": "x", "tipo": "struct Pessoa"}]})

    def test_signature_rejects_string_vector_on_create_and_update(self):
        with self.assertRaises(ValidationError):
            CriarFuncaoRequest(**{**FUNCTION, "parametros": [{"nome": "textos", "tipo": "string[]"}]})
        with self.assertRaises(ValidationError):
            AtualizarFuncaoRequest(parametros=[{"nome": "textos", "tipo": "string[]"}])

    def test_only_professor_can_create_library_function(self):
        self.professor.perfil = PerfilUsuario.ALUNO
        with TestClient(self.app) as client:
            response = client.post("/api/funcoes", json=FUNCTION)
        self.assertEqual(response.status_code, 403)

    def test_new_function_is_shared_even_when_client_sends_false(self):
        db = Mock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        request = CriarFuncaoRequest(**{**FUNCTION, "compartilhada": False})

        function = asyncio.run(criar_funcao(request, self.professor, db))

        self.assertTrue(function.compartilhada)

    def test_function_response_includes_owner_name(self):
        function = SimpleNamespace(
            uuid=uuid4(), nome="somar", enunciado="Soma dois valores.", tipo_retorno="int",
            parametros=[], dificuldade="FACIL", compartilhada=True,
            professor_uuid=self.professor.uuid, professor=SimpleNamespace(nome="Ana Souza"),
        )

        response = to_response(function, total_casos_teste=3)

        self.assertEqual(response.professor_nome, "Ana Souza")
        self.assertEqual(response.total_casos_teste, 3)

    def test_private_function_is_hidden_from_other_professor(self):
        function = SimpleNamespace(uuid=uuid4(), professor_uuid=uuid4(), compartilhada=False)
        db = Mock(); db.scalar = AsyncMock(return_value=function)
        with self.assertRaisesRegex(CodelabException, "não encontrado") as error:
            asyncio.run(obter_funcao(function.uuid, self.professor, db))
        self.assertEqual(error.exception.status_code, 404)

    def test_shared_function_cannot_be_changed_by_non_owner(self):
        function = SimpleNamespace(uuid=uuid4(), professor_uuid=uuid4(), compartilhada=True)
        db = Mock(); db.scalar = AsyncMock(return_value=function)
        with self.assertRaisesRegex(CodelabException, "proprietário") as error:
            asyncio.run(atualizar_funcao(function.uuid, __import__("backend_v2.app.schemas.funcao", fromlist=["AtualizarFuncaoRequest"]).AtualizarFuncaoRequest(nome="Outro"), self.professor, db))
        self.assertEqual(error.exception.status_code, 403)
        db.commit.assert_not_called()


if __name__ == "__main__": unittest.main()
