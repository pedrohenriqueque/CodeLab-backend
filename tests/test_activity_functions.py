import asyncio
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.schemas.funcao_atividade import (
    AssociarFuncaoAtividadeRequest,
    ReordenarFuncoesAtividadeRequest,
)
from backend_v2.app.services.activity_service import associar_funcao, reordenar_funcoes_internas


class ActivityFunctionTests(unittest.TestCase):
    def setUp(self):
        self.professor = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)
        self.activity = SimpleNamespace(uuid=uuid4(), status="RASCUNHO")
        self.source = SimpleNamespace(
            uuid=uuid4(), nome="somar", enunciado="Soma dois inteiros.", tipo_retorno="int",
            parametros=[{"nome": "a", "tipo": "int"}, {"nome": "b", "tipo": "int"}],
            dificuldade="MEDIO",
        )
        self.source_case = SimpleNamespace(
            entradas=[1, 2], retorno_esperado=3, visibilidade="OCULTO", descricao="Valores positivos"
        )

    def test_association_copies_function_and_cases_in_one_commit(self):
        db = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.rollback = AsyncMock()
        request = AssociarFuncaoAtividadeRequest(funcaoUuid=self.source.uuid, notaMaxima=Decimal("4.50"))

        with (
            patch("backend_v2.app.services.activity_service.obter_atividade", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.services.activity_service.obter_funcao", new=AsyncMock(return_value=self.source)),
            patch("backend_v2.app.services.activity_service.TestCaseRepository.list_by_function", new=AsyncMock(return_value=[self.source_case])),
            patch("backend_v2.app.services.activity_service.ActivityFunctionRepository.next_order", new=AsyncMock(return_value=1)),
        ):
            internal, cases = asyncio.run(associar_funcao(self.activity.uuid, request, self.professor, db))

        self.assertNotEqual(internal.uuid, self.source.uuid)
        self.assertEqual(internal.atividade_uuid, self.activity.uuid)
        self.assertEqual(internal.dificuldade, "MEDIO")
        self.assertEqual(internal.nota_maxima, Decimal("4.50"))
        self.assertEqual(cases[0].funcao_atividade_uuid, internal.uuid)
        self.assertNotEqual(cases[0].uuid, self.source_case.__dict__.get("uuid"))
        internal.parametros[0]["nome"] = "alterado"
        cases[0].entradas[0] = 99
        self.assertEqual(self.source.parametros[0]["nome"], "a")
        self.assertEqual(self.source_case.entradas[0], 1)
        db.commit.assert_awaited_once()
        self.assertEqual(db.add.call_count, 2)

    def test_association_is_refused_after_activity_leaves_draft(self):
        self.activity.status = "PUBLICADA"
        db = Mock()
        request = AssociarFuncaoAtividadeRequest(funcaoUuid=self.source.uuid, notaMaxima=Decimal("1"))
        with patch("backend_v2.app.services.activity_service.obter_atividade", new=AsyncMock(return_value=self.activity)):
            with self.assertRaisesRegex(CodelabException, "rascunho"):
                asyncio.run(associar_funcao(self.activity.uuid, request, self.professor, db))

    def test_reorder_requires_every_internal_function_once(self):
        first = SimpleNamespace(uuid=uuid4(), atividade_uuid=self.activity.uuid, ordem=1)
        second = SimpleNamespace(uuid=uuid4(), atividade_uuid=self.activity.uuid, ordem=2)
        db = Mock()
        request = ReordenarFuncoesAtividadeRequest(funcoesAtividadeUuid=[first.uuid])
        with (
            patch("backend_v2.app.services.activity_service.obter_atividade", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.services.activity_service.ActivityFunctionRepository.list_functions", new=AsyncMock(return_value=[first, second])),
        ):
            with self.assertRaisesRegex(CodelabException, "exatamente"):
                asyncio.run(reordenar_funcoes_internas(self.activity.uuid, request, self.professor, db))
        db.commit.assert_not_called()

    def test_reorder_updates_each_internal_function_position(self):
        first = SimpleNamespace(uuid=uuid4(), atividade_uuid=self.activity.uuid, ordem=1)
        second = SimpleNamespace(uuid=uuid4(), atividade_uuid=self.activity.uuid, ordem=2)
        db = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        request = ReordenarFuncoesAtividadeRequest(funcoesAtividadeUuid=[second.uuid, first.uuid])
        with (
            patch("backend_v2.app.services.activity_service.obter_atividade", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.services.activity_service.ActivityFunctionRepository.list_functions", new=AsyncMock(return_value=[first, second])),
        ):
            ordered = asyncio.run(reordenar_funcoes_internas(self.activity.uuid, request, self.professor, db))
        self.assertEqual([funcao.uuid for funcao in ordered], [second.uuid, first.uuid])
        self.assertEqual((second.ordem, first.ordem), (1, 2))
        db.flush.assert_awaited_once()
        db.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
