import importlib
import os

import pytest


@pytest.fixture
def fresh_modules(tmp_path, monkeypatch):
    """Point config at a throwaway sqlite DB and reload the modules that
    read settings at import time, so each test gets an isolated registry."""
    monkeypatch.setenv("DEVPS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DEVPS_TOKEN", "test-token")
    monkeypatch.setenv("DEVPS_PORT_RANGE_START", "40000")
    monkeypatch.setenv("DEVPS_PORT_RANGE_END", "40003")
    for name in (
        "devps_agent.config",
        "devps_agent.db",
        "devps_agent.ports",
        "devps_agent.registry",
    ):
        if name in os.sys.modules:
            importlib.reload(os.sys.modules[name])
    from devps_agent import config, db, ports, registry

    db.init_db()
    return config, db, ports, registry
