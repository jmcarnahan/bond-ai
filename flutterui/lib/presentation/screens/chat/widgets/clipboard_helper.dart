import 'dart:typed_data';

import 'clipboard_helper_stub.dart'
    if (dart.library.html) 'clipboard_helper_web.dart' as impl;

/// Platform-agnostic clipboard helper for image operations
class ClipboardHelper {
  /// Copy image bytes to clipboard. Returns true if successful.
  static Future<bool> copyImageToClipboard(Uint8List bytes) {
    return impl.copyImageToClipboard(bytes);
  }

  /// Read files (images, PDFs, etc.) from the clipboard.
  /// Returns a list of (name, bytes) records for any non-text clipboard items.
  static Future<List<({String name, Uint8List bytes})>> readFilesFromClipboard() {
    return impl.readFilesFromClipboard();
  }

  /// Download image bytes as a file with the given filename.
  static void downloadImage(Uint8List bytes, String filename) {
    impl.downloadImage(bytes, filename);
  }

  /// Check if clipboard image operations are supported on this platform.
  static bool get isSupported => impl.isSupported;
}
