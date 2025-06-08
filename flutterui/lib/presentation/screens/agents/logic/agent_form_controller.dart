import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/providers/group_provider.dart';
import '../../../../core/utils/logger.dart';

class AgentFormController {
  final WidgetRef ref;
  final GlobalKey<FormState> formKey;
  final TextEditingController nameController;
  final TextEditingController descriptionController;
  final TextEditingController instructionsController;
  final TextEditingController introductionController;
  final TextEditingController reminderController;
  final String? agentId;

  AgentFormController({
    required this.ref,
    required this.formKey,
    required this.nameController,
    required this.descriptionController,
    required this.instructionsController,
    required this.introductionController,
    required this.reminderController,
    this.agentId,
  });

  CreateAgentFormNotifier get _notifier => ref.read(createAgentFormProvider.notifier);

  void initializeForm() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (agentId != null) {
        _notifier.loadAgentForEditing(agentId!);
      } else {
        _notifier.resetState();
      }
    });

    _setupControllerListeners();
  }

  void _setupControllerListeners() {
    ref.listenManual(createAgentFormProvider, (previous, next) {
      _updateControllerIfNeeded(nameController, next.name);
      _updateControllerIfNeeded(descriptionController, next.description);
      _updateControllerIfNeeded(instructionsController, next.instructions);
      _updateControllerIfNeeded(introductionController, next.introduction);
      _updateControllerIfNeeded(reminderController, next.reminder);
    });
  }

  void _updateControllerIfNeeded(TextEditingController controller, String value) {
    if (controller.text != value) {
      controller.text = value;
    }
  }

  void onNameChanged(String value) {
    _notifier.setName(value);
  }

  void onDescriptionChanged(String value) {
    _notifier.setDescription(value);
  }

  void onInstructionsChanged(String value) {
    _notifier.setInstructions(value);
  }

  void onIntroductionChanged(String value) {
    _notifier.setIntroduction(value);
  }

  void onReminderChanged(String value) {
    _notifier.setReminder(value);
  }

  void onMcpToolsChanged(Set<String> tools) {
    _notifier.setSelectedMcpTools(tools);
  }

  void onMcpResourcesChanged(Set<String> resources) {
    _notifier.setSelectedMcpResources(resources);
  }

  void onGroupSelectionChanged(Set<String> groupIds) {
    _notifier.setSelectedGroupIds(groupIds);
  }

  bool get isFormValid {
    return nameController.text.isNotEmpty && 
           instructionsController.text.isNotEmpty;
  }

  bool get isEditing => agentId != null;

  Future<bool> saveAgent(BuildContext context) async {
    if (!formKey.currentState!.validate()) {
      return false;
    }

    formKey.currentState!.save();

    // Ensure provider has the latest values from controllers
    _notifier.setName(nameController.text);
    _notifier.setDescription(descriptionController.text);
    _notifier.setInstructions(instructionsController.text);
    _notifier.setIntroduction(introductionController.text);
    _notifier.setReminder(reminderController.text);

    final bool success = await _notifier.saveAgent(agentId: agentId);

    if (success && context.mounted) {
      await _handleSuccessfulSave(context);
    }

    return success;
  }

  Future<void> _handleSuccessfulSave(BuildContext context) async {
    _notifier.setLoading(true);
    
    try {
      // Refresh the agents list
      ref.invalidate(agentsProvider);
      
      // Refresh the groups list (to show new default group if creating agent)
      if (!isEditing) {
        ref.invalidate(groupsProvider);
        ref.invalidate(groupNotifierProvider);
      }
      
      if (context.mounted) {
        _showSuccessMessage(context);
        Navigator.of(context).pop();
      }
    } catch (e) {
      logger.e('Error refreshing lists after save: $e');
      if (context.mounted) {
        _showPartialSuccessMessage(context, e.toString());
        Navigator.of(context).pop();
      }
    } finally {
      if (context.mounted) {
        _notifier.setLoading(false);
      }
    }
  }

  void _showSuccessMessage(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Agent ${isEditing ? "updated" : "created"} and list refreshed!',
        ),
        backgroundColor: Colors.green,
      ),
    );
  }

  void _showPartialSuccessMessage(BuildContext context, String error) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Agent saved, but error refreshing list: $error',
        ),
        backgroundColor: Colors.orange,
      ),
    );
  }

  void dispose() {
    nameController.dispose();
    descriptionController.dispose();
    instructionsController.dispose();
    introductionController.dispose();
    reminderController.dispose();
  }
}