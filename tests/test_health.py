"""Tests for the /health endpoint and basic CLI commands.

The "db up" tests need Postgres running (docker compose locally, a service container in CI).
The "db down" tests fake the connection check, so they run anywhere.
"""

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tide import __version__, db
from tide.api.main import app as api_app
from tide.cli import app as cli_app

client = TestClient(api_app)
runner = CliRunner()


def test_health_ok_when_db_reachable():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_503_when_db_unreachable(monkeypatch):
    monkeypatch.setattr(db, "check_connection", lambda: False)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["db"] == "unreachable"


def test_cli_version():
    result = runner.invoke(cli_app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_db_check_ok():
    result = runner.invoke(cli_app, ["db-check"])
    assert result.exit_code == 0
    assert "database: ok" in result.output


def test_cli_db_check_fails_when_db_unreachable(monkeypatch):
    monkeypatch.setattr(db, "check_connection", lambda: False)
    result = runner.invoke(cli_app, ["db-check"])
    assert result.exit_code == 1
