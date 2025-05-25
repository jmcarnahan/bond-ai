import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart'; // Import Riverpod
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/main.dart'; // Import for appThemeProvider

class AgentCard extends ConsumerWidget { // Change to ConsumerWidget
  final AgentListItemModel agent;

  const AgentCard({super.key, required this.agent});

  @override
  Widget build(BuildContext context, WidgetRef ref) { // Add WidgetRef
    final appThemeInstance = ref.watch(appThemeProvider);
    final themeData = appThemeInstance.themeData;
    final colorScheme = themeData.colorScheme;
    final textTheme = themeData.textTheme;

    return Card(
      elevation: 2.0, // Further reduced elevation
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8.0), // Smaller border radius
      ),
      color: themeData.cardTheme.color ?? colorScheme.background,
      margin: const EdgeInsets.symmetric(vertical: 4.0, horizontal: 4.0), // Reduced vertical margin
      child: InkWell(
        onTap: () {
          Navigator.pushNamed(
            context,
            '/chat/${agent.id}',
            arguments: agent,
          );
        },
        borderRadius: BorderRadius.circular(8.0), // Smaller border radius
        child: Padding(
          padding: const EdgeInsets.all(12.0), // Reduced padding
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center, // Center content horizontally
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center, // Center content vertically
            children: <Widget>[
              CircleAvatar(
                backgroundColor: colorScheme.primary, // McAfee Red
                foregroundColor: colorScheme.onPrimary, // White
                radius: 24, // Slightly larger icon
                child: const Icon(Icons.smart_toy_outlined, size: 28), // New Icon
              ),
              const SizedBox(height: 12), // Space between icon and name
              Text(
                agent.name,
                textAlign: TextAlign.center, // Center text
                style: textTheme.titleMedium?.copyWith( // Adjusted style for better fit
                  color: colorScheme.onSurface,
                  fontWeight: FontWeight.w600,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              // Display Created At (Moved Up)
              if (agent.createdAtDisplay != null && agent.createdAtDisplay!.isNotEmpty) ...[
                const SizedBox(height: 6), // Space between name and date
                Row(
                  mainAxisSize: MainAxisSize.min, // Row takes minimum space
                  mainAxisAlignment: MainAxisAlignment.center, // Center row content
                  children: [
                    Icon(Icons.calendar_today_outlined, size: 12, color: colorScheme.onSurfaceVariant.withOpacity(0.7)),
                    const SizedBox(width: 4),
                    Text(
                      agent.createdAtDisplay!,
                      style: textTheme.bodySmall?.copyWith(
                        fontSize: 11,
                        color: colorScheme.onSurfaceVariant.withOpacity(0.7),
                      ),
                    ),
                  ],
                ),
              ],
              // Description section
              if (agent.description != null &&
                  agent.description!.isNotEmpty) ...[
                const SizedBox(height: 8), // Space between date and description
                Text(
                  agent.description!,
                  textAlign: TextAlign.center, // Center text
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                  maxLines: 2, // Reduced max lines for brevity
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              const Spacer(), // Pushes "Tap to chat" to the bottom
              const SizedBox(height: 8), // Consistent small space above "Tap to chat"
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
    );
  }
}
