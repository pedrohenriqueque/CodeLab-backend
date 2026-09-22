"""Verificação local sem criar engine, sessão, cliente HTTP ou recursos externos."""

import sys

from pydantic import ValidationError
from pydantic_settings import SettingsError

from .app.config.settings import get_settings


def main() -> int:
    try:
        settings = get_settings()
    except (ValidationError, SettingsError):
        # Não imprimir a exceção: valores de configuração podem conter segredos.
        print(
            "Configuração inválida. Revise as variáveis CODELAB_V2_ e "
            "backend_v2/.env conforme backend_v2/README.md.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Configuração do backend_v2 válida ({settings.environment}). "
        "Nenhuma conexão com banco ou Judge0 foi realizada."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
