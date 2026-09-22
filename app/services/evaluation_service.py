"""Coordena a geração e a execução isolada de uma avaliação."""

from dataclasses import dataclass
import re
from typing import Any, Protocol

from ..integrations.judge0 import Judge0TechnicalFailure
from .gerador_service import gerar_programa_teste


class CodeExecutor(Protocol):
    async def executar_codigo(self, source_code: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class EvaluationResult:
    passed_cases: int
    total_cases: int
    technical_failure: bool = False
    compilation_error: bool = False
    case_results: tuple[bool, ...] = ()


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
        if status_id != 3:
            return EvaluationResult(0, program.total_cases)
        match = re.search(
            rf"(?:^|\n){re.escape(program.result_marker)}(\d+)/(\d+)\|([01]+)(?:\r?\n|$)",
            execution.get("stdout", ""),
        )
        if match is None or int(match.group(2)) != program.total_cases or len(match.group(3)) != program.total_cases:
            return EvaluationResult(0, program.total_cases)
        case_results = tuple(value == "1" for value in match.group(3))
        if sum(case_results) != int(match.group(1)):
            return EvaluationResult(0, program.total_cases)
        return EvaluationResult(int(match.group(1)), program.total_cases, case_results=case_results)
