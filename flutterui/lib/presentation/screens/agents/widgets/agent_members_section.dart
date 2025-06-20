import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/manage_members_panel.dart';
import 'package:flutterui/presentation/widgets/common/bondai_widgets.dart';

class AgentMembersSection extends ConsumerStatefulWidget {
  final String? agentName;

  const AgentMembersSection({
    super.key,
    this.agentName,
  });

  @override
  ConsumerState<AgentMembersSection> createState() => _AgentMembersSectionState();
}

class _AgentMembersSectionState extends ConsumerState<AgentMembersSection> {
  Group? _cachedDefaultGroup;
  String? _lastAgentName;
  List<Group>? _cachedGroups;
  
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadGroups();
    });
    
    ref.listenManual(groupsProvider, (previous, next) {
      _loadGroups();
    });
  }
  
  Future<void> _loadGroups() async {
    try {
      final groups = await ref.read(groupsProvider.future);
      if (mounted) {
        setState(() {
          _cachedGroups = groups;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _cachedGroups = null;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {    
    return BondAIContainer(
      icon: Icons.people,
      title: 'Share with Users',
      subtitle: 'Add users who can access this agent. These users will be automatically added to the agent\'s sharing group.',
      children: [
        if (widget.agentName == null)
          BondAIResourceUnavailable(
            message: 'Finish creating your agent before sharing with users.',
            icon: Icons.person_add,
            type: ResourceUnavailableType.empty,
            showBorder: false,
            padding: EdgeInsets.zero,
            iconSize: AppSizes.iconEnormous / 2,
          )
        else if (_cachedGroups == null)
          BondAILoadingState(
            message: 'Loading groups...',
            showBackground: false,
          )
            else
              Builder(builder: (context) {
                final groups = _cachedGroups!;
                  final agentName = widget.agentName!;
                  final defaultGroupName = '$agentName Default Group';
                  
                  try {
                    final defaultGroup = groups.firstWhere(
                      (group) => group.name == defaultGroupName,
                    );

                    if (_lastAgentName != agentName || 
                        _cachedDefaultGroup?.id != defaultGroup.id ||
                        _cachedDefaultGroup?.updatedAt != defaultGroup.updatedAt) {
                      _cachedDefaultGroup = defaultGroup;
                      _lastAgentName = agentName;
                    }

                    return SizedBox(
                      height: 400,
                      child: ManageMembersPanel(
                        key: ValueKey(_cachedDefaultGroup!.id),
                        group: _cachedDefaultGroup!,
                        onChanged: null,
                      ),
                    );
                  } catch (e) {
                    return BondAIResourceUnavailable(
                      message: 'Agent sharing group will be created when you save.',
                      icon: Icons.info_outline,
                      type: ResourceUnavailableType.empty,
                      showBorder: false,
                      padding: EdgeInsets.zero,
                      iconSize: AppSizes.iconEnormous / 2,
                    );
                  }
                }),
      ],
    );
  }
}