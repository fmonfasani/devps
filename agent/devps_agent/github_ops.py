"""GitHub API operations for creating repos and initial setup."""

import subprocess
import json
from pathlib import Path

from . import config


def create_repo(repo_name: str, github_token: str, description: str = "") -> str:
    """Create a repository on GitHub and return the clone URL.

    Args:
        repo_name: Repository name (e.g., "my-app")
        github_token: GitHub Personal Access Token
        description: Optional repo description

    Returns:
        Clone URL (https://github.com/username/repo-name.git)

    Raises:
        RuntimeError: If API call fails
    """
    if not github_token:
        raise RuntimeError("GITHUB_TOKEN not configured")

    # Get GitHub username from token
    result = subprocess.run(
        ["curl", "-sS", "-H", f"Authorization: token {github_token}",
         "https://api.github.com/user"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get GitHub user: {result.stderr}")

    user_data = json.loads(result.stdout)
    if "login" not in user_data:
        raise RuntimeError(f"Invalid GitHub token: {user_data.get('message', 'unknown error')}")

    username = user_data["login"]

    # Create repository via GitHub API
    payload = json.dumps({
        "name": repo_name,
        "description": description,
        "private": False,
        "auto_init": True,
        "gitignore_template": "Node",
    })

    result = subprocess.run(
        ["curl", "-sS", "-X", "POST",
         "-H", f"Authorization: token {github_token}",
         "-H", "Content-Type: application/json",
         "https://api.github.com/user/repos",
         "-d", payload],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create repo: {result.stderr}")

    repo_data = json.loads(result.stdout)
    if "clone_url" not in repo_data:
        error_msg = repo_data.get("message", "unknown error")
        raise RuntimeError(f"GitHub API error: {error_msg}")

    return repo_data["clone_url"]


def init_repo_with_compose(project_dir: Path, project_name: str):
    """Initialize repo with basic docker-compose.yml and README.

    Args:
        project_dir: Path to clone directory
        project_name: Project name for README
    """
    # Create basic docker-compose.yml
    compose_content = f"""version: '3.8'

services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
"""

    with open(project_dir / "docker-compose.yml", "w") as f:
        f.write(compose_content)

    # Create basic .gitignore if not exists
    if not (project_dir / ".gitignore").exists():
        gitignore = """node_modules/
.env
.env.local
.DS_Store
dist/
build/
*.log
"""
        with open(project_dir / ".gitignore", "w") as f:
            f.write(gitignore)

    # Create basic Dockerfile if not exists
    if not (project_dir / "Dockerfile").exists():
        dockerfile = """FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
"""
        with open(project_dir / "Dockerfile", "w") as f:
            f.write(dockerfile)

    # Create README if not exists
    if not (project_dir / "README.md").exists():
        readme = f"""# {project_name}

This project was auto-created by devps.

## Development

\`\`\`bash
npm install
npm run dev
\`\`\`

## Docker

\`\`\`bash
docker compose up --build
\`\`\`
"""
        with open(project_dir / "README.md", "w") as f:
            f.write(readme)

    # Add and commit
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit: docker-compose setup"],
        cwd=project_dir,
        check=True,
    )
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=project_dir, check=True)
