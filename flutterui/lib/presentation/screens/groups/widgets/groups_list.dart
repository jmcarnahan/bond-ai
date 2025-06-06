import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/screens/groups/widgets/group_card.dart';

class GroupsList extends ConsumerWidget {
  final List<Group> groups;
  final User? currentUser;

  const GroupsList({
    super.key,
    required this.groups,
    this.currentUser,
  });

  List<Group> _sortGroups(List<Group> groups) {
    final sortedGroups = [...groups];
    sortedGroups.sort((a, b) {
      final aIsOwned = currentUser?.userId == a.ownerUserId;
      final bIsOwned = currentUser?.userId == b.ownerUserId;
      
      if (aIsOwned && !bIsOwned) return -1;
      if (!aIsOwned && bIsOwned) return 1;
      return a.name.compareTo(b.name);
    });
    return sortedGroups;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sortedGroups = _sortGroups(groups);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(groupNotifierProvider);
      },
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: sortedGroups.length,
        itemBuilder: (context, index) {
          final group = sortedGroups[index];
          final isOwner = currentUser?.userId == group.ownerUserId;

          return GroupCard(
            group: group,
            isOwner: isOwner,
            onTap: isOwner ? () {
              Navigator.pushNamed(
                context,
                '/groups/${group.id}/edit',
                arguments: group,
              );
            } : null,
          );
        },
      ),
    );
  }
}