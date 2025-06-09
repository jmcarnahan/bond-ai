import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';

class BondAILoadingState extends StatelessWidget {
  final String? message;
  final double? size;
  final Color? color;
  final bool showBackground;
  final EdgeInsetsGeometry? padding;

  const BondAILoadingState({
    super.key,
    this.message,
    this.size,
    this.color,
    this.showBackground = true,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    final content = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: size ?? 20,
          height: size ?? 20,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            valueColor: AlwaysStoppedAnimation(
              color ?? theme.colorScheme.primary,
            ),
          ),
        ),
        if (message != null) ...[
          SizedBox(width: AppSpacing.lg),
          Text(
            message!,
            style: theme.textTheme.bodyMedium,
          ),
        ],
      ],
    );

    if (!showBackground) {
      return Center(child: content);
    }

    return Container(
      padding: padding ?? AppSpacing.allXl,
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        borderRadius: AppBorderRadius.allMd,
        border: Border.all(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.3),
        ),
      ),
      child: content,
    );
  }
}