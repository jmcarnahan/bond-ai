import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/providers/manage_members_provider.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';
import '../../../../core/utils/logger.dart';

class AgentFormController with ErrorHandlingMixin {
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
      // Force fresh data for sharing panel — the cached providers
      // may not include groups/users created since last load
      ref.invalidate(groupsProvider);
      ref.invalidate(allUsersProvider);

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

  Future<void> _saveMemberChanges() async {
    final formState = ref.read(createAgentFormProvider);
    final defaultGroupId = formState.defaultGroupId;

    // Primary: use default group ID directly (reliable, handles special characters)
    if (defaultGroupId != null) {
      try {
        final memberNotifier = ref.read(manageMembersProvider(defaultGroupId).notifier);
        await memberNotifier.saveChanges();
        return;
      } catch (e) {
        logger.e('Error saving member changes: $e');
        return;
      }
    }

    // Fallback: name matching for backward compatibility with old agents
    final agentName = nameController.text;
    if (agentName.isEmpty) return;

    try {
      final defaultGroupName = '$agentName Default Group';
      final groups = await ref.read(groupsProvider.future);
      final defaultGroup = groups.where((g) => g.name == defaultGroupName).firstOrNull;

      if (defaultGroup != null) {
        final memberNotifier = ref.read(manageMembersProvider(defaultGroup.id).notifier);
        await memberNotifier.saveChanges();
      }
    } catch (e) {
      logger.e('Error saving member changes (fallback): $e');
    }
  }

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
      await _saveMemberChanges();
      await _handleSuccessfulSave(context);
    }

    return success;
  }

  Future<void> _handleSuccessfulSave(BuildContext context) async {
    _notifier.setLoading(true);

    try {
      // Refresh the agents list
      ref.invalidate(agentsProvider);

      if (!isEditing) {
        ref.invalidate(groupsProvider);
        ref.invalidate(groupNotifierProvider);
      } else {
        ref.invalidate(groupsProvider);
        ref.invalidate(groupNotifierProvider);

        final allGroups = ref.read(groupsProvider);
        allGroups.whenData((groups) {
          for (final group in groups) {
            ref.invalidate(manageMembersProvider(group.id));
          }
        });
      }

      if (context.mounted) {
        _showSuccessMessage(context);
        Navigator.of(context).pop();
      }
    } catch (e) {
      logger.e('Error refreshing lists after save: $e');
      if (context.mounted) {
        // Handle as service error - the save succeeded but refresh failed
        handleServiceError(e, ref, customMessage: 'Agent saved, but failed to refresh lists');
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

  Future<bool> deleteAgent(BuildContext context) async {
    if (agentId == null) {
      logger.e('Cannot delete agent: agentId is null');
      return false;
    }

    _notifier.setLoading(true);

    try {
      final bool success = await _notifier.deleteAgent(agentId!);

      if (success && context.mounted) {
        await _handleSuccessfulDelete(context);
      }

      return success;
    } catch (e) {
      logger.e('Error deleting agent: $e');
      if (context.mounted) {
        handleServiceError(e, ref, customMessage: 'Failed to delete agent');
      }
      return false;
    } finally {
      if (context.mounted) {
        _notifier.setLoading(false);
      }
    }
  }

  Future<void> _handleSuccessfulDelete(BuildContext context) async {
    try {
      // Refresh the agents list
      ref.invalidate(agentsProvider);
      ref.invalidate(groupsProvider);
      ref.invalidate(groupNotifierProvider);

      if (context.mounted) {
        _showDeleteSuccessMessage(context);
        // Navigate to home screen after successful deletion
        Navigator.of(context).pushNamedAndRemoveUntil('/home', (route) => false);
      }
    } catch (e) {
      logger.e('Error refreshing lists after delete: $e');
      if (context.mounted) {
        // Handle as service error - the delete succeeded but refresh failed
        handleServiceError(e, ref, customMessage: 'Agent deleted, but failed to refresh lists');
        Navigator.of(context).pushNamedAndRemoveUntil('/home', (route) => false);
      }
    }
  }

  void _showDeleteSuccessMessage(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Agent deleted successfully!'),
        backgroundColor: Colors.green,
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
