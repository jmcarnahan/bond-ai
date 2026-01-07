import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/data/services/group_service.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/core/utils/logger.dart';

final groupServiceProvider = Provider<GroupService>((ref) {
  final authService = ref.watch(authServiceProvider);
  return GroupService(authService);
});

final groupsProvider = FutureProvider<List<Group>>((ref) async {
  final groupService = ref.watch(groupServiceProvider);
  return groupService.getUserGroups();
});

final groupProvider = FutureProvider.family<GroupWithMembers, String>((ref, groupId) async {
  final groupService = ref.watch(groupServiceProvider);
  return groupService.getGroup(groupId);
});

class GroupNotifier extends StateNotifier<AsyncValue<List<Group>>> {
  final GroupService _groupService;

  GroupNotifier(this._groupService) : super(const AsyncValue.loading()) {
    loadGroups();
  }

  Future<void> loadGroups() async {
    state = const AsyncValue.loading();
    try {
      final groups = await _groupService.getUserGroups();
      state = AsyncValue.data(groups);
    } catch (error, stackTrace) {
      logger.e('Error loading groups: $error');
      state = AsyncValue.error(error, stackTrace);
    }
  }

  Future<void> createGroup({
    required String name,
    String? description,
  }) async {
    try {
      await _groupService.createGroup(name: name, description: description);
      await loadGroups();
    } catch (error) {
      logger.e('Error creating group: $error');
      rethrow;
    }
  }

  Future<void> updateGroup(
    String groupId, {
    String? name,
    String? description,
  }) async {
    try {
      await _groupService.updateGroup(groupId, name: name, description: description);
      await loadGroups();
    } catch (error) {
      logger.e('Error updating group: $error');
      rethrow;
    }
  }

  Future<void> deleteGroup(String groupId) async {
    try {
      await _groupService.deleteGroup(groupId);
      await loadGroups();
    } catch (error) {
      logger.e('Error deleting group: $error');
      rethrow;
    }
  }
}

final groupNotifierProvider = StateNotifierProvider<GroupNotifier, AsyncValue<List<Group>>>((ref) {
  final groupService = ref.watch(groupServiceProvider);
  return GroupNotifier(groupService);
});
