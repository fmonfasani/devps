"""Request/response schemas."""

from pydantic import BaseModel, model_validator


class DeployRequest(BaseModel):
    repo_url: str
    git_ref: str = "main"
    compose_file: str = "docker-compose.yml"
    domain: str | None = None
    # service name -> container-internal port, e.g. {"backend": 3001, "frontend": 3000}
    services: dict[str, int]
    # which key of `services` gets the nginx vhost; required if domain is set
    primary_service: str | None = None

    @model_validator(mode="after")
    def _primary_required_with_domain(self) -> "DeployRequest":
        if self.domain and self.primary_service is None:
            raise ValueError("primary_service is required when domain is set")
        if self.primary_service is not None and self.primary_service not in self.services:
            raise ValueError("primary_service must be a key in services")
        return self


class AdoptRequest(BaseModel):
    container_name: str
    domain: str | None = None
