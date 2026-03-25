// ignore_for_file: avoid_web_libraries_in_flutter
import 'dart:html' show AnchorElement, Blob, Url, document;
import 'dart:typed_data';

/// Web implementation: triggers a file download via a temporary blob URL.
void triggerBrowserDownload(String fileName, Uint8List bytes) {
  final blob = Blob([bytes]);
  final blobUrl = Url.createObjectUrlFromBlob(blob);

  final anchor = AnchorElement()
    ..href = blobUrl
    ..download = fileName
    ..style.display = 'none';
  document.body?.append(anchor);
  anchor.click();
  anchor.remove();

  Url.revokeObjectUrl(blobUrl);
}
