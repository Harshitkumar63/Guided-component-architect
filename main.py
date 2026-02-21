"""
main.py — CLI entry-point for the Guided Component Architect.

Usage
─────
    python main.py
    python main.py "A login card with glassmorphism effect"

If no argument is provided the program prompts interactively.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# Load .env file if present (for OPENAI_API_KEY and other config).
load_dotenv()


def main() -> None:
    """Run the Guided Component Architect CLI."""

    # ── Validate environment ──────────────────────────────────────────
    if not os.getenv("GROQ_API_KEY"):
        print(
            "ERROR: GROQ_API_KEY environment variable is not set.\n"
            "Export it or add it to a .env file in the project root.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Obtain user description ───────────────────────────────────────
    if len(sys.argv) > 1:
        description = " ".join(sys.argv[1:])
    else:
        print("╔══════════════════════════════════════════════╗")
        print("║   Guided Component Architect                ║")
        print("║   Describe the Angular component you need   ║")
        print("╚══════════════════════════════════════════════╝")
        description = input("\n> ").strip()

    if not description:
        print("ERROR: Empty description.  Please provide a component description.", file=sys.stderr)
        sys.exit(1)

    # ── Late import to keep top-level light and testable ──────────────
    from agent_loop import run_agent_loop

    print("\n" + "═" * 60, file=sys.stderr)
    print("  Guided Component Architect — Generation Pipeline", file=sys.stderr)
    print("═" * 60 + "\n", file=sys.stderr)

    component_code: str = run_agent_loop(description, verbose=True)

    # ── Output ────────────────────────────────────────────────────────
    print("\n" + "═" * 60, file=sys.stderr)
    print("  ✅  FINAL ANGULAR COMPONENT", file=sys.stderr)
    print("═" * 60 + "\n", file=sys.stderr)

    # The actual code goes to stdout so it can be piped / redirected.
    print(component_code)


if __name__ == "__main__":
    main()
