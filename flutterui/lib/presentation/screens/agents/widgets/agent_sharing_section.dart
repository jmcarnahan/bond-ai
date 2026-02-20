import 'package:flutter/material.dart';
import 'package:flutterui/presentation/screens/agents/widgets/agent_members_section.dart';
import 'package:flutterui/presentation/screens/agents/widgets/additional_groups_section.dart';

class AgentSharingSection extends StatelessWidget {
  final String? agentName;
  final String? defaultGroupId;
  final Set<String> selectedGroupIds;
  final Function(Set<String>) onGroupSelectionChanged;
  final Map<String, String> groupPermissions;
  final Function(Map<String, String>)? onGroupPermissionsChanged;

  const AgentSharingSection({
    super.key,
    this.agentName,
    this.defaultGroupId,
    required this.selectedGroupIds,
    required this.onGroupSelectionChanged,
    this.groupPermissions = const {},
    this.onGroupPermissionsChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        AgentMembersSection(
          agentName: agentName,
          defaultGroupId: defaultGroupId,
          defaultGroupPermission: defaultGroupId != null
              ? (groupPermissions[defaultGroupId] ?? 'can_use')
              : 'can_use',
          onDefaultGroupPermissionChanged: defaultGroupId != null && onGroupPermissionsChanged != null
              ? (permission) {
                  final newPerms = Map<String, String>.from(groupPermissions);
                  newPerms[defaultGroupId!] = permission;
                  onGroupPermissionsChanged!(newPerms);
                }
              : null,
        ),
        AdditionalGroupsSection(
          selectedGroupIds: selectedGroupIds,
          onGroupSelectionChanged: onGroupSelectionChanged,
          agentName: agentName,
          groupPermissions: groupPermissions,
          onGroupPermissionsChanged: onGroupPermissionsChanged,
        ),
      ],
    );
  }
}
