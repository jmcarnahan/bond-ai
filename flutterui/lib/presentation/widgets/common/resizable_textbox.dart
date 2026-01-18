import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';

/// A resizable text box that wraps BondAITextBox with a drag handle
/// allowing users to vertically resize the text area.
class ResizableTextBox extends StatefulWidget {
  final TextEditingController controller;
  final String labelText;
  final bool enabled;
  final String? Function(String?)? validator;
  final void Function(String)? onChanged;
  final String? helpTooltip;
  final double? fontSize;
  final double initialHeight;
  final double minHeight;
  final double maxHeight;

  const ResizableTextBox({
    super.key,
    required this.controller,
    required this.labelText,
    this.enabled = true,
    this.validator,
    this.onChanged,
    this.helpTooltip,
    this.fontSize,
    this.initialHeight = 120,
    this.minHeight = 80,
    this.maxHeight = 400,
  });

  @override
  State<ResizableTextBox> createState() => _ResizableTextBoxState();
}

class _ResizableTextBoxState extends State<ResizableTextBox> {
  late double _currentHeight;
  bool _isHovering = false;
  bool _isDragging = false;

  @override
  void initState() {
    super.initState();
    _currentHeight = widget.initialHeight;
  }

  void _handleDragUpdate(DragUpdateDetails details) {
    setState(() {
      _currentHeight = (_currentHeight + details.delta.dy)
          .clamp(widget.minHeight, widget.maxHeight);
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Label row with help tooltip (if provided)
        if (widget.helpTooltip != null) ...[
          Row(
            children: [
              Text(
                widget.labelText,
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
              SizedBox(width: AppSpacing.sm),
              Tooltip(
                message: widget.helpTooltip!,
                child: Icon(
                  Icons.help_outline,
                  size: 14,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                ),
              ),
            ],
          ),
          SizedBox(height: AppSpacing.md),
        ],
        // Text field with resize handle
        Stack(
          children: [
            // The text field in a sized container
            SizedBox(
              height: _currentHeight,
              child: TextFormField(
                controller: widget.controller,
                enabled: widget.enabled,
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
                validator: widget.validator,
                onChanged: widget.onChanged,
                decoration: InputDecoration(
                  labelText: widget.helpTooltip != null ? null : widget.labelText,
                  border: OutlineInputBorder(
                    borderRadius: AppBorderRadius.allMd,
                    borderSide: BorderSide(
                      color: theme.colorScheme.outlineVariant,
                    ),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: AppBorderRadius.allMd,
                    borderSide: BorderSide(
                      color: theme.colorScheme.outlineVariant,
                    ),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: AppBorderRadius.allMd,
                    borderSide: BorderSide(
                      color: theme.colorScheme.primary,
                      width: 2.0,
                    ),
                  ),
                  errorBorder: OutlineInputBorder(
                    borderRadius: AppBorderRadius.allMd,
                    borderSide: BorderSide(
                      color: theme.colorScheme.error,
                    ),
                  ),
                  focusedErrorBorder: OutlineInputBorder(
                    borderRadius: AppBorderRadius.allMd,
                    borderSide: BorderSide(
                      color: theme.colorScheme.error,
                      width: 2.0,
                    ),
                  ),
                  disabledBorder: OutlineInputBorder(
                    borderRadius: AppBorderRadius.allMd,
                    borderSide: BorderSide(
                      color: theme.colorScheme.outlineVariant.withValues(alpha: 0.5),
                    ),
                  ),
                  filled: true,
                  fillColor: widget.enabled
                      ? theme.colorScheme.surfaceContainerLow
                      : theme.colorScheme.surfaceContainerHighest,
                  floatingLabelBehavior: FloatingLabelBehavior.auto,
                  contentPadding: EdgeInsets.symmetric(
                    horizontal: AppSpacing.xl,
                    vertical: AppSpacing.xl,
                  ),
                ),
                style: TextStyle(
                  color: widget.enabled
                      ? theme.colorScheme.onSurface
                      : theme.colorScheme.onSurface.withValues(alpha: 0.6),
                  fontSize: widget.fontSize,
                ),
              ),
            ),
            // Resize handle at bottom-right
            Positioned(
              right: 4,
              bottom: 4,
              child: MouseRegion(
                cursor: SystemMouseCursors.resizeUpDown,
                onEnter: (_) => setState(() => _isHovering = true),
                onExit: (_) => setState(() => _isHovering = false),
                child: GestureDetector(
                  onVerticalDragStart: (_) => setState(() => _isDragging = true),
                  onVerticalDragEnd: (_) => setState(() => _isDragging = false),
                  onVerticalDragUpdate: _handleDragUpdate,
                  child: Container(
                    width: 20,
                    height: 20,
                    decoration: BoxDecoration(
                      color: (_isHovering || _isDragging)
                          ? theme.colorScheme.primary.withValues(alpha: 0.1)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Icon(
                      Icons.drag_handle,
                      size: 16,
                      color: (_isHovering || _isDragging)
                          ? theme.colorScheme.primary
                          : theme.colorScheme.onSurface.withValues(alpha: 0.3),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}
