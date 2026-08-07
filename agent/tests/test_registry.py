def test_upsert_then_get(fresh_modules):
    _, _, _, registry = fresh_modules

    registry.upsert_project(
        "skillos",
        "devps",
        "https://example.com/repo.git",
        "main",
        "abc123",
        "skillos.example.com",
        "deployed",
    )
    registry.set_port("skillos", "backend", 40000, 3001)
    registry.set_port("skillos", "frontend", 40001, 3000)

    project = registry.get_project("skillos")
    assert project is not None
    assert project["managed_by"] == "devps"
    assert project["git_sha"] == "abc123"
    assert {p["service"] for p in project["ports"]} == {"backend", "frontend"}


def test_upsert_twice_updates_not_duplicates(fresh_modules):
    _, _, _, registry = fresh_modules

    registry.upsert_project("a", "devps", git_sha="sha1")
    registry.upsert_project("a", "devps", git_sha="sha2")

    assert len(registry.list_projects()) == 1
    assert registry.get_project("a")["git_sha"] == "sha2"


def test_adopted_project_has_no_repo(fresh_modules):
    _, _, _, registry = fresh_modules

    registry.upsert_project("legacy-site", "adopted", domain="legacy.example.com", status="adopted")

    project = registry.get_project("legacy-site")
    assert project["managed_by"] == "adopted"
    assert project["repo_url"] is None


def test_get_missing_project_returns_none(fresh_modules):
    _, _, _, registry = fresh_modules
    assert registry.get_project("nope") is None


def test_delete_project_cascades_ports(fresh_modules):
    _, _, ports, registry = fresh_modules

    registry.upsert_project("a", "devps")
    registry.set_port("a", "web", 40000, 3000)
    registry.delete_project("a")

    assert registry.get_project("a") is None
    assert ports.allocate_port() == 40000  # port freed by the cascade delete
