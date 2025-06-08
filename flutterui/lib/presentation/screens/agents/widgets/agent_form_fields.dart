import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/presentation/widgets/common/info_tooltip.dart';

class AgentFormFields extends StatelessWidget {
  final TextEditingController nameController;
  final TextEditingController descriptionController;
  final TextEditingController instructionsController;
  final TextEditingController introductionController;
  final TextEditingController reminderController;
  final bool enabled;
  final void Function(String) onNameChanged;
  final void Function(String) onDescriptionChanged;
  final void Function(String) onInstructionsChanged;
  final void Function(String) onIntroductionChanged;
  final void Function(String) onReminderChanged;

  const AgentFormFields({
    super.key,
    required this.nameController,
    required this.descriptionController,
    required this.instructionsController,
    required this.introductionController,
    required this.reminderController,
    required this.enabled,
    required this.onNameChanged,
    required this.onDescriptionChanged,
    required this.onInstructionsChanged,
    required this.onIntroductionChanged,
    required this.onReminderChanged,
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
          helpTooltip: 'A brief summary of what this agent does. This description helps you identify the agent in lists and understand its purpose at a glance.',
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
          helpTooltip: 'The main instructions that describe what the agent does, what data/tools it has access to, and examples of how to accomplish tasks. These instructions define the core behavior and capabilities of your agent.',
        ),
        SizedBox(height: AppSpacing.lg),
        AgentTextField(
          controller: introductionController,
          labelText: 'Introduction (Optional)',
          enabled: enabled,
          maxLines: 3,
          onChanged: onIntroductionChanged,
          helpTooltip: 'A system prompt sent when a user starts a NEW thread with the agent. Use this to greet users, explain what the agent can do, and perform initial processing. The system message is not shown to users, but the agent\'s response will be the first thing they see.',
        ),
        SizedBox(height: AppSpacing.lg),
        AgentTextField(
          controller: reminderController,
          labelText: 'Reminder (Optional)',
          enabled: enabled,
          maxLines: 3,
          onChanged: onReminderChanged,
          helpTooltip: 'Sent with every user message to remind the agent of important behaviors it might forget during long conversations. For example: "Always provide references when using file search" or "Respond in a specific format".',
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
  final String? helpTooltip;

  const AgentTextField({
    super.key,
    required this.controller,
    required this.labelText,
    this.enabled = true,
    this.maxLines = 1,
    this.validator,
    this.onChanged,
    this.helpTooltip,
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
                  color: theme.colorScheme.onSurface.withOpacity(0.6),
                ),
              ),
              SizedBox(width: 4),
              InfoIcon(
                tooltip: helpTooltip!,
                size: 14,
              ),
            ],
          ),
          SizedBox(height: 8),
        ],
        TextFormField(
          controller: controller,
          enabled: enabled,
          decoration: InputDecoration(
            labelText: helpTooltip != null ? null : labelText,
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
        ),
      ],
    );
  }
}