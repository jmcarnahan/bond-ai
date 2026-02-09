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

Future<List<({String name, Uint8List bytes})>> readFilesFromClipboard() async {
  try {
    final clipboard = html.window.navigator.clipboard;
    if (clipboard == null) return [];

    final items = await js_util.promiseToFuture(
      js_util.callMethod(clipboard, 'read', []),
    );

    final files = <({String name, Uint8List bytes})>[];
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    var fileIndex = 0;

    final length = (js_util.getProperty(items, 'length') as num).toInt();
    for (var i = 0; i < length; i++) {
      final item = js_util.getProperty(items, i);
      final types = js_util.getProperty(item, 'types');
      final typesLength =
          (js_util.getProperty(types, 'length') as num).toInt();

      for (var j = 0; j < typesLength; j++) {
        final type = js_util.getProperty(types, j).toString();
        // Skip text types - those are handled by the TextField
        if (type == 'text/plain' || type == 'text/html') continue;

        final blob = await js_util.promiseToFuture(
          js_util.callMethod(item, 'getType', [type]),
        );

        final reader = html.FileReader();
        reader.readAsArrayBuffer(blob);
        await reader.onLoadEnd.first;

        final result = reader.result;
        if (result != null) {
          final bytes = Uint8List.fromList((result as List).cast<int>());
          final ext = _extensionFromMimeType(type);
          final name = 'pasted_${timestamp}_${fileIndex++}.$ext';
          files.add((name: name, bytes: bytes));
        }
      }
    }
    return files;
  } catch (e) {
    return [];
  }
}

String _extensionFromMimeType(String mimeType) {
  switch (mimeType) {
    case 'image/png':
      return 'png';
    case 'image/jpeg':
      return 'jpg';
    case 'image/gif':
      return 'gif';
    case 'image/webp':
      return 'webp';
    case 'image/svg+xml':
      return 'svg';
    case 'application/pdf':
      return 'pdf';
    default:
      final parts = mimeType.split('/');
      return parts.length > 1 ? parts[1] : 'bin';
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
