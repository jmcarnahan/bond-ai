import 'dart:typed_data';

/// Stub implementation for non-web platforms.
/// Image clipboard operations are not supported on mobile/desktop.

bool get isSupported => false;

Future<bool> copyImageToClipboard(Uint8List bytes) async {
  // Not supported on non-web platforms
  return false;
}

void downloadImage(Uint8List bytes, String filename) {
  // Not supported on non-web platforms
}
