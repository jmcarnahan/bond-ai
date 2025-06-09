import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';

class AgentSaveButton extends StatelessWidget {
  final bool isLoading;
  final bool isFormValid;
  final bool isEditing;
  final VoidCallback? onPressed;

  const AgentSaveButton({
    super.key,
    required this.isLoading,
    required this.isFormValid,
    required this.isEditing,
    this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    return Align(
      alignment: Alignment.bottomCenter,
      child: Container(
        width: double.infinity,
        decoration: BoxDecoration(
          color: colorScheme.surface,
          border: Border(
            top: BorderSide(
              color: colorScheme.outlineVariant.withValues(alpha: 0.3),
              width: 1,
            ),
          ),
          boxShadow: [
            BoxShadow(
              color: colorScheme.shadow.withValues(alpha: 0.1),
              blurRadius: 8,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: SafeArea(
          child: Padding(
            padding: EdgeInsets.all(AppSpacing.xxl),
            child: SizedBox(
              width: double.infinity,
              height: AppSizes.buttonHeight,
              child: ElevatedButton(
                onPressed: (isLoading || !isFormValid) ? null : onPressed,
                style: ElevatedButton.styleFrom(
                  backgroundColor: colorScheme.primary,
                  foregroundColor: colorScheme.onPrimary,
                  disabledBackgroundColor: Colors.grey.shade400,
                  disabledForegroundColor: Colors.grey.shade700,
                  padding: AppSpacing.horizontalMassive.add(AppSpacing.verticalLg),
                  textStyle: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.5,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: AppBorderRadius.allMd,
                  ),
                  elevation: AppElevation.sm,
                ).copyWith(
                  mouseCursor: WidgetStateProperty.resolveWith<MouseCursor?>(
                    (Set<WidgetState> states) {
                      if (states.contains(WidgetState.disabled)) {
                        return SystemMouseCursors.forbidden;
                      }
                      return SystemMouseCursors.click;
                    },
                  ),
                ),
                child: Text(isEditing ? 'Save Changes' : 'Create Agent'),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
