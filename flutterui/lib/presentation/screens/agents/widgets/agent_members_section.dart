import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/manage_members_panel.dart';
import 'package:flutterui/presentation/widgets/manage_members_panel/providers/manage_members_provider.dart';

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

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Share with Users',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Add users who can access this agent. These users will be automatically added to the agent\'s sharing group.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).textTheme.bodySmall?.color,
              ),
            ),
            const SizedBox(height: 16),
            
            if (widget.agentName == null)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32.0),
                  child: Text(
                    'Enter an agent name to start adding users.',
                    textAlign: TextAlign.center,
                  ),
                ),
              )
            else if (_cachedGroups == null)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32.0),
                  child: CircularProgressIndicator(),
                ),
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
                    return Center(
                      child: Padding(
                        padding: const EdgeInsets.all(32.0),
                        child: Column(
                          children: [
                            Icon(
                              Icons.info_outline,
                              color: Theme.of(context).colorScheme.primary,
                              size: 48,
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Agent sharing group will be created when you save.',
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.primary,
                              ),
                              textAlign: TextAlign.center,
                            ),
                          ],
                        ),
                      ),
                    );
                  }
                }),
          ],
        ),
      ),
    );
  }
}