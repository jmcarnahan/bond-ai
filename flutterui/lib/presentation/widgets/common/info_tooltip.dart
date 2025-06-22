import 'package:flutter/material.dart';

class InfoTooltip extends StatelessWidget {
  final String message;
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final double? height;
  final TextStyle? textStyle;
  final Color? backgroundColor;
  final Duration? waitDuration;
  final Duration? showDuration;

  const InfoTooltip({
    super.key,
    required this.message,
    required this.child,
    this.padding,
    this.height,
    this.textStyle,
    this.backgroundColor,
    this.waitDuration,
    this.showDuration,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Tooltip(
      message: message,
      padding: padding ?? const EdgeInsets.all(12.0),
      height: height,
      textStyle: textStyle ?? TextStyle(
        color: Colors.white,
        fontSize: 14,
        height: 1.4,
      ),
      decoration: BoxDecoration(
        color: backgroundColor ?? theme.colorScheme.inverseSurface,
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      waitDuration: waitDuration ?? const Duration(milliseconds: 500),
      showDuration: showDuration ?? const Duration(seconds: 3),
      child: child,
    );
  }
}

class InfoIcon extends StatelessWidget {
  final String tooltip;
  final double size;
  final Color? color;

  const InfoIcon({
    super.key,
    required this.tooltip,
    this.size = 16,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return InfoTooltip(
      message: tooltip,
      child: Icon(
        Icons.help_outline,
        size: size,
        color: color ?? theme.colorScheme.onSurface.withValues(alpha: 0.6),
      ),
    );
  }
}