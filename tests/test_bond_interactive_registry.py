"""Tests for bond_interactive_registry — append/strip of bond:// definitions."""

import pytest
from bondable.bond.providers.bedrock.bond_interactive_registry import (
    append_bond_definitions,
    strip_bond_definitions,
    _BOND_DEFS_START,
    _BOND_DEFS_END,
    _BOND_DEFINITIONS,
    BOND_SCHEMES,
)


# ---------------------------------------------------------------------------
# append_bond_definitions
# ---------------------------------------------------------------------------

class TestAppendBondDefinitions:
    def test_normal_string(self):
        result = append_bond_definitions("You are a helpful assistant.")
        assert result.startswith("You are a helpful assistant.")
        assert _BOND_DEFS_START in result
        assert _BOND_DEFINITIONS in result
        assert _BOND_DEFS_END in result

    def test_empty_string(self):
        result = append_bond_definitions("")
        assert _BOND_DEFS_START in result
        assert _BOND_DEFINITIONS in result

    def test_none_input(self):
        result = append_bond_definitions(None)
        assert _BOND_DEFS_START in result
        assert _BOND_DEFINITIONS in result

    def test_preserves_original_content(self):
        original = "Custom instructions with special chars: <>&\""
        result = append_bond_definitions(original)
        assert original in result

    def test_block_appended_at_end(self):
        """Definitions block must be at the end, not the beginning."""
        result = append_bond_definitions("Instructions here")
        idx_instructions = result.index("Instructions here")
        idx_start_marker = result.index(_BOND_DEFS_START)
        assert idx_instructions < idx_start_marker

    def test_separated_by_double_newline(self):
        """Block is separated from instructions by exactly \\n\\n."""
        result = append_bond_definitions("Hello")
        assert "Hello\n\n" + _BOND_DEFS_START in result


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_double_append(self):
        once = append_bond_definitions("Hello")
        twice = append_bond_definitions(once)
        assert once == twice

    def test_triple_append(self):
        once = append_bond_definitions("Hello")
        twice = append_bond_definitions(once)
        thrice = append_bond_definitions(twice)
        assert once == twice == thrice

    def test_single_marker_block_after_multiple_appends(self):
        result = append_bond_definitions(append_bond_definitions("Test"))
        assert result.count(_BOND_DEFS_START) == 1
        assert result.count(_BOND_DEFS_END) == 1


# ---------------------------------------------------------------------------
# strip_bond_definitions
# ---------------------------------------------------------------------------

class TestStripBondDefinitions:
    def test_removes_block(self):
        with_defs = append_bond_definitions("Clean instructions")
        stripped = strip_bond_definitions(with_defs)
        assert _BOND_DEFS_START not in stripped
        assert _BOND_DEFS_END not in stripped
        assert _BOND_DEFINITIONS not in stripped
        assert "Clean instructions" in stripped

    def test_noop_on_clean_string(self):
        clean = "No definitions here."
        assert strip_bond_definitions(clean) == clean

    def test_none_returns_empty(self):
        assert strip_bond_definitions(None) == ""

    def test_empty_returns_empty(self):
        assert strip_bond_definitions("") == ""

    def test_malformed_start_only(self):
        """Start marker without end marker — strip from start marker to end."""
        text = f"Instructions\n{_BOND_DEFS_START}\npartial defs"
        result = strip_bond_definitions(text)
        assert _BOND_DEFS_START not in result
        assert "Instructions" in result

    def test_strips_surrounding_whitespace(self):
        """The newlines before the block should be cleaned up."""
        with_defs = append_bond_definitions("Hello")
        stripped = strip_bond_definitions(with_defs)
        assert not stripped.endswith("\n\n")
        assert stripped == "Hello"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_append_then_strip_returns_original(self):
        original = "You are a helpful AI assistant."
        assert strip_bond_definitions(append_bond_definitions(original)) == original

    def test_round_trip_with_trailing_whitespace(self):
        """Trailing whitespace is consumed by the marker delimiter — this is fine."""
        original = "Instructions with trailing space   "
        result = strip_bond_definitions(append_bond_definitions(original))
        assert result == original.rstrip()

    def test_round_trip_multiline(self):
        original = "Line 1\nLine 2\nLine 3"
        assert strip_bond_definitions(append_bond_definitions(original)) == original

    def test_round_trip_empty(self):
        assert strip_bond_definitions(append_bond_definitions("")) == ""

    def test_round_trip_none(self):
        # append(None) produces a defs-only string; strip returns ""
        result = strip_bond_definitions(append_bond_definitions(None))
        assert result == ""

    def test_round_trip_with_ljust_padding(self):
        """Simulates the real BedrockCRUD flow: ljust(40) then append then strip."""
        raw = "Short"
        padded = raw.ljust(40)
        appended = append_bond_definitions(padded)
        stripped = strip_bond_definitions(appended)
        # ljust pads with spaces; those trailing spaces get consumed, which is fine
        assert stripped.strip() == raw

    def test_round_trip_long_instructions_with_ljust(self):
        """ljust has no effect on strings already >= 40 chars."""
        raw = "You are a helpful AI assistant. Be helpful, accurate, and concise."
        padded = raw.ljust(40)  # no-op, already > 40
        assert padded == raw
        appended = append_bond_definitions(padded)
        stripped = strip_bond_definitions(appended)
        assert stripped == raw


# ---------------------------------------------------------------------------
# Marker integrity
# ---------------------------------------------------------------------------

class TestMarkerIntegrity:
    def test_markers_are_html_comments(self):
        assert _BOND_DEFS_START.startswith("<!--")
        assert _BOND_DEFS_START.endswith("-->")
        assert _BOND_DEFS_END.startswith("<!--")
        assert _BOND_DEFS_END.endswith("-->")

    def test_markers_are_distinct(self):
        assert _BOND_DEFS_START != _BOND_DEFS_END

    def test_definitions_do_not_contain_markers(self):
        assert _BOND_DEFS_START not in _BOND_DEFINITIONS
        assert _BOND_DEFS_END not in _BOND_DEFINITIONS

    def test_definitions_mention_bond_protocol(self):
        assert "bond://" in _BOND_DEFINITIONS


# ---------------------------------------------------------------------------
# Hostile / adversarial content
# ---------------------------------------------------------------------------

class TestAdversarialContent:
    def test_instructions_containing_start_marker(self):
        """If a user somehow writes the start marker in their instructions,
        strip must not eat the user's content on a clean (un-appended) string.
        After a round-trip, the user content between markers gets removed
        along with the injected definitions — this is an accepted trade-off
        since the markers are internal implementation details."""
        user_text = f"Do not use {_BOND_DEFS_START} in your output."
        # On a clean string with no end marker, strip removes from start marker to end
        result = strip_bond_definitions(user_text)
        assert _BOND_DEFS_START not in result

    def test_instructions_containing_end_marker_only(self):
        """End marker alone should be harmless — strip_bond_definitions is a no-op."""
        user_text = f"Random text {_BOND_DEFS_END} more text"
        result = strip_bond_definitions(user_text)
        assert result == user_text

    def test_instructions_containing_both_markers_manually(self):
        """User manually wrote both markers with fake content in between."""
        fake_block = f"{_BOND_DEFS_START}\nFake definitions\n{_BOND_DEFS_END}"
        user_text = f"Real instructions\n\n{fake_block}"
        # append should strip the fake block first, then add real definitions
        result = append_bond_definitions(user_text)
        assert result.count(_BOND_DEFS_START) == 1
        assert result.count(_BOND_DEFS_END) == 1
        assert "Fake definitions" not in result
        assert _BOND_DEFINITIONS in result
        assert "Real instructions" in result

    def test_instructions_with_html_comments(self):
        """Regular HTML comments should not be affected."""
        user_text = "Instructions <!-- this is a comment --> more text"
        result = strip_bond_definitions(user_text)
        assert result == user_text
        appended = append_bond_definitions(user_text)
        stripped = strip_bond_definitions(appended)
        assert stripped == user_text


# ---------------------------------------------------------------------------
# Scheme coverage — definitions text covers all frontend schemes
# ---------------------------------------------------------------------------

class TestSchemeCoverage:
    def test_all_schemes_mentioned_in_definitions(self):
        """Every scheme in BOND_SCHEMES must appear in _BOND_DEFINITIONS
        so agents learn about all supported interactive types."""
        for scheme in BOND_SCHEMES:
            assert scheme in _BOND_DEFINITIONS, (
                f"Scheme '{scheme}' is in BOND_SCHEMES but not mentioned "
                f"in _BOND_DEFINITIONS. Update the definitions text."
            )

    def test_bond_schemes_not_empty(self):
        """BOND_SCHEMES must list at least one scheme."""
        assert len(BOND_SCHEMES) > 0
