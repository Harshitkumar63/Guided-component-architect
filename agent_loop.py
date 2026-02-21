"""
agent_loop.py — Self-correcting agentic generation loop.

Flow

1.  Generate an Angular component from the user's natural-language description.
2.  Validate the output — returns a STRUCTURED REPORT:
        { "is_valid": bool, "errors": [...], "warnings": [...] }
3.  If validation fails, feed the original code + structured errors back to the
    LLM and request a corrected version.
4.  Repeat up to MAX_RETRIES times.
5.  Return the final component (valid or best-effort after retries are exhausted).

Logging conventions

      — operation starting
      — success
       — validation failure (errors detected)
      — warnings (non-blocking suggestions)
      — retry / self-correction attempt
      — hard failure (retries exhausted)

All diagnostic output goes to stderr; only the final component code goes to stdout.
"""

from __future__ import annotations

import sys
from typing import Dict, List, Optional

from generator import generate_component, load_design_system, regenerate_component
from validator import validate_component

# Maximum number of LLM self-correction attempts after the initial generation.
MAX_RETRIES: int = 2


def run_agent_loop(
    description: str,
    *,
    max_retries: int = MAX_RETRIES,
    model: str = "llama-3.3-70b-versatile",
    verbose: bool = True,
) -> str:
    """
    End-to-end agentic loop: generate -> validate -> (fix -> validate)*.

    Parameters
    ----------
    description : str
        Natural-language description of the desired Angular component.
    max_retries : int
        Maximum number of self-correction retries allowed (default: 2).
    model : str
        Groq model identifier to use for generation.
    verbose : bool
        When True, progress and diagnostic messages are printed to stderr.

    Returns
    -------
    str
        Final Angular component TypeScript source code.
    """
    tokens: Dict[str, str] = load_design_system()

    #  Step 1: Initial generation 
    _log(verbose, " Generating initial component...")
    code: str = generate_component(description, tokens=tokens, model=model)
    _log(verbose, " Initial generation complete.")

    #  Step 2: First validation pass 
    _log(verbose, " Running design-system validation...")
    report: Dict = validate_component(code, tokens)

    if report["is_valid"]:
        _log_warnings(verbose, report["warnings"])
        _log(verbose, " Component passed all validation checks on first attempt.")
        return code

    # Validation failed — log the errors
    _log(verbose, f"  Validation found {len(report['errors'])} error(s) on first attempt:")
    _log_errors(verbose, report["errors"])
    if report["warnings"]:
        _log_warnings(verbose, report["warnings"])

    #  Steps 3–4: Self-correction retry loop 
    for attempt in range(1, max_retries + 1):
        _log(verbose, f" Retry {attempt}/{max_retries} — sending errors to LLM for self-correction...")

        code = regenerate_component(
            original_code=code,
            errors=report["errors"],
            description=description,
            tokens=tokens,
            model=model,
        )
        _log(verbose, f" Retry {attempt} generation complete.")
        _log(verbose, f" Re-validating after retry {attempt}...")

        report = validate_component(code, tokens)

        if report["is_valid"]:
            _log_warnings(verbose, report["warnings"])
            _log(verbose, f" Component passed all checks after retry {attempt}.")
            return code

        _log(verbose, f"  Still {len(report['errors'])} error(s) after retry {attempt}:")
        _log_errors(verbose, report["errors"])
        if report["warnings"]:
            _log_warnings(verbose, report["warnings"])

    #  Step 5: Retries exhausted — return best-effort output 
    _log(
        verbose,
        f" Max retries ({max_retries}) exhausted. Returning best-effort output.\n"
        f"   Unresolved errors: {report['errors']}",
    )
    return code


# 
# Internal logging helpers
# 

def _log(verbose: bool, message: str) -> None:
    """Print a diagnostic message to stderr (keeps stdout clean for piped code)."""
    if verbose:
        print(message, file=sys.stderr)


def _log_errors(verbose: bool, errors: List[str]) -> None:
    """Pretty-print hard validation errors to stderr."""
    if not verbose:
        return
    for err in errors:
        print(f"    {err}", file=sys.stderr)


def _log_warnings(verbose: bool, warnings: List[str]) -> None:
    """Pretty-print soft validation warnings to stderr."""
    if not verbose or not warnings:
        return
    for warn in warnings:
        print(f"    {warn}", file=sys.stderr)