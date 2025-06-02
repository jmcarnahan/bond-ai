import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/main.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';
import '../../../core/utils/logger.dart';

class CreateAgentScreen extends ConsumerStatefulWidget {
  static const String routeName = '/create-agent';
  static const String editRouteNamePattern = '/edit-agent/:id';
  
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

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.agentId != null) {
        ref.read(createAgentFormProvider.notifier).loadAgentForEditing(widget.agentId!);
      } else {
        ref.read(createAgentFormProvider.notifier).resetState();
      }
    });
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _instructionsController.dispose();
    super.dispose();
  }

  void _saveAgent() {
    if (_formKey.currentState!.validate()) {
      _formKey.currentState!.save();
      final formState = ref.read(createAgentFormProvider);
      logger.i('Saving agent:');
      logger.i('Name: ${formState.name}');
      logger.i('Description: ${formState.description}');
      logger.i('Instructions: ${formState.instructions}');
      logger.i('Code Interpreter: ${formState.enableCodeInterpreter}');
      logger.i('File Search: ${formState.enableFileSearch}');

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Agent creation initiated...')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;
    final customColors = theme.extension<CustomColors>();
    final appBarBackgroundColor = customColors?.brandingSurface ?? theme.appBarTheme.backgroundColor ?? theme.colorScheme.surface; // Generic fallback
    final appTheme = ref.watch(appThemeProvider);
    final formState = ref.watch(createAgentFormProvider);

    if (_nameController.text != formState.name) {
      _nameController.text = formState.name;
    }
    if (_descriptionController.text != formState.description) {
      _descriptionController.text = formState.description;
    }
    if (_instructionsController.text != formState.instructions) {
      _instructionsController.text = formState.instructions;
    }


    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        backgroundColor: appBarBackgroundColor,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset(
              appTheme.logoIcon,
              height: 24,
              width: 24,
            ),
            const SizedBox(width: 8),
            Text(
              widget.agentId != null ? "Edit Agent" : "Create Agent",
              style: textTheme.titleLarge?.copyWith(color: Colors.white),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.save_outlined, color: Colors.white),
            tooltip: 'Save Agent',
            onPressed: _saveAgent,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              _buildTextField(
                controller: _nameController,
                labelText: 'Agent Name',
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Please enter an agent name';
                  }
                  return null;
                },
                onSaved: (value) => ref.read(createAgentFormProvider.notifier).setName(value!),
              ),
              const SizedBox(height: 16),
              _buildTextField(
                controller: _descriptionController,
                labelText: 'Description (Optional)',
                onSaved: (value) => ref.read(createAgentFormProvider.notifier).setDescription(value!),
              ),
              const SizedBox(height: 16),
              _buildTextField(
                controller: _instructionsController,
                labelText: 'Instructions',
                maxLines: 5,
                onSaved: (value) => ref.read(createAgentFormProvider.notifier).setInstructions(value!),
                 validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Please enter instructions for the agent';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 24),
              _buildSwitchTile(
                title: 'Code Interpreter',
                value: formState.enableCodeInterpreter,
                onChanged: (value) => ref.read(createAgentFormProvider.notifier).setEnableCodeInterpreter(value),
              ),
              _buildSwitchTile(
                title: 'File Search',
                value: formState.enableFileSearch,
                onChanged: (value) => ref.read(createAgentFormProvider.notifier).setEnableFileSearch(value),
              ),
              const SizedBox(height: 24),
              Center(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: colorScheme.primary,
                    foregroundColor: colorScheme.onPrimary,
                    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 12),
                    textStyle: textTheme.labelLarge,
                  ),
                  onPressed: _saveAgent,
                  child: Text(widget.agentId != null ? 'Update Agent' : 'Create Agent'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String labelText,
    int? maxLines = 1,
    String? Function(String?)? validator,
    void Function(String?)? onSaved,
  }) {
    final theme = Theme.of(context);
    return TextFormField(
      controller: controller,
      decoration: InputDecoration(
        labelText: labelText,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8.0),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8.0),
          borderSide: BorderSide(color: theme.colorScheme.primary, width: 2.0),
        ),
        filled: true,
        fillColor: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
      ),
      maxLines: maxLines,
      validator: validator,
      onSaved: onSaved,
      onChanged: (value) {
        if (labelText == 'Agent Name') {
          ref.read(createAgentFormProvider.notifier).setName(value);
        } else if (labelText == 'Description (Optional)') {
          ref.read(createAgentFormProvider.notifier).setDescription(value);
        } else if (labelText == 'Instructions') {
          ref.read(createAgentFormProvider.notifier).setInstructions(value);
        }
      },
    );
  }

  Widget _buildSwitchTile({
    required String title,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    final theme = Theme.of(context);
    return Card(
      elevation: 0.5,
      margin: const EdgeInsets.symmetric(vertical: 4.0),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8.0)),
      color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
      child: SwitchListTile(
        title: Text(title, style: theme.textTheme.titleMedium),
        value: value,
        onChanged: onChanged,
        activeColor: theme.colorScheme.primary,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 4.0),
      ),
    );
  }
}
