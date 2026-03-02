"""Unit tests for deterministic validator rules."""

from __future__ import annotations

from validator import validate_colors, validate_structure, validate_syntax


TOKENS = {
    "primary_color": "#6366f1",
    "secondary_color": "#f1f5f9",
    "border_radius": "8px",
    "font_family": "Inter",
    "spacing": "16px",
}


def test_validate_colors_allows_only_design_hex_tokens() -> None:
    code = """
    .card {
      background: #f1f5f9;
      color: #6366f1;
      border: 1px solid #6366f1;
    }
    """
    errors = validate_colors(code, TOKENS)
    assert errors == []


def test_validate_colors_rejects_rgba_rgb_hsl_named_and_unknown_hex() -> None:
    code = """
    .card {
      background: rgba(99, 102, 241, 0.2);
      border-color: rgb(99, 102, 241);
      color: hsl(210, 50%, 50%);
      box-shadow: 0 0 8px #ffffff;
      outline-color: black;
    }
    """
    errors = validate_colors(code, TOKENS)

    assert any("UNAUTHORIZED_COLOR: rgba" in item for item in errors)
    assert any("UNAUTHORIZED_COLOR: rgb" in item for item in errors)
    assert any("UNAUTHORIZED_COLOR: hsl" in item for item in errors)
    assert any("UNAUTHORIZED_COLOR: #ffffff" in item for item in errors)
    assert any("UNAUTHORIZED_COLOR: black" in item for item in errors)


def test_validate_syntax_detects_early_closing_and_unclosed_template_string() -> None:
    code = """
    @Component({
      template: `
        <div>
      
    })
    export class TestComponent {
      total: number = 1;
      submit(): void {
      }
    }
    }
    """
    errors = validate_syntax(code)
    assert any("Unclosed template string" in item for item in errors)
    assert len(errors) >= 1


def test_validate_structure_requires_typed_property_and_method() -> None:
    invalid_code = """
    @Component({selector: 'x', template: '', styles: []})
    export class BrokenComponent {
      title = 'missing-type';
    }
    """

    valid_code = """
    @Component({selector: 'x', template: '', styles: []})
    export class ValidComponent {
      title: string = 'ok';

      submit(): void {
        return;
      }
    }
    """

    assert validate_structure(invalid_code) == [
        "INCOMPLETE_STRUCTURE: Angular component structure invalid."
    ]
    assert validate_structure(valid_code) == []
