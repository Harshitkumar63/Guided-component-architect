"""
validator.py — Deterministic validation engine for generated Angular components.

This module enforces a strict design-system contract and returns a structured
validation report suitable for agentic retry loops.
"""

from __future__ import annotations

import re
from typing import Dict, List, TypedDict


class ValidationReport(TypedDict):
    """Structured validation report returned to the agent loop."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]


def validate(code: str, tokens: Dict[str, str]) -> ValidationReport:
    """Run all validation layers and return a structured report."""
    errors: List[str] = []
    warnings: List[str] = []

    errors.extend(validate_design_tokens(code, tokens))
    errors.extend(validate_colors(code, tokens))
    errors.extend(validate_syntax(code))
    errors.extend(validate_structure(code))

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def validate_component(code: str, tokens: Dict[str, str]) -> ValidationReport:
    """Backward-compatible wrapper used by existing call sites."""
    return validate(code, tokens)


def validate_design_tokens(code: str, tokens: Dict[str, str]) -> List[str]:
    """Ensure core design tokens are present in generated source."""
    errors: List[str] = []

    primary = tokens["primary_color"].lower()
    if primary not in code.lower():
        errors.append("MISSING_PRIMARY_COLOR: Primary design token not found.")

    if tokens["border_radius"] not in code:
        errors.append("MISSING_BORDER_RADIUS: Border radius token not found.")

    if tokens["font_family"].lower() not in code.lower():
        errors.append("MISSING_FONT_FAMILY: Font family token not found.")

    return errors


def validate_colors(code: str, tokens: Dict[str, str]) -> List[str]:
    """
    Strict color validator.

    Rules:
    - Extract all hex colors and allow ONLY exact design-system hex tokens.
    - Reject rgba(), rgb(), hsl(), hsla(), hwb().
    - Reject named colors (including black, white).
    """
    errors: List[str] = []

    allowed_tokens = {
        value.lower()
        for value in tokens.values()
        if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value)
    }

    # 1) Reject functional color formats.
    func_pattern = re.compile(r"\b(rgba?|hsla?|hwb)\s*\([^)]*\)", re.IGNORECASE)
    for match in func_pattern.finditer(code):
        errors.append(
            f"UNAUTHORIZED_COLOR: {match.group(0)} is not part of the design system."
        )

    # 2) Reject non-token hex literals.
    hex_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    for match in hex_pattern.finditer(code):
        found = match.group(0)
        if found.lower() not in allowed_tokens:
            errors.append(
                f"UNAUTHORIZED_COLOR: {found} is not part of the design system."
            )

    # 3) Reject named colors in CSS-like declarations.
    named_colors = {
        "black",
        "white",
        "red",
        "blue",
        "green",
        "yellow",
        "orange",
        "purple",
        "pink",
        "brown",
        "gray",
        "grey",
        "teal",
        "navy",
        "maroon",
        "cyan",
        "magenta",
        "gold",
        "silver",
        "lime",
        "olive",
        "coral",
        "tomato",
        "violet",
        "indigo",
    }
    named_pattern = re.compile(r":\s*([a-zA-Z]+)\b")
    for match in named_pattern.finditer(code):
        candidate = match.group(1).lower()
        if candidate in named_colors:
            errors.append(
                f"UNAUTHORIZED_COLOR: {match.group(1)} is not part of the design system."
            )

    return _dedupe(errors)


def validate_syntax(code: str) -> List[str]:
    """
    Stack-based syntax validation.

    Detects:
    - Early closing braces/brackets/parentheses
    - Missing closing braces/brackets/parentheses
    - Improper nesting
    - Unclosed template strings and string literals
    """
    errors: List[str] = []

    pairs = {"(": ")", "[": "]", "{": "}"}
    inverse = {")": "(", "]": "[", "}": "{"}
    stack: List[tuple[str, int]] = []

    i = 0
    line = 1
    length = len(code)

    while i < length:
        ch = code[i]

        if ch == "\n":
            line += 1
            i += 1
            continue

        # Single-line comments
        if ch == "/" and i + 1 < length and code[i + 1] == "/":
            i += 2
            while i < length and code[i] != "\n":
                i += 1
            continue

        # Multi-line comments
        if ch == "/" and i + 1 < length and code[i + 1] == "*":
            i += 2
            while i < length - 1:
                if code[i] == "\n":
                    line += 1
                if code[i] == "*" and code[i + 1] == "/":
                    i += 2
                    break
                i += 1
            else:
                errors.append("SYNTAX_ERROR: Unclosed multiline comment.")
            continue

        # String / template literals with unclosed detection
        if ch in {"'", '"', "`"}:
            quote = ch
            start_line = line
            i += 1
            closed = False
            while i < length:
                if code[i] == "\n":
                    line += 1
                if code[i] == "\\" and i + 1 < length:
                    i += 2
                    continue
                if code[i] == quote:
                    i += 1
                    closed = True
                    break
                i += 1

            if not closed:
                if quote == "`":
                    errors.append(
                        f"SYNTAX_ERROR: Unclosed template string starting on line {start_line}."
                    )
                else:
                    errors.append(
                        f"SYNTAX_ERROR: Unclosed string literal starting on line {start_line}."
                    )
            continue

        # Bracket stack matching
        if ch in pairs:
            stack.append((ch, line))
        elif ch in inverse:
            if not stack:
                errors.append(
                    f"SYNTAX_ERROR: Early closing '{ch}' found on line {line}."
                )
            else:
                opener, opener_line = stack.pop()
                if opener != inverse[ch]:
                    expected = pairs[opener]
                    errors.append(
                        f"SYNTAX_ERROR: Improper nesting on line {line}; expected '{expected}' "
                        f"to close '{opener}' opened on line {opener_line}, got '{ch}'."
                    )

        i += 1

    for opener, opener_line in stack:
        errors.append(
            f"SYNTAX_ERROR: Missing closing '{pairs[opener]}' for '{opener}' opened on line {opener_line}."
        )

    return errors


def validate_structure(code: str) -> List[str]:
    """
    Validate Angular component structure.

    Required:
    - @Component decorator
    - export class declaration
    - at least one typed property
    - at least one method
    - source ends with closing brace
    """
    has_component = "@Component" in code
    class_match = re.search(r"\bexport\s+class\s+\w+\s*\{", code)
    ends_with_brace = code.rstrip().endswith("}")

    class_body = _extract_class_body(code, class_match.start()) if class_match else ""

    # Typed property, e.g. foo: string = 'bar';  or  total: number;
    has_typed_property = bool(
        re.search(
            r"\b(?:public|private|protected)?\s*\w+\s*:\s*"
            r"[A-Za-z_][A-Za-z0-9_<>,\[\]\s|]*\s*(=|;)",
            class_body,
        )
    )

    # Method signature, e.g. submit(): void { ... }
    has_method = bool(
        re.search(
            r"\b\w+\s*\([^)]*\)\s*(?::\s*[A-Za-z_][A-Za-z0-9_<>,\[\]\s|]*)?\s*\{",
            class_body,
        )
    )

    if not all([has_component, class_match, has_typed_property, has_method, ends_with_brace]):
        return ["INCOMPLETE_STRUCTURE: Angular component structure invalid."]

    return []


def _dedupe(items: List[str]) -> List[str]:
    """Return list without duplicates while preserving order."""
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _extract_class_body(code: str, class_start_index: int) -> str:
    """Extract the first class body using brace stack from class declaration index."""
    brace_open_index = code.find("{", class_start_index)
    if brace_open_index == -1:
        return ""

    depth = 0
    i = brace_open_index
    start = brace_open_index + 1

    while i < len(code):
        char = code[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return code[start:i]
        i += 1

    return ""
