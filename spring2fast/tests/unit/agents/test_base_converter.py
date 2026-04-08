"""Tests for base converter helpers."""

from app.agents.converter_agents.base import BaseConverterAgent


def test_resolve_imports_rewrites_known_registry_modules() -> None:
    code = "from app.services.placeholder import OwnerService\n"
    resolved = BaseConverterAgent._resolve_imports(
        code,
        output_registry={"OwnerService": "app/services/owner_service.py"},
        unresolved=["app.services.placeholder"],
    )

    assert "from app.services.owner_service import OwnerService" in resolved


def test_resolve_imports_comments_unknown_modules_only_when_still_missing() -> None:
    code = "from app.services.placeholder import MissingService\n"
    resolved = BaseConverterAgent._resolve_imports(
        code,
        output_registry={"OwnerService": "app/services/owner_service.py"},
        unresolved=["app.services.placeholder"],
    )

    assert "# FIXME: unresolved - from app.services.placeholder import MissingService" in resolved
