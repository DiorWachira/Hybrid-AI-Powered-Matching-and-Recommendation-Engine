from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.fixture(autouse=True)
def isolated_settings_environment(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv(name, raising=False)


def test_development_defaults_remain_available():
    assert Settings(_env_file=None).environment == "development"


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_shared_deployment_rejects_default_signing_secret(environment):
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, environment=environment)


def test_production_rejects_short_signing_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, environment="production", jwt_secret="short")


@pytest.mark.parametrize("origins", [[], ["*"], ["http://localhost:5173"], ["https://example.org/path"]])
def test_production_rejects_unsafe_origins(origins):
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(_env_file=None, environment="production", jwt_secret="test-only-" * 8, cors_origins=origins)


def test_explicit_production_settings_are_accepted():
    settings = Settings(_env_file=None, environment="production", jwt_secret="test-only-" * 8, cors_origins=["https://jobs.example.org"])
    assert settings.environment == "production"


def test_dotenv_path_is_repository_root():
    assert Settings.model_config["env_file"] == Path(__file__).resolve().parents[2] / ".env"