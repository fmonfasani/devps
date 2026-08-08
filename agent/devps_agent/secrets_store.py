"""Manage .env files for projects."""

from pathlib import Path


def write_env_file(project_name: str, values: dict[str, str]) -> str:
    """Write environment variables to a .env file in /opt/devps/secrets/.

    Returns the path to the written file for use as env_file parameter.
    """
    secrets_dir = Path("/opt/devps/secrets")
    secrets_dir.mkdir(parents=True, exist_ok=True)

    env_file = secrets_dir / f"{project_name}.env"
    with open(env_file, "w") as f:
        for key, value in values.items():
            f.write(f"{key}={value}\n")

    env_file.chmod(0o600)
    return str(env_file)
