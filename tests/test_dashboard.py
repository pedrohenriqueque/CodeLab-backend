import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.schemas.dashboard import DashboardResponse
from backend_v2.app.services.dashboard_service import consultar_dashboard, projetar_dashboard


class DashboardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.student = NS(uuid=uuid4(), nome='Aluno', perfil=PerfilUsuario.ALUNO)
        self.teacher = NS(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)
        self.turma = NS(uuid=uuid4(), nome='Turma', codigo='ABC123', professor_uuid=self.teacher.uuid)
        self.activity = NS(uuid=uuid4(), titulo='Prova', tipo='PROVA', status='PUBLICADA', inicio_em=self.now-timedelta(days=1), fim_em=self.now+timedelta(days=1))
        self.functions = [NS(uuid=uuid4(), atividade_uuid=self.activity.uuid, nome='soma', nota_maxima=Decimal('5')) for _ in range(2)]
        self.attempts = [NS(uuid=uuid4(), funcao_atividade_uuid=self.functions[0].uuid, aluno_uuid=self.student.uuid, recebida_em=self.now, status='AVALIADA', nota=Decimal('5')) for _ in range(2)]

    def project(self, user):
        return DashboardResponse(**projetar_dashboard(self.turma, [self.activity], self.functions, self.attempts, [self.student], user, self.now))

    def test_open_exam_masks_results_and_counts_distinct_functions(self):
        result = self.project(self.student)
        self.assertEqual(result.funcoes_enviadas, 1)
        self.assertEqual(result.atividades_iniciadas, 1)
        self.assertIsNone(result.codigo)
        for attempt in result.recentes:
            self.assertIsNone(attempt.nota)
            self.assertIsNone(attempt.nota_maxima)
            self.assertEqual(attempt.status, 'ENVIO_REGISTRADO')

    def test_teacher_counts_started_separately_from_all_sent(self):
        result = self.project(self.teacher)
        self.assertEqual(result.atividades[0].alunos_iniciaram, 1)
        self.assertEqual(result.atividades[0].alunos_enviaram_todas, 0)
        self.attempts[1].funcao_atividade_uuid = self.functions[1].uuid
        self.assertEqual(self.project(self.teacher).atividades[0].alunos_enviaram_todas, 1)

    def test_closed_exam_releases_result_and_technical_failure_has_no_grade(self):
        self.activity.fim_em = self.now-timedelta(seconds=1)
        self.assertEqual(self.project(self.student).recentes[0].nota, Decimal('5'))
        for attempt in self.attempts:
            attempt.status = 'FALHA_TECNICA'
        self.assertTrue(all(t.nota is None for t in self.project(self.student).recentes))

    def test_compilation_error_keeps_zero_grade_for_teacher_and_after_exam(self):
        for attempt in self.attempts:
            attempt.status = 'ERRO_COMPILACAO'
            attempt.nota = Decimal('0')
        teacher_result = self.project(self.teacher)
        self.assertEqual(teacher_result.recentes[0].status, 'ERRO_COMPILACAO')
        self.assertEqual(teacher_result.recentes[0].nota, Decimal('0'))
        self.assertEqual(self.project(self.student).recentes[0].status, 'ENVIO_REGISTRADO')
        self.activity.fim_em = self.now - timedelta(seconds=1)
        self.assertEqual(self.project(self.student).recentes[0].nota, Decimal('0'))

    def test_draft_and_other_student_not_exposed(self):
        self.attempts[0].aluno_uuid = uuid4()
        self.assertEqual(len(self.project(self.student).recentes), 1)
        self.activity.status = 'RASCUNHO'
        self.assertEqual(self.project(self.student).atividades, [])
        self.assertEqual(self.project(self.student).recentes, [])

    def test_removed_students_excluded_from_participation(self):
        for attempt in self.attempts:
            attempt.aluno_uuid = uuid4()
        self.assertEqual(self.project(self.teacher).atividades[0].alunos_iniciaram, 0)

    async def test_wrong_profile_denied_before_database_access(self):
        with self.assertRaises(CodelabException) as error:
            await consultar_dashboard(self.turma.uuid, self.student, PerfilUsuario.PROFESSOR, None)
        self.assertEqual(error.exception.status_code, 403)

    async def test_foreign_teacher_and_unenrolled_student_denied(self):
        with patch('backend_v2.app.services.dashboard_service.ClassRepository') as classes, patch('backend_v2.app.services.dashboard_service.EnrollmentRepository') as enrollments:
            classes.return_value.get_by_uuid = AsyncMock(return_value=self.turma)
            enrollments.return_value.exists = AsyncMock(return_value=False)
            for user in [NS(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR), self.student]:
                with self.assertRaises(CodelabException) as error:
                    await consultar_dashboard(self.turma.uuid, user, user.perfil, None)
                self.assertEqual(error.exception.status_code, 403)
