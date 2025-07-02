import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/providers/agent_provider.dart';

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

  String _getAgentAbbreviation(String name) {
    final trimmedName = name.trim();

    // Special case for 'Home'
    if (trimmedName.toLowerCase() == 'home') {
      return 'Home';
    }

    // Split into words and filter out 'Agent' if it's the last word
    var words =
        trimmedName.split(' ').where((word) => word.isNotEmpty).toList();
    if (words.isEmpty) return '?';

    // Remove 'Agent' if it's the last word (case-insensitive)
    if (words.length > 1 && words.last.toLowerCase() == 'agent') {
      words = words.sublist(0, words.length - 1);
    }

    // If we have no words left after removing 'Agent', use the original
    if (words.isEmpty) {
      words = trimmedName.split(' ').where((word) => word.isNotEmpty).toList();
    }

    // Generate abbreviation based on remaining words
    if (words.length == 1) {
      final word = words[0];
      // For single words, use first letter or first two if very short
      if (word.length <= 3) {
        return word.toUpperCase();
      } else {
        return word[0].toUpperCase();
      }
    } else if (words.length == 2) {
      // For two words, use first letter of each
      return words.map((w) => w[0].toUpperCase()).join('');
    } else {
      // For 3+ words, prioritize important words (skip common ones)
      final skipWords = {
        'the',
        'and',
        'of',
        'for',
        'to',
        'in',
        'on',
        'at',
        'by',
      };
      final importantWords =
          words.where((w) => !skipWords.contains(w.toLowerCase())).toList();

      if (importantWords.isEmpty) {
        // If all words are common, use first letters of first two words
        return words.take(2).map((w) => w[0].toUpperCase()).join('');
      } else if (importantWords.length == 1) {
        // If only one important word, use its first letter
        return importantWords[0][0].toUpperCase();
      } else {
        // Use first letters of important words, max 2 characters
        return importantWords.take(2).map((w) => w[0].toUpperCase()).join('');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 12),
      child: Tooltip(
        message: agent.name,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(24),
          child: Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color:
                  isSelected
                      ? colorScheme.primary.withValues(alpha: 0.2)
                      : colorScheme.surfaceContainerHighest,
              border:
                  isSelected
                      ? Border.all(color: colorScheme.primary, width: 2)
                      : null,
            ),
            child: Center(
              child: Text(
                _getAgentAbbreviation(agent.name),
                style: TextStyle(
                  color:
                      isSelected
                          ? colorScheme.primary
                          : colorScheme.onSurfaceVariant,
                  fontSize:
                      _getAgentAbbreviation(agent.name).length > 2 ? 12 : 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
