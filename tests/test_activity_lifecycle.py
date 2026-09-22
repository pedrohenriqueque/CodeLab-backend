import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.services.activity_service import (
    atividade_aceita_submissoes,
    encerrar_atividade,
    obter_atividade,
    publicar_atividade,
)


class ActivityLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.professor = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)
        now = datetime.now(timezone.utc)
        self.activity = SimpleNamespace(
            uuid=uuid4(), status="RASCUNHO", inicio_em=now - timedelta(hours=1), fim_em=now + timedelta(hours=1)
        )

    def test_publish_requires_complete_composition_with_total_ten(self):
        first = SimpleNamespace(uuid=uuid4(), nota_maxima=Decimal("4.5"))
        second = SimpleNamespace(uuid=uuid4(), nota_maxima=Decimal("5.5"))
        cases = [
            SimpleNamespace(funcao_atividade_uuid=first.uuid),
            SimpleNamespace(funcao_atividade_uuid=second.uuid),
        ]
        db = Mock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        with (
            patch("backend_v2.app.services.activity_service.obter_atividade", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.services.activity_service.ActivityFunctionRepository.list_functions", new=AsyncMock(return_value=[first, second])),
            patch("backend_v2.app.services.activity_service.ActivityFunctionRepository.list_cases", new=AsyncMock(return_value=cases)),
        ):
            published = asyncio.run(publicar_atividade(self.activity.uuid, self.professor, db))
        self.assertEqual(published.status, "PUBLICADA")
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(self.activity)

    def test_publish_rejects_function_without_case(self):
        function = SimpleNamespace(uuid=uuid4(), nota_maxima=Decimal("10"))
        db = Mock()
        with (
            patch("backend_v2.app.services.activity_service.obter_atividade", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.services.activity_service.ActivityFunctionRepository.list_functions", new=AsyncMock(return_value=[function])),
            patch("backend_v2.app.services.activity_service.ActivityFunctionRepository.list_cases", new=AsyncMock(return_value=[])),
        ):
            with self.assertRaisesRegex(CodelabException, "caso de teste"):
                asyncio.run(publicar_atividade(self.activity.uuid, self.professor, db))
        db.commit.assert_not_called()

    def test_publish_rejects_total_different_from_ten(self):
        function = SimpleNamespace(uuid=uuid4(), nota_maxima=Decimal("9"))
        db = Mock()
        with (
            patch("backend_v2.app.services.activity_service.obter_atividade", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.services.activity_service.ActivityFunctionRepository.list_functions", new=AsyncMock(return_value=[function])),
            patch("backend_v2.app.services.activity_service.ActivityFunctionRepository.list_cases", new=AsyncMock(return_value=[SimpleNamespace(funcao_atividade_uuid=function.uuid)])),
        ):
            with self.assertRaisesRegex(CodelabException, "totalizar 10"):
                asyncio.run(publicar_atividade(self.activity.uuid, self.professor, db))
        db.commit.assert_not_called()

    def test_manual_close_only_accepts_published_activity(self):
        db = Mock()
        with patch("backend_v2.app.services.activity_service.obter_atividade", new=AsyncMock(return_value=self.activity)):
            with self.assertRaisesRegex(CodelabException, "publicadas"):
                asyncio.run(encerrar_atividade(self.activity.uuid, self.professor, db))

        self.activity.status = "PUBLICADA"
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        with patch("backend_v2.app.services.activity_service.obter_atividade", new=AsyncMock(return_value=self.activity)):
            closed = asyncio.run(encerrar_atividade(self.activity.uuid, self.professor, db))
        self.assertEqual(closed.status, "ENCERRADA")
        db.commit.assert_awaited_once()

    def test_deadline_prevents_future_submissions_without_changing_status(self):
        self.activity.status = "PUBLICADA"
        self.assertTrue(atividade_aceita_submissoes(self.activity))
        self.assertFalse(atividade_aceita_submissoes(self.activity, self.activity.fim_em))
        self.assertEqual(self.activity.status, "PUBLICADA")

    def test_enrolled_student_can_read_published_activity(self):
        aluno = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.ALUNO)
        self.activity.status = "PUBLICADA"
        self.activity.turma_uuid = uuid4()
        with (
            patch("backend_v2.app.services.activity_service.ActivityRepository.get_by_uuid", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.services.activity_service.EnrollmentRepository.exists", new=AsyncMock(return_value=True)),
        ):
            activity = asyncio.run(obter_atividade(self.activity.uuid, aluno, Mock()))
        self.assertEqual(activity, self.activity)

    def test_student_cannot_read_draft_or_activity_outside_class(self):
        aluno = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.ALUNO)
        self.activity.turma_uuid = uuid4()
        with (
            patch("backend_v2.app.services.activity_service.ActivityRepository.get_by_uuid", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.services.activity_service.EnrollmentRepository.exists", new=AsyncMock(return_value=True)),
        ):
            with self.assertRaisesRegex(CodelabException, "não disponível"):
                asyncio.run(obter_atividade(self.activity.uuid, aluno, Mock()))


if __name__ == "__main__":
    unittest.main()
