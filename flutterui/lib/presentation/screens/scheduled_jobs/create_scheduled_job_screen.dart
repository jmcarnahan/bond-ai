import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/scheduled_job_model.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/providers/scheduled_job_provider.dart';
import 'package:flutterui/presentation/widgets/common/resizable_textbox.dart';
import 'package:flutterui/core/utils/timezone_helper.dart';

class CreateScheduledJobScreen extends ConsumerStatefulWidget {
  static const String routeName = '/create-scheduled-job';

  final ScheduledJob? existingJob;

  const CreateScheduledJobScreen({super.key, this.existingJob});

  @override
  ConsumerState<CreateScheduledJobScreen> createState() =>
      _CreateScheduledJobScreenState();
}

class _CreateScheduledJobScreenState
    extends ConsumerState<CreateScheduledJobScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _nameController;
  late TextEditingController _promptController;
  late TextEditingController _cronController;
  String? _selectedAgentId;
  String _selectedPreset = 'custom';
  bool _isEnabled = true;
  int _timeoutSeconds = 300;
  bool _isSaving = false;
  late final String _userTimezone;

  bool get _isEditing => widget.existingJob != null;

  static const Map<String, String> _cronPresets = {
    'every_hour': '0 * * * *',
    'every_4_hours': '0 */4 * * *',
    'daily_9am': '0 9 * * *',
    'weekly_monday': '0 9 * * 1',
    'first_of_month': '0 9 1 * *',
    'custom': '',
  };

  static const Map<String, String> _presetLabels = {
    'every_hour': 'Every hour',
    'every_4_hours': 'Every 4 hours',
    'daily_9am': 'Daily at 9:00 AM',
    'weekly_monday': 'Weekly on Monday 9 AM',
    'first_of_month': 'First of month 9 AM',
    'custom': 'Custom...',
  };

  @override
  void initState() {
    super.initState();
    _userTimezone = widget.existingJob?.timezone ?? getLocalTimezone();
    _nameController =
        TextEditingController(text: widget.existingJob?.name ?? '');
    _promptController =
        TextEditingController(text: widget.existingJob?.prompt ?? '');
    _cronController =
        TextEditingController(text: widget.existingJob?.schedule ?? '');
    _selectedAgentId = widget.existingJob?.agentId;
    _isEnabled = widget.existingJob?.isEnabled ?? true;
    _timeoutSeconds = widget.existingJob?.timeoutSeconds ?? 300;

    if (widget.existingJob != null) {
      final schedule = widget.existingJob!.schedule;
      final matchingPreset = _cronPresets.entries
          .where((e) => e.value == schedule && e.key != 'custom')
          .firstOrNull;
      _selectedPreset = matchingPreset?.key ?? 'custom';
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _promptController.dispose();
    _cronController.dispose();
    super.dispose();
  }

  Future<void> _onDelete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Scheduled Job'),
        content: Text(
          'Are you sure you want to delete "${widget.existingJob!.name}"? '
          'This cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(
              'Delete',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      final success = await ref
          .read(scheduledJobsNotifierProvider.notifier)
          .deleteJob(widget.existingJob!.id);
      if (mounted) {
        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Deleted "${widget.existingJob!.name}"'),
            ),
          );
          Navigator.of(context).pop();
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to delete job. Please try again.')),
          );
        }
      }
    }
  }

  Future<void> _onSave() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isSaving = true);

    try {
      final notifier = ref.read(scheduledJobsNotifierProvider.notifier);

      if (_isEditing) {
        final success = await notifier.updateJob(
          widget.existingJob!.id,
          name: _nameController.text.trim(),
          prompt: _promptController.text.trim(),
          schedule: _cronController.text.trim(),
          timezone: _userTimezone,
          isEnabled: _isEnabled,
          timeoutSeconds: _timeoutSeconds,
        );
        if (mounted) {
          if (success) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Job updated')),
            );
            Navigator.of(context).pop();
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Failed to update job. Please try again.')),
            );
          }
        }
      } else {
        final job = await notifier.createJob(
          agentId: _selectedAgentId!,
          name: _nameController.text.trim(),
          prompt: _promptController.text.trim(),
          schedule: _cronController.text.trim(),
          timezone: _userTimezone,
          isEnabled: _isEnabled,
          timeoutSeconds: _timeoutSeconds,
        );
        if (mounted) {
          if (job != null) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Created scheduled job: ${job.name}')),
            );
            Navigator.of(context).pop();
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Failed to create job. Please try again.')),
            );
          }
        }
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final agentsAsync = ref.watch(agentsProvider);

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
                color:
                    theme.colorScheme.outlineVariant.withValues(alpha: 0.2),
                width: 1,
              ),
            ),
          ),
          child: SafeArea(
            child: Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back),
                  onPressed:
                      _isSaving ? null : () => Navigator.of(context).pop(),
                ),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _isEditing
                            ? 'Edit Scheduled Job'
                            : 'Create Scheduled Job',
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _isEditing
                            ? 'Update your scheduled job configuration'
                            : 'Configure an agent to run on a schedule',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                if (_isEditing)
                  IconButton(
                    icon: Icon(Icons.delete,
                        color: theme.colorScheme.error),
                    onPressed: _isSaving ? null : _onDelete,
                    tooltip: 'Delete Job',
                  ),
              ],
            ),
          ),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Basic Information section
                    _buildSectionCard(
                      title: 'Basic Information',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Name
                          TextFormField(
                            controller: _nameController,
                            enabled: !_isSaving,
                            decoration: const InputDecoration(
                              labelText: 'Name',
                              hintText: 'e.g., Daily Summary Report',
                              border: OutlineInputBorder(),
                            ),
                            validator: (v) =>
                                (v == null || v.trim().isEmpty)
                                    ? 'Name is required'
                                    : null,
                          ),
                          const SizedBox(height: 16),

                          // Agent dropdown (exclude default Home agent)
                          agentsAsync.when(
                            data: (agents) {
                              final schedulableAgents = agents
                                  .where((a) =>
                                      a.metadata?['is_default'] != 'true')
                                  .toList();
                              if (_selectedAgentId == null &&
                                  schedulableAgents.isNotEmpty) {
                                WidgetsBinding.instance
                                    .addPostFrameCallback((_) {
                                  if (mounted && _selectedAgentId == null) {
                                    setState(() => _selectedAgentId =
                                        schedulableAgents.first.id);
                                  }
                                });
                              }
                              return DropdownButtonFormField<String>(
                                value: _selectedAgentId,
                                decoration: const InputDecoration(
                                  labelText: 'Agent',
                                  border: OutlineInputBorder(),
                                ),
                                items: schedulableAgents
                                    .map((a) => DropdownMenuItem(
                                          value: a.id,
                                          child: Text(a.name),
                                        ))
                                    .toList(),
                                onChanged: _isEditing || _isSaving
                                    ? null
                                    : (v) =>
                                        setState(() => _selectedAgentId = v),
                                validator: (v) =>
                                    v == null ? 'Agent is required' : null,
                              );
                            },
                            loading: () => const LinearProgressIndicator(),
                            error: (e, _) => Text(
                              'Error loading agents: $e',
                              style: TextStyle(
                                  color: theme.colorScheme.error),
                            ),
                          ),
                          const SizedBox(height: 16),

                          // Prompt (resizable)
                          ResizableTextBox(
                            controller: _promptController,
                            labelText: 'Prompt',
                            enabled: !_isSaving,
                            initialHeight: 140,
                            minHeight: 80,
                            maxHeight: 500,
                            validator: (v) =>
                                (v == null || v.trim().isEmpty)
                                    ? 'Prompt is required'
                                    : null,
                          ),
                        ],
                      ),
                      theme: theme,
                    ),
                    const SizedBox(height: 16),

                    // Schedule section
                    _buildSectionCard(
                      title: 'Schedule',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          DropdownButtonFormField<String>(
                            value: _selectedPreset,
                            decoration: const InputDecoration(
                              labelText: 'Preset',
                              border: OutlineInputBorder(),
                            ),
                            items: _presetLabels.entries
                                .map((e) => DropdownMenuItem(
                                      value: e.key,
                                      child: Text(e.value),
                                    ))
                                .toList(),
                            onChanged: _isSaving
                                ? null
                                : (v) {
                                    setState(() {
                                      _selectedPreset = v ?? 'custom';
                                      if (_selectedPreset != 'custom') {
                                        _cronController.text =
                                            _cronPresets[_selectedPreset] ??
                                                '';
                                      }
                                    });
                                  },
                          ),
                          const SizedBox(height: 16),

                          TextFormField(
                            controller: _cronController,
                            enabled:
                                _selectedPreset == 'custom' && !_isSaving,
                            decoration: const InputDecoration(
                              labelText: 'Cron Expression',
                              hintText: '0 9 * * *',
                              border: OutlineInputBorder(),
                              helperText: 'min hour day month weekday',
                            ),
                            validator: (v) {
                              if (v == null || v.trim().isEmpty) {
                                return 'Schedule is required';
                              }
                              final parts = v.trim().split(RegExp(r'\s+'));
                              if (parts.length != 5) {
                                return 'Must have 5 fields (min hour day month weekday)';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              Icon(Icons.language, size: 16,
                                  color: theme.colorScheme.onSurfaceVariant),
                              const SizedBox(width: 6),
                              Text(
                                'Times are in $_userTimezone',
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: theme.colorScheme.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                      theme: theme,
                    ),
                    const SizedBox(height: 16),

                    // Options section
                    _buildSectionCard(
                      title: 'Options',
                      child: SwitchListTile(
                        title: const Text('Enabled'),
                        subtitle: Text(
                          _isEditing
                              ? 'Job is currently ${_isEnabled ? "enabled" : "disabled"}'
                              : 'Start running immediately after creation',
                        ),
                        value: _isEnabled,
                        onChanged: _isSaving
                            ? null
                            : (v) => setState(() => _isEnabled = v),
                        contentPadding: EdgeInsets.zero,
                      ),
                      theme: theme,
                    ),
                    const SizedBox(height: 80),
                  ],
                ),
              ),
            ),
          ),
          _buildBottomSaveButton(theme),
        ],
      ),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required Widget child,
    required ThemeData theme,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest
            .withValues(alpha: 0.3),
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

  Widget _buildBottomSaveButton(ThemeData theme) {
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
            onPressed: _isSaving ? null : _onSave,
            style: ElevatedButton.styleFrom(
              backgroundColor: theme.colorScheme.primary,
              foregroundColor: theme.colorScheme.onPrimary,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: _isSaving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(
                    _isEditing ? 'Update Job' : 'Create Job',
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
