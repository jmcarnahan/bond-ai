import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/presentation/screens/groups/widgets/edit_group_form.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/manage_members_panel.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/providers/manage_members_provider.dart';
import 'package:flutterui/presentation/widgets/success_banner.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';

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

class _EditGroupScreenState extends ConsumerState<EditGroupScreen> with ErrorHandlingMixin {
  final GlobalKey<EditGroupFormState> _formKey = GlobalKey<EditGroupFormState>();
  final GlobalKey<ManageMembersPanelState> _membersKey = GlobalKey<ManageMembersPanelState>();

  @override
  void initState() {
    super.initState();
  }

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
      ref.invalidate(groupNotifierProvider);
      ref.invalidate(manageMembersProvider(widget.group.id));

      // Show success message and navigate back
      if (mounted) {
        SuccessBanner.show(context, 'Group updated successfully');
        Navigator.pop(context);
      }
    } catch (error) {
      if (mounted) {
        handleServiceError(error, ref, customMessage: 'Failed to save group changes');
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
            Text(
              'Manage Members',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 16),
            Expanded(
              flex: 3,
              child: ManageMembersPanel(
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
