import 'dart:typed_data';

/// Stub implementation for non-web platforms.
/// Desktop platforms use desktop_drop's native platform channels instead.

bool get isWebDropSupported => false;

void initWebDrop({
  required void Function(List<({String name, Uint8List bytes})> files) onFileDrop,
  required void Function() onDragEnter,
  required void Function() onDragLeave,
}) {
  // No-op on native platforms
}

void disposeWebDrop() {
  // No-op on native platforms
}
