import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.schemas.caso_teste import CriarCasoTesteRequest
from backend_v2.app.services.test_case_service import criar_caso, listar_casos


class TestCaseServiceTests(unittest.TestCase):
    def setUp(self):
        self.professor = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)
        self.function = SimpleNamespace(
            uuid=uuid4(), professor_uuid=self.professor.uuid,
            parametros=[{"nome": "valores", "tipo": "int[]"}, {"nome": "ativo", "tipo": "bool"}],
            tipo_retorno="string",
        )

    def test_accepts_values_matching_vector_boolean_and_string_signature(self):
        db = Mock(); db.scalar = AsyncMock(return_value=self.function)
        db.commit = AsyncMock(); db.refresh = AsyncMock()
        case = asyncio.run(criar_caso(
            self.function.uuid,
            CriarCasoTesteRequest(entradas=[[1, 2, 3], True], retornoEsperado="três", visibilidade="OCULTO"),
            self.professor, db,
        ))
        self.assertEqual(case.visibilidade, "OCULTO")
        db.commit.assert_awaited_once()

    def test_rejects_incompatible_input_or_return(self):
        db = Mock(); db.scalar = AsyncMock(return_value=self.function)
        with self.assertRaisesRegex(CodelabException, "Entrada incompatível"):
            asyncio.run(criar_caso(
                self.function.uuid,
                CriarCasoTesteRequest(entradas=[[1, 2], "true"], retornoEsperado="dois", visibilidade="VISIVEL"),
                self.professor, db,
            ))
        with self.assertRaisesRegex(CodelabException, "Retorno esperado"):
            asyncio.run(criar_caso(
                self.function.uuid,
                CriarCasoTesteRequest(entradas=[[1, 2], True], retornoEsperado=2, visibilidade="VISIVEL"),
                self.professor, db,
            ))

    def test_non_owner_cannot_add_case_to_shared_function(self):
        self.function.professor_uuid = uuid4()
        db = Mock(); db.scalar = AsyncMock(return_value=self.function)
        with self.assertRaisesRegex(CodelabException, "proprietário") as error:
            asyncio.run(criar_caso(
                self.function.uuid,
                CriarCasoTesteRequest(entradas=[[1], True], retornoEsperado="um", visibilidade="VISIVEL"),
                self.professor, db,
            ))
        self.assertEqual(error.exception.status_code, 403)
        db.add.assert_not_called()

    def test_non_owner_can_list_cases_of_shared_function(self):
        self.function.professor_uuid = uuid4()
        self.function.compartilhada = True
        cases = [SimpleNamespace(uuid=uuid4())]
        db = Mock()
        db.scalar = AsyncMock(return_value=self.function)
        db.scalars = AsyncMock(return_value=cases)

        result = asyncio.run(listar_casos(self.function.uuid, self.professor, db))

        self.assertEqual(result, cases)


if __name__ == "__main__": unittest.main()
