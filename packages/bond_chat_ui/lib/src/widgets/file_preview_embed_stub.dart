import 'package:flutter/material.dart';

import 'file_utils.dart';

/// Stub implementation for non-web platforms.
/// Returns a fallback icon display since iframes are not available.
Widget buildPreviewEmbed({
  required String url,
  required String mimeType,
  required double height,
  required String viewId,
}) {
  return SizedBox(
    height: height,
    child: Center(
      child: Icon(
        getFileIcon(mimeType),
        size: 64,
        color: Colors.grey,
      ),
    ),
  );
}
