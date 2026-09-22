"""Cliente assíncrono e isolado para a API do Judge0."""

import asyncio
import base64
import logging
from typing import Any

import httpx

from ..config.settings import Settings

logger = logging.getLogger(__name__)


class Judge0TechnicalFailure(RuntimeError):
    """Falha de infraestrutura que não representa erro da solução do aluno."""


class Judge0Client:
    """Submete programas C ao Judge0 usando limites controlados pelo backend."""

    C_LANGUAGE_ID = 50
    _PENDING_STATUSES = {1, 2}

    def __init__(self, settings: Settings):
        self.api_url = str(settings.judge0_api_url).rstrip("/")
        self.api_key = settings.judge0_api_key.get_secret_value()
        self.api_host = settings.judge0_api_host
        self.is_rapidapi = "rapidapi" in self.api_url.lower()
        self.time_limit_seconds = settings.judge0_time_limit_seconds
        self.memory_limit_kb = settings.judge0_memory_limit_kb
        self.request_timeout_seconds = settings.judge0_request_timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.is_rapidapi:
            headers["X-RapidAPI-Key"] = self.api_key
            headers["X-RapidAPI-Host"] = self.api_host
        return headers

    async def executar_codigo(self, source_code: str, language_id: int | None = None) -> dict[str, Any]:
        """Envia um programa e devolve somente o resultado técnico do Judge0."""
        language_id = language_id or self.C_LANGUAGE_ID
        payload = {
            "source_code": source_code,
            "language_id": language_id,
            "cpu_time_limit": self.time_limit_seconds,
            "wall_time_limit": self.time_limit_seconds * 2,
            "memory_limit": self.memory_limit_kb,
        }
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
                response = await client.post(
                    f"{self.api_url}/submissions", json=payload, headers=self._headers()
                )
                if response.status_code != 201:
                    logger.warning("Judge0 rejeitou submissão: status=%d", response.status_code)
                    raise Judge0TechnicalFailure("Judge0 indisponível no momento.")
                try:
                    token = response.json()["token"]
                except (KeyError, ValueError, TypeError):
                    logger.warning("Judge0 respondeu uma submissão sem token válido")
                    raise Judge0TechnicalFailure("Judge0 retornou uma resposta inválida.") from None
                return await self._poll_resultado(client, token, self._headers())
        except httpx.RequestError as error:
            logger.warning("Falha de rede ao comunicar com o Judge0: %s", error.__class__.__name__)
            raise Judge0TechnicalFailure("Judge0 indisponível no momento.") from None

    async def _poll_resultado(
        self,
        client: httpx.AsyncClient,
        token: str,
        headers: dict[str, str],
        max_tentativas: int = 15,
        intervalo: float = 1.5,
    ) -> dict[str, Any]:
        url = f"{self.api_url}/submissions/{token}"
        params = {"fields": "*", "base64_encoded": "true"}
        for _ in range(max_tentativas):
            try:
                response = await client.get(url, params=params, headers=headers)
            except httpx.RequestError as error:
                logger.warning("Polling Judge0 falhou: %s", error.__class__.__name__)
                await asyncio.sleep(intervalo)
                continue
            if response.status_code != 200:
                logger.warning("Polling Judge0 retornou status=%d", response.status_code)
                await asyncio.sleep(intervalo)
                continue
            try:
                resultado = response.json()
                status_id = resultado["status"]["id"]
            except (KeyError, TypeError, ValueError):
                logger.warning("Polling Judge0 retornou resposta inválida")
                await asyncio.sleep(intervalo)
                continue
            if status_id in self._PENDING_STATUSES:
                await asyncio.sleep(intervalo)
                continue
            resultado["stdout"] = self._decode_b64(resultado.get("stdout"))
            resultado["stderr"] = self._decode_b64(resultado.get("stderr"))
            resultado["compile_output"] = self._decode_b64(resultado.get("compile_output"))
            return resultado
        raise Judge0TechnicalFailure("Judge0 não concluiu a avaliação a tempo.")

    @staticmethod
    def _decode_b64(value: str | None) -> str:
        if not value:
            return ""
        try:
            return base64.b64decode(value, validate=True).decode("utf-8", errors="replace")
        except (ValueError, UnicodeError):
            return ""
