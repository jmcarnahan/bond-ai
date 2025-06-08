import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/providers/manage_members_provider.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/widgets/available_users_panel.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/widgets/group_members_list_panel.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/widgets/confirm_changes_dialog.dart';

class ManageMembersPanel extends ConsumerStatefulWidget {
  final Group group;
  final VoidCallback? onChanged;
  final String? title;

  const ManageMembersPanel({
    super.key,
    required this.group,
    this.onChanged,
    this.title,
  });

  @override
  ConsumerState<ManageMembersPanel> createState() => ManageMembersPanelState();
}

class ManageMembersPanelState extends ConsumerState<ManageMembersPanel> {
  late final ManageMembersNotifier _notifier;

  @override
  void initState() {
    super.initState();
    _notifier = ref.read(manageMembersProvider(widget.group.id).notifier);
  }

  bool get hasChanges {
    final state = ref.read(manageMembersProvider(widget.group.id));
    return state.hasChanges;
  }

  void _onAddUser(GroupMember user) {
    _notifier.addPendingMember(user);
    widget.onChanged?.call();
  }

  void _onRemoveUser(GroupMember user) {
    _notifier.removePendingMember(user);
    widget.onChanged?.call();
  }

  void _onCancelAddition(GroupMember user) {
    _notifier.cancelPendingAddition(user);
    widget.onChanged?.call();
  }

  void _onCancelRemoval(GroupMember user) {
    _notifier.cancelPendingRemoval(user);
    widget.onChanged?.call();
  }

  Future<void> saveChanges() async {
    final state = ref.read(manageMembersProvider(widget.group.id));
    if (!state.hasChanges) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => ConfirmChangesDialog(
        additionsCount: state.pendingAdditions.length,
        removalsCount: state.pendingRemovals.length,
      ),
    );

    if (confirmed != true) return;

    try {
      await _notifier.saveChanges();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error updating group members: $error')),
        );
      }
    }
  }

  void reset() {
    _notifier.reset();
    widget.onChanged?.call();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(manageMembersProvider(widget.group.id));

    return Column(
      children: [
        Text(
          widget.title ?? 'Manage Members',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 16),
        Expanded(
          child: Row(
            children: [
              Expanded(
                child: AvailableUsersPanel(
                  groupId: widget.group.id,
                  pendingAdditions: state.pendingAdditions,
                  pendingRemovals: state.pendingRemovals,
                  onAddUser: _onAddUser,
                  onCancelAddition: _onCancelAddition,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: GroupMembersListPanel(
                  groupId: widget.group.id,
                  pendingAdditions: state.pendingAdditions,
                  pendingRemovals: state.pendingRemovals,
                  onRemoveUser: _onRemoveUser,
                  onCancelRemoval: _onCancelRemoval,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}