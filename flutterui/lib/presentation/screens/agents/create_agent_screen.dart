import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/theme/app_theme.dart'; // For AppTheme and CustomColors
import 'package:flutterui/main.dart'; // For appThemeProvider
import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/providers/agent_provider.dart'; // Import agentsProvider
// Import AgentService if you directly call it, or rely on provider methods
// import 'package:flutterui/data/services/agent_service.dart';

class CreateAgentScreen extends ConsumerStatefulWidget {
  static const String routeName = '/create-agent'; // For new agent
  static const String editRouteNamePattern = '/edit-agent/:agentId'; // For editing


  // agentId can be used to determine if creating or editing.
  // For this revamp, we'll focus on creation as per the main goal.
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
    // If editing, you would fetch agent details and populate the form.
    // For now, we reset to ensure a clean slate for creation.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(createAgentFormProvider.notifier).resetState();
      // If you were to support editing, you might do:
      // if (widget.agentId != null) {
      //   ref.read(createAgentFormProvider.notifier).loadAgentForEditing(widget.agentId!);
      // } else {
      //   ref.read(createAgentFormProvider.notifier).resetState();
      // }
    });

    // Listen to provider state changes to update controllers
    // This is important if the state can be changed by means other than these controllers (e.g. resetState)
    ref.listenManual(createAgentFormProvider, (previous, next) {
      if (_nameController.text != (next.name ?? '')) {
        _nameController.text = next.name ?? '';
      }
      if (_descriptionController.text != (next.description ?? '')) {
        _descriptionController.text = next.description ?? '';
      }
      if (_instructionsController.text != (next.instructions ?? '')) {
        _instructionsController.text = next.instructions ?? '';
      }
    });

    // Listen to text controllers to enable/disable the save button
    _nameController.addListener(_onFormValuesChanged);
    _instructionsController.addListener(_onFormValuesChanged);
  }

  void _onFormValuesChanged() {
    // Call setState to rebuild the widget and update button state
    if (mounted) {
      setState(() {});
    }
  }

  @override
  void dispose() {
    _nameController.removeListener(_onFormValuesChanged);
    _instructionsController.removeListener(_onFormValuesChanged);
    _nameController.dispose();
    _descriptionController.dispose();
    _instructionsController.dispose();
    super.dispose();
  }

  Future<void> _saveAgent() async {
    if (_formKey.currentState!.validate()) {
      _formKey.currentState!.save(); // This will trigger onSaved for TextFormFields if used

      // Ensure provider has the latest from controllers before saving
      // This is redundant if onSaved or onChanged is perfectly updating the provider.
      // However, it's a good safeguard.
      final notifier = ref.read(createAgentFormProvider.notifier);
      notifier.setName(_nameController.text);
      notifier.setDescription(_descriptionController.text);
      notifier.setInstructions(_instructionsController.text);
      // Toggle states are already in provider via their onChanged.

      // Note: notifier.saveAgent internally sets isLoading = true, then false on completion/error.
      final bool agentSuccessfullySaved;
      if (widget.agentId != null) {
        agentSuccessfullySaved = await notifier.saveAgent(agentId: widget.agentId!);
      } else {
        // Assumes saveAgent can be called without agentId for creation,
        // and that agentId parameter is optional (not required).
        agentSuccessfullySaved = await notifier.saveAgent();
      }

      if (agentSuccessfullySaved) {
        // Keep loading indicator on CreateAgentScreen while HomeScreen data is fetched
        notifier.setLoading(true); 
        try {
          // Refresh agentsProvider and wait for it to complete
          await ref.refresh(agentsProvider.future);
          
          // Only show success and pop if refresh was also successful (or at least didn't throw)
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Agent ${widget.agentId == null ? "created" : "updated"} and list refreshed!'),
                backgroundColor: Colors.green,
              ),
            );
            Navigator.of(context).pop();
          }
        } catch (e) {
          // Handle error during refresh if necessary
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Agent saved, but error refreshing list: ${e.toString()}'),
                backgroundColor: Colors.orange,
              ),
            );
            // Still pop, as agent was saved. Or decide on different UX.
            Navigator.of(context).pop(); 
          }
        } finally {
          // Ensure loading is turned off in the form provider if still mounted
          // (might have already popped if successful)
          if (mounted) {
            notifier.setLoading(false);
          }
        }
      }
      // Error message from saveAgent is handled by watching formState.errorMessage in build
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;
    final customColors = theme.extension<CustomColors>();
    // Use a generic fallback from the current theme if customColors or brandingSurface is not available
    final appBarBackgroundColor = customColors?.brandingSurface ?? theme.appBarTheme.backgroundColor ?? theme.colorScheme.surface;
    final appTheme = ref.watch(appThemeProvider);
    final formState = ref.watch(createAgentFormProvider);
    final formNotifier = ref.read(createAgentFormProvider.notifier);

    // Determine if the form is valid for enabling the button
    final bool isFormValid = _nameController.text.isNotEmpty && _instructionsController.text.isNotEmpty;

    return Scaffold(
      backgroundColor: colorScheme.background,
      appBar: AppBar(
        backgroundColor: appBarBackgroundColor,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: formState.isLoading ? null : () => Navigator.of(context).pop(),
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
              widget.agentId == null ? "Create Agent" : "Edit Agent",
              style: textTheme.titleLarge?.copyWith(color: Colors.white),
            ),
          ],
        ),
      ),
      body: Stack(
        children: [
          SingleChildScrollView(
            // Add padding to the bottom to ensure content is not obscured by the floating button
            padding: const EdgeInsets.fromLTRB(16.0, 16.0, 16.0, 80.0), // Increased bottom padding
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  if (formState.errorMessage != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16.0),
                      child: Text(
                        formState.errorMessage!,
                        style: TextStyle(color: theme.colorScheme.error, fontWeight: FontWeight.bold),
                      ),
                    ),
                  _buildTextField(
                    controller: _nameController,
                    labelText: 'Agent Name',
                    enabled: !formState.isLoading,
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter an agent name';
                      }
                      return null;
                    },
                    onChanged: (value) => formNotifier.setName(value),
                  ),
                  const SizedBox(height: 12.0),
                  _buildTextField(
                    controller: _descriptionController,
                    labelText: 'Description (Optional)',
                    enabled: !formState.isLoading,
                    onChanged: (value) => formNotifier.setDescription(value),
                  ),
                  const SizedBox(height: 12.0),
                  _buildTextField(
                    controller: _instructionsController,
                    labelText: 'Instructions',
                    enabled: !formState.isLoading,
                    maxLines: 5,
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter instructions for the agent';
                      }
                      return null;
                    },
                    onChanged: (value) => formNotifier.setInstructions(value),
                  ),
                  const SizedBox(height: 20.0),
                  _buildSwitchTile(
                    title: 'Code Interpreter',
                    value: formState.enableCodeInterpreter,
                    onChanged: formState.isLoading ? null :(value) => formNotifier.setEnableCodeInterpreter(value),
                  ),
                  _buildSwitchTile(
                    title: 'File Search',
                    value: formState.enableFileSearch,
                    onChanged: formState.isLoading ? null : (value) => formNotifier.setEnableFileSearch(value),
                  ),
                  // The SizedBox below was for spacing before the button,
                  // it can be removed or adjusted if needed, but since the button is floating,
                  // the main scroll content doesn't need to space for it anymore here.
                  // const SizedBox(height: 32), 
                  // Button is removed from here
                ],
              ),
            ),
          ),
          // Floating Action Button Area
          Align(
            alignment: Alignment.bottomCenter,
            child: Padding(
              padding: const EdgeInsets.only(bottom: 24.0, left: 16.0, right: 16.0),
              // MouseRegion removed
              child: SizedBox(
                child: ElevatedButton(
                  onPressed: (formState.isLoading || !isFormValid) ? null : _saveAgent,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: colorScheme.primary,
                    foregroundColor: colorScheme.onPrimary,
                    disabledBackgroundColor: Colors.grey.shade400,
                    disabledForegroundColor: Colors.grey.shade700,
                    padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 14),
                    textStyle: textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.5,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8.0), // Consistent with text fields
                    ),
                    elevation: 2.0, // Slightly reduced elevation
                  ).copyWith(
                    mouseCursor: MaterialStateProperty.resolveWith<MouseCursor?>(
                      (Set<MaterialState> states) {
                        if (states.contains(MaterialState.disabled)) {
                          return SystemMouseCursors.forbidden;
                        }
                        return SystemMouseCursors.click; // Default for enabled state
                      },
                    ),
                  ),
                  child: Text(widget.agentId == null ? 'Create Agent' : 'Save Changes'),
                ), // ElevatedButton ends
              ), // SizedBox ends
            ), // Padding ends
          ), // Align ends
          if (formState.isLoading)
            Container(
              color: Colors.black.withOpacity(0.3),
              child: const Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 16),
                    Text('Saving agent...', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String labelText,
    bool enabled = true,
    int? maxLines = 1,
    String? Function(String?)? validator,
    void Function(String)? onChanged,
  }) {
    final theme = Theme.of(context);
    return TextFormField(
      controller: controller,
      enabled: enabled,
      decoration: InputDecoration(
        labelText: labelText,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8.0),
          borderSide: BorderSide(color: theme.colorScheme.onSurface.withOpacity(0.3)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8.0),
          borderSide: BorderSide(color: theme.colorScheme.onSurface.withOpacity(0.3)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8.0),
          borderSide: BorderSide(color: theme.colorScheme.primary, width: 2.0),
        ),
        filled: true,
        // Using Material 3 surface container colors for a more defined look
        fillColor: enabled ? theme.colorScheme.surfaceContainerLow : theme.colorScheme.onSurface.withOpacity(0.05),
        floatingLabelBehavior: FloatingLabelBehavior.auto,
      ),
      maxLines: maxLines,
      validator: validator,
      onChanged: onChanged,
      style: TextStyle(color: enabled ? theme.colorScheme.onSurface : theme.colorScheme.onSurface.withOpacity(0.6)),
    );
  }

  Widget _buildSwitchTile({
    required String title,
    required bool value,
    ValueChanged<bool>? onChanged, // Nullable if disabled
  }) {
    final theme = Theme.of(context);
    return Card(
      elevation: 0.0, // Flatter design
      margin: const EdgeInsets.symmetric(vertical: 4.0), // Tighter margin
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8.0),
        // Using outlineVariant for a subtle border, consistent with M3 guidelines
        side: BorderSide(color: theme.colorScheme.outlineVariant.withOpacity(0.5)),
      ),
      // Using a more defined surface color from M3 palette
      color: theme.colorScheme.surfaceContainer,
      child: SwitchListTile(
        title: Text(title, style: theme.textTheme.titleMedium?.copyWith(
          // Ensuring text color contrasts well with the new card color
          color: onChanged == null ? theme.disabledColor : theme.colorScheme.onSurface
        )),
        value: value,
        onChanged: onChanged,
        activeColor: theme.colorScheme.primary,
        inactiveThumbColor: theme.colorScheme.onSurface.withOpacity(0.4),
        inactiveTrackColor: theme.colorScheme.onSurface.withOpacity(0.2),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 6.0),
      ),
    );
  }
}
