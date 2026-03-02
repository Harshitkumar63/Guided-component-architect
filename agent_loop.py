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

from typing import Dict

from generator import generate_component, load_design_system, regenerate_component
from logger import log_error, log_info, log_lines, log_warn
from validator import validate

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

    log_info("Generation start: creating initial component.", verbose=verbose)
    code: str = generate_component(description, tokens=tokens, model=model)
    log_info("Initial generation complete.", verbose=verbose)

    log_info("Running validation pass 1.", verbose=verbose)
    report = validate(code, tokens)

    if report["is_valid"]:
        if report["warnings"]:
            log_lines(report["warnings"], prefix="WARN ", verbose=verbose)
        log_info("Final success: component passed validation on first attempt.", verbose=verbose)
        return code

    log_warn(
        f"Validation failed on first attempt with {len(report['errors'])} error(s).",
        verbose=verbose,
    )
    log_lines(report["errors"], prefix="ERROR", verbose=verbose)
    if report["warnings"]:
        log_lines(report["warnings"], prefix="WARN ", verbose=verbose)

    for attempt in range(1, max_retries + 1):
        log_info(
            f"Retry {attempt}/{max_retries}: requesting self-correction.",
            verbose=verbose,
        )

        code = regenerate_component(
            original_code=code,
            errors=report["errors"],
            description=description,
            tokens=tokens,
            model=model,
        )
        log_info(f"Retry {attempt} generation complete.", verbose=verbose)
        log_info(f"Running validation pass retry-{attempt}.", verbose=verbose)

        report = validate(code, tokens)

        if report["is_valid"]:
            if report["warnings"]:
                log_lines(report["warnings"], prefix="WARN ", verbose=verbose)
            log_info(f"Final success: component passed after retry {attempt}.", verbose=verbose)
            return code

        log_warn(
            f"Validation failed after retry {attempt} with {len(report['errors'])} error(s).",
            verbose=verbose,
        )
        log_lines(report["errors"], prefix="ERROR", verbose=verbose)
        if report["warnings"]:
            log_lines(report["warnings"], prefix="WARN ", verbose=verbose)

    log_error(
        f"Retries exhausted ({max_retries}). Returning best-effort output.",
        verbose=verbose,
    )
    log_lines(report["errors"], prefix="ERROR", verbose=verbose)
    return code