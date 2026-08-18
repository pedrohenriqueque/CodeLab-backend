"""
Cliente assíncrono para a API do Judge0 (RapidAPI ou self-hosted).

Usa httpx.AsyncClient para não bloquear o event loop durante
polling de resultados.
"""

import base64
import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class Judge0Client:
    """Cliente assíncrono para a API pública do Judge0."""

    # Language ID 50 = C (GCC 9.2.0) no Judge0 CE
    C_LANGUAGE_ID = 50

    def __init__(self):
        self.api_url = settings.judge0_api_url
        self.api_key = settings.judge0_api_key
        self.api_host = settings.judge0_api_host
        self.is_rapidapi = "rapidapi" in self.api_url.lower()

        logger.info(
            "Judge0 configurado: url=%s rapidapi=%s",
            self.api_url, self.is_rapidapi,
        )

    def _headers(self) -> dict[str, str]:
        """Monta headers com autenticação se necessário."""
        headers = {"content-type": "application/json"}
        if self.is_rapidapi:
            headers["X-RapidAPI-Key"] = self.api_key
            headers["X-RapidAPI-Host"] = self.api_host
        return headers

    async def executar_codigo(self, source_code: str, language_id: int | None = None) -> dict:
        """
        Envia código para o Judge0 e aguarda o resultado (async).

        Args:
            source_code: código-fonte completo em C
            language_id: ID da linguagem (default: C/GCC)

        Returns:
            dict com campos: stdout, stderr, compile_output, status, time, memory

        Raises:
            Exception: se a submissão falhar
            TimeoutError: se o polling esgotar
        """
        if language_id is None:
            language_id = self.C_LANGUAGE_ID

        url = f"{self.api_url}/submissions"
        headers = self._headers()
        payload = {
            "source_code": source_code,
            "language_id": language_id,
        }

        logger.info(
            "Enviando submissao para Judge0 (lang=%d, %d bytes)",
            language_id, len(source_code),
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code != 201:
                logger.error(
                    "Judge0 rejeitou submissao: %d %s",
                    response.status_code, response.text[:300],
                )
                raise Exception(
                    f"Judge0 retornou status {response.status_code}: {response.text[:300]}"
                )

            token = response.json()["token"]
            logger.info("Submissao aceita, token=%s", token)

            return await self._poll_resultado(client, token, headers)

    async def _poll_resultado(
        self,
        client: httpx.AsyncClient,
        token: str,
        headers: dict,
        max_tentativas: int = 15,
        intervalo: float = 1.5,
    ) -> dict:
        """Faz polling assíncrono do resultado até a execução terminar."""
        url = f"{self.api_url}/submissions/{token}"
        params = {"fields": "*", "base64_encoded": "true"}

        logger.info("Aguardando resultado (max %d tentativas)...", max_tentativas)

        for tentativa in range(1, max_tentativas + 1):
            try:
                response = await client.get(url, params=params, headers=headers)
            except httpx.RequestError as e:
                logger.warning("Tentativa %d - erro de rede: %s", tentativa, e)
                await asyncio.sleep(intervalo)
                continue

            if response.status_code != 200:
                logger.warning("Tentativa %d - status %d", tentativa, response.status_code)
                await asyncio.sleep(intervalo)
                continue

            try:
                resultado = response.json()
            except ValueError:
                logger.warning("Tentativa %d - resposta nao e JSON", tentativa)
                await asyncio.sleep(intervalo)
                continue

            if "status" not in resultado:
                if "error" in resultado or "message" in resultado:
                    erro = resultado.get("error") or resultado.get("message")
                    raise Exception(f"Erro Judge0: {erro}")
                logger.warning("Tentativa %d - campo 'status' ausente", tentativa)
                await asyncio.sleep(intervalo)
                continue

            status_id = resultado["status"]["id"]
            status_desc = resultado["status"]["description"]
            logger.info("Tentativa %d - %s (id=%d)", tentativa, status_desc, status_id)

            # 1 = In Queue, 2 = Processing
            if status_id in (1, 2):
                await asyncio.sleep(intervalo)
                continue

            # Decodificar Base64
            resultado["stdout"] = self._decode_b64(resultado.get("stdout"))
            resultado["stderr"] = self._decode_b64(resultado.get("stderr"))
            resultado["compile_output"] = self._decode_b64(resultado.get("compile_output"))

            logger.info("Execucao finalizada: %s", status_desc)
            return resultado

        raise TimeoutError(f"Tempo limite excedido apos {max_tentativas} tentativas")

    @staticmethod
    def _decode_b64(value: str | None) -> str:
        """Decodifica string Base64 ou retorna string vazia."""
        if not value:
            return ""
        try:
            return base64.b64decode(value).decode("utf-8", errors="replace")
        except Exception:
            return str(value)


# Singleton
judge0_client = Judge0Client()
