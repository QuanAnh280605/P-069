"""Regression test: application startup must not create schema at runtime.

Alembic is the sole owner of schema creation. The lifespan must never call
``get_async_engine``/``Base.metadata.create_all`` during startup; doing so
creates tables without Alembic version state and can corrupt migrations
(e.g. the Docker dev ``users.role`` drop failure).
"""

from unittest.mock import AsyncMock, MagicMock, patch

from src.main import app, lifespan


async def test_lifespan_does_not_create_schema_at_runtime() -> None:
    dev_settings = MagicMock()
    dev_settings.app_env = "development"
    dev_settings.app_name = "test-app"

    mock_engine = MagicMock()
    begin_cm = AsyncMock()
    begin_cm.__aenter__.return_value = AsyncMock()
    begin_cm.__aexit__.return_value = False
    mock_engine.begin.return_value = begin_cm

    with patch("src.main.get_settings", return_value=dev_settings), patch(
        "src.services.database.get_async_engine", return_value=mock_engine
    ) as mock_get_engine, patch("src.main.start_schema_cron_scheduler") as mock_start, patch(
        "src.main.stop_schema_cron_scheduler"
    ) as mock_stop:
        async with lifespan(app):
            pass

    mock_get_engine.assert_not_called()
    mock_start.assert_called_once()
    mock_stop.assert_called_once()
