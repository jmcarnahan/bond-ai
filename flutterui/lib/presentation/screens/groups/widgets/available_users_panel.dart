import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/screens/groups/widgets/user_tile.dart';

final allUsersProvider = FutureProvider<List<GroupMember>>((ref) async {
  final groupService = ref.watch(groupServiceProvider);
  return groupService.getAllUsers();
});

class AvailableUsersPanel extends ConsumerStatefulWidget {
  final String groupId;
  final Set<String> pendingAdditions;
  final Set<String> pendingRemovals;
  final Function(GroupMember) onAddUser;
  final Function(GroupMember) onCancelAddition;

  const AvailableUsersPanel({
    super.key,
    required this.groupId,
    required this.pendingAdditions,
    required this.pendingRemovals,
    required this.onAddUser,
    required this.onCancelAddition,
  });

  @override
  ConsumerState<AvailableUsersPanel> createState() => _AvailableUsersPanelState();
}

class _AvailableUsersPanelState extends ConsumerState<AvailableUsersPanel> {
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<GroupMember> _filterUsers(List<GroupMember> allUsers, GroupWithMembers groupWithMembers) {
    final currentMemberIds = groupWithMembers.members.map((m) => m.userId).toSet();
    
    return allUsers.where((user) {
      final isOwner = user.userId == groupWithMembers.ownerUserId;
      final isCurrentMember = currentMemberIds.contains(user.userId);
      final isPendingRemoval = widget.pendingRemovals.contains(user.userId);
      
      if (isOwner) return false;
      
      if (isCurrentMember && !isPendingRemoval) return false;
      
      if (_searchQuery.isEmpty) return true;
      
      final query = _searchQuery.toLowerCase();
      return user.email.toLowerCase().contains(query) ||
             (user.name?.toLowerCase().contains(query) ?? false);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final allUsersAsync = ref.watch(allUsersProvider);
    final groupWithMembersAsync = ref.watch(groupProvider(widget.groupId));

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Available Users',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search users...',
                prefixIcon: const Icon(Icons.search),
                border: const OutlineInputBorder(),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          setState(() {
                            _searchQuery = '';
                          });
                        },
                      )
                    : null,
              ),
              onChanged: (value) {
                setState(() {
                  _searchQuery = value;
                });
              },
            ),
            const SizedBox(height: 12),
            Expanded(
              child: allUsersAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, stack) => Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, size: 48),
                      const SizedBox(height: 8),
                      Text('Error loading users: $error'),
                    ],
                  ),
                ),
                data: (allUsers) => groupWithMembersAsync.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (error, stack) => Center(
                    child: Text('Error loading group members: $error'),
                  ),
                  data: (groupWithMembers) {
                    final availableUsers = _filterUsers(allUsers, groupWithMembers);
                    
                    if (availableUsers.isEmpty) {
                      return const Center(
                        child: Text('No available users'),
                      );
                    }

                    return ListView.builder(
                      itemCount: availableUsers.length,
                      itemBuilder: (context, index) {
                        final user = availableUsers[index];
                        final isPendingAddition = widget.pendingAdditions.contains(user.userId);

                        return UserTile(
                          user: user,
                          trailing: isPendingAddition
                              ? IconButton(
                                  icon: const Icon(Icons.undo, color: Colors.orange),
                                  onPressed: () => widget.onCancelAddition(user),
                                  tooltip: 'Cancel addition',
                                )
                              : IconButton(
                                  icon: const Icon(Icons.arrow_forward),
                                  onPressed: () => widget.onAddUser(user),
                                  tooltip: 'Add to group',
                                ),
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