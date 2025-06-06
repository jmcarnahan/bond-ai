import 'package:flutter/material.dart';
import 'package:flutterui/data/models/group_model.dart';

class GroupCard extends StatelessWidget {
  final Group group;
  final bool isOwner;
  final VoidCallback? onTap;

  const GroupCard({
    super.key,
    required this.group,
    required this.isOwner,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Theme.of(context).colorScheme.primary,
          child: Icon(
            Icons.group,
            color: Theme.of(context).colorScheme.onPrimary,
          ),
        ),
        title: Text(
          group.name,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        subtitle: group.description != null
            ? Text(
                group.description!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              )
            : null,
        trailing: isOwner
            ? IconButton(
                icon: const Icon(Icons.edit),
                onPressed: onTap,
                tooltip: 'Edit Group',
              )
            : null,
        onTap: isOwner ? onTap : null,
      ),
    );
  }
}