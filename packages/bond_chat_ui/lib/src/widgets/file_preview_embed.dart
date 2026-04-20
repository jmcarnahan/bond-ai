import 'package:flutter/material.dart';

import 'file_preview_embed_stub.dart'
    if (dart.library.html) 'file_preview_embed_web.dart' as impl;

/// Platform-agnostic file preview embed.
/// On web, renders an iframe with the preview URL.
/// On other platforms, shows a fallback icon.
class FilePreviewEmbed {
  static Widget build({
    required String url,
    required String mimeType,
    required double height,
    required String viewId,
  }) {
    return impl.buildPreviewEmbed(
      url: url,
      mimeType: mimeType,
      height: height,
      viewId: viewId,
    );
  }
}
