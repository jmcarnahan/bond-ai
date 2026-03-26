import 'dart:typed_data';

/// Stub implementation for non-web platforms.
void triggerBrowserDownload(String fileName, Uint8List bytes) {
  throw UnsupportedError('Download is only supported on web platform currently');
}
