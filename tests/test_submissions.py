import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from backend_v2.app.core.exceptions import CodelabException, NotFoundError
from backend_v2.app.integrations.judge0 import Judge0TechnicalFailure
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.schemas.tentativa import CriarTentativaRequest, TentativaHistoricoResponse
from backend_v2.app.services.submission_service import calcular_nota, consultar_tentativa, criar_tentativa, listar_tentativas, resposta_tentativa, resultado_liberado
from backend_v2.app.routes.activities import list_activity_functions


class FakeExecutor:
    async def executar_codigo(self, source_code):
        marker = source_code.split("__CODELAB_RESULT_")[1].split("__")[0]
        return {"status": {"id": 3}, "stdout": f"__CODELAB_RESULT_{marker}__1/1|1\n"}


class SubmissionServiceTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.student = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.ALUNO)
        self.function = SimpleNamespace(
            uuid=uuid4(),
            atividade_uuid=uuid4(),
            nome="identidade",
            tipo_retorno="int",
            parametros=[{"nome": "valor", "tipo": "int"}],
            nota_maxima=Decimal("10.00"),
        )
        self.activity = SimpleNamespace(
            uuid=self.function.atividade_uuid,
            turma_uuid=uuid4(),
            status="PUBLICADA",
            tipo="EXERCICIO",
            permitir_multiplas_submissoes=True,
            max_tentativas_por_funcao=None,
            inicio_em=now - timedelta(minutes=1),
            fim_em=now + timedelta(minutes=1),
        )
        self.case = SimpleNamespace(uuid=uuid4(), entradas=[7], retorno_esperado=7)
        self.request = CriarTentativaRequest(
            funcao_atividade_uuid=self.function.uuid,
            codigo_fonte="int identidade(int valor) { return valor; }",
        )
        self.db = Mock()
        self.db.commit = AsyncMock()
        self.db.refresh = AsyncMock()

    def _patch_data(self, *, enrolled=True):
        return (
            patch("backend_v2.app.services.submission_service.ActivityFunctionRepository.get_function", new=AsyncMock(return_value=self.function)),
            patch("backend_v2.app.services.submission_service.ActivityFunctionRepository.list_cases", new=AsyncMock(return_value=[self.case])),
            patch("backend_v2.app.services.submission_service.ActivityRepository.get_by_uuid", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.services.submission_service.EnrollmentRepository.exists", new=AsyncMock(return_value=enrolled)),
            patch("backend_v2.app.services.submission_service.SubmissionRepository.count_consumed_attempts", new=AsyncMock(return_value=0)),
        )

    def test_enrolled_student_creates_an_immutable_evaluated_attempt(self):
        patches = self._patch_data()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            first = asyncio.run(criar_tentativa(self.request, self.student, self.db, FakeExecutor()))
            second = asyncio.run(criar_tentativa(self.request, self.student, self.db, FakeExecutor()))

        self.assertEqual(first.status, "AVALIADA")
        self.assertEqual((first.casos_aprovados, first.total_casos), (1, 1))
        self.assertEqual(first.nota, Decimal("10.00"))
        self.assertNotEqual(first, second)
        self.assertEqual(self.db.commit.await_count, 4)

    def test_rejects_student_outside_class_before_recording_attempt(self):
        patches = self._patch_data(enrolled=False)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            with self.assertRaisesRegex(CodelabException, "matriculado"):
                asyncio.run(criar_tentativa(self.request, self.student, self.db, FakeExecutor()))
        self.db.commit.assert_not_awaited()

    def test_rejects_closed_or_expired_activity_before_recording_attempt(self):
        self.activity.fim_em = datetime.now(timezone.utc) - timedelta(seconds=1)
        patches = self._patch_data()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            with self.assertRaisesRegex(CodelabException, "aberta"):
                asyncio.run(criar_tentativa(self.request, self.student, self.db, FakeExecutor()))
        self.db.commit.assert_not_awaited()

    def test_only_students_can_submit(self):
        professor = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)
        with self.assertRaisesRegex(CodelabException, "Somente alunos"):
            asyncio.run(criar_tentativa(self.request, professor, self.db, FakeExecutor()))
        self.db.commit.assert_not_awaited()

    def test_grade_is_proportional_and_rounded_to_two_decimal_places(self):
        self.assertEqual(calcular_nota(Decimal("10"), 1, 3), Decimal("3.33"))
        self.assertEqual(calcular_nota(Decimal("10"), 2, 3), Decimal("6.67"))
        self.assertEqual(calcular_nota(Decimal("7.5"), 0, 3), Decimal("0.00"))

    def test_technical_failure_keeps_attempt_without_grade(self):
        class UnavailableExecutor:
            async def executar_codigo(self, source_code):
                raise Judge0TechnicalFailure("indisponível")

        patches = self._patch_data()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            tentativa = asyncio.run(criar_tentativa(self.request, self.student, self.db, UnavailableExecutor()))
        self.assertEqual(tentativa.status, "FALHA_TECNICA")
        self.assertIsNone(tentativa.nota)

    def test_compilation_failure_has_distinct_status_and_zero_grade(self):
        class CompilationFailureExecutor:
            async def executar_codigo(self, source_code):
                return {"status": {"id": 6}, "stdout": ""}

        patches = self._patch_data()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            tentativa = asyncio.run(criar_tentativa(self.request, self.student, self.db, CompilationFailureExecutor()))
        self.assertEqual(tentativa.status, "ERRO_COMPILACAO")
        self.assertEqual(tentativa.nota, Decimal("0.00"))
        self.assertEqual(tentativa.casos_aprovados, 0)

    def test_wrong_answer_with_zero_grade_is_not_compilation_error(self):
        class WrongAnswerExecutor:
            async def executar_codigo(self, source_code):
                marker = source_code.split("__CODELAB_RESULT_")[1].split("__")[0]
                return {"status": {"id": 3}, "stdout": f"__CODELAB_RESULT_{marker}__0/1|0\n"}

        patches = self._patch_data()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            tentativa = asyncio.run(criar_tentativa(self.request, self.student, self.db, WrongAnswerExecutor()))
        self.assertEqual(tentativa.status, "AVALIADA")
        self.assertEqual(tentativa.nota, Decimal("0.00"))

    def test_rejects_submission_when_attempt_limit_is_reached(self):
        self.activity.max_tentativas_por_funcao = 1
        patches = self._patch_data()
        with patches[0], patches[1], patches[2], patches[3], patch(
            "backend_v2.app.services.submission_service.SubmissionRepository.count_consumed_attempts",
            new=AsyncMock(return_value=1),
        ):
            with self.assertRaisesRegex(CodelabException, "limite de tentativas") as error:
                asyncio.run(criar_tentativa(self.request, self.student, self.db, FakeExecutor()))

        self.assertEqual(error.exception.status_code, 409)
        self.db.commit.assert_not_awaited()

    def test_proof_allows_only_one_consumed_submission(self):
        self.activity.tipo = "PROVA"
        patches = self._patch_data()
        with patches[0], patches[1], patches[2], patches[3], patch(
            "backend_v2.app.services.submission_service.SubmissionRepository.count_consumed_attempts",
            new=AsyncMock(return_value=1),
        ):
            with self.assertRaisesRegex(CodelabException, "limite de tentativas"):
                asyncio.run(criar_tentativa(self.request, self.student, self.db, FakeExecutor()))

        self.db.commit.assert_not_awaited()

    def test_open_proof_submission_response_hides_grade_and_case_counts(self):
        tentativa = SimpleNamespace(
            uuid=uuid4(),
            funcao_atividade_uuid=self.function.uuid,
            aluno_uuid=self.student.uuid,
            recebida_em=datetime.now(timezone.utc),
            avaliada_em=datetime.now(timezone.utc),
            status="AVALIADA",
            total_casos=3,
            casos_aprovados=2,
            nota=Decimal("6.67"),
        )
        with patch(
            "backend_v2.app.services.submission_service.SubmissionRepository.best_score",
            new=AsyncMock(return_value=Decimal("6.67")),
        ) as best_score:
            response = asyncio.run(resposta_tentativa(
                tentativa,
                self.db,
                self.function.nota_maxima,
                liberar_resultado=False,
            ))

        self.assertIsNone(response["nota"])
        self.assertIsNone(response["melhor_nota_funcao"])
        self.assertIsNone(response["casos_aprovados"])
        self.assertIsNone(response["total_casos"])
        self.assertEqual(response["status"], "ENVIO_REGISTRADO")
        best_score.assert_not_awaited()

    def test_open_proof_does_not_reveal_compilation_error(self):
        tentativa = SimpleNamespace(
            uuid=uuid4(), funcao_atividade_uuid=self.function.uuid, aluno_uuid=self.student.uuid,
            recebida_em=datetime.now(timezone.utc), avaliada_em=datetime.now(timezone.utc),
            status="ERRO_COMPILACAO", total_casos=1, casos_aprovados=0, nota=Decimal("0.00"),
        )
        response = asyncio.run(resposta_tentativa(
            tentativa, self.db, self.function.nota_maxima, liberar_resultado=False,
        ))
        self.assertEqual(response["status"], "ENVIO_REGISTRADO")
        self.assertIsNone(response["nota"])

    def test_proof_results_are_released_after_deadline(self):
        self.activity.tipo = "PROVA"
        self.activity.fim_em = datetime.now(timezone.utc) - timedelta(seconds=1)

        self.assertTrue(resultado_liberado(self.activity))
    def test_student_function_projection_does_not_expose_test_cases(self):
        snapshot = SimpleNamespace(
            uuid=self.function.uuid,
            nome="identidade",
            enunciado="Retorne o valor recebido.",
            tipo_retorno="int",
            parametros=self.function.parametros,
            dificuldade="FACIL",
            nota_maxima=10,
            ordem=1,
        )
        internal_case = SimpleNamespace(
            uuid=uuid4(),
            funcao_atividade_uuid=snapshot.uuid,
            entradas=[7],
            retorno_esperado=7,
            visibilidade="OCULTO",
            descricao="Interno",
        )
        with patch("backend_v2.app.routes.activities.listar_funcoes_internas", new=AsyncMock(return_value=([snapshot], [internal_case]))):
            response = asyncio.run(list_activity_functions(self.activity.uuid, self.student, Mock()))
        self.assertEqual(response[0].casos_teste, [])


class SubmissionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.student = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.ALUNO)
        self.teacher = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)
        self.attempt = SimpleNamespace(
            uuid=uuid4(), aluno_uuid=self.student.uuid, funcao_atividade_uuid=uuid4(),
            recebida_em=datetime.now(timezone.utc), status="AVALIADA", nota=Decimal("10"),
            casos_aprovados=1, total_casos=1, codigo_fonte="int f() { return 1; }",
        )
        self.function = SimpleNamespace(
            uuid=self.attempt.funcao_atividade_uuid, atividade_uuid=uuid4(),
            nome="f", nota_maxima=Decimal("10"),
        )
        self.activity = SimpleNamespace(
            uuid=self.function.atividade_uuid, turma_uuid=uuid4(), titulo="Atividade",
            tipo="EXERCICIO", status="PUBLICADA",
        )
        self.db = Mock()
        self.db.get = AsyncMock(return_value=SimpleNamespace(
            uuid=self.student.uuid, nome="Ana Souza", matricula="2026001",
        ))

    def _patch_history(self):
        return (
            patch("backend_v2.app.services.submission_service.SubmissionRepository.get_by_uuid", new=AsyncMock(return_value=self.attempt)),
            patch("backend_v2.app.services.submission_service.ActivityFunctionRepository.get_function", new=AsyncMock(return_value=self.function)),
            patch("backend_v2.app.services.submission_service.ActivityRepository.get_by_uuid", new=AsyncMock(return_value=self.activity)),
            patch("backend_v2.app.repositories.class_repository.ClassRepository.get_by_uuid", new=AsyncMock(return_value=SimpleNamespace(professor_uuid=self.teacher.uuid))),
            patch("backend_v2.app.services.submission_service.SubmissionRepository.list_case_results", new=AsyncMock(return_value=[])),
            patch("backend_v2.app.services.submission_service.ActivityFunctionRepository.list_cases", new=AsyncMock(return_value=[])),
        )

    def test_teacher_detail_includes_student_name_and_enrollment_number(self):
        from contextlib import ExitStack

        with ExitStack() as stack:
            for context in self._patch_history():
                stack.enter_context(context)
            result = asyncio.run(consultar_tentativa(self.attempt.uuid, self.teacher, self.db))

        self.assertEqual(result["aluno_nome"], "Ana Souza")
        self.assertEqual(result["aluno_matricula"], "2026001")
        self.assertFalse(TentativaHistoricoResponse(**result).falha_tecnica)
        self.db.get.assert_awaited_once()

    def test_student_history_does_not_include_identity_fields(self):
        from contextlib import ExitStack

        with ExitStack() as stack:
            for context in self._patch_history():
                stack.enter_context(context)
            stack.enter_context(patch(
                "backend_v2.app.services.submission_service.EnrollmentRepository.exists",
                new=AsyncMock(return_value=True),
            ))
            result = asyncio.run(consultar_tentativa(self.attempt.uuid, self.student, self.db))

        self.assertNotIn("aluno_nome", result)
        self.assertNotIn("aluno_matricula", result)
        self.assertFalse(TentativaHistoricoResponse(**result).falha_tecnica)
        self.db.get.assert_not_awaited()

    def test_student_history_masks_compilation_error_during_open_exam(self):
        from contextlib import ExitStack

        self.activity.tipo = "PROVA"
        self.activity.fim_em = datetime.now(timezone.utc) + timedelta(hours=1)
        self.attempt.status = "ERRO_COMPILACAO"
        self.attempt.nota = Decimal("0")
        with ExitStack() as stack:
            for context in self._patch_history():
                stack.enter_context(context)
            stack.enter_context(patch(
                "backend_v2.app.services.submission_service.EnrollmentRepository.exists",
                new=AsyncMock(return_value=True),
            ))
            result = asyncio.run(consultar_tentativa(self.attempt.uuid, self.student, self.db))

        self.assertEqual(result["status"], "ENVIO_REGISTRADO")
        self.assertNotIn("nota", result)

    def test_teacher_history_fetches_student_identity_once_for_list(self):
        from contextlib import ExitStack

        second = SimpleNamespace(**{**vars(self.attempt), "uuid": uuid4()})
        self.db.scalars = AsyncMock(return_value=[SimpleNamespace(
            uuid=self.student.uuid, nome="Ana Souza", matricula="2026001",
        )])
        with ExitStack() as stack:
            for context in self._patch_history():
                stack.enter_context(context)
            stack.enter_context(patch(
                "backend_v2.app.services.submission_service.SubmissionRepository.list_by_professor",
                new=AsyncMock(return_value=[self.attempt, second]),
            ))
            result = asyncio.run(listar_tentativas(self.teacher, self.db))

        self.assertEqual(len(result), 2)
        self.assertTrue(all(item["aluno_nome"] == "Ana Souza" for item in result))
        self.db.scalars.assert_awaited_once()
        self.db.get.assert_not_awaited()

    def test_other_teacher_cannot_read_student_identity(self):
        from contextlib import ExitStack

        other_teacher = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)
        with ExitStack() as stack:
            for context in self._patch_history():
                stack.enter_context(context)
            with self.assertRaises(NotFoundError):
                asyncio.run(consultar_tentativa(self.attempt.uuid, other_teacher, self.db))

        self.db.get.assert_not_awaited()
