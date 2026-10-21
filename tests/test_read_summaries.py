"""Regressões de consulta, contratos e autorização em SQLite efêmero, sem .env."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from backend_v2.app.config.database import get_db
from backend_v2.app.config.settings import Settings
from backend_v2.app.dependencies.authentication import get_current_user
from backend_v2.app.main import create_app
from backend_v2.app.models.base import Base
from backend_v2.app.models.usuario import Usuario, PerfilUsuario
from backend_v2.app.models.turma import Turma, MatriculaTurma
from backend_v2.app.models.atividade import Atividade
from backend_v2.app.models.funcao_atividade import FuncaoAtividade, CasoTesteAtividade
from backend_v2.app.models.tentativa import Tentativa, ResultadoCasoTentativa
from backend_v2.app.services.progress_service import calcular_progresso_funcao
from backend_v2.app.services.submission_service import listar_tentativas


class AsyncSessionFixture:
    """Usa o SQL real dos repositórios no SQLite síncrono disponível no Python."""
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def get(self, model, identifier):
        return self.session.get(model, identifier)


class ReadSummaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False, autoflush=False)
        self.db = AsyncSessionFixture(self.session)
        self.now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.teacher = self.user(PerfilUsuario.PROFESSOR, "Professor")
        self.other_teacher = self.user(PerfilUsuario.PROFESSOR, "Outro professor")
        self.student = self.user(PerfilUsuario.ALUNO, "Aluno")
        self.other_student = self.user(PerfilUsuario.ALUNO, "Outro aluno")
        self.turma = Turma(uuid=uuid4(), nome="Turma A", codigo="A", professor_uuid=self.teacher.uuid)
        self.other_class = Turma(uuid=uuid4(), nome="Turma B", codigo="B", professor_uuid=self.other_teacher.uuid)
        self.session.add_all([self.turma, self.other_class])
        self.session.add(MatriculaTurma(turma_uuid=self.turma.uuid, aluno_uuid=self.student.uuid))
        self.activity, self.function = self.add_activity()
        self.foreign_activity, self.foreign_function = self.add_activity(class_id=self.other_class.uuid)
        self.attempt = self.add_attempt(self.function)
        self.add_attempt(self.function, student=self.other_student)
        self.add_attempt(self.foreign_function)  # histórico fora da matrícula deve continuar inacessível
        self.visible = CasoTesteAtividade(uuid=uuid4(), funcao_atividade_uuid=self.function.uuid,
            entradas=[1], retorno_esperado=2, visibilidade="VISIVEL", descricao="Público", peso=1)
        self.hidden = CasoTesteAtividade(uuid=uuid4(), funcao_atividade_uuid=self.function.uuid,
            entradas=[99], retorno_esperado=100, visibilidade="OCULTO", descricao="Oculto", peso=3)
        self.session.add_all([self.visible, self.hidden])
        for caso in [self.visible, self.hidden]:
            self.session.add(ResultadoCasoTentativa(tentativa_uuid=self.attempt.uuid,
                caso_teste_atividade_uuid=caso.uuid, aprovado=False, retorno_obtido=0,
                status_retorno="DISPONIVEL"))
        self.session.commit()
        self.queries = []
        event.listen(self.engine, "before_cursor_execute", self.record_query)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def record_query(self, conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            self.queries.append(statement)

    def user(self, perfil, nome):
        user = Usuario(uuid=uuid4(), nome=nome, email=f"{uuid4()}@test.invalid", senha_hash="fixture",
                       matricula=str(uuid4()) if perfil == PerfilUsuario.ALUNO else None, ativo=True, perfil=perfil)
        self.session.add(user)
        return user

    def add_activity(self, *, class_id=None, tipo="EXERCICIO", status="PUBLICADA"):
        activity = Atividade(uuid=uuid4(), turma_uuid=class_id or self.turma.uuid, titulo="Atividade",
            descricao="Instruções", inicio_em=self.now, fim_em=datetime(2099, 1, 1, tzinfo=timezone.utc),
            status=status, tipo=tipo, permitir_multiplas_submissoes=True,
            max_tentativas_por_funcao=None, mostrar_ocultos_apos_fechamento=False)
        function = FuncaoAtividade(uuid=uuid4(), atividade_uuid=activity.uuid, nome="somar", enunciado="Somar",
            tipo_retorno="int", parametros=[{"nome": "a", "tipo": "int"}], dificuldade="FACIL",
            nota_maxima=Decimal("10"), ordem=1)
        self.session.add_all([activity, function])
        return activity, function

    def add_attempt(self, function, *, student=None, status="AVALIADA", nota=Decimal("0"), minute=0):
        attempt = Tentativa(uuid=uuid4(), funcao_atividade_uuid=function.uuid,
            aluno_uuid=(student or self.student).uuid, codigo_fonte="int somar(int a) { return 0; }",
            recebida_em=self.now + timedelta(minutes=minute), avaliada_em=self.now, status=status,
            total_casos=2, casos_aprovados=0, nota=nota)
        self.session.add(attempt)
        return attempt

    async def request(self, path, user=None):
        settings = Settings(_env_file=None, environment="test",
            database_url="postgresql+asyncpg://fixture:fixture@localhost/codelab_v2_test",
            secret_key="fixture-only-" + "x" * 36)
        app = create_app(settings)
        app.dependency_overrides[get_current_user] = lambda: user or self.student
        app.dependency_overrides[get_db] = lambda: self.db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path)

    async def test_list_uses_one_query_independent_of_number_of_attempts(self):
        for i in range(100):
            self.add_attempt(self.function, minute=i+1)
        self.session.commit()
        self.session.expunge_all()  # nenhuma entidade pode esconder consultas pelo identity map
        result = await listar_tentativas(self.student, self.db)
        self.assertEqual(len(result), 101)
        self.assertEqual(len(self.queries), 1)
        self.assertEqual([r["tentativa_numero"] for r in result], list(range(101, 0, -1)))
        for item in result:
            self.assertNotIn("codigo_fonte", item)
            self.assertNotIn("resultados_casos", item)
            self.assertEqual(item["nota"], Decimal("0"))
        selected = self.queries[0].split("FROM")[0]
        self.assertNotIn("codigo_fonte", selected)
        self.assertNotIn("senha_hash", selected)
        self.assertNotIn("resultados_casos_tentativa", self.queries[0])
        self.queries.clear()
        result = await listar_tentativas(self.teacher, self.db)
        self.assertEqual(len(result), 102)
        self.assertEqual(len(self.queries), 1)

    async def test_teacher_filters_are_scoped_and_keep_attempt_number_per_student(self):
        result = await listar_tentativas(self.teacher, self.db, turma_uuid=self.turma.uuid,
            atividade_uuid=self.activity.uuid, funcao_uuid=self.function.uuid, aluno_uuid=self.other_student.uuid)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["aluno_nome"], self.other_student.nome)
        self.assertEqual(result[0]["tentativa_numero"], 1)
        denied = await listar_tentativas(self.teacher, self.db, turma_uuid=self.other_class.uuid)
        self.assertEqual(denied, [])
        denied = await listar_tentativas(self.student, self.db, aluno_uuid=self.other_student.uuid)
        self.assertEqual(denied, [])

    async def test_exam_status_filters_cannot_reveal_hidden_result(self):
        activity, function = self.add_activity(tipo="PROVA")
        self.add_attempt(function, nota=Decimal("10"))
        self.session.commit()
        result = await listar_tentativas(self.student, self.db, atividade_uuid=activity.uuid, status="AVALIADA")
        self.assertEqual(result, [])
        result = await listar_tentativas(self.student, self.db, atividade_uuid=activity.uuid, status="ENVIO_REGISTRADO")
        self.assertEqual(len(result), 1)
        self.assertNotIn("nota", result[0])
        self.assertNotIn("casos_aprovados", result[0])

    async def test_activity_summary_has_bounded_queries_and_no_case_payloads(self):
        for i in range(20):
            activity, function = self.add_activity()
            self.add_attempt(function)
        self.add_activity(status="RASCUNHO")
        self.session.commit()
        self.session.expunge_all()
        response = await self.request(f"/api/atividades/resumo?turmaUuid={self.turma.uuid}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 21)
        self.assertEqual(len(self.queries), 4)
        for activity in response.json():
            self.assertEqual(len(activity["funcoes"]), 1)
            self.assertEqual(len(activity["progresso"]), 1)
            self.assertNotIn("casosTeste", activity["funcoes"][0])
            self.assertNotIn("enunciado", activity["funcoes"][0])
        self.assertFalse(any("casos_teste_atividade" in q or "codigo_fonte" in q for q in self.queries))

    async def test_teacher_summary_counts_attempts_without_loading_them(self):
        response = await self.request(f"/api/atividades/resumo?turmaUuid={self.turma.uuid}", self.teacher)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()[0]["totalSubmissoes"], 2)
        self.assertIsNone(response.json()[0]["progresso"])
        self.assertEqual(len(self.queries), 4)
        self.assertFalse(any("codigo_fonte" in q for q in self.queries))

    async def test_summary_rejects_other_class_and_student_does_not_see_drafts(self):
        response = await self.request(f"/api/atividades/resumo?turmaUuid={self.other_class.uuid}")
        self.assertEqual(response.status_code, 403)
        response = await self.request(f"/api/atividades?turmaUuid={self.other_class.uuid}", self.teacher)
        self.assertEqual(response.status_code, 403)

    async def test_list_and_detail_contracts_preserve_code_and_visible_return(self):
        response = await self.request("/api/submissoes")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 1)
        self.assertNotIn("codigoFonte", response.json()[0])
        self.assertNotIn("resultadosCasos", response.json()[0])
        response = await self.request(f"/api/submissoes/{self.attempt.uuid}")
        self.assertEqual(response.status_code, 200, response.text)
        detail = response.json()
        self.assertEqual(detail["codigoFonte"], self.attempt.codigo_fonte)
        self.assertEqual(detail["parametros"], self.function.parametros)
        self.assertEqual(len(detail["resultadosCasos"]), 1)
        self.assertEqual(detail["resultadosCasos"][0]["retornoObtido"], 0)
        response = await self.request(f"/api/submissoes/{self.attempt.uuid}", self.other_student)
        self.assertEqual(response.status_code, 404)

    async def test_empty_summary_and_invalid_filters_are_explicit(self):
        response = await self.request("/api/submissoes?funcaoUuid=invalid")
        self.assertEqual(response.status_code, 422)
        result = await listar_tentativas(self.teacher, self.db, funcao_uuid=uuid4())
        self.assertEqual(result, [])

        empty_class = Turma(uuid=uuid4(), nome="Vazia", codigo="EMPTY", professor_uuid=self.teacher.uuid)
        self.session.add(empty_class)
        self.session.commit()
        response = await self.request(f"/api/atividades/resumo?turmaUuid={empty_class.uuid}", self.teacher)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    async def test_progress_reuses_rules_for_zero_technical_failure_and_open_exam(self):
        failed = self.add_attempt(self.function, status="FALHA_TECNICA", nota=None, minute=4)
        best = self.add_attempt(self.function, nota=Decimal("8"), minute=1)
        result = calcular_progresso_funcao(self.function, [failed, best, self.attempt], self.activity)
        self.assertEqual(result["total_tentativas"], 2)
        self.assertEqual(result["melhor_nota"], Decimal("8"))
        self.assertEqual(result["melhor_tentativa_uuid"], best.uuid)
        self.activity.tipo = "PROVA"
        compilation = self.add_attempt(self.function, status="ERRO_COMPILACAO", minute=5)
        result = calcular_progresso_funcao(self.function, [compilation, failed, best, self.attempt], self.activity)
        self.assertEqual(result["total_tentativas"], 2)
        self.assertIsNone(result["melhor_nota"])
        self.assertIsNone(result["aprovada"])
        self.assertEqual(result["melhor_tentativa_uuid"], best.uuid)  # última válida, não revela a melhor nota
