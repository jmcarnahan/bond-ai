# Changelog

## 0.2.0 (2026-07-07)

- `parseAllBondMessages` now skips empty assistant `type="text"` messages —
  the bookend pair the server emits when a tool round produces a file or
  card before any text. These messages are never persisted server-side, so
  the live view now matches a thread reload.
- **Behavioral notes for consumers with their own stream handlers:**
  - The first parsed assistant message can now be a non-`text` type
    (`image_file`, `file_link`, `resource_card`) — a placeholder-replacement
    pattern must not assume the first message is text.
  - A turn whose only assistant output was empty/whitespace text now parses
    to zero assistant messages; handlers should surface the server's trailing
    `role="system"` error message in that case (the bond-ai router always
    appends one).
- New server message type `resource_card` (structured card envelope JSON from
  MCP tool results) passes through the parser as a normal typed message;
  renderers without a card widget fall through to plain text.
