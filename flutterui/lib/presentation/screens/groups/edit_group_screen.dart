import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/presentation/screens/groups/widgets/edit_group_form.dart';
import 'package:flutterui/presentation/screens/groups/widgets/group_members_panel.dart';
import 'package:flutterui/presentation/screens/groups/widgets/available_users_panel.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/widgets/success_banner.dart';

class EditGroupScreen extends ConsumerStatefulWidget {
  static const String routeName = '/groups/:id/edit';
  
  final Group group;

  const EditGroupScreen({
    super.key,
    required this.group,
  });

  @override
  ConsumerState<EditGroupScreen> createState() => _EditGroupScreenState();
}

class _EditGroupScreenState extends ConsumerState<EditGroupScreen> {
  final GlobalKey<EditGroupFormState> _formKey = GlobalKey<EditGroupFormState>();
  final GlobalKey<GroupMembersPanelState> _membersKey = GlobalKey<GroupMembersPanelState>();

  bool get _hasAnyChanges {
    final formHasChanges = _formKey.currentState?.hasChanges ?? false;
    final membersHaveChanges = _membersKey.currentState?.hasChanges ?? false;
    return formHasChanges || membersHaveChanges;
  }

  Future<void> _saveAllChanges() async {
    try {
      bool hasFormChanges = _formKey.currentState?.hasChanges ?? false;
      bool hasMemberChanges = _membersKey.currentState?.hasChanges ?? false;
      
      if (hasFormChanges) {
        await _formKey.currentState?.saveChanges();
      }
      if (hasMemberChanges) {
        await _membersKey.currentState?.saveChanges();
      }

      // Reset providers to ensure fresh data
      ref.invalidate(groupsProvider);
      ref.invalidate(groupProvider(widget.group.id));
      ref.invalidate(allUsersProvider);
      ref.invalidate(groupNotifierProvider);

      // Show success message and navigate back
      if (mounted) {
        SuccessBanner.show(context, 'Group updated successfully');
        Navigator.pop(context);
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving changes: $error')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Edit ${widget.group.name}'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            EditGroupForm(
              key: _formKey,
              group: widget.group,
              onChanged: () => setState(() {}),
            ),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 16),
            Expanded(
              flex: 3,
              child: GroupMembersPanel(
                key: _membersKey,
                group: widget.group,
                onChanged: () => setState(() {}),
              ),
            ),
            const SizedBox(height: 16),
            if (_hasAnyChanges)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _saveAllChanges,
                  child: const Text('Save All Changes'),
                ),
              ),
          ],
        ),
      ),
    );
  }
}