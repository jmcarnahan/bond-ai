import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/screens/groups/widgets/available_users_panel.dart';
import 'package:flutterui/presentation/screens/groups/widgets/group_members_list_panel.dart';
import 'package:flutterui/presentation/screens/groups/widgets/confirm_changes_dialog.dart';

class GroupMembersPanel extends ConsumerStatefulWidget {
  final Group group;
  final VoidCallback? onChanged;

  const GroupMembersPanel({
    super.key,
    required this.group,
    this.onChanged,
  });

  @override
  ConsumerState<GroupMembersPanel> createState() => GroupMembersPanelState();
}

class GroupMembersPanelState extends ConsumerState<GroupMembersPanel> {
  final Set<String> _pendingAdditions = {};
  final Set<String> _pendingRemovals = {};

  bool get hasChanges {
    final hasChanges = _pendingAdditions.isNotEmpty || _pendingRemovals.isNotEmpty;
    return hasChanges;
  }

  void _addPendingMember(GroupMember user) {
    setState(() {
      _pendingRemovals.remove(user.userId);
      _pendingAdditions.add(user.userId);
    });
    widget.onChanged?.call();
  }

  void _removePendingMember(GroupMember user) {
    setState(() {
      _pendingAdditions.remove(user.userId);
      _pendingRemovals.add(user.userId);
    });
    widget.onChanged?.call();
  }

  void _cancelPendingAddition(GroupMember user) {
    setState(() {
      _pendingAdditions.remove(user.userId);
    });
    widget.onChanged?.call();
  }

  void _cancelPendingRemoval(GroupMember user) {
    setState(() {
      _pendingRemovals.remove(user.userId);
    });
    widget.onChanged?.call();
  }

  Future<void> saveChanges() async {
    if (!hasChanges) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => ConfirmChangesDialog(
        additionsCount: _pendingAdditions.length,
        removalsCount: _pendingRemovals.length,
      ),
    );

    if (confirmed != true) return;

    try {
      final groupService = ref.read(groupServiceProvider);
      
      for (final userId in _pendingAdditions) {
        await groupService.addGroupMember(widget.group.id, userId);
      }
      
      for (final userId in _pendingRemovals) {
        await groupService.removeGroupMember(widget.group.id, userId);
      }

      setState(() {
        _pendingAdditions.clear();
        _pendingRemovals.clear();
      });

      ref.invalidate(groupProvider(widget.group.id));
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error updating group members: $error')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          'Manage Members',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 16),
        Expanded(
          child: Row(
            children: [
              Expanded(
                child: AvailableUsersPanel(
                  groupId: widget.group.id,
                  pendingAdditions: _pendingAdditions,
                  pendingRemovals: _pendingRemovals,
                  onAddUser: _addPendingMember,
                  onCancelAddition: _cancelPendingAddition,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: GroupMembersListPanel(
                  groupId: widget.group.id,
                  pendingAdditions: _pendingAdditions,
                  pendingRemovals: _pendingRemovals,
                  onRemoveUser: _removePendingMember,
                  onCancelRemoval: _cancelPendingRemoval,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}