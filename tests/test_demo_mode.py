"""Unit tests for DEMO_MODE behavior without external API access."""

from __future__ import annotations

from generator import generate_component, load_design_system, regenerate_component


def test_generate_component_in_demo_mode(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    tokens = load_design_system()

    code = generate_component("A simple login card", tokens=tokens)

    assert "@Component" in code
    assert "export class" in code
    assert "#6366f1" in code
    assert "#f1f5f9" in code


def test_regenerate_component_in_demo_mode(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    tokens = load_design_system()

    code = regenerate_component(
        original_code="broken",
        errors=["dummy error"],
        description="A card",
        tokens=tokens,
    )

    assert "@Component" in code
    assert "LoginCardComponent" in code
