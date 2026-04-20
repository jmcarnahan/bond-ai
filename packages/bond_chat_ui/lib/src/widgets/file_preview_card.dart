import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'file_preview_embed.dart';
import 'file_utils.dart';

/// A file preview card that shows a visual preview of the file content
/// with open and download actions.
///
/// The preview area displays:
/// - An image (from bytes or network URL) for image files
/// - An iframe embed (web only) for HTML and PDF files
/// - A styled proxy preview (icon + type label) for other known file types
/// - A plain icon fallback when no preview data is available
///
/// The info bar below shows filename, type badge, file size, and a download button.
class FilePreviewCard extends StatefulWidget {
  /// JSON string containing file metadata:
  /// `{file_id, file_name, file_size, mime_type}`
  final String fileDataJson;

  /// Callback to resolve a file ID to a preview URL (e.g., blob URL, presigned URL).
  /// If null or returns null, falls back to proxy preview or icon display.
  final Future<String?> Function(String fileId)? onPreviewUrl;

  /// Pre-loaded preview image bytes. Takes priority over [onPreviewUrl] for images.
  final Uint8List? previewImageBytes;

  /// Called when the user taps the preview area to open the document.
  /// If null and a preview URL is available, opens the URL in a new browser tab.
  final VoidCallback? onOpen;

  /// Called when the user taps the download button.
  final Future<void> Function(String fileId, String fileName)? onDownload;

  /// Maximum width of the card.
  final double maxWidth;

  /// Height of the preview area.
  final double previewHeight;

  /// Called when a previously created preview URL is no longer needed.
  /// Use this to revoke blob URLs and free memory.
  final void Function(String url)? onPreviewUrlDispose;

  const FilePreviewCard({
    super.key,
    required this.fileDataJson,
    this.onPreviewUrl,
    this.previewImageBytes,
    this.onOpen,
    this.onDownload,
    this.maxWidth = 400,
    this.previewHeight = 200,
    this.onPreviewUrlDispose,
  });

  @override
  State<FilePreviewCard> createState() => _FilePreviewCardState();
}

class _FilePreviewCardState extends State<FilePreviewCard> {
  bool _isDownloading = false;
  bool _isLoadingPreview = false;
  String? _previewUrl;
  bool _previewFailed = false;

  @override
  void initState() {
    super.initState();
    _loadPreviewUrl();
  }

  @override
  void didUpdateWidget(FilePreviewCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.fileDataJson != widget.fileDataJson) {
      _revokePreviewUrl();
      _loadPreviewUrl();
    }
  }

  @override
  void dispose() {
    _revokePreviewUrl();
    super.dispose();
  }

  void _revokePreviewUrl() {
    if (_previewUrl != null && widget.onPreviewUrlDispose != null) {
      widget.onPreviewUrlDispose!(_previewUrl!);
    }
    _previewUrl = null;
  }

  void _loadPreviewUrl() {
    if (widget.previewImageBytes != null || widget.onPreviewUrl == null) return;

    final fileData = parseFileDataJson(widget.fileDataJson);
    final fileId = fileData['file_id'] as String?;
    final mimeType = fileData['mime_type'] as String?;
    if (fileId == null) return;

    // Only fetch preview URL for types that can actually be rendered inline.
    // Other types get a styled proxy preview without fetching.
    if (!isImageMimeType(mimeType) && !isIframePreviewable(mimeType)) return;

    setState(() {
      _isLoadingPreview = true;
      _previewFailed = false;
      _previewUrl = null;
    });

    widget.onPreviewUrl!(fileId).then((url) {
      if (mounted) {
        setState(() {
          _previewUrl = url;
          _isLoadingPreview = false;
          _previewFailed = url == null;
        });
      }
    }).catchError((Object e) {
      if (mounted) {
        setState(() {
          _isLoadingPreview = false;
          _previewFailed = true;
        });
      }
    });
  }

  Future<void> _downloadFile(String fileId, String fileName) async {
    if (widget.onDownload == null) return;

    setState(() {
      _isDownloading = true;
    });

    try {
      await widget.onDownload!(fileId, fileName);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Downloaded: $fileName'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Download failed: ${e.toString()}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isDownloading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final fileData = parseFileDataJson(widget.fileDataJson);
    final fileName = fileData['file_name'] as String? ?? 'Unknown File';
    final fileSize = fileData['file_size'] as int?;
    final mimeType = fileData['mime_type'] as String?;
    final fileId = fileData['file_id'] as String?;

    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Container(
      constraints: BoxConstraints(maxWidth: widget.maxWidth),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: colorScheme.outlineVariant,
          width: 1,
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Preview area
          _buildPreviewArea(context, fileId, mimeType, colorScheme),
          // Info bar
          _buildInfoBar(context, fileId, fileName, fileSize, mimeType, colorScheme),
        ],
      ),
    );
  }

  void _handlePreviewTap() {
    if (widget.onOpen != null) {
      widget.onOpen!();
      return;
    }
    // Default: open preview URL in a new browser tab
    if (_previewUrl != null) {
      final uri = Uri.tryParse(_previewUrl!);
      if (uri != null) {
        launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    }
  }

  Widget _buildPreviewArea(
    BuildContext context,
    String? fileId,
    String? mimeType,
    ColorScheme colorScheme,
  ) {
    final hasAction = widget.onOpen != null || _previewUrl != null;

    return ClipRRect(
      borderRadius: const BorderRadius.only(
        topLeft: Radius.circular(11),
        topRight: Radius.circular(11),
      ),
      child: Stack(
        children: [
          SizedBox(
            height: widget.previewHeight,
            width: double.infinity,
            child: _buildPreviewContent(fileId, mimeType, colorScheme),
          ),
          // Transparent overlay to capture taps above iframes.
          // Iframes consume pointer events, so without this overlay
          // the InkWell would never receive taps on iframe content.
          Positioned.fill(
            child: MouseRegion(
              cursor: hasAction ? SystemMouseCursors.click : SystemMouseCursors.basic,
              child: Material(
                color: Colors.transparent,
                child: InkWell(
                  onTap: hasAction ? _handlePreviewTap : null,
                  child: const SizedBox.expand(),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPreviewContent(
    String? fileId,
    String? mimeType,
    ColorScheme colorScheme,
  ) {
    // Priority 1: Pre-loaded image bytes
    if (widget.previewImageBytes != null) {
      return Image.memory(
        widget.previewImageBytes!,
        fit: BoxFit.cover,
        width: double.infinity,
        height: widget.previewHeight,
        errorBuilder: (context, error, stackTrace) =>
            _buildIconFallback(mimeType, colorScheme),
      );
    }

    // Priority 2: Loading state (only shown for previewable types)
    if (_isLoadingPreview) {
      return _buildLoadingPlaceholder(mimeType, colorScheme);
    }

    // Priority 3: Preview URL loaded successfully
    if (_previewUrl != null && !_previewFailed) {
      // Image preview
      if (isImageMimeType(mimeType)) {
        return Image.network(
          _previewUrl!,
          fit: BoxFit.cover,
          width: double.infinity,
          height: widget.previewHeight,
          loadingBuilder: (context, child, loadingProgress) {
            if (loadingProgress == null) return child;
            return _buildLoadingPlaceholder(mimeType, colorScheme);
          },
          errorBuilder: (context, error, stackTrace) =>
              _buildIconFallback(mimeType, colorScheme),
        );
      }

      // HTML or PDF — use iframe embed on web
      if (isIframePreviewable(mimeType) && fileId != null) {
        return FilePreviewEmbed.build(
          url: _previewUrl!,
          mimeType: mimeType!,
          height: widget.previewHeight,
          viewId: fileId,
        );
      }
    }

    // Priority 4: Proxy preview for known file types (CSV, Word, Excel, etc.)
    // Shows a styled icon + type label — looks intentional, not broken.
    if (mimeType != null && !isImageMimeType(mimeType) && !isIframePreviewable(mimeType)) {
      return _buildProxyPreview(mimeType, colorScheme);
    }

    // Priority 5: Fallback icon (unknown type or preview failed)
    return _buildIconFallback(mimeType, colorScheme);
  }

  Widget _buildProxyPreview(String mimeType, ColorScheme colorScheme) {
    return Container(
      color: colorScheme.primaryContainer.withValues(alpha: 0.15),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: colorScheme.primaryContainer.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(
                getFileIcon(mimeType),
                size: 40,
                color: colorScheme.onPrimaryContainer,
              ),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: colorScheme.secondaryContainer.withValues(alpha: 0.7),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                getFileTypeLabel(mimeType),
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onSecondaryContainer,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingPlaceholder(String? mimeType, ColorScheme colorScheme) {
    return Container(
      color: colorScheme.primaryContainer.withValues(alpha: 0.2),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              getFileIcon(mimeType),
              size: 40,
              color: colorScheme.onPrimaryContainer.withValues(alpha: 0.5),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: colorScheme.onPrimaryContainer.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildIconFallback(String? mimeType, ColorScheme colorScheme) {
    return Container(
      color: colorScheme.primaryContainer.withValues(alpha: 0.2),
      child: Center(
        child: Icon(
          getFileIcon(mimeType),
          size: 64,
          color: colorScheme.onPrimaryContainer.withValues(alpha: 0.6),
        ),
      ),
    );
  }

  Widget _buildInfoBar(
    BuildContext context,
    String? fileId,
    String fileName,
    int? fileSize,
    String? mimeType,
    ColorScheme colorScheme,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12.0, vertical: 8.0),
      child: Row(
        children: [
          // Small file icon
          Icon(
            getFileIcon(mimeType),
            size: 20,
            color: colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 8),
          // File name
          Expanded(
            child: Text(
              fileName,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: colorScheme.onSurface,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          // Type badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: colorScheme.secondaryContainer,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              getFileTypeLabel(mimeType),
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w500,
                color: colorScheme.onSecondaryContainer,
              ),
            ),
          ),
          const SizedBox(width: 6),
          // File size
          Text(
            formatFileSize(fileSize),
            style: TextStyle(
              fontSize: 11,
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(width: 8),
          // Download button
          if (_isDownloading)
            const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          else
            InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: fileId != null && widget.onDownload != null
                  ? () => _downloadFile(fileId, fileName)
                  : null,
              child: Icon(
                Icons.download,
                color: colorScheme.primary,
                size: 20,
              ),
            ),
        ],
      ),
    );
  }
}
