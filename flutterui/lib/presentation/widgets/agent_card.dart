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
      elevation: 3.0, // Slightly reduced elevation for a cleaner look
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12.0),
      ),
      color: themeData.cardTheme.color ?? colorScheme.background, // Ensure card uses theme background
      margin: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0),
      child: InkWell(
        onTap: () {
          Navigator.pushNamed(
            context,
            '/chat/${agent.id}',
            arguments: agent,
          );
        },
        borderRadius: BorderRadius.circular(12.0),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: <Widget>[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    backgroundColor: colorScheme.primary, // McAfee Red
                    foregroundColor: colorScheme.onPrimary, // White
                    child: const Icon(Icons.person_outline),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          agent.name,
                          style: textTheme.headlineSmall?.copyWith( // More prominent name
                            color: colorScheme.onSurface,
                            fontWeight: FontWeight.w600, // Slightly bolder for headline
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        if (agent.description != null &&
                            agent.description!.isNotEmpty) ...[
                          const SizedBox(height: 6), // Increased spacing
                          Text(
                            agent.description!,
                            style: textTheme.bodySmall?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                            ),
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                        // Display Model
                        if (agent.model != null && agent.model!.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Icon(Icons.memory, size: 14, color: colorScheme.onSurfaceVariant),
                              const SizedBox(width: 4),
                              Text(
                                'Model: ${agent.model}',
                                style: textTheme.bodySmall?.copyWith(
                                  color: colorScheme.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ],
                        // Display Created At
                        if (agent.createdAtDisplay != null && agent.createdAtDisplay!.isNotEmpty) ...[
                          const SizedBox(height: 4), // Smaller spacing
                          Row(
                            children: [
                              Icon(Icons.calendar_today_outlined, size: 12, color: colorScheme.onSurfaceVariant.withOpacity(0.7)),
                              const SizedBox(width: 4),
                              Text(
                                'Created: ${agent.createdAtDisplay}',
                                style: textTheme.bodySmall?.copyWith(
                                  fontSize: 11, // Slightly smaller
                                  color: colorScheme.onSurfaceVariant.withOpacity(0.7),
                                ),
                              ),
                            ],
                          ),
                        ],
                        // Display Tool Types
                        if (agent.tool_types != null && agent.tool_types!.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(Icons.build_circle_outlined, size: 14, color: colorScheme.onSurfaceVariant),
                              const SizedBox(width: 4),
                              Expanded(
                                child: Wrap(
                                  spacing: 4.0,
                                  runSpacing: 2.0,
                                  children: agent.tool_types!
                                      .map((type) => Chip(
                                            label: Text(
                                              type.replaceAll('_', ' '), // Make it more readable
                                              style: textTheme.labelSmall?.copyWith(
                                                color: colorScheme.onSecondaryContainer, // Adjusted for chip
                                              )
                                            ),
                                            backgroundColor: colorScheme.secondaryContainer, // Adjusted for chip
                                            padding: const EdgeInsets.symmetric(horizontal: 6.0, vertical: 0.0), // Smaller padding
                                            labelPadding: EdgeInsets.zero, // Remove extra padding around label
                                            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap, // Reduce tap target size
                                            visualDensity: VisualDensity.compact, // Make chip more compact
                                          ))
                                      .toList(),
                                ),
                              ),
                            ],
                          ),
                        ],
                        // Display Sample Prompt
                        if (agent.samplePrompt != null && agent.samplePrompt!.isNotEmpty) ...[
                          const SizedBox(height: 10),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 6.0),
                            decoration: BoxDecoration(
                              color: colorScheme.surfaceVariant.withOpacity(0.5),
                              borderRadius: BorderRadius.circular(6.0),
                              border: Border.all(color: colorScheme.outline.withOpacity(0.3))
                            ),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Icon(Icons.lightbulb_outline, size: 16, color: colorScheme.onSurfaceVariant),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: Text(
                                    '"${agent.samplePrompt}"',
                                    style: textTheme.bodySmall?.copyWith(
                                      color: colorScheme.onSurfaceVariant,
                                      fontStyle: FontStyle.italic,
                                    ),
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16), // Increased space before "Tap to chat"
              Align(
                alignment: Alignment.bottomRight,
                child: Text(
                  'Tap to chat',
                  style: textTheme.labelSmall?.copyWith(
                    color: colorScheme.primary, // McAfee Red for action text
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
