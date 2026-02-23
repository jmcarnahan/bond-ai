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

1. Implement the new type in the Flutter frontend:
   - Add handling in `bond_link_builder.dart` (check href scheme)
   - Create a widget if needed (like `prompt_button.dart`)
   - Add frontend tests

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

# All bond:// schemes the frontend currently handles.
# Keep in sync with bond_link_builder.dart.
# Used by tests to verify definitions text covers all supported schemes.
BOND_SCHEMES = ["bond://prompt"]

_BOND_DEFINITIONS = (
    "Bond UI supports interactive markdown links. "
    "Use [Label](bond://prompt) to render a clickable prompt button; "
    "when tapped the label text is sent as a user message. "
    "Always use the simple form bond://prompt — the label is the prompt."
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
