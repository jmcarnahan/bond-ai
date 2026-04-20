import 'dart:convert';
import 'package:flutter/material.dart';

/// Shared utility functions for file card widgets.

/// Parse file data JSON string into a map.
/// Returns an empty map if parsing fails.
Map<String, dynamic> parseFileDataJson(String json) {
  try {
    return jsonDecode(json) as Map<String, dynamic>;
  } catch (e) {
    return {};
  }
}

/// Get an appropriate icon for the given MIME type.
IconData getFileIcon(String? mimeType) {
  if (mimeType == null) return Icons.insert_drive_file;

  if (mimeType.startsWith('image/')) return Icons.image;
  if (mimeType.startsWith('video/')) return Icons.video_file;
  if (mimeType.startsWith('audio/')) return Icons.audio_file;
  if (mimeType == 'application/pdf') return Icons.picture_as_pdf;
  if (mimeType.contains('spreadsheet') ||
      mimeType.contains('excel') ||
      mimeType == 'text/csv') {
    return Icons.table_chart;
  }
  if (mimeType.contains('text/')) return Icons.description;
  if (mimeType.contains('document') || mimeType.contains('word')) {
    return Icons.article;
  }
  if (mimeType.contains('zip') || mimeType.contains('archive')) {
    return Icons.folder_zip;
  }
  if (mimeType.contains('json') || mimeType.contains('xml')) {
    return Icons.code;
  }

  return Icons.insert_drive_file;
}

/// Format file size in bytes to a human-readable string.
String formatFileSize(int? bytes) {
  if (bytes == null) return 'Unknown size';

  if (bytes < 1024) return '$bytes B';
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
  if (bytes < 1024 * 1024 * 1024) {
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
  return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
}

/// Get a human-readable label for the given MIME type.
String getFileTypeLabel(String? mimeType) {
  if (mimeType == null) return 'File';

  if (mimeType == 'application/pdf') return 'PDF';
  if (mimeType == 'text/csv') return 'CSV';
  if (mimeType == 'text/html') return 'HTML';
  if (mimeType.contains('spreadsheet') || mimeType.contains('excel')) {
    return 'Excel';
  }
  if (mimeType.contains('document') || mimeType.contains('word')) {
    return 'Word';
  }
  if (mimeType.contains('zip')) return 'ZIP';
  if (mimeType.startsWith('image/')) return 'Image';
  if (mimeType.startsWith('video/')) return 'Video';
  if (mimeType.startsWith('audio/')) return 'Audio';
  if (mimeType.startsWith('text/')) return 'Text';

  return 'File';
}

/// Check if a MIME type can be rendered inline in a browser iframe.
/// Only types that browsers can natively display well.
bool isIframePreviewable(String? mimeType) {
  if (mimeType == null) return false;
  return mimeType == 'application/pdf' || mimeType == 'text/html';
}

/// Check if a MIME type is an image that can be displayed via Image widget.
bool isImageMimeType(String? mimeType) {
  if (mimeType == null) return false;
  return mimeType.startsWith('image/');
}
