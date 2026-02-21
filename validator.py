"""
validator.py — Deterministic, extensible design-system linter for Angular components.

Architecture

Validation is split into four independent sub-validators, each responsible for
a distinct concern.  New rules can be added by extending any sub-validator or
by introducing an additional sub-validator function.

    validate_design_tokens()  — checks required token presence (colour, radius, font)
    validate_colors()         — strict colour enforcement; rejects rgba/rgb/hsl/hex non-tokens
    validate_structure()      — Angular component structural completeness
    validate_syntax()         — stack-based bracket/brace/parenthesis balance

The top-level validate_component() aggregates all sub-validators and returns a
structured report dict:

    {
        "is_valid": bool,        # True only when errors list is empty
        "errors":   List[str],   # Hard failures — must be fixed before acceptance
        "warnings": List[str],   # Soft notices — informational, not blocking
    }

All checks are deterministic — pure regex and string analysis, zero LLM calls.
"""

from __future__ import annotations

import re
from typing import Dict, List

# 
# Constants
# 

# CSS keywords that are structurally valid and never represent a colour value.
_SAFE_CSS_KEYWORDS: frozenset = frozenset({
    "transparent", "inherit", "currentcolor", "initial", "unset", "none",
})

# A broad list of named CSS colours that are explicitly forbidden.
_NAMED_COLORS: frozenset = frozenset({
    "red", "blue", "green", "yellow", "orange", "pink", "purple",
    "brown", "cyan", "magenta", "lime", "teal", "maroon", "navy",
    "olive", "aqua", "fuchsia", "coral", "crimson", "gold",
    "indigo", "khaki", "lavender", "salmon", "sienna", "tan",
    "tomato", "turquoise", "violet", "wheat",
})


# 
# Public top-level validator
# 

def validate_component(code: str, tokens: Dict[str, str]) -> Dict:
    """
    Run all sub-validators and return a structured validation report.

    Parameters
    ----------
    code : str
        Raw Angular TypeScript source to validate.
    tokens : dict
        Design-system tokens loaded from design-system.json.

    Returns
    -------
    dict
        {
            "is_valid": bool,        # True iff errors is empty
            "errors":   List[str],   # Hard failures that block acceptance
            "warnings": List[str],   # Soft suggestions (non-blocking)
        }
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Hard checks (order: tokens -> colour -> structure -> syntax)
    errors.extend(validate_design_tokens(code, tokens))
    errors.extend(validate_colors(code, tokens))
    errors.extend(validate_structure(code))
    errors.extend(validate_syntax(code))

    # Soft checks (warnings only — never block acceptance)
    warnings.extend(_warn_spacing_token(code, tokens))

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# 
# Sub-validator 1 — Design-token presence
# 

def validate_design_tokens(code: str, tokens: Dict[str, str]) -> List[str]:
    """
    Verify that every required design token is referenced in the output.

    Checks
    ------
    * Primary colour  — must appear at least once (case-insensitive hex match).
    * Border radius   — exact token string must be present in styles.
    * Font family     — case-insensitive presence check.
    """
    errors: List[str] = []

    # Primary colour
    primary = tokens["primary_color"].lower()
    if primary not in code.lower():
        errors.append(
            f"MISSING_PRIMARY_COLOR: The primary colour '{tokens['primary_color']}' "
            f"was not found in the generated component. "
            f"It must be applied to at least one interactive or accent element."
        )

    # Border radius
    radius = tokens["border_radius"]
    if radius not in code:
        errors.append(
            f"MISSING_BORDER_RADIUS: The design-system border-radius '{radius}' "
            f"was not found in the component styles. "
            f"Apply it to cards, inputs, and buttons."
        )

    # Font family
    font = tokens["font_family"]
    if font.lower() not in code.lower():
        errors.append(
            f"MISSING_FONT_FAMILY: The design-system font-family '{font}' "
            f"was not found in the component styles. "
            f"Set font-family: '{font}', sans-serif on the host or wrapper element."
        )

    return errors


# 
# Sub-validator 2 — Strict colour enforcement
# 

def validate_colors(code: str, tokens: Dict[str, str]) -> List[str]:
    """
    Enforce STRICT colour-token compliance.

    Hard rules
    
    1. Functional colour notations are FORBIDDEN:
       rgba(), rgb(), hsl(), hsla(), hwb() — even when derived from design tokens.
       Only exact hex values from the design system may be used.

    2. Every hex literal must be one of the approved set:
         * tokens["primary_color"]
         * tokens["secondary_color"]
         * #ffffff / #fff   (pure white — allowed for text contrast)
         * #000000 / #000   (pure black — allowed for text contrast)

    3. Named CSS colour keywords (red, blue, coral ...) are forbidden.

    Returns a list of error strings; empty list means all colour rules pass.
    """
    errors: List[str] = []

    # Rule 1: Ban all functional colour notations 
    functional_pattern = re.compile(
        r"\b(rgba?|hsla?|hwb)\s*\(", re.IGNORECASE
    )
    if functional_pattern.search(code):
        errors.append(
            "UNAUTHORIZED_COLOR_FORMAT: Functional colour notations (rgba, rgb, "
            "hsl, hsla, hwb) are not permitted. "
            "Use only the exact hex tokens defined in the design system: "
            f"{tokens['primary_color']} and {tokens['secondary_color']}."
        )

    # Rule 2: Reject non-approved hex literals 
    # Build the full set of approved hex values (tokens + neutral shorthands).
    approved_hex: set = {
        tokens["primary_color"].lower(),
        tokens["secondary_color"].lower(),
        "#ffffff", "#fff",
        "#000000", "#000",
    }
    # Admit 3-digit shorthand equivalents of 6-digit approved values.
    for h in list(approved_hex):
        if len(h) == 7:
            r, g, b = h[1:3], h[3:5], h[5:7]
            if r[0] == r[1] and g[0] == g[1] and b[0] == b[1]:
                approved_hex.add(f"#{r[0]}{g[0]}{b[0]}")

    normalised_approved = {_normalise_hex(h) for h in approved_hex}

    hex_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    seen_violations: set = set()  # deduplicate identical bad values

    for match in hex_pattern.finditer(code):
        found = match.group(0).lower()
        normalised = _normalise_hex(found)
        if normalised not in normalised_approved and found not in seen_violations:
            seen_violations.add(found)
            errors.append(
                f"UNAUTHORISED_HEX_COLOR: '{match.group(0)}' is not in the design "
                f"system. Approved hex values: "
                f"{tokens['primary_color']}, {tokens['secondary_color']}, "
                f"#ffffff, #000000."
            )

    # Rule 3: Reject named CSS colour keywords 
    named_pattern = re.compile(
        r":\s*(" + "|".join(_NAMED_COLORS) + r")\b", re.IGNORECASE
    )
    for match in named_pattern.finditer(code):
        colour_name = match.group(1).lower()
        if colour_name not in _SAFE_CSS_KEYWORDS:
            errors.append(
                f"UNAUTHORISED_NAMED_COLOR: Named CSS colour '{match.group(1)}' "
                f"is not permitted. Use only design-system hex tokens."
            )

    return errors


# 
# Sub-validator 3 — Angular component structural integrity
# 

def validate_structure(code: str) -> List[str]:
    """
    Verify the generated code contains a complete, well-formed Angular component.

    Checks
    ------
    * @Component decorator is present.
    * 'export class' declaration is present.
    * Code ends with a closing brace '}' (class not truncated).
    * At least one class member (property or method) is defined inside the class.
    """
    errors: List[str] = []

    # @Component decorator
    if "@Component" not in code:
        errors.append(
            "INCOMPLETE_STRUCTURE: Missing @Component decorator. "
            "The generated output must be a valid Angular standalone component."
        )

    # export class
    if not re.search(r"\bexport\s+class\b", code):
        errors.append(
            "INCOMPLETE_STRUCTURE: Missing 'export class' declaration. "
            "The component class must be exported for Angular to register it."
        )

    # Ends with closing brace (class body not truncated)
    stripped = code.strip()
    if stripped and stripped[-1] != "}":
        errors.append(
            "INCOMPLETE_STRUCTURE: Component source does not end with '}'. "
            "The class body may be truncated or improperly closed."
        )

    # At least one TypeScript class member — only checked when class exists.
    # We look for TypeScript-specific patterns to avoid matching CSS property
    # declarations (e.g. "padding: 8px") as false positives.
    if re.search(r"\bexport\s+class\b", code):
        ts_member_patterns = [
            # Access modifier prefix (public/private/protected)
            re.compile(r"\b(public|private|protected)\s+\w+", re.IGNORECASE),
            # Typed property with initialiser, e.g.  name: string = ''
            re.compile(r"\b\w+\s*:\s*(string|number|boolean|any|void|object|Array|Observable|Subject|EventEmitter)\b"),
            # Method with return type, e.g.  onLogin(): void {
            re.compile(r"\b\w+\s*\([^)]*\)\s*(?::\s*\w+\s*)?\{"),
            # Angular lifecycle hooks
            re.compile(r"\b(constructor|ngOnInit|ngOnDestroy|ngOnChanges|ngAfterViewInit)\b"),
        ]
        has_member = any(p.search(code) for p in ts_member_patterns)
        if not has_member:
            errors.append(
                "INCOMPLETE_STRUCTURE: No TypeScript class members (typed properties "
                "or methods) detected inside the component class body. "
                "The class appears to be empty."
            )

    return errors


# 
# Sub-validator 4 — Bracket / brace / parenthesis balance
# 

def validate_syntax(code: str) -> List[str]:
    """
    Verify all brackets, braces, and parentheses are correctly balanced.

    Algorithm
    ---------
    Stack-based single-pass parser.  String literals (single-quoted,
    double-quoted, backtick/template) and comments (// and /* */) are skipped
    so bracket characters inside them do not trigger false positives.

    Each stack entry stores (opener_char, line_number) so error messages
    reference the exact source line where a mismatch or unclosed opener occurs.
    """
    errors: List[str] = []

    openers = {"(": ")", "{": "}", "[": "]"}
    closers = {")": "(", "}": "{", "]": "["}
    bracket_names = {
        "(": "opening parenthesis '('",
        ")": "closing parenthesis ')'",
        "{": "opening brace '{'",
        "}": "closing brace '}'",
        "[": "opening bracket '['",
        "]": "closing bracket ']'",
    }

    stack: list = []   # list of (opener_char: str, line_number: int)
    i = 0
    length = len(code)
    line = 1

    while i < length:
        ch = code[i]

        # Track newlines for accurate line numbers
        if ch == "\n":
            line += 1
            i += 1
            continue

        # Skip string literals 
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            while i < length:
                if code[i] == "\n":
                    line += 1
                if code[i] == "\\" and i + 1 < length:
                    i += 2   # skip escaped character
                    continue
                if code[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        # Skip single-line comments 
        if ch == "/" and i + 1 < length and code[i + 1] == "/":
            while i < length and code[i] != "\n":
                i += 1
            continue

        # Skip multi-line comments 
        if ch == "/" and i + 1 < length and code[i + 1] == "*":
            i += 2
            while i < length - 1:
                if code[i] == "\n":
                    line += 1
                if code[i] == "*" and code[i + 1] == "/":
                    i += 2
                    break
                i += 1
            continue

        # Stack-based bracket matching 
        if ch in openers:
            stack.append((ch, line))

        elif ch in closers:
            if not stack:
                # Closing bracket with nothing open
                errors.append(
                    f"SYNTAX_ERROR: Unexpected {bracket_names[ch]} on line {line} "
                    f"— no matching opener exists. "
                    f"Check for an extra or misplaced '{ch}'."
                )
            elif stack[-1][0] != closers[ch]:
                # Top of stack does not match this closer
                opener_char, opener_line = stack[-1]
                errors.append(
                    f"SYNTAX_ERROR: Mismatched brackets — {bracket_names[ch]} on "
                    f"line {line} does not match {bracket_names[opener_char]} "
                    f"opened on line {opener_line}."
                )
                stack.pop()  # consume to avoid cascading errors
            else:
                stack.pop()  # matched — remove from stack

        i += 1

    # Any remaining unclosed openers after full traversal
    for opener_char, opener_line in stack:
        errors.append(
            f"SYNTAX_ERROR: Unclosed {bracket_names[opener_char]} opened on "
            f"line {opener_line} — missing closing '{openers[opener_char]}'."
        )

    return errors


# 
# Warning-only checks (non-blocking)
# 

def _warn_spacing_token(code: str, tokens: Dict[str, str]) -> List[str]:
    """
    Soft check: encourage use of the spacing token.

    Returns a warning (not an error) if the spacing token value does not appear
    anywhere in the generated source.  The loop treats warnings as informational
    and does not trigger a retry on their account.
    """
    spacing = tokens.get("spacing", "")
    if spacing and spacing not in code:
        return [
            f"SPACING_SUGGESTION: The spacing token '{spacing}' was not detected. "
            f"Consider applying it to padding/margin for visual consistency."
        ]
    return []


# 
# Internal helpers
# 

def _normalise_hex(h: str) -> str:
    """Expand a 3-digit hex shorthand to lowercase 7-character form (#rrggbb)."""
    h = h.lower()
    if len(h) == 4:  # #rgb -> #rrggbb
        return f"#{h[1] * 2}{h[2] * 2}{h[3] * 2}"
    return h