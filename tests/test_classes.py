import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend_v2.app.config.database import get_db
from backend_v2.app.config.settings import Settings
from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.dependencies.authentication import get_current_user
from backend_v2.app.main import create_app
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.schemas.turma import AtualizarTurmaRequest, IngressarTurmaRequest
from backend_v2.app.services.class_service import atualizar_turma, ingressar_na_turma, listar_alunos_turma, remover_aluno_turma


DATABASE_URL = "postgresql+asyncpg://fixture:fixture_password@localhost:5432/codelab_v2"
SECRET_KEY = "fixture-only-not-for-runtime-" + "x" * 32


class ClassTests(unittest.TestCase):
    def setUp(self):
        settings = Settings(_env_file=None, database_url=DATABASE_URL, secret_key=SECRET_KEY)
        self.app = create_app(settings)
        self.professor = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.PROFESSOR)

        async def user_override():
            return self.professor

        async def db_override():
            yield Mock()

        self.app.dependency_overrides[get_current_user] = user_override
        self.app.dependency_overrides[get_db] = db_override

    def test_professor_creates_class_and_receives_join_code(self):
        turma = SimpleNamespace(
            uuid=uuid4(), nome="Algoritmos", codigo="ABCD1234", ativa=True,
            professor_uuid=self.professor.uuid,
        )
        with (
            patch("backend_v2.app.routes.classes.criar_turma", new_callable=AsyncMock, return_value=turma) as create,
            TestClient(self.app) as client,
        ):
            response = client.post("/api/turmas", json={"nome": "Algoritmos"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["codigo"], "ABCD1234")
        self.assertEqual(response.json()["professorUuid"], str(self.professor.uuid))
        create.assert_awaited_once_with(ANY, self.professor, ANY)

    def test_student_cannot_create_class(self):
        self.professor.perfil = PerfilUsuario.ALUNO
        with TestClient(self.app) as client:
            response = client.post("/api/turmas", json={"nome": "Algoritmos"})
        self.assertEqual(response.status_code, 403)

    def test_only_owner_can_update_class(self):
        turma = SimpleNamespace(
            uuid=uuid4(), nome="Algoritmos", ativa=True, professor_uuid=uuid4()
        )
        db = Mock()
        db.get = AsyncMock(return_value=turma)
        with self.assertRaisesRegex(CodelabException, "não gerencia") as error:
            asyncio.run(
                atualizar_turma(turma.uuid, AtualizarTurmaRequest(nome="Nova"), self.professor, db)
            )
        self.assertEqual(error.exception.status_code, 403)
        db.commit.assert_not_called()

    def test_inactive_class_preserves_membership_but_refuses_new_enrollment(self):
        aluno = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.ALUNO)
        turma = SimpleNamespace(uuid=uuid4(), ativa=False)
        db = Mock()
        db.scalar = AsyncMock(return_value=turma)
        with self.assertRaisesRegex(CodelabException, "inativa") as error:
            asyncio.run(ingressar_na_turma(IngressarTurmaRequest(codigo="ABCD1234"), aluno, db))
        self.assertEqual(error.exception.status_code, 409)
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_duplicate_enrollment_is_refused_before_commit(self):
        aluno = SimpleNamespace(uuid=uuid4(), perfil=PerfilUsuario.ALUNO)
        turma = SimpleNamespace(uuid=uuid4(), ativa=True)
        db = Mock()
        db.scalar = AsyncMock(side_effect=[turma, uuid4()])
        with self.assertRaisesRegex(CodelabException, "já está matriculado") as error:
            asyncio.run(ingressar_na_turma(IngressarTurmaRequest(codigo="ABCD1234"), aluno, db))
        self.assertEqual(error.exception.status_code, 409)
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_only_owner_can_list_enrolled_students(self):
        turma = SimpleNamespace(uuid=uuid4(), professor_uuid=uuid4())
        db = Mock()
        db.get = AsyncMock(return_value=turma)
        with self.assertRaisesRegex(CodelabException, "n\u00e3o gerencia") as error:
            asyncio.run(listar_alunos_turma(turma.uuid, self.professor, db))
        self.assertEqual(error.exception.status_code, 403)

    def test_owner_lists_enrolled_students(self):
        turma = SimpleNamespace(uuid=uuid4(), professor_uuid=self.professor.uuid)
        alunos = [SimpleNamespace(uuid=uuid4(), nome="Aluno", matricula="2026001")]
        db = Mock()
        db.get = AsyncMock(return_value=turma)
        with patch("backend_v2.app.services.class_service.EnrollmentRepository.list_students", new_callable=AsyncMock, return_value=alunos) as list_students:
            result = asyncio.run(listar_alunos_turma(turma.uuid, self.professor, db))
        self.assertEqual(result, alunos)
        list_students.assert_awaited_once()

    def test_owner_can_remove_enrolled_student(self):
        turma = SimpleNamespace(uuid=uuid4(), professor_uuid=self.professor.uuid)
        aluno = uuid4()
        db = Mock()
        db.commit = AsyncMock()
        db.get = AsyncMock(return_value=turma)
        with patch("backend_v2.app.services.class_service.EnrollmentRepository.remove", new_callable=AsyncMock, return_value=True) as remove:
            asyncio.run(remover_aluno_turma(turma.uuid, aluno, self.professor, db))
        remove.assert_awaited_once_with(turma.uuid, aluno)
        db.commit.assert_awaited_once()

    def test_remove_student_route_returns_no_content(self):
        turma = uuid4()
        aluno = uuid4()
        with (
            patch("backend_v2.app.routes.classes.remover_aluno_turma", new_callable=AsyncMock) as remove,
            TestClient(self.app) as client,
        ):
            response = client.delete(f"/api/turmas/{turma}/alunos/{aluno}")
        self.assertEqual(response.status_code, 204)
        remove.assert_awaited_once_with(turma, aluno, self.professor, ANY)

    def test_list_classes_returns_activity_and_student_counts(self):
        turma = SimpleNamespace(
            uuid=uuid4(),
            nome="Estruturas de Dados - 2026",
            codigo="EDA2026B",
            ativa=True,
            professor_uuid=self.professor.uuid,
            total_alunos=28,
            total_atividades=6,
            inicio_aulas="05/08/2026",
        )
        with (
            patch("backend_v2.app.routes.classes.listar_turmas", new_callable=AsyncMock, return_value=[turma]),
            TestClient(self.app) as client,
        ):
            response = client.get("/api/turmas")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["nome"], "Estruturas de Dados - 2026")
        self.assertEqual(items[0]["codigo"], "EDA2026B")
        self.assertEqual(items[0]["totalAlunos"], 28)
        self.assertEqual(items[0]["totalAtividades"], 6)
        self.assertEqual(items[0]["inicioAulas"], "05/08/2026")

    def test_create_class_success(self):
        turma = SimpleNamespace(
            uuid=uuid4(),
            nome="Algoritmos I - 2026",
            codigo="ALG2026A",
            ativa=True,
            professor_uuid=self.professor.uuid,
            total_alunos=0,
            total_atividades=0,
            inicio_aulas=None,
        )
        with (
            patch("backend_v2.app.routes.classes.criar_turma", new_callable=AsyncMock, return_value=turma) as create,
            TestClient(self.app) as client,
        ):
            response = client.post("/api/turmas", json={"nome": "Algoritmos I - 2026"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["codigo"], "ALG2026A")
        self.assertEqual(response.json()["totalAlunos"], 0)
        self.assertEqual(response.json()["totalAtividades"], 0)


if __name__ == "__main__":
    unittest.main()
