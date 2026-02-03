// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:html' as html;
import 'dart:js_util' as js_util;
import 'dart:typed_data';

/// Web implementation using browser APIs.

bool get isSupported => true;

Future<bool> copyImageToClipboard(Uint8List bytes) async {
  try {
    final blob = html.Blob([bytes], 'image/png');
    final clipboardItem = js_util.callConstructor(
      js_util.getProperty(html.window, 'ClipboardItem'),
      [
        js_util.jsify({'image/png': blob})
      ],
    );
    final clipboard = html.window.navigator.clipboard;
    if (clipboard == null) return false;
    await js_util.promiseToFuture(
      js_util.callMethod(
        clipboard,
        'write',
        [
          js_util.jsify([clipboardItem])
        ],
      ),
    );
    return true;
  } catch (e) {
    return false;
  }
}

void downloadImage(Uint8List bytes, String filename) {
  final blob = html.Blob([bytes], 'image/png');
  final url = html.Url.createObjectUrlFromBlob(blob);
  final anchor = html.AnchorElement()
    ..href = url
    ..download = filename
    ..style.display = 'none';
  html.document.body?.append(anchor);
  anchor.click();
  anchor.remove();
  html.Url.revokeObjectUrl(url);
}
