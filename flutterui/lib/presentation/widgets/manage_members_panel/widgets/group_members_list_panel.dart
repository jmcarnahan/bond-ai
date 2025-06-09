import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/widgets/user_tile.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/providers/manage_members_provider.dart';

class GroupMembersListPanel extends ConsumerWidget {
  final String groupId;
  final Set<String> pendingAdditions;
  final Set<String> pendingRemovals;
  final Function(GroupMember) onRemoveUser;
  final Function(GroupMember) onCancelRemoval;

  const GroupMembersListPanel({
    super.key,
    required this.groupId,
    required this.pendingAdditions,
    required this.pendingRemovals,
    required this.onRemoveUser,
    required this.onCancelRemoval,
  });

  List<GroupMember> _getDisplayMembers(GroupWithMembers groupWithMembers, List<GroupMember> allUsers) {
    final currentMembers = [...groupWithMembers.members];
    
    final ownerUser = allUsers.firstWhere(
      (user) => user.userId == groupWithMembers.ownerUserId,
      orElse: () => GroupMember(
        userId: groupWithMembers.ownerUserId,
        email: 'Owner',
        name: 'Group Owner',
      ),
    );
    
    final ownerAlreadyMember = currentMembers.any((member) => member.userId == groupWithMembers.ownerUserId);
    if (!ownerAlreadyMember) {
      currentMembers.insert(0, ownerUser);
    }
    
    for (final userId in pendingAdditions) {
      if (userId != groupWithMembers.ownerUserId) {
        final alreadyInList = currentMembers.any((member) => member.userId == userId);
        if (!alreadyInList) {
          final user = allUsers.firstWhere((u) => u.userId == userId);
          currentMembers.add(user);
        }
      }
    }
    
    return currentMembers;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final groupWithMembersAsync = ref.watch(groupProvider(groupId));
    final allUsersAsync = ref.watch(allUsersProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Group Members',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            Expanded(
              child: groupWithMembersAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, stack) => Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, size: 48),
                      const SizedBox(height: 8),
                      Text('Error loading group members: $error'),
                    ],
                  ),
                ),
                data: (groupWithMembers) => allUsersAsync.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (error, stack) => Center(
                    child: Text('Error loading users: $error'),
                  ),
                  data: (allUsers) {
                    final displayMembers = _getDisplayMembers(groupWithMembers, allUsers);
                    
                    if (displayMembers.isEmpty) {
                      return const Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.group_outlined, size: 48),
                            SizedBox(height: 8),
                            Text('No members in this group'),
                          ],
                        ),
                      );
                    }

                    return ListView.builder(
                      itemCount: displayMembers.length,
                      itemBuilder: (context, index) {
                        final member = displayMembers[index];
                        final isPendingRemoval = pendingRemovals.contains(member.userId);
                        final isPendingAddition = pendingAdditions.contains(member.userId);
                        final isOwner = member.userId == groupWithMembers.ownerUserId;

                        Widget? trailing;
                        if (isOwner) {
                          trailing = Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: Theme.of(context).colorScheme.primary.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: Theme.of(context).colorScheme.primary.withOpacity(0.3),
                                width: 1,
                              ),
                            ),
                            child: Text(
                              'Owner',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                                color: Theme.of(context).colorScheme.primary,
                              ),
                            ),
                          );
                        } else if (isPendingRemoval) {
                          trailing = IconButton(
                            icon: const Icon(Icons.undo, color: Colors.orange),
                            onPressed: () => onCancelRemoval(member),
                            tooltip: 'Cancel removal',
                          );
                        } else {
                          trailing = IconButton(
                            icon: const Icon(Icons.arrow_back),
                            onPressed: () => onRemoveUser(member),
                            tooltip: 'Remove from group',
                          );
                        }

                        return UserTile(
                          user: member,
                          isPendingRemoval: isPendingRemoval,
                          isPendingAddition: isPendingAddition,
                          trailing: trailing,
                        );
                      },
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}