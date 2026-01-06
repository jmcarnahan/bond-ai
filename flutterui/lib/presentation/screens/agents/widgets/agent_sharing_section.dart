import 'package:flutter/material.dart';
import 'package:flutterui/presentation/screens/agents/widgets/agent_members_section.dart';
import 'package:flutterui/presentation/screens/agents/widgets/additional_groups_section.dart';

class AgentSharingSection extends StatelessWidget {
  final String? agentName;
  final Set<String> selectedGroupIds;
  final Function(Set<String>) onGroupSelectionChanged;

  const AgentSharingSection({
    super.key,
    this.agentName,
    required this.selectedGroupIds,
    required this.onGroupSelectionChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        AgentMembersSection(
          agentName: agentName,
        ),
        AdditionalGroupsSection(
          selectedGroupIds: selectedGroupIds,
          onGroupSelectionChanged: onGroupSelectionChanged,
          agentName: agentName,
        ),
      ],
    );
  }
}
