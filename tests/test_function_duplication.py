import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.services.function_service import duplicar_funcao


class FunctionDuplicationTests(unittest.TestCase):
    def setUp(self):
        self.professor = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)
        self.source = SimpleNamespace(
            uuid=uuid4(), professor_uuid=uuid4(), compartilhada=True, nome="somar",
            enunciado="Some dois números.", tipo_retorno="int",
            parametros=[{"nome": "a", "tipo": "int"}, {"nome": "b", "tipo": "int"}],
            dificuldade="FACIL",
        )
        self.case = SimpleNamespace(entradas=[1, 2], retorno_esperado=3, visibilidade="OCULTO")

    def test_shared_function_and_cases_are_copied_as_private_and_independent(self):
        db = Mock()
        db.scalar = AsyncMock(return_value=self.source)
        db.scalars = AsyncMock(return_value=[self.case])
        db.flush = AsyncMock(); db.commit = AsyncMock(); db.refresh = AsyncMock()
        copied = asyncio.run(duplicar_funcao(self.source.uuid, self.professor, db))
        self.assertEqual(copied.professor_uuid, self.professor.uuid)
        self.assertFalse(copied.compartilhada)
        self.assertEqual(copied.nome, "Cópia de somar")
        self.assertIsNot(copied.parametros, self.source.parametros)
        db.add.assert_called()
        self.assertEqual(db.add.call_count, 2)
        db.commit.assert_awaited_once()

    def test_private_or_own_source_is_not_duplicated(self):
        db = Mock(); db.scalar = AsyncMock(return_value=SimpleNamespace(compartilhada=False))
        with self.assertRaises(CodelabException):
            asyncio.run(duplicar_funcao(uuid4(), self.professor, db))
        db.add.assert_not_called()

        self.source.professor_uuid = self.professor.uuid
        db.scalar = AsyncMock(return_value=self.source)
        with self.assertRaisesRegex(CodelabException, "própria"):
            asyncio.run(duplicar_funcao(self.source.uuid, self.professor, db))


if __name__ == "__main__": unittest.main()
