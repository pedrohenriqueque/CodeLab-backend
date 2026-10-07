"""Coordena a geração e a execução isolada de uma avaliação."""

from dataclasses import dataclass
import json
import math
import re
from typing import Any, Protocol

from ..integrations.judge0 import Judge0TechnicalFailure
from .gerador_service import MAX_CAPTURED_STRING_BYTES, gerar_programa_teste


class CodeExecutor(Protocol):
    async def executar_codigo(self, source_code: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CapturedReturn:
    value: Any = None
    status: str = "NAO_EXECUTADO"


@dataclass(frozen=True)
class EvaluationResult:
    passed_cases: int
    total_cases: int
    technical_failure: bool = False
    compilation_error: bool = False
    case_results: tuple[bool, ...] = ()
    case_returns: tuple[CapturedReturn, ...] = ()


def _parse_return(payload: str, return_type: str) -> CapturedReturn:
    if return_type == "string" and payload == "TRUNCATED":
        return CapturedReturn(status="LIMITE_EXCEDIDO")
    if return_type in {"string", "char"}:
        if return_type == "string" and payload == "null":
            return CapturedReturn(None, "DISPONIVEL")
        if not payload.startswith("x:") or len(payload) > MAX_CAPTURED_STRING_BYTES * 2 + 2:
            raise ValueError("Retorno textual inválido.")
        encoded = payload[2:]
        if not re.fullmatch(r"(?:[0-9a-f]{2})*", encoded) or (return_type == "char" and len(encoded) != 2):
            raise ValueError("Retorno textual inválido.")
        raw = bytes.fromhex(encoded)
        try:
            value = raw.decode("latin-1" if return_type == "char" else "utf-8")
        except UnicodeDecodeError:
            # Não substitui bytes inválidos por um texto que a função não retornou.
            return CapturedReturn(status="NAO_INFORMADO")
        return CapturedReturn(value, "DISPONIVEL")
    if len(payload) > 128:
        raise ValueError("Retorno numérico inválido.")
    value = json.loads(payload)
    if return_type == "bool":
        valid = isinstance(value, bool)
    elif return_type in {"int", "long"}:
        valid = isinstance(value, int) and not isinstance(value, bool)
    else:
        valid = (
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        ) or (isinstance(value, str) and value in {"NaN", "Infinity", "-Infinity"})
    if not valid:
        raise ValueError("Tipo de retorno inválido.")
    return CapturedReturn(value, "DISPONIVEL")


class EvaluationService:
    """Não expõe programa gerado, casos ocultos ou saída bruta do executor."""

    def __init__(self, executor: CodeExecutor):
        self._executor = executor

    async def avaliar(
        self,
        funcao: dict[str, Any],
        casos_teste: list[dict[str, Any]],
        codigo_aluno: str,
    ) -> EvaluationResult:
        program = gerar_programa_teste(funcao, casos_teste, codigo_aluno)
        try:
            execution = await self._executor.executar_codigo(program.source_code)
        except Judge0TechnicalFailure:
            return EvaluationResult(0, program.total_cases, technical_failure=True)

        status_id = execution.get("status", {}).get("id")
        if status_id == 6:
            return EvaluationResult(0, program.total_cases, compilation_error=True)
        if status_id not in {3, 4, 5, 7, 8, 9, 10, 11, 12}:
            return EvaluationResult(0, program.total_cases, technical_failure=True)
        stdout = execution.get("stdout") or ""
        if not isinstance(stdout, str):
            return EvaluationResult(0, program.total_cases, technical_failure=True)
        return_type = (funcao.get("tipo_retorno") or funcao.get("tipoRetorno") or funcao.get("retorno")).lower()
        results: list[bool] = []
        returns: list[CapturedReturn] = []
        prefix = f"{program.result_marker}CASE|"
        try:
            for line in stdout.splitlines(keepends=True):
                if not line.startswith(prefix):
                    continue
                if not line.endswith("\n"):
                    break
                line = line.rstrip("\r\n")
                parts = line[len(prefix):].split("|", 2)
                if len(parts) != 3 or parts[0] != str(len(results)) or parts[1] not in {"0", "1"} or len(results) >= program.total_cases:
                    raise ValueError("Resultado de caso inválido.")
                returns.append(_parse_return(parts[2], return_type))
                results.append(parts[1] == "1")
        except (ValueError, OverflowError):
            return EvaluationResult(0, program.total_cases, technical_failure=True)
        # Uma falha fatal interrompe o processo único; casos já concluídos permanecem válidos.
        missing = program.total_cases - len(results)
        if missing:
            returns.append(CapturedReturn(status="ERRO_EXECUCAO"))
            returns.extend(CapturedReturn() for _ in range(missing - 1))
            results.extend(False for _ in range(missing))
        return EvaluationResult(sum(results), program.total_cases, case_results=tuple(results), case_returns=tuple(returns))
