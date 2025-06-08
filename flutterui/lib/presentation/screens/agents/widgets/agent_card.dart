import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/main.dart';
import 'package:flutterui/providers/auth_provider.dart';

class AgentCard extends ConsumerWidget {
  final AgentListItemModel agent;

  const AgentCard({super.key, required this.agent});

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
      elevation: 2.0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8.0),
      ),
      color: themeData.cardTheme.color ?? colorScheme.surface,
      margin: const EdgeInsets.symmetric(vertical: 4.0, horizontal: 4.0),
      child: Stack(
        children: [
          InkWell(
            onTap: () {
              Navigator.pushNamed(
                context,
                '/chat/${agent.id}',
                arguments: agent,
              );
            },
            borderRadius: BorderRadius.circular(8.0),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: <Widget>[
              CircleAvatar(
                backgroundColor: colorScheme.primary,
                foregroundColor: colorScheme.onPrimary,
                radius: 24,
                child: const Icon(Icons.smart_toy_outlined, size: 28),
              ),
              const SizedBox(height: 12),
              Text(
                agent.name,
                textAlign: TextAlign.center,
                style: textTheme.titleMedium?.copyWith(
                  color: colorScheme.onSurface,
                  fontWeight: FontWeight.w600,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              if (agent.createdAtDisplay != null && agent.createdAtDisplay!.isNotEmpty) ...[
                const SizedBox(height: 6),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.calendar_today_outlined, size: 12, color: colorScheme.onSurfaceVariant.withValues(alpha: 0.7)),
                    const SizedBox(width: 4),
                    Text(
                      agent.createdAtDisplay!,
                      style: textTheme.bodySmall?.copyWith(
                        fontSize: 11,
                        color: colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
                      ),
                    ),
                  ],
                ),
              ],
              if (agent.description != null &&
                  agent.description!.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  agent.description!,
                  textAlign: TextAlign.center,
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              const Spacer(),
              const SizedBox(height: 8),
              Text(
                'Tap to chat',
                style: textTheme.labelSmall?.copyWith(
                  color: colorScheme.primary,
                  fontWeight: FontWeight.w500,
                ),
              ),
                ],
              ),
            ),
          ),
          if (isOwner)
            Positioned(
              top: 8,
              right: 8,
              child: Material(
                color: Colors.transparent,
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
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: colorScheme.primary,
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.1),
                          blurRadius: 4,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Icon(
                      Icons.edit,
                      size: 16,
                      color: colorScheme.onPrimary,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
