"""
Cliente para a API do Judge0 (RapidAPI ou self-hosted).

Responsabilidades:
- Enviar código-fonte para execução
- Polling assíncrono do resultado
- Decodificação Base64 da resposta
"""

import requests
import time
import os
import base64
import logging
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

# Carregar .env do diretório do projeto
_project_dir = Path(__file__).parent
load_dotenv(dotenv_path=_project_dir / '.env')


class Judge0Client:
    """Cliente para a API pública do Judge0."""

    # Language ID 50 = C (GCC 9.2.0) no Judge0 CE
    C_LANGUAGE_ID = 50

    def __init__(self):
        self.api_url = os.getenv('JUDGE0_API_URL', 'http://localhost:2358')
        self.api_key = os.getenv('JUDGE0_API_KEY', '')
        self.api_host = os.getenv('JUDGE0_API_HOST', '')

        # Detectar se é RapidAPI
        self.is_rapidapi = 'rapidapi' in self.api_url.lower()

        logger.info(
            "Judge0 configurado: url=%s rapidapi=%s",
            self.api_url, self.is_rapidapi
        )

    def _headers(self):
        """Monta headers com autenticação se necessário."""
        headers = {"content-type": "application/json"}
        if self.is_rapidapi:
            headers["X-RapidAPI-Key"] = self.api_key
            headers["X-RapidAPI-Host"] = self.api_host
        return headers

    def executar_codigo(self, source_code, language_id=None):
        """
        Envia código para o Judge0 e aguarda o resultado.

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

        logger.info("Enviando submissao para Judge0 (lang=%d, %d bytes)",
                     language_id, len(source_code))

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            if response.status_code != 201:
                logger.error("Judge0 rejeitou submissao: %d %s",
                             response.status_code, response.text[:300])
                raise Exception(
                    f"Judge0 retornou status {response.status_code}: {response.text[:300]}"
                )

            token = response.json()['token']
            logger.info("Submissao aceita, token=%s", token)

            return self._poll_resultado(token, headers)

        except requests.exceptions.RequestException as e:
            logger.error("Erro de conexao com Judge0: %s", e)
            raise

    def _poll_resultado(self, token, headers, max_tentativas=15, intervalo=1.5):
        """
        Faz polling do resultado até a execução terminar.

        Args:
            token: token da submissão
            headers: headers HTTP
            max_tentativas: máximo de tentativas de polling
            intervalo: segundos entre tentativas

        Returns:
            dict com resultado decodificado
        """
        url = f"{self.api_url}/submissions/{token}"
        params = {"fields": "*", "base64_encoded": "true"}

        logger.info("Aguardando resultado (max %d tentativas)...", max_tentativas)

        for tentativa in range(1, max_tentativas + 1):
            try:
                response = requests.get(
                    url, params=params, headers=headers, timeout=30
                )
            except requests.exceptions.RequestException as e:
                logger.warning("Tentativa %d - erro de rede: %s", tentativa, e)
                time.sleep(intervalo)
                continue

            if response.status_code != 200:
                logger.warning("Tentativa %d - status %d", tentativa, response.status_code)
                time.sleep(intervalo)
                continue

            try:
                resultado = response.json()
            except ValueError:
                logger.warning("Tentativa %d - resposta nao e JSON", tentativa)
                time.sleep(intervalo)
                continue

            if 'status' not in resultado:
                if 'error' in resultado or 'message' in resultado:
                    erro = resultado.get('error') or resultado.get('message')
                    raise Exception(f"Erro Judge0: {erro}")
                logger.warning("Tentativa %d - campo 'status' ausente", tentativa)
                time.sleep(intervalo)
                continue

            status_id = resultado['status']['id']
            status_desc = resultado['status']['description']
            logger.info("Tentativa %d - status: %s (id=%d)", tentativa, status_desc, status_id)

            # 1 = In Queue, 2 = Processing
            if status_id in (1, 2):
                time.sleep(intervalo)
                continue

            # Execução finalizada - decodificar campos Base64
            resultado['stdout'] = self._decode_b64(resultado.get('stdout'))
            resultado['stderr'] = self._decode_b64(resultado.get('stderr'))
            resultado['compile_output'] = self._decode_b64(resultado.get('compile_output'))

            logger.info("Execucao finalizada: %s", status_desc)
            return resultado

        raise TimeoutError(
            f"Tempo limite excedido apos {max_tentativas} tentativas"
        )

    @staticmethod
    def _decode_b64(value):
        """Decodifica string Base64 ou retorna string vazia."""
        if not value:
            return ''
        try:
            return base64.b64decode(value).decode('utf-8', errors='replace')
        except Exception:
            return str(value)
