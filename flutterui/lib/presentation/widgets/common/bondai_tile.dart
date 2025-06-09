import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';

enum BondAITileType {
  normal,
  selectable,
  checkbox,
  radio,
  switch_,
}

class BondAITile extends StatelessWidget {
  final String title;
  final String? subtitle;
  final String? description;
  final Widget? leading;
  final Widget? trailing;
  final BondAITileType type;
  final bool selected;
  final bool? value;
  final ValueChanged<bool?>? onChanged;
  final VoidCallback? onTap;
  final bool enabled;
  final EdgeInsetsGeometry? contentPadding;
  final Color? backgroundColor;
  final Color? selectedBackgroundColor;
  final Color? borderColor;
  final Color? selectedBorderColor;
  final double? borderWidth;
  final double? selectedBorderWidth;
  final BorderRadius? borderRadius;
  final bool showBorder;
  final bool dense;

  const BondAITile({
    super.key,
    required this.title,
    this.subtitle,
    this.description,
    this.leading,
    this.trailing,
    this.type = BondAITileType.normal,
    this.selected = false,
    this.value,
    this.onChanged,
    this.onTap,
    this.enabled = true,
    this.contentPadding,
    this.backgroundColor,
    this.selectedBackgroundColor,
    this.borderColor,
    this.selectedBorderColor,
    this.borderWidth,
    this.selectedBorderWidth,
    this.borderRadius,
    this.showBorder = true,
    this.dense = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isSelected = selected || (value ?? false);
    
    return Container(
      margin: EdgeInsets.only(bottom: AppSpacing.md),
      decoration: BoxDecoration(
        borderRadius: borderRadius ?? AppBorderRadius.allMd,
        border: showBorder
            ? Border.all(
                color: isSelected
                    ? (selectedBorderColor ?? theme.colorScheme.primary.withValues(alpha: 0.5))
                    : (borderColor ?? theme.colorScheme.outlineVariant.withValues(alpha: 0.3)),
                width: isSelected 
                    ? (selectedBorderWidth ?? 2) 
                    : (borderWidth ?? 1),
              )
            : null,
        color: isSelected
            ? (selectedBackgroundColor ?? theme.colorScheme.primaryContainer.withValues(alpha: 0.1))
            : (backgroundColor ?? theme.colorScheme.surfaceContainerLow),
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: borderRadius ?? AppBorderRadius.allMd,
        child: InkWell(
          onTap: enabled ? (_getOnTap() ?? onTap) : null,
          borderRadius: borderRadius ?? AppBorderRadius.allMd,
          child: _buildContent(context, theme),
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, ThemeData theme) {
    switch (type) {
      case BondAITileType.checkbox:
        return CheckboxListTile(
          title: _buildTitle(theme),
          subtitle: _buildSubtitle(theme),
          secondary: leading,
          value: value ?? false,
          onChanged: enabled ? onChanged : null,
          activeColor: theme.colorScheme.primary,
          contentPadding: contentPadding ?? EdgeInsets.symmetric(
            horizontal: AppSpacing.xl,
            vertical: dense ? AppSpacing.md : AppSpacing.lg,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: borderRadius ?? AppBorderRadius.allMd,
          ),
          dense: dense,
        );
        
      case BondAITileType.radio:
        return RadioListTile<bool>(
          title: _buildTitle(theme),
          subtitle: _buildSubtitle(theme),
          secondary: leading,
          value: true,
          groupValue: value ?? false,
          onChanged: enabled ? (val) => onChanged?.call(val) : null,
          activeColor: theme.colorScheme.primary,
          contentPadding: contentPadding ?? EdgeInsets.symmetric(
            horizontal: AppSpacing.xl,
            vertical: dense ? AppSpacing.md : AppSpacing.lg,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: borderRadius ?? AppBorderRadius.allMd,
          ),
          dense: dense,
        );
        
      case BondAITileType.switch_:
        return SwitchListTile(
          title: _buildTitle(theme),
          subtitle: _buildSubtitle(theme),
          secondary: leading,
          value: value ?? false,
          onChanged: enabled ? onChanged : null,
          activeColor: theme.colorScheme.primary,
          contentPadding: contentPadding ?? EdgeInsets.symmetric(
            horizontal: AppSpacing.xl,
            vertical: dense ? AppSpacing.md : AppSpacing.lg,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: borderRadius ?? AppBorderRadius.allMd,
          ),
          dense: dense,
        );
        
      case BondAITileType.selectable:
      case BondAITileType.normal:
        return ListTile(
          leading: leading,
          title: _buildTitle(theme),
          subtitle: _buildSubtitle(theme),
          trailing: trailing ?? (type == BondAITileType.selectable && selected
              ? Icon(
                  Icons.check_circle,
                  color: theme.colorScheme.primary,
                  size: AppSizes.iconLg,
                )
              : null),
          enabled: enabled,
          selected: selected,
          selectedColor: theme.colorScheme.primary,
          contentPadding: contentPadding ?? EdgeInsets.symmetric(
            horizontal: AppSpacing.xl,
            vertical: dense ? AppSpacing.md : AppSpacing.lg,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: borderRadius ?? AppBorderRadius.allMd,
          ),
          dense: dense,
        );
    }
  }

  Widget _buildTitle(ThemeData theme) {
    return Text(
      title,
      style: theme.textTheme.titleSmall?.copyWith(
        fontWeight: FontWeight.w500,
        color: enabled
            ? theme.colorScheme.onSurface
            : theme.disabledColor,
      ),
    );
  }

  Widget? _buildSubtitle(ThemeData theme) {
    if (subtitle == null && description == null) return null;
    
    if (description != null && subtitle != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            subtitle!,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: enabled
                  ? theme.colorScheme.onSurface.withValues(alpha: 0.8)
                  : theme.disabledColor,
            ),
          ),
          SizedBox(height: AppSpacing.xs),
          Text(
            description!,
            style: theme.textTheme.bodySmall?.copyWith(
              color: enabled
                  ? theme.colorScheme.onSurface.withValues(alpha: 0.6)
                  : theme.disabledColor,
            ),
          ),
        ],
      );
    }
    
    return Text(
      subtitle ?? description!,
      style: theme.textTheme.bodySmall?.copyWith(
        color: enabled
            ? theme.colorScheme.onSurface.withValues(alpha: 0.7)
            : theme.disabledColor,
      ),
    );
  }

  VoidCallback? _getOnTap() {
    switch (type) {
      case BondAITileType.checkbox:
      case BondAITileType.switch_:
        return enabled ? () => onChanged?.call(!(value ?? false)) : null;
      case BondAITileType.radio:
        return enabled ? () => onChanged?.call(true) : null;
      case BondAITileType.selectable:
      case BondAITileType.normal:
        return null;
    }
  }
}

class BondAITileGroup extends StatelessWidget {
  final List<Widget> children;
  final EdgeInsetsGeometry? padding;
  final String? title;
  final bool showDividers;
  final double spacing;

  const BondAITileGroup({
    super.key,
    required this.children,
    this.padding,
    this.title,
    this.showDividers = false,
    this.spacing = 0,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Padding(
      padding: padding ?? EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (title != null) ...[
            Text(
              title!,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w500,
                color: theme.colorScheme.onSurface,
              ),
            ),
            SizedBox(height: AppSpacing.md),
          ],
          if (showDividers)
            ...children.expand((child) => [
              child,
              if (children.last != child) ...[
                SizedBox(height: spacing),
                Divider(
                  color: theme.colorScheme.outlineVariant.withValues(alpha: 0.2),
                  height: 1,
                ),
                SizedBox(height: spacing),
              ],
            ]).toList()
          else
            ...children,
        ],
      ),
    );
  }
}