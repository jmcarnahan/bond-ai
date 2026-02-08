// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:async';
import 'dart:html' as html;
import 'dart:js_util' as js_util;
import 'dart:typed_data';

/// Web implementation of drag-and-drop file handling.
///
/// Listens for custom events dispatched by the JavaScript bridge in
/// index.html. Uses dart:html's addEventListener (not package:web property
/// setters) so the event registrations survive dart2js tree-shaking.

bool get isWebDropSupported => true;

StreamSubscription? _dropSub;
StreamSubscription? _enterSub;
StreamSubscription? _leaveSub;

void initWebDrop({
  required void Function(List<({String name, Uint8List bytes})> files) onFileDrop,
  required void Function() onDragEnter,
  required void Function() onDragLeave,
}) {
  // Clean up any previous subscriptions
  disposeWebDrop();

  _enterSub = html.window.on['bond-drag-enter'].listen((_) {
    onDragEnter();
  });

  _leaveSub = html.window.on['bond-drag-leave'].listen((_) {
    onDragLeave();
  });

  _dropSub = html.window.on['bond-file-drop'].listen((_) async {
    final files = await _readDroppedFiles();
    if (files.isNotEmpty) {
      onFileDrop(files);
    }
  });
}

void disposeWebDrop() {
  _dropSub?.cancel();
  _dropSub = null;
  _enterSub?.cancel();
  _enterSub = null;
  _leaveSub?.cancel();
  _leaveSub = null;
}

/// Read files from the global _bondDroppedFiles set by JavaScript.
Future<List<({String name, Uint8List bytes})>> _readDroppedFiles() async {
  try {
    final dynamic fileList =
        js_util.getProperty(html.window, '_bondDroppedFiles');
    if (fileList == null) return [];

    final int length =
        (js_util.getProperty(fileList, 'length') as num).toInt();
    final files = <({String name, Uint8List bytes})>[];

    for (var i = 0; i < length; i++) {
      final dynamic file = js_util.callMethod(fileList, 'item', [i]);
      if (file == null) continue;

      final String name = js_util.getProperty(file, 'name').toString();

      // Read file contents using FileReader
      final reader = html.FileReader();
      reader.readAsArrayBuffer(file as html.Blob);
      await reader.onLoadEnd.first;

      final result = reader.result;
      if (result != null) {
        final bytes = Uint8List.fromList((result as List).cast<int>());
        files.add((name: name, bytes: bytes));
      }
    }

    // Clear the global reference
    js_util.setProperty(html.window, '_bondDroppedFiles', null);

    return files;
  } catch (e) {
    return [];
  }
}
