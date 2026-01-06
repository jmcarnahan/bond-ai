import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/group_provider.dart';

final allUsersProvider = FutureProvider<List<GroupMember>>((ref) async {
  final groupService = ref.watch(groupServiceProvider);
  return groupService.getAllUsers();
});

class ManageMembersState {
  final Set<String> pendingAdditions;
  final Set<String> pendingRemovals;
  final Set<String> originalMemberIds;

  const ManageMembersState({
    this.pendingAdditions = const {},
    this.pendingRemovals = const {},
    this.originalMemberIds = const {},
  });

  ManageMembersState copyWith({
    Set<String>? pendingAdditions,
    Set<String>? pendingRemovals,
    Set<String>? originalMemberIds,
  }) {
    return ManageMembersState(
      pendingAdditions: pendingAdditions ?? this.pendingAdditions,
      pendingRemovals: pendingRemovals ?? this.pendingRemovals,
      originalMemberIds: originalMemberIds ?? this.originalMemberIds,
    );
  }

  bool get hasChanges {
    return pendingAdditions.isNotEmpty || pendingRemovals.isNotEmpty;
  }
}

class ManageMembersNotifier extends StateNotifier<ManageMembersState> {
  final String groupId;
  final Ref ref;

  ManageMembersNotifier(this.groupId, this.ref) : super(const ManageMembersState()) {
    _loadOriginalMembers();
  }

  void _loadOriginalMembers() {
    ref.listen(groupProvider(groupId), (previous, next) {
      next.whenData((groupWithMembers) {
        state = state.copyWith(
          originalMemberIds: groupWithMembers.members.map((m) => m.userId).toSet(),
        );
      });
    }, fireImmediately: true);
  }

  void addPendingMember(GroupMember user) {
    final newRemovals = Set<String>.from(state.pendingRemovals);
    newRemovals.remove(user.userId);

    final newAdditions = Set<String>.from(state.pendingAdditions);
    if (!state.originalMemberIds.contains(user.userId)) {
      newAdditions.add(user.userId);
    }

    state = state.copyWith(
      pendingAdditions: newAdditions,
      pendingRemovals: newRemovals,
    );
  }

  void removePendingMember(GroupMember user) {
    final newAdditions = Set<String>.from(state.pendingAdditions);
    newAdditions.remove(user.userId);

    final newRemovals = Set<String>.from(state.pendingRemovals);
    newRemovals.add(user.userId);

    state = state.copyWith(
      pendingAdditions: newAdditions,
      pendingRemovals: newRemovals,
    );
  }

  void cancelPendingAddition(GroupMember user) {
    final newAdditions = Set<String>.from(state.pendingAdditions);
    newAdditions.remove(user.userId);

    state = state.copyWith(pendingAdditions: newAdditions);
  }

  void cancelPendingRemoval(GroupMember user) {
    final newRemovals = Set<String>.from(state.pendingRemovals);
    newRemovals.remove(user.userId);

    state = state.copyWith(pendingRemovals: newRemovals);
  }

  Future<void> saveChanges() async {
    if (!state.hasChanges) return;

    try {
      final groupService = ref.read(groupServiceProvider);

      for (final userId in state.pendingAdditions) {
        await groupService.addGroupMember(groupId, userId);
      }

      for (final userId in state.pendingRemovals) {
        await groupService.removeGroupMember(groupId, userId);
      }

      state = state.copyWith(
        pendingAdditions: {},
        pendingRemovals: {},
      );

      ref.invalidate(groupProvider(groupId));
      _loadOriginalMembers();
    } catch (error) {
      rethrow;
    }
  }

  void reset() {
    state = state.copyWith(
      pendingAdditions: {},
      pendingRemovals: {},
    );
  }
}

final manageMembersProvider = StateNotifierProvider.family.autoDispose<ManageMembersNotifier, ManageMembersState, String>((ref, groupId) {
  ref.onDispose(() {
    ref.notifier.reset();
  });
  return ManageMembersNotifier(groupId, ref);
});

void resetManageMembersProvider(WidgetRef ref, String groupId) {
  ref.read(manageMembersProvider(groupId).notifier).reset();
}
