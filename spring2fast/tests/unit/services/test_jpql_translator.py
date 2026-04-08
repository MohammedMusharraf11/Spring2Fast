"""Tests for JPQL translation helpers."""

from app.agents.tools.jpql_translator import JPQLTranslator


def test_jpql_translator_translates_basic_select_query() -> None:
    translator = JPQLTranslator()

    translated = translator.translate_jpql(
        '@Query("SELECT u FROM User u WHERE u.email = :email")',
        "User",
    )

    assert translated is not None
    assert "select(User)" in translated
    assert "User.email == email" in translated


def test_jpql_translator_translates_method_name_conventions() -> None:
    translator = JPQLTranslator()

    translated = translator.translate_method_name("existsByEmail", "User")

    assert translated is not None
    assert "exists().where(User.email == email)" in translated
