"""Cria o primeiro administrador por execução manual e confirmada."""

import argparse
import asyncio
import getpass
import sys

from pydantic import ValidationError

from .app.config.database import dispose_db_engine, make_engine, make_session_factory
from .app.config.settings import Settings, get_settings
from .app.core.exceptions import CodelabException
from .app.models.usuario import PerfilUsuario
from .app.repositories.user_repository import UserRepository
from .app.schemas.usuario import CriarProfessorRequest
from .app.services.user_service import criar_usuario


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cria o primeiro administrador do CodeLab."
    )
    parser.add_argument("--nome", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--matricula", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args(argv)


def validate_approval(settings: Settings, args: argparse.Namespace) -> None:
    email = args.email.strip().lower()
    if args.environment != settings.environment:
        raise ValueError("O ambiente informado não corresponde à configuração.")
    if args.confirm != f"CREATE-FIRST-ADMIN:{settings.environment}:{email}":
        raise ValueError("Confirmação inválida para criação do primeiro administrador.")


async def create_first_admin(
    settings: Settings, args: argparse.Namespace, password: str
) -> None:
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as db:
            if await UserRepository(db).count_admins():
                raise CodelabException("Já existe um administrador cadastrado.", 409)
            dados = CriarProfessorRequest(
                nome=args.nome,
                email=args.email,
                matricula=args.matricula,
                senha=password,
            )
            await criar_usuario(dados, PerfilUsuario.ADMIN, db)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        settings = get_settings()
        validate_approval(settings, args)
        password = getpass.getpass("Senha inicial: ")
        confirmation = getpass.getpass("Repita a senha: ")
        if password != confirmation:
            raise ValueError("As senhas não conferem.")
        asyncio.run(create_first_admin(settings, args, password))
    except (CodelabException, ValidationError, ValueError) as error:
        print(f"Criação não realizada: {error}", file=sys.stderr)
        return 1
    print("Primeiro administrador criado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
