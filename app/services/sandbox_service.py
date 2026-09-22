"""Execução isolada de programas C sem avaliação ou persistência."""

from typing import Any

from ..integrations.judge0 import Judge0TechnicalFailure
from .evaluation_service import CodeExecutor


async def executar_playground(codigo: str, executor: CodeExecutor) -> dict[str, Any]:
    """Executa código livre no Judge0 e projeta somente o resultado técnico."""
    try:
        resultado = await executor.executar_codigo(codigo)
    except Judge0TechnicalFailure:
        raise

    status = resultado.get("status") or {}
    return {
        "stdout": resultado.get("stdout") or "",
        "stderr": resultado.get("stderr") or "",
        "compile_output": resultado.get("compile_output") or "",
        "status": status.get("description") or "Resultado indisponível",
        "time": resultado.get("time"),
        "memory": resultado.get("memory"),
    }
