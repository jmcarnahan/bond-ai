import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/presentation/widgets/common/bondai_widgets.dart';

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
    return BondAIContainer(
      icon: Icons.edit_note,
      title: 'Agent Details',
      margin: EdgeInsets.zero,
      children: [
        BondAITextBox(
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
        SizedBox(height: AppSpacing.xl),
        BondAITextBox(
          controller: descriptionController,
          labelText: 'Description (Optional)',
          enabled: enabled,
          onChanged: onDescriptionChanged,
          helpTooltip: 'A brief summary of what this agent does. This description helps you identify the agent in lists and understand its purpose at a glance.',
        ),
        SizedBox(height: AppSpacing.xl),
        ResizableTextBox(
          controller: instructionsController,
          labelText: 'Instructions',
          enabled: enabled,
          initialHeight: 140,
          minHeight: 80,
          maxHeight: 500,
          fontSize: 13,
          validator: (value) {
            if (value == null || value.isEmpty) {
              return 'Please enter instructions for the agent';
            }
            return null;
          },
          onChanged: onInstructionsChanged,
          helpTooltip: 'The main instructions that describe what the agent does, what data/tools it has access to, and examples of how to accomplish tasks. These instructions define the core behavior and capabilities of your agent.',
        ),
        SizedBox(height: AppSpacing.xl),
        ResizableTextBox(
          controller: introductionController,
          labelText: 'Introduction (Optional)',
          enabled: enabled,
          initialHeight: 100,
          minHeight: 60,
          maxHeight: 400,
          fontSize: 13,
          onChanged: onIntroductionChanged,
          helpTooltip: 'A system prompt sent when a user starts a NEW thread with the agent. Use this to greet users, explain what the agent can do, and perform initial processing. The system message is not shown to users, but the agent\'s response will be the first thing they see.',
        ),
        SizedBox(height: AppSpacing.xl),
        ResizableTextBox(
          controller: reminderController,
          labelText: 'Reminder (Optional)',
          enabled: enabled,
          initialHeight: 100,
          minHeight: 60,
          maxHeight: 400,
          fontSize: 13,
          onChanged: onReminderChanged,
          helpTooltip: 'Sent with every user message to remind the agent of important behaviors it might forget during long conversations. For example: "Always provide references when using file search" or "Respond in a specific format".',
        ),
      ],
    );
  }
}
