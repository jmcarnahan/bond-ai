import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'widgets/agent_form_app_bar.dart';
import 'widgets/agent_form_fields.dart';
import 'widgets/agent_files_table.dart';
import 'widgets/mcp_selection_section.dart';
import 'widgets/group_selection_section.dart';
import 'widgets/agent_save_button.dart';
import 'widgets/agent_loading_overlay.dart';
import 'widgets/agent_error_banner.dart';
import 'logic/agent_form_controller.dart';

class CreateAgentScreen extends ConsumerStatefulWidget {
  static const String routeName = '/create-agent';
  static const String editRouteNamePattern = '/edit-agent/:agentId';

  final String? agentId;

  const CreateAgentScreen({super.key, this.agentId});

  @override
  ConsumerState<CreateAgentScreen> createState() => _CreateAgentScreenState();
}

class _CreateAgentScreenState extends ConsumerState<CreateAgentScreen> {
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

  @override
  Widget build(BuildContext context) {
    final formState = ref.watch(createAgentFormProvider);
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.colorScheme.background,
      appBar: AgentFormAppBar(
        isEditing: _controller.isEditing,
        isLoading: formState.isLoading,
        onBack: _onBackPressed,
      ),
      body: Stack(
        children: [
          _buildFormContent(formState),
          _buildSaveButton(formState),
          AgentLoadingOverlay(isVisible: formState.isLoading),
        ],
      ),
    );
  }

  Widget _buildFormContent(CreateAgentFormState formState) {
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.xl,
        AppSpacing.xl,
        AppSpacing.xl,
        AppSizes.buttonHeight +
            AppSpacing.enormous, // Space for floating button
      ),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AgentErrorBanner(errorMessage: formState.errorMessage),
            AgentFormFields(
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
            const AgentFilesTable(),
            McpSelectionSection(
              selectedToolNames: formState.selectedMcpTools,
              selectedResourceUris: formState.selectedMcpResources,
              enabled: !formState.isLoading,
              onToolsChanged: _controller.onMcpToolsChanged,
              onResourcesChanged: _controller.onMcpResourcesChanged,
            ),
            GroupSelectionSection(
              selectedGroupIds: formState.selectedGroupIds,
              onGroupSelectionChanged: _controller.onGroupSelectionChanged,
            ),
            SizedBox(height: AppSpacing.enormous), // Extra space at bottom
          ],
        ),
      ),
    );
  }

  Widget _buildSaveButton(CreateAgentFormState formState) {
    return AgentSaveButton(
      isLoading: formState.isLoading,
      isFormValid: _controller.isFormValid,
      isEditing: _controller.isEditing,
      onPressed: _onSavePressed,
    );
  }
}
