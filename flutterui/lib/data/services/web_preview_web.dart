// ignore_for_file: avoid_web_libraries_in_flutter
import 'dart:html' show Blob, Url;
import 'dart:typed_data';

/// Web implementation: creates a blob URL for inline file preview.
String createBlobUrl(Uint8List bytes, String mimeType) {
  final blob = Blob([bytes], mimeType);
  return Url.createObjectUrlFromBlob(blob);
}

/// Revoke a previously created blob URL to free memory.
void revokeBlobUrl(String url) {
  Url.revokeObjectUrl(url);
}
