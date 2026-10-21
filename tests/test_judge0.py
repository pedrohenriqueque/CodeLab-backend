import asyncio
import base64
from copy import deepcopy
import unittest
from unittest.mock import patch

from backend_v2.app.config.settings import Settings
from backend_v2.app.integrations.judge0 import Judge0Client, Judge0TechnicalFailure


def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://fixture:password@localhost/codelab_v2",
        secret_key="fixture-key-" + "x" * 32,
    )


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return deepcopy(self._data)


class FakeAsyncClient:
    response = FakeResponse(201, {"token": "submission-token"})
    result = FakeResponse(
        200,
        {
            "status": {"id": 3, "description": "Accepted"},
            "stdout": base64.b64encode(b"result").decode(),
            "stderr": None,
            "compile_output": None,
        },
    )
    posted = None

    def __init__(self, **kwargs):
        self.timeout = kwargs["timeout"]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, **kwargs):
        type(self).posted = (url, kwargs)
        return type(self).response

    async def get(self, url, **kwargs):
        return type(self).result


class Judge0ClientTests(unittest.TestCase):
    def test_sends_backend_limits_and_decodes_the_result(self):
        with patch("backend_v2.app.integrations.judge0.httpx.AsyncClient", FakeAsyncClient):
            result = asyncio.run(Judge0Client(settings()).executar_codigo("int main(void) { return 0; }"))

        _, request = FakeAsyncClient.posted
        self.assertEqual(request["json"]["cpu_time_limit"], 2.0)
        self.assertEqual(request["json"]["memory_limit"], 131_072)
        self.assertEqual(result["stdout"], "result")

    def test_links_math_library_for_c(self):
        source = (
            "#include <math.h>\n"
            "int main(void) { volatile double x = 2.0; return sqrt(x) > 0 ? 0 : 1; }"
        )
        for language_id in (None, Judge0Client.C_LANGUAGE_ID):
            with self.subTest(language_id=language_id):
                with patch("backend_v2.app.integrations.judge0.httpx.AsyncClient", FakeAsyncClient):
                    asyncio.run(Judge0Client(settings()).executar_codigo(source, language_id))

                _, request = FakeAsyncClient.posted
                self.assertEqual(request["json"]["source_code"], source)
                self.assertEqual(request["json"]["language_id"], Judge0Client.C_LANGUAGE_ID)
                self.assertEqual(request["json"]["compiler_options"], "-lm")

    def test_does_not_send_c_linker_options_for_other_languages(self):
        with patch("backend_v2.app.integrations.judge0.httpx.AsyncClient", FakeAsyncClient):
            asyncio.run(Judge0Client(settings()).executar_codigo("print(1)", language_id=71))

        _, request = FakeAsyncClient.posted
        self.assertEqual(request["json"]["language_id"], 71)
        self.assertNotIn("compiler_options", request["json"])

    def test_rejected_submission_is_a_technical_failure(self):
        original = FakeAsyncClient.response
        FakeAsyncClient.response = FakeResponse(503, {"message": "unavailable"})
        try:
            with patch("backend_v2.app.integrations.judge0.httpx.AsyncClient", FakeAsyncClient):
                with self.assertRaises(Judge0TechnicalFailure):
                    asyncio.run(Judge0Client(settings()).executar_codigo("int main(void) { return 0; }"))
        finally:
            FakeAsyncClient.response = original
