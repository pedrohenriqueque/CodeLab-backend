"""Regressões do seed sem abrir conexão com o banco."""

import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from backend_v2.seed_demo import (
    ATTEMPT_CASES,
    ATTEMPT_CODES,
    USERS,
    create_demo_activity,
    ensure_demo_attempts,
    get_or_create_class,
    get_or_create_function,
    get_or_create_user,
    seed,
    seed_case_scenarios,
    validate_seed_target,
)
from backend_v2.app.models.usuario import PerfilUsuario, Usuario


class SeedTargetTests(unittest.TestCase):
    def test_demo_admin_email_is_valid_for_api_response(self):
        from backend_v2.app.schemas.usuario import UsuarioResponse

        admin = next(user for user in USERS if user[3] == PerfilUsuario.ADMIN)
        response = UsuarioResponse(
            uuid=uuid4(), nome=admin[0], email=admin[1], matricula=admin[2],
            perfil=admin[3].value, ativo=True,
        )
        self.assertEqual(response.email, "admin@codelab.com")

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
    async def test_case_scenarios_keep_empty_function_outside_activity_and_copy_hidden_functions(self):
        session = Mock(flush=AsyncMock())
        professor = SimpleNamespace(uuid=uuid4())
        turma = SimpleNamespace(uuid=uuid4())
        empty, hidden_sum, hidden_bool = [SimpleNamespace(uuid=uuid4()) for _ in range(3)]
        with (
            patch("backend_v2.seed_demo.get_or_create_function", new=AsyncMock(side_effect=[empty, hidden_sum, hidden_bool])) as functions,
            patch("backend_v2.seed_demo.create_demo_activity", new=AsyncMock()) as activities,
        ):
            await seed_case_scenarios(session, professor, turma)
        self.assertEqual(functions.call_args_list[0].args[7], [])
        for call in functions.call_args_list[1:]:
            self.assertEqual(call.kwargs["visibilidade_casos"], "OCULTO")
            self.assertEqual(len(call.args[7]), 3)
        for call in activities.call_args_list[:2]:
            self.assertEqual(call.args[4], [hidden_sum, hidden_bool])
            self.assertEqual(call.args[5], "PUBLICADA")
        self.assertEqual(activities.call_args_list[2].args[4], [])
        self.assertEqual(activities.call_args_list[2].args[5], "RASCUNHO")

    async def test_demo_activity_rejects_empty_function_before_creating_internal_function(self):
        session = Mock()
        session.scalar = AsyncMock(return_value=None)
        session.scalars = AsyncMock(return_value=[])
        session.flush = AsyncMock()
        turma = SimpleNamespace(uuid=uuid4())
        function = SimpleNamespace(uuid=uuid4(), nome="semCasosDemo")
        with self.assertRaisesRegex(ValueError, "precisa de casos"):
            await create_demo_activity(session, turma, "Exemplo", "", [function], "RASCUNHO")
        self.assertEqual(session.add.call_count, 1)  # Somente o rascunho; a transação chamadora faz rollback.
        session.add_all.assert_not_called()

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

    async def test_known_legacy_vector_function_is_upgraded_without_changing_snapshots(self):
        professor = SimpleNamespace(uuid=uuid4())
        function = SimpleNamespace(
            uuid=uuid4(), professor_uuid=professor.uuid, nome="contarPositivos",
            enunciado="Conte os valores positivos de um vetor.", tipo_retorno="int",
            parametros=[{"nome": "valores", "tipo": "int[]"}], dificuldade="MEDIO", compartilhada=True,
        )
        old_cases = [
            SimpleNamespace(entradas=[[1, -2, 3]], retorno_esperado=2, descricao="Mistos",
                            visibilidade="VISIVEL", peso=Decimal("1.00")),
            SimpleNamespace(entradas=[[-1, -4]], retorno_esperado=0, descricao="Nenhum positivo",
                            visibilidade="VISIVEL", peso=Decimal("1.00")),
        ]
        session = Mock()
        session.scalar = AsyncMock(side_effect=[function, None])
        session.scalars = AsyncMock(return_value=old_cases)
        session.delete = AsyncMock()
        session.flush = AsyncMock()

        updated = await get_or_create_function(
            session,
            professor,
            "contarPositivos",
            "Conte os valores positivos entre os primeiros tamanho itens.",
            "int",
            [{"nome": "valores", "tipo": "int[]"}, {"nome": "tamanho", "tipo": "int"}],
            "MEDIO",
            [([[1, -2, 3], 3], 2, "Mistos"), ([[-1, -4], 2], 0, "Nenhum positivo")],
            legacy={
                "tipo_retorno": "int",
                "parametros": [{"nome": "valores", "tipo": "int[]"}],
                "enunciado": "Conte os valores positivos de um vetor.",
                "dificuldade": "MEDIO",
                "compartilhada": True,
                "casos": [([[1, -2, 3]], 2, "Mistos"), ([[-1, -4]], 0, "Nenhum positivo")],
            },
        )

        self.assertIs(updated, function)
        self.assertEqual(function.parametros, [{"nome": "valores", "tipo": "int[]"}, {"nome": "tamanho", "tipo": "int"}])
        self.assertEqual(function.enunciado, "Conte os valores positivos entre os primeiros tamanho itens.")
        self.assertEqual(session.delete.await_count, 2)
        session.add_all.assert_called_once()
        recreated_cases = list(session.add_all.call_args.args[0])
        self.assertEqual([case.entradas for case in recreated_cases], [[ [1, -2, 3], 3 ], [[-1, -4], 2]])

    async def test_legacy_demo_function_with_edited_cases_is_preserved_as_conflict(self):
        professor = SimpleNamespace(uuid=uuid4())
        function = SimpleNamespace(
            uuid=uuid4(), professor_uuid=professor.uuid, nome="contarPositivos",
            enunciado="Conte os valores positivos de um vetor.", tipo_retorno="int",
            parametros=[{"nome": "valores", "tipo": "int[]"}], dificuldade="MEDIO", compartilhada=True,
        )
        edited_case = SimpleNamespace(entradas=[[1, -2, 3]], retorno_esperado=99, descricao="Editado",
                                      visibilidade="VISIVEL", peso=Decimal("1.00"))
        session = Mock()
        session.scalar = AsyncMock(return_value=function)
        session.scalars = AsyncMock(return_value=[edited_case])
        session.delete = AsyncMock()

        with self.assertRaisesRegex(ValueError, "Dados da função.*conflito"):
            await get_or_create_function(
                session,
                professor,
                "contarPositivos",
                "Conte os valores positivos entre os primeiros tamanho itens.",
                "int",
                [{"nome": "valores", "tipo": "int[]"}, {"nome": "tamanho", "tipo": "int"}],
                "MEDIO",
                [([[1, -2, 3], 3], 2, "Mistos")],
                legacy={
                    "tipo_retorno": "int",
                    "parametros": [{"nome": "valores", "tipo": "int[]"}],
                    "enunciado": "Conte os valores positivos de um vetor.",
                    "dificuldade": "MEDIO",
                    "compartilhada": True,
                    "casos": [([[1, -2, 3]], 2, "Mistos"), ([[-1, -4]], 0, "Nenhum positivo")],
                },
            )

        self.assertEqual(function.parametros, [{"nome": "valores", "tipo": "int[]"}])
        session.delete.assert_not_awaited()
        session.add_all.assert_not_called()

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
