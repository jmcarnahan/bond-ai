import 'package:flutter/material.dart';
import 'package:flutterui/data/models/group_model.dart';

class UserTile extends StatelessWidget {
  final GroupMember user;
  final Widget? trailing;
  final bool isPendingRemoval;
  final bool isPendingAddition;

  const UserTile({
    super.key,
    required this.user,
    this.trailing,
    this.isPendingRemoval = false,
    this.isPendingAddition = false,
  });

  @override
  Widget build(BuildContext context) {
    Color? backgroundColor;
    if (isPendingRemoval) {
      backgroundColor = Colors.red.withValues(alpha: 0.1);
    } else if (isPendingAddition) {
      backgroundColor = Colors.green.withValues(alpha: 0.1);
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: backgroundColor != null
          ? BoxDecoration(
              color: backgroundColor,
              borderRadius: BorderRadius.circular(8),
            )
          : null,
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Theme.of(context).colorScheme.primary,
          child: Text(
            user.email.substring(0, 1).toUpperCase(),
            style: TextStyle(
              color: Theme.of(context).colorScheme.onPrimary,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        title: Text(
          user.name ?? user.email,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            decoration: isPendingRemoval ? TextDecoration.lineThrough : null,
            fontWeight: isPendingAddition ? FontWeight.bold : null,
          ),
        ),
        subtitle: user.name != null ? Text(user.email) : null,
        trailing: trailing,
      ),
    );
  }
}