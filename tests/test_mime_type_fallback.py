"""Tests for MIME type extension fallback.

Verifies that when Magika classifies a file as text/plain but the file
extension indicates a more specific type (e.g., .html), the extension-based
MIME type is used instead.
"""
import pytest
from bondable.bond.providers.files import _EXTENSION_MIME_OVERRIDES, _apply_mime_override


class TestExtensionMimeOverrides:
    """Tests for the _EXTENSION_MIME_OVERRIDES mapping."""

    def test_html_extensions_mapped(self):
        assert _EXTENSION_MIME_OVERRIDES['.html'] == 'text/html'
        assert _EXTENSION_MIME_OVERRIDES['.htm'] == 'text/html'

    def test_common_extensions_present(self):
        assert '.css' in _EXTENSION_MIME_OVERRIDES
        assert '.js' in _EXTENSION_MIME_OVERRIDES
        assert '.json' in _EXTENSION_MIME_OVERRIDES
        assert '.xml' in _EXTENSION_MIME_OVERRIDES
        assert '.csv' in _EXTENSION_MIME_OVERRIDES
        assert '.md' in _EXTENSION_MIME_OVERRIDES

    def test_no_binary_overrides(self):
        """Extension overrides should only apply to text-like formats."""
        for ext, mime in _EXTENSION_MIME_OVERRIDES.items():
            assert mime.startswith('text/') or mime.startswith('application/'), \
                f"Unexpected MIME type {mime} for extension {ext}"


class TestApplyMimeOverride:
    """Tests for _apply_mime_override() — the production function."""

    def test_html_overridden(self):
        assert _apply_mime_override('text/plain', 'hello_world.html') == 'text/html'

    def test_htm_overridden(self):
        assert _apply_mime_override('text/plain', 'page.htm') == 'text/html'

    def test_csv_overridden(self):
        assert _apply_mime_override('text/plain', 'data.csv') == 'text/csv'

    def test_json_overridden(self):
        assert _apply_mime_override('text/plain', 'config.json') == 'application/json'

    def test_txt_stays_text_plain(self):
        """A .txt file classified as text/plain should remain text/plain."""
        assert _apply_mime_override('text/plain', 'readme.txt') == 'text/plain'

    def test_no_extension_stays_text_plain(self):
        """File with no extension should remain text/plain."""
        assert _apply_mime_override('text/plain', 'Makefile') == 'text/plain'

    def test_non_text_plain_not_overridden(self):
        """Only text/plain triggers the fallback — other MIME types pass through."""
        assert _apply_mime_override('application/octet-stream', 'hello.html') == 'application/octet-stream'

    def test_text_html_not_overridden(self):
        """Already-correct text/html should pass through unchanged."""
        assert _apply_mime_override('text/html', 'page.html') == 'text/html'

    def test_case_insensitive_extension(self):
        assert _apply_mime_override('text/plain', 'Page.HTML') == 'text/html'
        assert _apply_mime_override('text/plain', 'DATA.JSON') == 'application/json'

    def test_unknown_extension_stays_text_plain(self):
        """Extensions not in the override map should remain text/plain."""
        assert _apply_mime_override('text/plain', 'script.rb') == 'text/plain'
        assert _apply_mime_override('text/plain', 'notes.rst') == 'text/plain'
