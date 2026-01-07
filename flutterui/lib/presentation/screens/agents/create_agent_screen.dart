import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'widgets/agent_form_fields.dart';
import 'widgets/agent_files_table.dart';
import 'widgets/agent_model_section.dart';
import 'widgets/mcp_selection_section.dart';
import 'widgets/agent_sharing_section.dart';
import 'widgets/agent_loading_overlay.dart';
import 'widgets/agent_error_banner.dart';
import 'logic/agent_form_controller.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';

class CreateAgentScreen extends ConsumerStatefulWidget {
  static const String routeName = '/create-agent';
  static const String editRouteNamePattern = '/edit-agent/:agentId';

  final String? agentId;

  const CreateAgentScreen({super.key, this.agentId});

  @override
  ConsumerState<CreateAgentScreen> createState() => _CreateAgentScreenState();
}

class _CreateAgentScreenState extends ConsumerState<CreateAgentScreen> with ErrorHandlingMixin {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _instructionsController = TextEditingController();
  final _introductionController = TextEditingController();
  final _reminderController = TextEditingController();

  late final AgentFormController _controller;

  @override
  void initState() {
    super.initState();

    _controller = AgentFormController(
      ref: ref,
      formKey: _formKey,
      nameController: _nameController,
      descriptionController: _descriptionController,
      instructionsController: _instructionsController,
      introductionController: _introductionController,
      reminderController: _reminderController,
      agentId: widget.agentId,
    );

    _controller.initializeForm();
    _setupFormValidationListeners();
  }

  void _setupFormValidationListeners() {
    _nameController.addListener(_onFormValuesChanged);
    _instructionsController.addListener(_onFormValuesChanged);
  }

  void _onFormValuesChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  void dispose() {
    _nameController.removeListener(_onFormValuesChanged);
    _instructionsController.removeListener(_onFormValuesChanged);
    _controller.dispose();
    super.dispose();
  }

  Future<void> _onSavePressed() async {
    await _controller.saveAgent(context);
  }

  void _onBackPressed() {
    // Cancel any ongoing operations and navigate back immediately
    final formNotifier = ref.read(createAgentFormProvider.notifier);
    formNotifier.cancelLoading();

    Navigator.of(context).pop();
  }

  Future<void> _onDeletePressed() async {
    if (widget.agentId == null) return;

    final confirmed = await _showDeleteConfirmationDialog();
    if (confirmed == true && mounted) {
      await _controller.deleteAgent(context);
    }
  }

  Future<bool?> _showDeleteConfirmationDialog() {
    return showDialog<bool>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Delete Agent'),
          content: const Text(
            'Are you sure you want to delete this agent? This action cannot be undone.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
              ),
              child: const Text('Delete'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final formState = ref.watch(createAgentFormProvider);
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.colorScheme.surface,
      resizeToAvoidBottomInset: true,
      appBar: AppBar(
        automaticallyImplyLeading: false,
        centerTitle: false,
        backgroundColor: Colors.transparent,
        elevation: 0,
        toolbarHeight: 80,
        flexibleSpace: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: theme.colorScheme.surface,
            border: Border(
              bottom: BorderSide(
                color: theme.colorScheme.outlineVariant.withValues(alpha: 0.2),
                width: 1,
              ),
            ),
          ),
          child: SafeArea(
            child: Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back),
                  onPressed: formState.isLoading ? null : _onBackPressed,
                ),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _controller.isEditing ? 'Edit Agent' : 'Create Agent',
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _controller.isEditing ? 'Update your AI assistant' : 'Configure a new AI assistant',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                if (_controller.isEditing)
                  IconButton(
                    icon: Icon(Icons.delete, color: theme.colorScheme.error),
                    onPressed: formState.isLoading ? null : _onDeletePressed,
                  ),
              ],
            ),
          ),
        ),
      ),
      body: Stack(
        children: [
          _buildFormContent(formState, theme),
          if (formState.isLoading)
            AgentLoadingOverlay(isVisible: formState.isLoading),
        ],
      ),
    );
  }

  Widget _buildFormContent(CreateAgentFormState formState, ThemeData theme) {
    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16.0),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  AgentErrorBanner(errorMessage: formState.errorMessage),
                  _buildSectionCard(
                    title: 'Basic Information',
                    child: AgentFormFields(
                      nameController: _nameController,
                      descriptionController: _descriptionController,
                      instructionsController: _instructionsController,
                      introductionController: _introductionController,
                      reminderController: _reminderController,
                      enabled: !formState.isLoading,
                      onNameChanged: _controller.onNameChanged,
                      onDescriptionChanged: _controller.onDescriptionChanged,
                      onInstructionsChanged: _controller.onInstructionsChanged,
                      onIntroductionChanged: _controller.onIntroductionChanged,
                      onReminderChanged: _controller.onReminderChanged,
                    ),
                    theme: theme,
                  ),
                  const SizedBox(height: 16),
                  const AgentModelSection(),
                  const SizedBox(height: 16),
                  _buildSectionCard(
                    title: 'Files & Resources',
                    child: const AgentFilesTable(),
                    theme: theme,
                  ),
                  const SizedBox(height: 16),
                  _buildSectionCard(
                    title: 'Tools & Resources',
                    child: McpSelectionSection(
                      selectedToolNames: formState.selectedMcpTools,
                      selectedResourceUris: formState.selectedMcpResources,
                      enabled: !formState.isLoading,
                      onToolsChanged: _controller.onMcpToolsChanged,
                      onResourcesChanged: _controller.onMcpResourcesChanged,
                    ),
                    theme: theme,
                  ),
                  const SizedBox(height: 16),
                  _buildSectionCard(
                    title: 'Sharing',
                    child: AgentSharingSection(
                      agentName: _nameController.text.isNotEmpty ? _nameController.text : null,
                      selectedGroupIds: formState.selectedGroupIds,
                      onGroupSelectionChanged: _controller.onGroupSelectionChanged,
                    ),
                    theme: theme,
                  ),
                  const SizedBox(height: 80), // Space for bottom button
                ],
              ),
            ),
          ),
        ),
        _buildBottomSaveButton(formState, theme),
      ],
    );
  }

  Widget _buildSectionCard({
    required String title,
    required Widget child,
    required ThemeData theme,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Text(
              title,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
                color: theme.colorScheme.onSurface,
              ),
            ),
          ),
          Divider(
            height: 1,
            thickness: 1,
            color: theme.colorScheme.outlineVariant.withValues(alpha: 0.2),
          ),
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: child,
          ),
        ],
      ),
    );
  }

  Widget _buildBottomSaveButton(CreateAgentFormState formState, ThemeData theme) {
    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(
          top: BorderSide(
            color: theme.colorScheme.outlineVariant.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
      ),
      padding: const EdgeInsets.all(16.0),
      child: SafeArea(
        child: SizedBox(
          width: double.infinity,
          height: 48,
          child: ElevatedButton(
            onPressed: formState.isLoading || !_controller.isFormValid
                ? null
                : _onSavePressed,
            style: ElevatedButton.styleFrom(
              backgroundColor: theme.colorScheme.primary,
              foregroundColor: theme.colorScheme.onPrimary,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: Text(
              _controller.isEditing ? 'Update Agent' : 'Create Agent',
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
