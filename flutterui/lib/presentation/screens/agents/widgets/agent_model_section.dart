import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/models_provider.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/data/models/model_info.dart';

class AgentModelSection extends ConsumerWidget {
  final bool readOnly;

  const AgentModelSection({super.key, this.readOnly = false});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final modelsAsync = ref.watch(availableModelsProvider);
    final formState = ref.watch(createAgentFormProvider);
    final defaultModel = ref.watch(defaultModelProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.psychology,
                  size: 20,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  'AI Model',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            modelsAsync.when(
              data: (models) => _buildDropdown(
                context,
                ref,
                theme,
                models,
                formState.selectedModel,
                defaultModel,
              ),
              loading: () => _buildLoadingState(theme),
              error: (error, stack) => _buildErrorState(theme),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDropdown(
    BuildContext context,
    WidgetRef ref,
    ThemeData theme,
    List<ModelInfo> models,
    String? selectedModel,
    String? defaultModel,
  ) {
    if (models.isEmpty) {
      return _buildNoModelsState(theme);
    }

    // Determine which model to show as selected
    // Priority: selectedModel from form state > defaultModel
    final effectiveSelectedModel = selectedModel ?? defaultModel;

    // Check if the selected model is in the available list
    final modelInList = effectiveSelectedModel != null &&
        models.any((m) => m.name == effectiveSelectedModel);

    // Get the actual value to use in dropdown
    final dropdownValue = modelInList ? effectiveSelectedModel : models.first.name;

    // Show warning if agent's model is not in available list
    final showWarning = selectedModel != null &&
        selectedModel.isNotEmpty &&
        !models.any((m) => m.name == selectedModel);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (showWarning) ...[
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: theme.colorScheme.errorContainer.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Row(
              children: [
                Icon(Icons.warning, size: 16, color: theme.colorScheme.error),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Current model ($selectedModel) is no longer available. Please select a new model.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.error,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
        ],
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: theme.colorScheme.outline.withValues(alpha: 0.2),
            ),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: dropdownValue,
              isExpanded: true,
              style: theme.textTheme.bodyMedium,
              dropdownColor: theme.colorScheme.surfaceContainerHighest,
              onChanged: readOnly ? null : (value) {
                if (value != null) {
                  ref.read(createAgentFormProvider.notifier).setSelectedModel(value);
                }
              },
              items: models.map((model) => DropdownMenuItem<String>(
                value: model.name,
                child: Row(
                  children: [
                    if (model.isDefault)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: Icon(
                          Icons.star,
                          size: 16,
                          color: theme.colorScheme.primary,
                        ),
                      ),
                    Expanded(
                      child: Text(
                        '${_formatModelName(model.name)} - ${model.description}',
                        style: theme.textTheme.bodyMedium,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              )).toList(),
            ),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          _getHelperText(dropdownValue, defaultModel, models),
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.6),
          ),
        ),
      ],
    );
  }

  String _formatModelName(String modelId) {
    // Extract a cleaner display name from model ID
    // e.g., "us.anthropic.claude-sonnet-4-20250514-v1:0" -> "Claude Sonnet 4"
    if (modelId.contains('claude')) {
      final parts = modelId.split('.');
      final modelPart = parts.last.split('-');

      if (modelPart.length >= 2) {
        final claudeIndex = modelPart.indexOf('claude');
        if (claudeIndex >= 0 && claudeIndex + 1 < modelPart.length) {
          final variant = modelPart[claudeIndex + 1];
          final version = modelPart.length > claudeIndex + 2 ? modelPart[claudeIndex + 2] : '';
          return 'Claude ${_capitalize(variant)} $version'.trim();
        }
      }
    }
    // Fallback to showing the model ID
    return modelId;
  }

  String _capitalize(String s) {
    if (s.isEmpty) return s;
    return s[0].toUpperCase() + s.substring(1);
  }

  String _getHelperText(String? selectedModel, String? defaultModel, List<ModelInfo> models) {
    if (selectedModel == null) return 'Select a model for the agent';

    final model = models.firstWhere(
      (m) => m.name == selectedModel,
      orElse: () => models.first,
    );

    if (model.isDefault) {
      return 'Default model';
    }
    return 'Custom selection';
  }

  Widget _buildLoadingState(ThemeData theme) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(
                theme.colorScheme.primary,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            'Loading available models...',
            style: theme.textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState(ThemeData theme) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: theme.colorScheme.error.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.warning,
            size: 16,
            color: theme.colorScheme.error,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Failed to load models. Default model will be used.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNoModelsState(ThemeData theme) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: theme.colorScheme.error.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.error_outline,
            size: 16,
            color: theme.colorScheme.error,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'No models available. Please check your configuration.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
