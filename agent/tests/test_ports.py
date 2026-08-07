def test_allocate_port_picks_lowest_free(fresh_modules):
    _, _, ports, registry = fresh_modules

    assert ports.allocate_port() == 40000

    registry.upsert_project("a", "devps")
    registry.set_port("a", "web", 40000, 3000)

    assert ports.allocate_port() == 40001


def test_allocate_port_reuses_gap(fresh_modules):
    _, _, ports, registry = fresh_modules

    registry.upsert_project("a", "devps")
    registry.set_port("a", "web", 40000, 3000)
    registry.set_port("a", "api", 40001, 8000)
    registry.upsert_project("b", "devps")
    registry.set_port("b", "web", 40002, 3000)

    registry.delete_project("a")  # cascades, frees 40000 and 40001

    assert ports.allocate_port() == 40000


def test_allocate_port_raises_when_exhausted(fresh_modules):
    _, _, ports, registry = fresh_modules

    registry.upsert_project("a", "devps")
    for i, port in enumerate(range(40000, 40004)):
        registry.set_port("a", f"svc{i}", port, 3000 + i)

    import pytest

    with pytest.raises(RuntimeError, match="no free ports"):
        ports.allocate_port()
