"""IMP-01.03: testes unitários de persistência sem PostgreSQL externo."""

import asyncio
import contextlib
import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from alembic import command
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

from backend_v2 import manage_db
from backend_v2.app.config import database
from backend_v2.app.config.settings import Settings
from backend_v2.app.main import create_app
from backend_v2.app.models.base import Base


TEST_DATABASE_URL = "postgresql+asyncpg://fixture:secret@localhost/codelab_v2_test"


def fixture_settings(*, environment="test", database_url=TEST_DATABASE_URL):
    return Settings(
        _env_file=None,
        environment=environment,
        database_url=database_url,
        secret_key="fixture-only-" + "x" * 36,
    )


class SessionStub:
    def __init__(self, open_transaction=True):
        self.open_transaction = open_transaction
        self.rollback_count = 0
        self.enter_count = 0
        self.exit_count = 0

    async def __aenter__(self):
        self.enter_count += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exit_count += 1

    def in_transaction(self):
        return self.open_transaction

    async def rollback(self):
        self.rollback_count += 1
        self.open_transaction = False


class DatabaseTests(unittest.TestCase):
    def test_user_model_is_registered_without_creating_tables(self):
        self.assertEqual(
            list(Base.metadata.tables), ["usuarios", "turmas", "matriculas_turma", "funcoes_biblioteca", "casos_teste", "atividades", "funcoes_atividade", "casos_teste_atividade", "tentativas", "resultados_casos_tentativa"]
        )

    def test_create_app_and_health_never_construct_database_engine(self):
        with patch.object(database, "make_engine", side_effect=AssertionError("engine at startup")):
            with TestClient(create_app(fixture_settings())) as client:
                self.assertEqual(client.get("/api/health").json(), {"status": "ok"})

    def test_make_engine_uses_asyncpg_url_without_connecting(self):
        engine = Mock()
        with patch.object(database, "create_async_engine", return_value=engine) as create:
            self.assertIs(database.make_engine(fixture_settings()), engine)
        create.assert_called_once_with(TEST_DATABASE_URL, pool_pre_ping=True)

    def test_session_factory_does_not_autocommit(self):
        engine = Mock()
        with patch.object(database, "async_sessionmaker", return_value="factory") as create:
            self.assertEqual(database.make_session_factory(engine), "factory")
        create.assert_called_once_with(engine, expire_on_commit=False, autoflush=False)

    def test_session_is_lazy_and_rolls_back_uncommitted_work(self):
        async def run():
            app = create_app(fixture_settings())
            session = SessionStub()
            engine = Mock()
            request = SimpleNamespace(app=app)
            with patch.object(database, "make_engine", return_value=engine) as make:
                with patch.object(database, "make_session_factory", return_value=lambda: session):
                    dependency = database.get_db(request)
                    self.assertIs(await anext(dependency), session)
                    self.assertIs(app.state.db_engine, engine)
                    await dependency.aclose()
                    make.assert_called_once()
            self.assertEqual(session.rollback_count, 1)
            self.assertEqual(session.exit_count, 1)
        asyncio.run(run())

    def test_session_rolls_back_when_endpoint_raises(self):
        async def run():
            app = create_app(fixture_settings())
            session = SessionStub()
            app.state.session_factory = lambda: session
            dep = database.get_db(SimpleNamespace(app=app))
            self.assertIs(await anext(dep), session)
            with self.assertRaisesRegex(RuntimeError, "erro sintético"):
                await dep.athrow(RuntimeError("erro sintético"))
            self.assertEqual(session.rollback_count, 1)
        asyncio.run(run())

    def test_session_does_not_rollback_after_explicit_commit(self):
        async def run():
            app = create_app(fixture_settings())
            session = SessionStub()
            app.state.session_factory = lambda: session
            dep = database.get_db(SimpleNamespace(app=app))
            await anext(dep)
            session.open_transaction = False  # serviço executou commit
            await dep.aclose()
            self.assertEqual(session.rollback_count, 0)
        asyncio.run(run())

    def test_engine_is_disposed_only_when_created(self):
        async def run():
            app = create_app(fixture_settings())
            await database.dispose_db_engine(app)
            engine = SimpleNamespace(dispose=AsyncMock())
            app.state.db_engine = engine
            app.state.session_factory = object()
            await database.dispose_db_engine(app)
            engine.dispose.assert_awaited_once()
            self.assertIsNone(app.state.db_engine)
            self.assertIsNone(app.state.session_factory)
        asyncio.run(run())

    def test_migrations_include_users_and_offline_sql_contains_no_password(self):
        settings = fixture_settings()
        config = manage_db.migration_config(settings)
        script = ScriptDirectory.from_config(config)
        self.assertEqual(script.get_current_head(), "c3e9a7d51201")
        rendered = io.StringIO()
        with contextlib.redirect_stdout(rendered):
            command.upgrade(config, "head", sql=True)
        sql = rendered.getvalue()
        self.assertIn("CREATE TABLE alembic_version", sql)
        self.assertIn("d7f4a2b9008", sql)
        self.assertNotIn("secret", sql)
        self.assertIn("CREATE TABLE usuarios", sql)
        self.assertIn("CREATE TABLE turmas", sql)
        self.assertIn("CREATE TABLE matriculas_turma", sql)
        self.assertIn("CREATE TABLE funcoes_biblioteca", sql)
        self.assertIn("CREATE TABLE casos_teste", sql)
        self.assertIn("CREATE TABLE tentativas", sql)
        self.assertIn("ALTER TABLE tentativas ADD COLUMN nota", sql)
        self.assertIn("CREATE TABLE resultados_casos_tentativa", sql)
        self.assertIn("CREATE TABLE atividades", sql)
        self.assertIn("CREATE TABLE funcoes_atividade", sql)
        self.assertIn("CREATE TABLE casos_teste_atividade", sql)

    def test_command_requires_exact_environment_and_confirmation(self):
        settings = fixture_settings()
        with self.assertRaises(ValueError):
            manage_db.validate_approval(
                settings, action="upgrade", environment="development",
                confirmation="MIGRATE:development:codelab_v2_test",
            )
        with self.assertRaises(ValueError):
            manage_db.validate_approval(
                settings, action="upgrade", environment="test", confirmation="yes"
            )
        manage_db.validate_approval(
            settings, action="upgrade", environment="test",
            confirmation="MIGRATE:test:codelab_v2_test",
        )
        with self.assertRaises(ValueError):
            manage_db.validate_approval(
                settings, action="reset-test", environment="development",
                confirmation="RESET:test:codelab_v2_test",
            )

    def test_cli_does_not_touch_database_before_approval(self):
        with patch.object(manage_db, "get_settings", return_value=fixture_settings()):
            with patch.object(manage_db.command, "upgrade") as upgrade:
                with contextlib.redirect_stderr(io.StringIO()):
                    result = manage_db.main([
                        "upgrade", "--environment", "test", "--confirm", "wrong"
                    ])
                self.assertEqual(result, 1)
                upgrade.assert_not_called()

    def test_cli_runs_only_explicit_command(self):
        with patch.object(manage_db, "get_settings", return_value=fixture_settings()):
            with patch.object(manage_db.command, "upgrade") as upgrade:
                with patch.object(manage_db.command, "downgrade") as downgrade:
                    with contextlib.redirect_stdout(io.StringIO()):
                        result = manage_db.main([
                            "upgrade", "--environment", "test",
                            "--confirm", "MIGRATE:test:codelab_v2_test",
                        ])
                    self.assertEqual(result, 0)
                    upgrade.assert_called_once()
                    downgrade.assert_not_called()

    def test_cli_reset_test_never_uses_unapproved_production(self):
        production = fixture_settings(
            environment="production",
            database_url="postgresql+asyncpg://fixture:secret@localhost/codelab_v2",
        )
        with patch.object(manage_db, "get_settings", return_value=production):
            with patch.object(manage_db.command, "downgrade") as downgrade:
                with contextlib.redirect_stderr(io.StringIO()):
                    result = manage_db.main([
                        "reset-test", "--environment", "production",
                        "--confirm", "RESET:test:codelab_v2_test",
                    ])
                self.assertEqual(result, 1)
                downgrade.assert_not_called()

    def test_no_db_connection_or_schema_creation_on_module_import(self):
        import importlib
        with patch("sqlalchemy.ext.asyncio.create_async_engine", side_effect=AssertionError("engine")):
            with patch("sqlalchemy.MetaData.create_all", side_effect=AssertionError("DDL")):
                importlib.reload(database)
                importlib.reload(manage_db)
        # Os objetos já construídos continuam funcionalmente idênticos.
        self.assertTrue(callable(database.get_db))


if __name__ == "__main__":
    unittest.main()
