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
      logger.i('[ModelsProvider] Available models count: ${models.length}');

      // Log all models and their default status
      for (var model in models) {
        logger.d('[ModelsProvider] Model: ${model.name}, isDefault: ${model.isDefault}');
      }

      // Find the default model
      try {
        final defaultModel = models.firstWhere((model) => model.isDefault);
        logger.i('[ModelsProvider] Selected default model: ${defaultModel.name} (isDefault: ${defaultModel.isDefault})');
        return defaultModel.name;
      } catch (e) {
        // No model marked as default
        if (models.isNotEmpty) {
          logger.w('[ModelsProvider] No model marked as default, falling back to first model: ${models.first.name}');
          return models.first.name;
        } else {
          logger.e('[ModelsProvider] No models available');
          return null;
        }
      }
    },
    loading: () {
      logger.d('[ModelsProvider] Models still loading, returning null');
      return null;
    },
    error: (error, stack) {
      logger.e('[ModelsProvider] Error loading models: $error');
      return null; // Return null on error instead of hardcoded default
    },
  );
});

/// Provider to get model by name
final modelByNameProvider = Provider.family<ModelInfo?, String>((ref, modelName) {
  final modelsAsync = ref.watch(availableModelsProvider);

  return modelsAsync.maybeWhen(
    data: (models) {
      try {
        return models.firstWhere((model) => model.name == modelName);
      } catch (e) {
        logger.w('[ModelsProvider] Model not found: $modelName');
        return null;
      }
    },
    orElse: () => null,
  );
});
