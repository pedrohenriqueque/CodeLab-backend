import ast
import importlib
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from backend_v2.app.config.settings import BACKEND_ROOT


class IsolationTests(unittest.TestCase):
    def test_current_entrypoint_and_modules_import_without_configuration_or_io(self):
        # Processo novo para não mascarar efeitos de import com sys.modules/cache.
        script = """
import importlib
import sys
from unittest.mock import patch
from pydantic_settings import BaseSettings

modules = (
    'backend_v2',
    'backend_v2.app.config.settings',
    'backend_v2.app.config.database',
    'backend_v2.app.models',
    'backend_v2.manage_db',
    'backend_v2.app.core.security',
    'backend_v2.app.core.exceptions',
    'backend_v2.app.integrations.judge0',
    'backend_v2.app.services.gerador_service',
    'backend_v2.check_config',
)
with patch.object(BaseSettings, '__init__', side_effect=AssertionError('eager settings')):
    with patch('socket.socket.connect', side_effect=AssertionError('network on import')):
        for name in modules:
            importlib.import_module(name)
assert not any(name == 'app' or name.startswith('app.') or name == 'backend'
               or name.startswith('backend.') for name in sys.modules)
"""
        environment = {
            key: value for key, value in os.environ.items()
            if not key.upper().startswith("CODELAB_V2_")
            and key.upper() not in {"DATABASE_URL", "SECRET_KEY", "PYTHONPATH"}
        }
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=BACKEND_ROOT.parent,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_v2_imports_do_not_reference_legacy_or_ambiguous_app(self):
        paths = [BACKEND_ROOT / "check_config.py", BACKEND_ROOT / "__init__.py"]
        paths.extend((BACKEND_ROOT / "app").rglob("*.py"))
        for source in paths:
            tree = ast.parse(source.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    modules = [node.module or ""]
                for module in modules:
                    with self.subTest(file=source.name, module=module):
                        self.assertNotIn(module.split(".")[0], {"app", "backend"})

    def test_imports_resolve_inside_backend_v2(self):
        for name in (
            "backend_v2.app.core.security",
            "backend_v2.app.integrations.judge0",
            "backend_v2.check_config",
        ):
            module = importlib.import_module(name)
            self.assertTrue(Path(module.__file__).resolve().is_relative_to(BACKEND_ROOT))

    def test_judge0_candidate_has_no_global_client(self):
        module = importlib.import_module("backend_v2.app.integrations.judge0")
        self.assertFalse(hasattr(module, "judge0_client"))
        with patch.object(module, "httpx") as httpx, patch.dict(os.environ, {}, clear=True):
            from backend_v2.app.config.settings import Settings

            settings = Settings(
                _env_file=None,
                database_url="postgresql+asyncpg://fixture:password@localhost/codelab_v2",
                secret_key="fixture-key-" + "x" * 32,
                judge0_api_key="fixture_api_key",
            )
            client = module.Judge0Client(settings)
            self.assertEqual(client.api_url, "http://localhost:2358")
            self.assertEqual(client.api_key, "fixture_api_key")
            httpx.AsyncClient.assert_not_called()


if __name__ == "__main__":
    unittest.main()
