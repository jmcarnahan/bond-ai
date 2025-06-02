import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';

class AgentFormFields extends StatelessWidget {
  final TextEditingController nameController;
  final TextEditingController descriptionController;
  final TextEditingController instructionsController;
  final bool enabled;
  final void Function(String) onNameChanged;
  final void Function(String) onDescriptionChanged;
  final void Function(String) onInstructionsChanged;

  const AgentFormFields({
    super.key,
    required this.nameController,
    required this.descriptionController,
    required this.instructionsController,
    required this.enabled,
    required this.onNameChanged,
    required this.onDescriptionChanged,
    required this.onInstructionsChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        AgentTextField(
          controller: nameController,
          labelText: 'Agent Name',
          enabled: enabled,
          validator: (value) {
            if (value == null || value.isEmpty) {
              return 'Please enter an agent name';
            }
            return null;
          },
          onChanged: onNameChanged,
        ),
        SizedBox(height: AppSpacing.lg),
        AgentTextField(
          controller: descriptionController,
          labelText: 'Description (Optional)',
          enabled: enabled,
          onChanged: onDescriptionChanged,
        ),
        SizedBox(height: AppSpacing.lg),
        AgentTextField(
          controller: instructionsController,
          labelText: 'Instructions',
          enabled: enabled,
          maxLines: 5,
          validator: (value) {
            if (value == null || value.isEmpty) {
              return 'Please enter instructions for the agent';
            }
            return null;
          },
          onChanged: onInstructionsChanged,
        ),
      ],
    );
  }
}

class AgentTextField extends StatelessWidget {
  final TextEditingController controller;
  final String labelText;
  final bool enabled;
  final int? maxLines;
  final String? Function(String?)? validator;
  final void Function(String)? onChanged;

  const AgentTextField({
    super.key,
    required this.controller,
    required this.labelText,
    this.enabled = true,
    this.maxLines = 1,
    this.validator,
    this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return TextFormField(
      controller: controller,
      enabled: enabled,
      decoration: InputDecoration(
        labelText: labelText,
        border: OutlineInputBorder(
          borderRadius: AppBorderRadius.allMd,
          borderSide: BorderSide(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
          ),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: AppBorderRadius.allMd,
          borderSide: BorderSide(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
          ),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: AppBorderRadius.allMd,
          borderSide: BorderSide(
            color: theme.colorScheme.primary,
            width: 2.0,
          ),
        ),
        filled: true,
        fillColor: enabled 
            ? theme.colorScheme.surfaceContainerLow 
            : theme.colorScheme.onSurface.withValues(alpha: 0.05),
        floatingLabelBehavior: FloatingLabelBehavior.auto,
      ),
      maxLines: maxLines,
      validator: validator,
      onChanged: onChanged,
      style: TextStyle(
        color: enabled 
            ? theme.colorScheme.onSurface 
            : theme.colorScheme.onSurface.withValues(alpha: 0.6),
      ),
    );
  }
}