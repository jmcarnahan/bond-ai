import 'dart:typed_data';

/// Stub implementation for non-web platforms.
String createBlobUrl(Uint8List bytes, String mimeType) {
  throw UnsupportedError('Preview blob URLs only supported on web');
}

void revokeBlobUrl(String url) {
  throw UnsupportedError('Preview blob URLs only supported on web');
}
