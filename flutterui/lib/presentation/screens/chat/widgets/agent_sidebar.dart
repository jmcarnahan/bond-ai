import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/presentation/widgets/agent_icon.dart';

class AgentSidebar extends ConsumerWidget {
  final String currentAgentId;
  final Function(AgentListItemModel) onAgentSelected;

  const AgentSidebar({
    super.key,
    required this.currentAgentId,
    required this.onAgentSelected,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final agentsAsyncValue = ref.watch(agentsProvider);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Container(
      width: 72,
      decoration: BoxDecoration(
        color: colorScheme.surface,
        border: Border(
          right: BorderSide(
            color: theme.dividerColor.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 4,
            offset: const Offset(2, 0),
          ),
        ],
      ),
      child: agentsAsyncValue.when(
        data:
            (agents) => ListView.builder(
              padding: const EdgeInsets.symmetric(vertical: 16),
              itemCount: agents.length,
              itemBuilder: (context, index) {
                final agent = agents[index];
                return _AgentIconButton(
                  agent: agent,
                  isSelected: agent.id == currentAgentId,
                  onTap: () {
                    if (agent.id != currentAgentId) {
                      onAgentSelected(agent);
                    }
                  },
                );
              },
            ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const SizedBox.shrink(),
      ),
    );
  }
}

class _AgentIconButton extends StatelessWidget {
  final AgentListItemModel agent;
  final bool isSelected;
  final VoidCallback onTap;

  const _AgentIconButton({
    required this.agent,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Tooltip(
            message: agent.name,
            child: InkWell(
              onTap: onTap,
              borderRadius: BorderRadius.circular(24),
              child: AgentIcon(
                agentName: agent.name,
                metadata: agent.metadata,
                size: 48,
                showBackground: true,
                isSelected: isSelected,
              ),
            ),
          ),
          const SizedBox(height: 2),
          // Agent name below icon
          SizedBox(
            width: 56,
            child: Text(
              agent.name,
              style: TextStyle(
                color: isSelected
                    ? colorScheme.primary
                    : colorScheme.onSurfaceVariant,
                fontSize: 10,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
              ),
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}