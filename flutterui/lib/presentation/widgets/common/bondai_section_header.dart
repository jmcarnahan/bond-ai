import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';

class BondAISectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final Color? iconColor;
  final EdgeInsetsGeometry? padding;
  final bool showDivider;
  final double? iconSize;

  const BondAISectionHeader({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.trailing,
    this.iconColor,
    this.padding,
    this.showDivider = false,
    this.iconSize,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Padding(
      padding: padding ?? EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                icon,
                color: iconColor ?? theme.colorScheme.primary,
                size: iconSize ?? AppSizes.iconLg,
              ),
              SizedBox(width: AppSpacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (subtitle != null) ...[
                      SizedBox(height: AppSpacing.xs),
                      Text(
                        subtitle!,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (trailing != null) ...[
                SizedBox(width: AppSpacing.lg),
                trailing!,
              ],
            ],
          ),
          if (showDivider) ...[
            SizedBox(height: AppSpacing.xl),
            Divider(
              color: theme.colorScheme.outlineVariant.withValues(alpha: 0.2),
              height: 1,
            ),
          ],
        ],
      ),
    );
  }
}