"""IMP-01.02: smoke HTTP, configuração, erros públicos, CORS e isolamento."""

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from backend_v2.app.config.settings import BACKEND_ROOT, Settings
from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.schemas.base import ApiSchema
from backend_v2.app.main import create_app


DATABASE_URL = "postgresql+asyncpg://fixture:fixture_password@localhost:5432/codelab_v2"
SECRET_KEY = "fixture-only-not-for-runtime-" + "x" * 32


class AppTests(unittest.TestCase):
    def settings(self, **changes):
        values = {"database_url": DATABASE_URL, "secret_key": SECRET_KEY}
        values.update(changes)
        return Settings(_env_file=None, **values)

    def test_health_and_openapi_without_external_services(self):
        with patch("sqlalchemy.ext.asyncio.create_async_engine", side_effect=AssertionError("DDL/DB")):
            with patch("httpx.AsyncClient", side_effect=AssertionError("Judge0/HTTP externo")):
                with TestClient(create_app(self.settings())) as client:
                    response = client.get("/api/health")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {"status": "ok"})
                    schema = client.get("/openapi.json")
                    self.assertEqual(schema.status_code, 200)
                    self.assertIn("/api/health", schema.json()["paths"])
                    self.assertIn("/api/sandbox", schema.json()["paths"])
                    self.assertEqual(client.get("/docs").status_code, 200)
                    self.assertIn("/api/auth/login", schema.json()["paths"])

    def test_unknown_route_has_public_error_envelope(self):
        with TestClient(create_app(self.settings())) as client:
            response = client.get("/api/nao-existe")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"erro": "Recurso não encontrado."})

    def test_validation_error_lists_only_field_paths_not_inputs(self):
        class Payload(ApiSchema):
            nome_completo: int

        app = create_app(self.settings())

        @app.post("/api/_teste/validacao")
        async def check(payload: Payload):
            return payload

        secret = "segredo-nao-retornar-abc-123"
        with TestClient(app) as client:
            response = client.post("/api/_teste/validacao", json={"nomeCompleto": secret})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"erro": "Dados inválidos.", "campos": ["body.nomeCompleto"]})
        self.assertNotIn(secret, response.text)

    def test_bad_json_is_422_without_echoing_body(self):
        class Payload(ApiSchema):
            nome_completo: str

        app = create_app(self.settings())

        @app.post("/api/_teste/json")
        async def check(payload: Payload):
            return payload

        with TestClient(app) as client:
            response = client.post(
                "/api/_teste/json", content=b'{"nomeCompleto": "segredo-aqui",',
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("segredo-aqui", response.text)

    def test_unexpected_error_does_not_expose_stack_or_secrets(self):
        app = create_app(self.settings())

        @app.get("/api/_teste/falha")
        async def fail():
            raise RuntimeError("segredo-fonte-e-chave-privada")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/_teste/falha")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"erro": "Erro interno do servidor."})
        self.assertNotIn("segredo", response.text)
        self.assertNotIn("Traceback", response.text)

    def test_expected_errors_and_http_headers(self):
        app = create_app(self.settings())

        @app.get("/api/_teste/esperado")
        async def expected():
            raise CodelabException("Operação inválida.", status_code=409)

        @app.get("/api/_teste/auth")
        async def unauthorized():
            raise HTTPException(401, "Não autenticado.", headers={"WWW-Authenticate": "Bearer"})

        @app.get("/api/_teste/erro-interno")
        async def internal():
            raise CodelabException("não revelar segredo", status_code=500)

        with TestClient(app) as client:
            expected_response = client.get("/api/_teste/esperado")
            unauthorized_response = client.get("/api/_teste/auth")
            internal_response = client.get("/api/_teste/erro-interno")
        self.assertEqual(expected_response.status_code, 409)
        self.assertEqual(expected_response.json(), {"erro": "Operação inválida."})
        self.assertEqual(unauthorized_response.status_code, 401)
        self.assertEqual(unauthorized_response.headers["www-authenticate"], "Bearer")
        self.assertEqual(internal_response.json(), {"erro": "Erro interno do servidor."})

    def test_cors_allows_only_explicit_origins_and_auth_header(self):
        app = create_app(self.settings(cors_origins=["http://localhost:5173"]))
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        with TestClient(app) as client:
            accepted = client.options("/api/health", headers=headers)
            rejected = client.options("/api/health", headers={**headers, "Origin": "https://outro.example"})
            simple = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.headers["access-control-allow-origin"], "http://localhost:5173")
        self.assertIn("authorization", accepted.headers["access-control-allow-headers"].lower())
        self.assertNotIn("access-control-allow-credentials", accepted.headers)
        self.assertEqual(rejected.status_code, 400)
        self.assertNotIn("access-control-allow-origin", rejected.headers)
        self.assertEqual(simple.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_cors_default_denies_browser_origin(self):
        with TestClient(create_app(self.settings())) as client:
            response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_reject_malformed_cors_origin(self):
        for origin in ("*", "http://localhost:5173/path", "https://u:password@host", "http://host:foo", "file:///tmp", "https://host?key=secret"):
            with self.subTest(origin=origin), self.assertRaises(PydanticValidationError):
                self.settings(cors_origins=[origin])
        with self.assertRaises(PydanticValidationError):
            self.settings(cors_origins=["http://localhost:5173", "http://localhost:5173"])

    def test_camel_case_schema_rejects_unknown_fields(self):
        class Payload(ApiSchema):
            nome_completo: str

        payload = Payload(nome_completo="Maria")
        self.assertEqual(payload.model_dump(by_alias=False), {"nome_completo": "Maria"})
        self.assertEqual(payload.model_dump(by_alias=True), {"nomeCompleto": "Maria"})
        self.assertEqual(payload.model_dump(mode="json"), {"nomeCompleto": "Maria"})
        self.assertEqual(Payload.model_validate({"nomeCompleto": "Maria"}), payload)
        with self.assertRaises(PydanticValidationError):
            Payload.model_validate({"nomeCompleto": "Maria", "perfil": "ADMIN"})

    def test_importing_main_does_not_load_config_or_use_network(self):
        script = '''
from unittest.mock import patch
from pydantic_settings import BaseSettings
with patch.object(BaseSettings, '__init__', side_effect=AssertionError('eager settings')):
    with patch('socket.socket.connect', side_effect=AssertionError('network on import')):
        from backend_v2.app.main import app, create_app
assert callable(app)
'''
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() not in {"PYTHONPATH", "DATABASE_URL", "SECRET_KEY"}
                       and not key.upper().startswith("CODELAB_V2_")}
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=BACKEND_ROOT.parent,
            env=environment, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_asgi_entrypoint_initializes_only_when_called(self):
        from backend_v2.app import main as main_module

        main_module._runtime.cache_clear()
        try:
            with patch.object(main_module, "get_settings", return_value=self.settings()) as load:
                with TestClient(main_module.app) as client:
                    self.assertEqual(client.get("/api/health").json(), {"status": "ok"})
                load.assert_called_once()
        finally:
            main_module._runtime.cache_clear()

    def test_asgi_entrypoint_rejects_invalid_config_on_startup(self):
        from backend_v2.app import main as main_module

        main_module._runtime.cache_clear()
        try:
            with patch.object(main_module, "get_settings", side_effect=ValueError("configuração inválida")):
                with self.assertRaisesRegex(ValueError, "configuração inválida"):
                    with TestClient(main_module.app):
                        pass
        finally:
            main_module._runtime.cache_clear()

    def test_invalid_configuration_fails_explicitly_before_serving(self):
        with patch("backend_v2.app.main.get_settings", side_effect=ValueError("configuração ausente")):
            with self.assertRaisesRegex(ValueError, "configuração ausente"):
                create_app()


if __name__ == "__main__":
    unittest.main()
