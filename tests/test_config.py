import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from backend_v2 import check_config
from backend_v2.app.config.settings import BACKEND_ROOT, Settings


# Valores sintéticos: nunca conectamos ao banco nem usamos credenciais reais.
DATABASE_URL = "postgresql+asyncpg://fixture:fixture_password@localhost:5432/codelab_v2"
SECRET_KEY = "fixture-only-not-for-runtime-" + "x" * 32


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def settings(self, **overrides):
        values = {"database_url": DATABASE_URL, "secret_key": SECRET_KEY}
        values.update(overrides)
        return Settings(_env_file=None, **values)

    def test_valid_configuration_uses_postgresql_without_connecting(self):
        settings = self.settings()
        self.assertEqual(settings.database_url.get_secret_value(), DATABASE_URL)
        self.assertEqual(settings.environment, "development")
        self.assertEqual(settings.access_token_expire_minutes, 10080)

    def test_missing_configuration_has_no_legacy_defaults(self):
        with self.assertRaises(ValidationError):
            Settings(_env_file=None)

    def test_unprefixed_legacy_variables_cannot_configure_v2(self):
        os.environ.update(DATABASE_URL=DATABASE_URL, SECRET_KEY=SECRET_KEY)
        with self.assertRaises(ValidationError):
            Settings(_env_file=None)

    def test_only_prefixed_environment_is_consumed(self):
        os.environ.update(
            DATABASE_URL="sqlite:///legacy.db",
            SECRET_KEY="legacy",
            CODELAB_V2_DATABASE_URL=DATABASE_URL,
            CODELAB_V2_SECRET_KEY=SECRET_KEY,
        )
        settings = Settings(_env_file=None)
        self.assertEqual(settings.database_url.get_secret_value(), DATABASE_URL)

    def test_invalid_or_legacy_database_is_rejected(self):
        for url in (
            "not-a-url",
            "sqlite:///legacy.db",
            "postgresql://fixture:password@localhost/codelab_v2",
            "postgresql+asyncpg://fixture:password@localhost/codelab",
            "postgresql+asyncpg://fixture:password@localhost/",
            "postgresql+asyncpg://fixture:password@localhost:invalid/codelab_v2",
            "postgresql+asyncpg:///codelab_v2",
            DATABASE_URL + "?database=codelab",
            DATABASE_URL + "?host=legacy.example",
        ):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                self.settings(database_url=url)

    def test_test_environment_requires_separate_database(self):
        with self.assertRaises(ValidationError):
            self.settings(environment="test")
        settings = self.settings(
            environment="test", database_url=DATABASE_URL + "_test"
        )
        self.assertEqual(settings.environment, "test")
        with self.assertRaises(ValidationError):
            self.settings(environment="production", database_url=DATABASE_URL + "_test")

    def test_invalid_environment_and_security_configuration_are_rejected(self):
        for values in (
            {"environment": "unknown"},
            {"secret_key": ""},
            {"secret_key": "short"},
            {"secret_key": " " * 64},
            {"algorithm": "none"},
            {"access_token_expire_minutes": 0},
        ):
            with self.subTest(values=list(values)), self.assertRaises(ValidationError):
                self.settings(**values)

    def test_judge0_url_is_http_and_has_no_embedded_credentials(self):
        for url in (
            "file:///tmp/judge0",
            "http://user:password@localhost:2358",
            "http://localhost:2358?api_key=private",
            "http://localhost:2358#private",
        ):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                self.settings(judge0_api_url=url)

    def test_representation_masks_database_and_keys(self):
        settings = self.settings(judge0_api_key="fixture_judge0_key")
        representation = repr(settings)
        for secret in (DATABASE_URL, "fixture_password", SECRET_KEY, "fixture_judge0_key"):
            self.assertNotIn(secret, representation)

    def test_env_file_is_anchored_to_backend_v2_not_current_directory(self):
        self.assertEqual(Settings.model_config["env_file"], BACKEND_ROOT / ".env")
        self.assertTrue(Settings.model_config["env_file"].is_absolute())
        with tempfile.TemporaryDirectory(dir=BACKEND_ROOT) as directory:
            root = Path(directory)
            own_env = root / "own.env"
            own_env.write_text(
                f"CODELAB_V2_DATABASE_URL={DATABASE_URL}\n"
                f"CODELAB_V2_SECRET_KEY={SECRET_KEY}\n",
                encoding="utf-8",
            )
            (root / ".env").write_text("FOREIGN_SETTING=not_ours\n", encoding="utf-8")
            with patch.dict(Settings.model_config, {"env_file": own_env}):
                with contextlib.chdir(root):
                    settings = Settings()
            self.assertEqual(settings.database_url.get_secret_value(), DATABASE_URL)

    def test_copying_legacy_dotenv_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=BACKEND_ROOT) as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                f"DATABASE_URL={DATABASE_URL}\nSECRET_KEY={SECRET_KEY}\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValidationError):
                Settings(_env_file=env_file)

    def test_prefixed_environment_overrides_own_dotenv(self):
        with tempfile.TemporaryDirectory(dir=BACKEND_ROOT) as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                f"CODELAB_V2_DATABASE_URL={DATABASE_URL}\n"
                f"CODELAB_V2_SECRET_KEY={SECRET_KEY}\n",
                encoding="utf-8",
            )
            os.environ.update(
                CODELAB_V2_ENVIRONMENT="test",
                CODELAB_V2_DATABASE_URL=DATABASE_URL + "_test",
            )
            settings = Settings(_env_file=env_file)
            self.assertEqual(settings.environment, "test")
            self.assertTrue(settings.database_url.get_secret_value().endswith("_test"))

    def test_checker_reports_success_without_exposing_configuration(self):
        output = io.StringIO()
        with patch.object(check_config, "get_settings", side_effect=self.settings):
            with contextlib.redirect_stdout(output):
                self.assertEqual(check_config.main(), 0)
        self.assertIn("Nenhuma conexão", output.getvalue())
        for secret in (DATABASE_URL, SECRET_KEY):
            self.assertNotIn(secret, output.getvalue())

    def test_checker_returns_failure_without_echoing_invalid_secrets(self):
        output = io.StringIO()
        invalid_url = "postgresql+asyncpg://fixture:private_value@localhost/codelab"
        with patch.object(
            check_config, "get_settings",
            side_effect=lambda: self.settings(database_url=invalid_url),
        ):
            with contextlib.redirect_stderr(output):
                self.assertEqual(check_config.main(), 1)
        self.assertIn("Configuração inválida", output.getvalue())
        self.assertNotIn("private_value", output.getvalue())
        self.assertNotIn(SECRET_KEY, output.getvalue())


if __name__ == "__main__":
    unittest.main()
