"""Comandos de migrations com confirmação explícita de ambiente e banco.

Não executa DDL, conecta ou imprime secrets durante importação.
"""

import argparse
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from .app.config.settings import BACKEND_ROOT, Settings, get_settings


def migration_config(settings: Settings) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["settings"] = settings
    return config


def validate_approval(
    settings: Settings,
    *,
    action: str,
    environment: str,
    confirmation: str,
) -> None:
    database = make_url(settings.database_url.get_secret_value()).database
    if settings.environment != environment:
        raise ValueError("Ambiente informado não corresponde à configuração CODELAB_V2_ENVIRONMENT.")
    if action == "reset-test" and environment != "test":
        raise ValueError("Reset permitido somente para ambiente test.")
    expected = (
        "RESET:test:codelab_v2_test"
        if action == "reset-test"
        else f"MIGRATE:{environment}:{database}"
    )
    if confirmation != expected:
        raise ValueError("Confirmação explícita de ambiente/banco ausente ou incorreta.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrations explícitas do CodeLab backend_v2")
    parser.add_argument("action", choices=("upgrade", "downgrade", "reset-test"))
    parser.add_argument("--environment", choices=("development", "test", "production"), required=True)
    parser.add_argument("--confirm", required=True, help="MIGRATE:<ambiente>:<banco>; reset: RESET:test:codelab_v2_test")
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
        validate_approval(
            settings, action=args.action, environment=args.environment, confirmation=args.confirm
        )
        config = migration_config(settings)
        if args.action == "upgrade":
            command.upgrade(config, "head")
        elif args.action == "downgrade":
            # Pode descartar dados de tabelas gerenciadas; nunca usar sem backup.
            command.downgrade(config, "base")
        else:
            # Reseta somente migrations gerenciadas, NÃO derruba o banco inteiro.
            command.downgrade(config, "base")
            command.upgrade(config, "head")
    except Exception:
        # Nem exceções de conexão nem valores de Settings devem aparecer no console.
        print("Operação não concluída. Confira ambiente, aprovação e conectividade.", file=sys.stderr)
        return 1
    print("Operação concluída no ambiente explicitamente confirmado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
