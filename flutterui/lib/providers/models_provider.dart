import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/model_info.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import '../core/utils/logger.dart';

/// Provider for fetching available models from the API
final availableModelsProvider = FutureProvider<List<ModelInfo>>((ref) async {
  try {
    final agentService = ref.read(agentServiceProvider);
    final models = await agentService.getAvailableModels();
    logger.i('[ModelsProvider] Fetched ${models.length} available models');
    return models;
  } catch (e) {
    logger.e('[ModelsProvider] Error fetching available models: $e');
    rethrow;
  }
});

/// Provider to get the default model
final defaultModelProvider = Provider<String?>((ref) {
  final modelsAsync = ref.watch(availableModelsProvider);
  
  return modelsAsync.when(
    data: (models) {
      // Find the default model
      final defaultModel = models.firstWhere(
        (model) => model.isDefault,
        orElse: () => models.isNotEmpty ? models.first : ModelInfo(
          name: 'gpt-4o',
          description: 'Default model',
          isDefault: true,
        ),
      );
      logger.i('[ModelsProvider] Default model: ${defaultModel.name}');
      return defaultModel.name;
    },
    loading: () => null,
    error: (_, __) => 'gpt-4o', // Fallback default
  );
});

/// Provider to get model by name
final modelByNameProvider = Provider.family<ModelInfo?, String>((ref, modelName) {
  final modelsAsync = ref.watch(availableModelsProvider);
  
  return modelsAsync.maybeWhen(
    data: (models) => models.firstWhere(
      (model) => model.name == modelName,
      orElse: () => ModelInfo(
        name: modelName,
        description: modelName,
        isDefault: false,
      ),
    ),
    orElse: () => null,
  );
});