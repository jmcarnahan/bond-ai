# bond_chat_ui

Reusable Flutter chat message rendering widgets extracted from the Bond AI project. Provides markdown-powered message display, feedback thumbs, file cards, image rendering, and interactive `bond://prompt` links — all with zero Riverpod dependency.

## Installation

### From a git repository

```yaml
# pubspec.yaml
dependencies:
  bond_chat_ui:
    git:
      url: https://github.com/jmcarnahan/bond-ai.git
      path: packages/bond_chat_ui
      ref: main
```

### From a local path

```yaml
# pubspec.yaml
dependencies:
  bond_chat_ui:
    path: ../path/to/bond-ai/packages/bond_chat_ui
```

Then run:

```bash
flutter pub get
```

## Usage

```dart
import 'package:bond_chat_ui/bond_chat_ui.dart';
```

### Display a list of chat messages

```dart
ChatMessagesList(
  messages: myMessages,
  isSendingMessage: isStreaming,
  scrollController: scrollCtrl,
  imageCache: imageCache,  // shared Map<String, Uint8List> for decoded images
  onSendPrompt: (prompt) => sendMessage(prompt),
  onFeedbackSubmit: (messageId, type, comment) async {
    await myApi.submitFeedback(messageId, type, comment);
  },
  onFeedbackDelete: (messageId) async {
    await myApi.deleteFeedback(messageId);
  },
  onFeedbackChanged: (messageId, type, comment) {
    // Update local state after feedback changes
  },
  assistantAvatarBuilder: (context, message) {
    return CircleAvatar(child: Icon(Icons.smart_toy));
  },
  fileCardBuilder: (context, fileDataJson) {
    return FileCard(
      fileDataJson: fileDataJson,
      onDownload: (fileId, fileName) async {
        await myApi.downloadFile(fileId, fileName);
      },
    );
  },
);
```

### Display a single message

```dart
ChatMessageItem(
  message: message,
  isSendingMessage: false,
  isLastMessage: true,
  imageCache: imageCache,
  onSendPrompt: (prompt) => sendMessage(prompt),
  onFeedbackSubmit: (messageId, type, comment) async {
    await myApi.submitFeedback(messageId, type, comment);
  },
);
```

### Use the markdown renderer directly

```dart
InteractiveMarkdownBody(
  data: '**Hello** from [Ask me](bond://prompt)',
  onTapLink: (text, href, title) {
    if (href != null) launchUrl(Uri.parse(href));
  },
  onPromptButtonTap: (prompt) => sendMessage(prompt),
);
```

### Parse streaming XML messages

```dart
// During streaming — extract displayable content from partial XML
final displayText = BondMessageParser.extractStreamingBodyContent(xmlChunk);

// After stream completes — parse all messages from full XML
final messages = BondMessageParser.parseAllBondMessages(fullXml);
```

## API Reference

### Widgets

| Widget | Description |
|--------|-------------|
| `ChatMessagesList` | ListView of messages with feedback, avatars, and file cards |
| `ChatMessageItem` | Single message bubble with markdown, images, or file links |
| `InteractiveMarkdownBody` | Markdown renderer with `bond://prompt` button support |
| `FileCard` | File download card with icon, name, size, and type label |
| `FeedbackDialog` | Animated thumbs up/down feedback form |
| `PromptButton` | Clickable prompt button rendered from `bond://prompt` links |

### Models

| Class | Description |
|-------|-------------|
| `Message` | Immutable chat message with id, type, role, content, imageData, feedback |
| `ParsedBondMessage` | Result of XML message parsing with thread/agent metadata |

### Utilities

| Class | Description |
|-------|-------------|
| `BondMessageParser` | XML streaming parser and entity unescaping |
| `MarkdownTextExtractor` | Extracts plain text from markdown (for clipboard copy) |
| `ClipboardHelper` | Platform-agnostic image clipboard operations (web/stub) |
| `BondLinkBuilder` | Custom `MarkdownElementBuilder` for `bond://` protocol links |

## Customization

All service interactions are injected via callbacks — the package never calls APIs directly:

- **`onFeedbackSubmit` / `onFeedbackDelete`** — wire to your feedback API
- **`onDownload`** (on `FileCard`) — wire to your file download service
- **`assistantAvatarBuilder`** — provide a custom avatar widget per message (defaults to a robot icon)
- **`fileCardBuilder`** — provide a custom file card widget (defaults to the built-in `FileCard`)

The `imageCache` parameter is a shared mutable `Map<String, Uint8List>` that avoids repeated base64 decoding. Pass the same instance across all message widgets in a list.
