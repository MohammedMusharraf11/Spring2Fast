"""Tests for validation service matching helpers."""

from pathlib import Path

from app.services.validation_service import ValidationService


def test_validation_service_matches_service_impl_to_generated_service_file(tmp_path: Path) -> None:
    services_dir = tmp_path / "app" / "services"
    services_dir.mkdir(parents=True)
    (services_dir / "account.py").write_text("class AccountService: ...\n", encoding="utf-8")

    assert ValidationService()._find_generated_file(services_dir, "AccountServiceImpl") is True


def test_validation_service_matches_contracts_by_normalized_component_name(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    endpoints_dir = output_dir / "app" / "api" / "v1" / "endpoints"
    endpoints_dir.mkdir(parents=True)
    (endpoints_dir / "travel.py").write_text("router = object()\n", encoding="utf-8")

    contract_file = tmp_path / "contracts" / "api" / "travel_controller.md"
    contract_file.parent.mkdir(parents=True)
    contract_file.write_text("# contract\n", encoding="utf-8")

    matched = ValidationService()._find_matching_code(output_dir, contract_file)

    assert matched == "router = object()\n"
