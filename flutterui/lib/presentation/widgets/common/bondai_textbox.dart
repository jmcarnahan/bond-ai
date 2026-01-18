import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/presentation/widgets/common/info_tooltip.dart';

class BondAITextBox extends StatelessWidget {
  final TextEditingController controller;
  final String labelText;
  final bool enabled;
  final int? maxLines;
  final String? Function(String?)? validator;
  final void Function(String)? onChanged;
  final String? helpTooltip;
  final TextInputType? keyboardType;
  final bool obscureText;
  final Widget? suffixIcon;
  final Widget? prefixIcon;
  final String? hintText;
  final int? maxLength;
  final bool readOnly;
  final VoidCallback? onTap;
  final FocusNode? focusNode;
  final TextInputAction? textInputAction;
  final void Function(String)? onFieldSubmitted;
  final double? fontSize;

  const BondAITextBox({
    super.key,
    required this.controller,
    required this.labelText,
    this.enabled = true,
    this.maxLines = 1,
    this.validator,
    this.onChanged,
    this.helpTooltip,
    this.keyboardType,
    this.obscureText = false,
    this.suffixIcon,
    this.prefixIcon,
    this.hintText,
    this.maxLength,
    this.readOnly = false,
    this.onTap,
    this.focusNode,
    this.textInputAction,
    this.onFieldSubmitted,
    this.fontSize,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (helpTooltip != null) ...[
          Row(
            children: [
              Text(
                labelText,
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
              SizedBox(width: AppSpacing.sm),
              InfoIcon(
                tooltip: helpTooltip!,
                size: 14,
              ),
            ],
          ),
          SizedBox(height: AppSpacing.md),
        ],
        TextFormField(
          controller: controller,
          enabled: enabled,
          maxLines: maxLines,
          validator: validator,
          onChanged: onChanged,
          keyboardType: keyboardType,
          obscureText: obscureText,
          maxLength: maxLength,
          readOnly: readOnly,
          onTap: onTap,
          focusNode: focusNode,
          textInputAction: textInputAction,
          onFieldSubmitted: onFieldSubmitted,
          decoration: InputDecoration(
            labelText: helpTooltip != null ? null : labelText,
            hintText: hintText,
            suffixIcon: suffixIcon,
            prefixIcon: prefixIcon,
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
            fillColor: enabled
                ? (readOnly
                    ? theme.colorScheme.surfaceContainerHighest
                    : theme.colorScheme.surfaceContainerLow)
                : theme.colorScheme.surfaceContainerHighest,
            floatingLabelBehavior: FloatingLabelBehavior.auto,
            contentPadding: EdgeInsets.symmetric(
              horizontal: AppSpacing.xl,
              vertical: maxLines! > 1 ? AppSpacing.xl : AppSpacing.lg,
            ),
            counterText: '',
          ),
          style: TextStyle(
            color: enabled
                ? theme.colorScheme.onSurface
                : theme.colorScheme.onSurface.withValues(alpha: 0.6),
            fontSize: fontSize,
          ),
        ),
        if (maxLength != null)
          Padding(
            padding: EdgeInsets.only(top: AppSpacing.xs, right: AppSpacing.sm),
            child: Align(
              alignment: Alignment.centerRight,
              child: Text(
                '${controller.text.length}/$maxLength',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ),
      ],
    );
  }
}
