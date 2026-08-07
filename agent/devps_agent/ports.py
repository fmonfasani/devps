"""Port allocation — the whole reason nobody should ever run `ss -tlnp` by hand again."""

from . import config
from .db import connect


def allocate_port() -> int:
    with connect() as conn:
        used = {row["host_port"] for row in conn.execute("SELECT host_port FROM project_ports")}
    for port in range(config.PORT_RANGE_START, config.PORT_RANGE_END + 1):
        if port not in used:
            return port
    raise RuntimeError(f"no free ports left in {config.PORT_RANGE_START}-{config.PORT_RANGE_END}")
