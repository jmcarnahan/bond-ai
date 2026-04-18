// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:html' as html;
import 'dart:js_interop';
import 'dart:js_interop_unsafe';
import 'dart:typed_data';

/// Web implementation using browser APIs.

bool get isSupported => true;

/// Create an empty JS object (equivalent to {}).
JSObject _newJSObject() {
  return (globalContext['Object'] as JSFunction).callAsConstructor();
}

Future<bool> copyImageToClipboard(Uint8List bytes) async {
  try {
    final blob = html.Blob([bytes], 'image/png');
    // Build the ClipboardItem options: {'image/png': blob}
    final options = _newJSObject();
    options['image/png'] = (blob as dynamic) as JSObject;
    final clipboardItem =
        (globalContext['ClipboardItem'] as JSFunction).callAsConstructor(options);

    final clipboard =
        (globalContext['navigator'] as JSObject)['clipboard'];
    if (clipboard == null) return false;

    final itemsArray = <JSAny?>[clipboardItem].toJS;
    final writePromise =
        (clipboard as JSObject).callMethod('write'.toJS, itemsArray);
    await (writePromise! as JSPromise).toDart;

    return true;
  } catch (e) {
    return false;
  }
}

Future<List<({String name, Uint8List bytes})>> readFilesFromClipboard() async {
  try {
    final clipboard =
        (globalContext['navigator'] as JSObject)['clipboard'];
    if (clipboard == null) return [];

    final readPromise =
        (clipboard as JSObject).callMethod('read'.toJS);
    final items = await (readPromise! as JSPromise).toDart;

    final files = <({String name, Uint8List bytes})>[];
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    var fileIndex = 0;

    final length =
        ((items! as JSObject)['length']! as JSNumber).toDartDouble.toInt();
    for (var i = 0; i < length; i++) {
      final item = (items as JSObject)[i.toString()];
      final types = (item! as JSObject)['types'];
      final typesLength =
          ((types! as JSObject)['length']! as JSNumber).toDartDouble.toInt();

      for (var j = 0; j < typesLength; j++) {
        final type = ((types as JSObject)[j.toString()]! as JSString).toDart;
        // Skip text types - those are handled by the TextField
        if (type == 'text/plain' || type == 'text/html') continue;

        final blobPromise = (item as JSObject)
            .callMethodVarArgs('getType'.toJS, [type.toJS]);
        final blob = await (blobPromise! as JSPromise).toDart;

        // In dart2js, JS Blob objects are compatible with html.Blob via dynamic cast
        final reader = html.FileReader();
        reader.readAsArrayBuffer((blob as dynamic) as html.Blob);
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
