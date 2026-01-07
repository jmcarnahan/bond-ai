import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/config_provider.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/presentation/widgets/agent_icon.dart';
import 'package:flutterui/main.dart';

class AgentCard extends ConsumerWidget {
  final AgentListItemModel agent;
  final VoidCallback? onEdit;

  const AgentCard({super.key, required this.agent, this.onEdit});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appThemeInstance = ref.watch(appThemeProvider);
    final themeData = appThemeInstance.themeData;
    final colorScheme = themeData.colorScheme;
    final textTheme = themeData.textTheme;
    final authState = ref.watch(authNotifierProvider);
    String? currentUserId;
    if (authState is Authenticated) {
      currentUserId = authState.user.userId;
    }

    final bool isOwner = currentUserId != null &&
        agent.metadata != null &&
        (agent.metadata!['owner_user_id'] == currentUserId ||
         agent.metadata!['user_id'] == currentUserId);

    return Card(
      elevation: 1.0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8.0),
      ),
      color: themeData.cardTheme.color ?? colorScheme.surface,
      child: InkWell(
        onTap: () {
          // Update the selected agent
          ref.read(selectedAgentProvider.notifier).selectAgent(agent);

          // Navigate to the chat tab within the navigation shell
          final navItems = ref.read(bottomNavItemsProvider);
          final chatIndex = navItems.indexWhere((item) => item.label == 'Chat');
          if (chatIndex != -1) {
            ref.read(navigationIndexProvider.notifier).state = chatIndex;
          }
        },
        borderRadius: BorderRadius.circular(8.0),
        child: Container(
          padding: const EdgeInsets.all(8.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // Edit button in top right corner
              if (isOwner)
                Align(
                  alignment: Alignment.topRight,
                  child: InkWell(
                    onTap: () {
                      Navigator.pushNamed(
                        context,
                        '/edit-agent/${agent.id}',
                        arguments: agent,
                      );
                    },
                    borderRadius: BorderRadius.circular(16),
                    child: Container(
                      padding: const EdgeInsets.all(2),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        Icons.edit,
                        size: 12,
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                )
              else
                const SizedBox(height: 12), // Space when no edit button
              // Agent icon - slightly bigger for agent cards
              AgentIcon(
                agentName: agent.name,
                metadata: agent.metadata,
                size: 56,
                showBackground: true,
                isSelected: false,
              ),
              const SizedBox(height: 4),
              // Agent name
              Text(
                agent.name,
                style: textTheme.titleSmall?.copyWith(
                  color: colorScheme.onSurface,
                  fontWeight: FontWeight.w600,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
              ),
              // Description
              if (agent.description != null && agent.description!.isNotEmpty) ...[
                const SizedBox(height: 2),
                Text(
                  agent.description!,
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                    fontSize: 11,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                ),
              ],
              const SizedBox(height: 4),
              // Tap to chat text
              Text(
                'Tap to chat',
                style: TextStyle(
                  fontSize: 10,
                  color: colorScheme.primary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
