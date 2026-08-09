"""Input/output schemas for MCP tools."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# --- Projects ---

class ProjectsListRequest(BaseModel):
    """Input for devps.projects.list tool."""
    filter_owner: Optional[str] = Field(None, description="Filter by project owner")
    filter_status: Optional[str] = Field(None, description="Filter by status (deployed, build_failed, etc)")


class ProjectPort(BaseModel):
    """Port mapping for a project."""
    service: str
    host_port: int
    container_port: int


class ProjectEvent(BaseModel):
    """Last event for a project."""
    kind: str
    success: bool
    created_at: str


class ProjectInfo(BaseModel):
    """Project information."""
    name: str
    managed_by: str
    repo_url: Optional[str] = None
    git_ref: Optional[str] = None
    git_sha: Optional[str] = None
    domain: Optional[str] = None
    status: str
    health_status: Optional[str] = None
    restart_count: int = 0
    owner: Optional[str] = None
    created_at: str
    updated_at: str
    ports: List[ProjectPort] = Field(default_factory=list)
    last_event: Optional[ProjectEvent] = None


class ProjectsListResponse(BaseModel):
    """Output for devps.projects.list tool."""
    projects: List[ProjectInfo]


class ProjectGetRequest(BaseModel):
    """Input for devps.projects.get tool."""
    name: str = Field(description="Project name")


class ProjectGetResponse(BaseModel):
    """Output for devps.projects.get tool."""
    project: ProjectInfo


# --- Tool definitions ---

class ToolDefinition(BaseModel):
    """MCP tool definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class ToolCallRequest(BaseModel):
    """MCP tool call request."""
    name: str
    arguments: Dict[str, Any]


class ToolCallResponse(BaseModel):
    """MCP tool call response."""
    success: bool
    content: str
    error: Optional[str] = None
