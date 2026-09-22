"""Regressões do seed sem abrir conexão com o banco."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from backend_v2.seed_demo import (
    ATTEMPT_CASES,
    ATTEMPT_CODES,
    create_demo_activity,
    ensure_demo_attempts,
    get_or_create_class,
    get_or_create_user,
    seed,
    validate_seed_target,
)
from backend_v2.app.models.usuario import PerfilUsuario, Usuario


class SeedTargetTests(unittest.TestCase):
    def test_requires_matching_development_environment_and_confirmation(self):
        settings = SimpleNamespace(environment="development")
        validate_seed_target(settings, "development", "SEED:development:codelab_v2")
        validate_seed_target(SimpleNamespace(environment="production"), "production", "SEED:production:codelab_v2")
        for configured, requested, confirmation in (
            ("production", "development", "SEED:development:codelab_v2"),
            ("test", "development", "SEED:development:codelab_v2"),
            ("development", "production", "SEED:development:codelab_v2"),
            ("development", "development", "wrong"),
            ("production", "production", "SEED:development:codelab_v2"),
        ):
            with self.subTest(configured=configured, requested=requested, confirmation=confirmation):
                with self.assertRaises(ValueError):
                    validate_seed_target(SimpleNamespace(environment=configured), requested, confirmation)

    def test_demo_codes_have_a_partial_and_complete_version_for_each_fixture(self):
        self.assertEqual(set(ATTEMPT_CODES), set(ATTEMPT_CASES))
        for name, (partial, complete) in ATTEMPT_CODES.items():
            with self.subTest(name=name):
                self.assertIn(f"{name}(", partial)
                self.assertIn(f"{name}(", complete)
                self.assertNotEqual(partial, complete)


class SeedDataTests(unittest.IsolatedAsyncioTestCase):
    async def test_test_environment_is_rejected_before_creating_an_engine(self):
        with patch("backend_v2.seed_demo.make_engine") as make_engine:
            with self.assertRaises(ValueError):
                await seed(SimpleNamespace(environment="test"))
        make_engine.assert_not_called()

    async def test_existing_user_conflict_is_rejected_without_write(self):
        session = Mock()
        session.scalars = AsyncMock(return_value=[Usuario(
            uuid=uuid4(), nome="Outra pessoa", email="outra@example.com",
            matricula="ALU001", perfil=PerfilUsuario.ALUNO, senha_hash="hash",
        )])
        with self.assertRaisesRegex(ValueError, "conflito"):
            await get_or_create_user(session, "Pedro", "pedro@example.com", "ALU001", PerfilUsuario.ALUNO)
        session.add.assert_not_called()

    async def test_existing_user_keeps_credentials(self):
        user = Usuario(uuid=uuid4(), nome="Nome alterado", email="pedro@example.com",
                       matricula="ALU001", perfil=PerfilUsuario.ALUNO, senha_hash="existing-hash")
        session = Mock()
        session.scalars = AsyncMock(return_value=[user])
        result = await get_or_create_user(session, "Pedro", user.email, user.matricula, user.perfil)
        self.assertIs(result, user)
        self.assertEqual(user.senha_hash, "existing-hash")
        self.assertEqual(user.nome, "Nome alterado")
        session.add.assert_not_called()

    async def test_existing_class_cannot_be_claimed_by_another_teacher(self):
        owner = SimpleNamespace(uuid=uuid4())
        existing = SimpleNamespace(uuid=uuid4(), professor_uuid=uuid4(), nome="Algoritmos")
        session = Mock()
        session.scalar = AsyncMock(return_value=existing)
        with self.assertRaisesRegex(ValueError, "conflito"):
            await get_or_create_class(session, owner, "Algoritmos", "ALG2026A")
        session.add.assert_not_called()

    async def test_existing_activity_type_is_preserved(self):
        existing = SimpleNamespace(tipo="PROVA", status="ENCERRADA")
        session = Mock()
        session.scalar = AsyncMock(return_value=existing)
        turma = SimpleNamespace(uuid=uuid4())
        with self.assertRaisesRegex(ValueError, "conflito"):
            await create_demo_activity(session, turma, "Exemplo", "", [], "PUBLICADA")
        self.assertEqual(existing.tipo, "PROVA")
        self.assertEqual(existing.status, "ENCERRADA")

    async def test_attempt_results_follow_case_content_not_database_order(self):
        activity = SimpleNamespace(uuid=uuid4())
        student = SimpleNamespace(uuid=uuid4())
        function = SimpleNamespace(uuid=uuid4(), nome="somar", nota_maxima=10)
        positive = SimpleNamespace(uuid=uuid4(), entradas=[1, 2], retorno_esperado=3)
        negative = SimpleNamespace(uuid=uuid4(), entradas=[-5, 8], retorno_esperado=3)
        session = Mock()
        session.scalars = AsyncMock(side_effect=[[function], [negative, positive]])
        session.scalar = AsyncMock(return_value=None)
        async def flush():
            for call in session.add_all.call_args_list:
                for item in call.args[0]:
                    if hasattr(item, "codigo_fonte") and item.uuid is None:
                        item.uuid = uuid4()
        session.flush = AsyncMock(side_effect=flush)
        await ensure_demo_attempts(session, activity, student)
        added = [item for call in session.add_all.call_args_list for item in call.args[0]]
        attempts = [item for item in added if hasattr(item, "codigo_fonte")]
        results = [item for item in added if hasattr(item, "aprovado")]
        self.assertEqual(len(attempts), 2)
        self.assertEqual(len(results), 4)
        self.assertEqual([(item.caso_teste_atividade_uuid, item.aprovado)
                          for item in results if item.tentativa_uuid == attempts[0].uuid],
                         [(negative.uuid, False), (positive.uuid, True)])

    async def test_existing_attempts_are_not_recreated(self):
        activity = SimpleNamespace(uuid=uuid4())
        student = SimpleNamespace(uuid=uuid4())
        function = SimpleNamespace(uuid=uuid4(), nome="somar")
        session = Mock()
        session.scalars = AsyncMock(return_value=[function])
        session.scalar = AsyncMock(return_value=uuid4())
        await ensure_demo_attempts(session, activity, student)
        session.add_all.assert_not_called()


if __name__ == "__main__":
    unittest.main()
