import 'dart:typed_data';

import 'web_drop_helper_stub.dart'
    if (dart.library.html) 'web_drop_helper_web.dart' as impl;

/// Callback for when files are dropped.
typedef WebDropFilesCallback = void Function(
    List<({String name, Uint8List bytes})> files);

/// Callback for drag enter/leave visual state.
typedef WebDragStateCallback = void Function();

/// Platform-agnostic web drop helper.
///
/// On web: listens for custom JavaScript events dispatched by the
/// drag-and-drop bridge in index.html. Uses dart:html addEventListener
/// (not package:web property setters) so handlers survive dart2js
/// tree-shaking in release builds.
///
/// On native platforms: no-op (desktop_drop handles it via platform channels).
class WebDropHelper {
  static void init({
    required WebDropFilesCallback onFileDrop,
    required WebDragStateCallback onDragEnter,
    required WebDragStateCallback onDragLeave,
  }) {
    impl.initWebDrop(
      onFileDrop: onFileDrop,
      onDragEnter: onDragEnter,
      onDragLeave: onDragLeave,
    );
  }

  static void dispose() {
    impl.disposeWebDrop();
  }

  static bool get isSupported => impl.isWebDropSupported;
}
