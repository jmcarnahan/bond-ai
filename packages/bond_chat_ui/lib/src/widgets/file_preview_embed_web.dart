// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:html' as html;
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';

final _registeredViewTypes = <String>{};

/// Web implementation: renders an iframe with the preview URL.
/// Uses a unique view type per (viewId, url) pair so that a new blob URL
/// for the same file ID registers a fresh factory instead of serving a stale one.
Widget buildPreviewEmbed({
  required String url,
  required String mimeType,
  required double height,
  required String viewId,
}) {
  // Include URL hashCode to guarantee a new factory when the URL changes.
  final viewType = 'file-preview-$viewId-${url.hashCode}';

  if (!_registeredViewTypes.contains(viewType)) {
    ui_web.platformViewRegistry.registerViewFactory(viewType, (int id) {
      final iframe = html.IFrameElement()
        ..src = url
        ..style.border = 'none'
        ..style.width = '100%'
        ..style.height = '100%'
        ..style.pointerEvents = 'none'
        ..setAttribute('sandbox', 'allow-same-origin allow-scripts')
        ..setAttribute('loading', 'lazy');
      return iframe;
    });
    _registeredViewTypes.add(viewType);
  }

  return SizedBox(
    height: height,
    child: HtmlElementView(viewType: viewType),
  );
}
