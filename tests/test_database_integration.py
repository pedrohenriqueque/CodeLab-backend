"""Integração opt-in, SOMENTE PostgreSQL de testes descartável explicitamente aprovado.

Requisitos para executar este teste (não configura runtime/DB automaticamente):
- CODELAB_V2_RUN_DB_TESTS=1
- CODELAB_V2_TEST_DATABASE_URL=postgresql+asyncpg://.../codelab_v2_test
- CODELAB_V2_TEST_DB_APPROVED=codelab_v2_test
"""

import asyncio
import os
import unittest

from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend_v2.manage_db import migration_config
from backend_v2.app.config.settings import Settings


class PostgreSQLIntegrationTests(unittest.TestCase):
    def test_baseline_upgrade_idempotence_downgrade_and_transaction_rollback(self):
        if os.environ.get("CODELAB_V2_RUN_DB_TESTS") != "1":
            self.skipTest("Integração PostgreSQL opt-in não autorizada neste ambiente.")
        if os.environ.get("CODELAB_V2_TEST_DB_APPROVED") != "codelab_v2_test":
            self.skipTest("Falta aprovação explícita do banco descartável codelab_v2_test.")
        url = os.environ.get("CODELAB_V2_TEST_DATABASE_URL")
        if not url:
            self.skipTest("DSN do banco de teste não fornecida.")
        try:
            import asyncpg  # noqa: F401
        except ImportError:
            self.skipTest("asyncpg não está instalado neste ambiente.")

        settings = Settings(
            _env_file=None, environment="test", database_url=url,
            secret_key="fixture-only-" + "x" * 36,
        )
        config = migration_config(settings)
        engine = create_async_engine(url)

        initial_revision = None
        preflight_ok = False

        async def preflight():
            async with engine.connect() as connection:
                unexpected = (await connection.execute(text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname='public' AND tablename <> 'alembic_version'"
                ))).scalars().all()
                if unexpected:
                    raise RuntimeError("Banco não está vazio: recuse usar fixture compartilhada.")
                version_exists = (await connection.execute(text(
                    "SELECT to_regclass('public.alembic_version')"
                ))).scalar_one()
                nonlocal initial_revision
                if version_exists is not None:
                    current = (await connection.execute(text(
                        "SELECT version_num FROM alembic_version"
                    ))).scalars().all()
                    if current not in ([], ["0001_baseline"], ["ec12613fbb7f"], ["5c4c7736a002"], ["9f78b3d1c004"], ["a4c92e7b1005"], ["b5d8e1f2006"]):
                        raise RuntimeError("Banco de testes contém revision desconhecida.")
                    initial_revision = current[0] if current else None

        async def check_revision(expected):
            async with engine.connect() as connection:
                existing = (await connection.execute(text(
                    "SELECT to_regclass('public.alembic_version')"
                ))).scalar_one()
                if existing is None:
                    return None
                revisions = (await connection.execute(text(
                    "SELECT version_num FROM alembic_version"
                ))).scalars().all()
                self.assertEqual(revisions, [expected] if expected else [])

        async def check_rollback():
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            with self.assertRaisesRegex(RuntimeError, "rollback sintético"):
                async with session_factory() as session:
                    async with session.begin():
                        await session.execute(text(
                            "CREATE TABLE imp0103_rollback_probe (id INTEGER PRIMARY KEY)"
                        ))
                        raise RuntimeError("rollback sintético")
            async with engine.connect() as connection:
                table = (await connection.execute(text(
                    "SELECT to_regclass('public.imp0103_rollback_probe')"
                ))).scalar_one()
                self.assertIsNone(table)

        try:
            asyncio.run(preflight())
            preflight_ok = True
            command.upgrade(config, "head")
            asyncio.run(check_revision("b5d8e1f2006"))
            command.upgrade(config, "head")
            asyncio.run(check_revision("b5d8e1f2006"))
            asyncio.run(check_rollback())
            command.downgrade(config, "base")
            asyncio.run(check_revision(None))
            command.upgrade(config, "head")
            asyncio.run(check_revision("b5d8e1f2006"))
        finally:
            # Restaurar o estado inicial APENAS após pré-inspeção aprovada.
            # Nunca resetar um banco que falhou nas verificações de segurança.
            try:
                if preflight_ok and initial_revision is None:
                    command.downgrade(config, "base")
            finally:
                asyncio.run(engine.dispose())
