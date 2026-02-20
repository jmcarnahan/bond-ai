import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/manage_members_panel.dart';
import 'package:flutterui/presentation/widgets/common/bondai_widgets.dart';

class AgentMembersSection extends ConsumerStatefulWidget {
  final String? agentName;
  final String? defaultGroupId;
  final String defaultGroupPermission;
  final Function(String)? onDefaultGroupPermissionChanged;

  const AgentMembersSection({
    super.key,
    this.agentName,
    this.defaultGroupId,
    this.defaultGroupPermission = 'can_use',
    this.onDefaultGroupPermissionChanged,
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

                  // Primary: lookup by default group ID (reliable, handles special characters)
                  Group? defaultGroup;
                  if (widget.defaultGroupId != null) {
                    defaultGroup = groups.where(
                      (group) => group.id == widget.defaultGroupId,
                    ).firstOrNull;
                  }

                  // Fallback: lookup by name pattern (for backward compatibility with old agents)
                  if (defaultGroup == null && widget.agentName != null) {
                    final defaultGroupName = '${widget.agentName} Default Group';
                    defaultGroup = groups.where(
                      (group) => group.name == defaultGroupName,
                    ).firstOrNull;
                  }

                  if (defaultGroup == null) {
                    return BondAIResourceUnavailable(
                      message: 'Agent sharing group will be created when you save.',
                      icon: Icons.info_outline,
                      type: ResourceUnavailableType.empty,
                      showBorder: false,
                      padding: EdgeInsets.zero,
                      iconSize: AppSizes.iconEnormous / 2,
                    );
                  }

                  if (_lastAgentName != widget.agentName ||
                      _cachedDefaultGroup?.id != defaultGroup.id ||
                      _cachedDefaultGroup?.updatedAt != defaultGroup.updatedAt) {
                    _cachedDefaultGroup = defaultGroup;
                    _lastAgentName = widget.agentName;
                  }

                  final theme = Theme.of(context);
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Row(
                          children: [
                            Text(
                              'Permission for shared users: ',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(width: 8),
                            SegmentedButton<String>(
                              segments: const [
                                ButtonSegment<String>(
                                  value: 'can_use',
                                  label: Text('Can Use'),
                                  icon: Icon(Icons.visibility, size: 16),
                                ),
                                ButtonSegment<String>(
                                  value: 'can_edit',
                                  label: Text('Can Edit'),
                                  icon: Icon(Icons.edit, size: 16),
                                ),
                              ],
                              selected: {widget.defaultGroupPermission},
                              onSelectionChanged: (Set<String> selected) {
                                widget.onDefaultGroupPermissionChanged?.call(selected.first);
                              },
                              style: SegmentedButton.styleFrom(
                                textStyle: theme.textTheme.labelSmall,
                                visualDensity: VisualDensity.compact,
                              ),
                            ),
                          ],
                        ),
                      ),
                      SizedBox(
                        height: 400,
                        child: ManageMembersPanel(
                          key: ValueKey(_cachedDefaultGroup!.id),
                          group: _cachedDefaultGroup!,
                          onChanged: null,
                        ),
                      ),
                    ],
                  );
                }),
      ],
    );
  }
}
