"""
Bond Interactive Markdown Registry

Manages the auto-injection of bond:// interactive markdown definitions
into Bedrock agent instructions. The definitions are delimited by HTML
comment markers so they can be cleanly appended and stripped.

On write (create/update): append_bond_definitions() adds the block.
On read (edit screen): strip_bond_definitions() removes it.

## How it works

Every agent's instructions are stored in AWS Bedrock. Before writing
to Bedrock (create or update), we call append_bond_definitions() which
appends a marker-delimited block describing the bond:// protocol.
When reading back (for the edit screen), strip_bond_definitions()
removes that block so users never see it.

The markers are HTML comments that won't render in any markdown viewer:

    <!-- BOND_INTERACTIVE_DEFS_START -->
    ...definitions text...
    <!-- BOND_INTERACTIVE_DEFS_END -->

## Adding a new bond:// type

For **frontend-rendered** types (like bond://prompt):
1. Add handling in `bond_link_builder.dart` (check href scheme)
2. Create a widget if needed (like `prompt_button.dart`)
3. Add frontend tests

For **server-intercepted** types (like bond://forward):
1. Add detection and handling in `chat.py`

Then for both:
2. Update _BOND_DEFINITIONS below to describe the new type.
   Keep descriptions concise — this text is appended to every agent's
   system prompt, so token cost matters.
3. Add the new scheme to BOND_SCHEMES below for cross-referencing.
4. Update tests in `tests/test_bond_interactive_registry.py`.

No migration is needed — existing agents pick up the new definitions
on their next update.

## Integration points

- BedrockCRUD.py create_bedrock_agent() — calls append_bond_definitions()
- BedrockCRUD.py update_bedrock_agent() — calls append_bond_definitions()
- BedrockAgent.py __init__() — calls strip_bond_definitions()
"""

import re

_BOND_DEFS_START = "<!-- BOND_INTERACTIVE_DEFS_START -->"
_BOND_DEFS_END = "<!-- BOND_INTERACTIVE_DEFS_END -->"

# All bond:// schemes the system supports.
# Frontend-rendered schemes (e.g. bond://prompt) are in bond_link_builder.dart.
# Server-intercepted schemes (e.g. bond://forward) are handled in chat.py.
# Used by tests to verify definitions text covers all supported schemes.
BOND_SCHEMES = ["bond://prompt", "bond://forward"]

_BOND_DEFINITIONS = (
    "Bond UI supports interactive markdown links. "
    "Use [Label](bond://prompt) when asked to use 'bond prompt'. "
    "The frontend will render this as a clickable prompt button. "
    "Always use the simple form bond://prompt — the label is the prompt.\n\n"
    "To forward the conversation to another agent, output a link in the form "
    "[Display Name](bond://forward/AGENT_SLUG) where AGENT_SLUG is the target "
    "agent's slug (e.g. brave-sailing-fox). The system will seamlessly invoke "
    "the target agent on the same thread after your response completes. "
    "Use at most one forward link per response. Follow your specific "
    "instructions about when to forward."
)

# Compiled pattern to match the marker-delimited block (including surrounding whitespace)
_STRIP_PATTERN = re.compile(
    r"\s*" + re.escape(_BOND_DEFS_START) + r".*?" + re.escape(_BOND_DEFS_END),
    re.DOTALL,
)


def strip_bond_definitions(instructions: str | None) -> str:
    """Remove the marker-delimited bond definitions block from instructions.

    Returns empty string for None input. If only the start marker is present
    (malformed), strips from the start marker to end of string.
    """
    if instructions is None:
        return ""
    result = _STRIP_PATTERN.sub("", instructions)
    # Handle malformed case: start marker without end marker
    start_idx = result.find(_BOND_DEFS_START)
    if start_idx != -1:
        result = result[:start_idx].rstrip()
    return result


def append_bond_definitions(instructions: str | None) -> str:
    """Strip any existing bond definitions, then append current definitions.

    Idempotent: calling multiple times produces the same result as calling once.
    Returns the definitions block alone for None/empty input.
    """
    clean = strip_bond_definitions(instructions)
    block = f"\n\n{_BOND_DEFS_START}\n{_BOND_DEFINITIONS}\n{_BOND_DEFS_END}"
    if clean:
        return clean + block
    return block.lstrip("\n")
