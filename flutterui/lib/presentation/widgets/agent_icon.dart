import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:material_symbols_icons/symbols.dart';
import 'package:material_symbols_icons/get.dart';
import 'package:logger/logger.dart';

class AgentIcon extends StatelessWidget {
  final String agentName;
  final Map<String, dynamic>? metadata;
  final double size;
  final bool showBackground;
  final bool isSelected;

  const AgentIcon({
    super.key,
    required this.agentName,
    this.metadata,
    this.size = 48,
    this.showBackground = true,
    this.isSelected = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    final logger = Logger(
      printer: PrettyPrinter(methodCount: 0, noBoxingByDefault: true),
    );

    try {
      // Special handling for Home agent
      if (agentName.toLowerCase() == 'home') {
        // logger.i('[AgentIcon] Using hardcoded home icon for Home agent');
        if (showBackground) {
          return Container(
            width: size,
            height: size,
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
            child: Icon(
              Symbols.home,
              size: size * 0.6,
              color:
                  isSelected
                      ? colorScheme.primary
                      : colorScheme.onSurfaceVariant,
            ),
          );
        } else {
          return Icon(
            Symbols.home,
            size: size * 0.6,
            color: colorScheme.onSurfaceVariant,
          );
        }
      }

      // Check if agent has icon data
      if (metadata == null ||
          metadata!['icon_svg'] == null ||
          metadata!['icon_svg'].toString().isEmpty) {
        // Fallback to text icon
        return _buildTextIcon(context);
      }

      final iconDataStr = metadata!['icon_svg'] as String;
      // logger.i('[AgentIcon] Raw icon data for "$agentName": $iconDataStr');

      // Try to parse as JSON first (new format)
      String iconName = 'smart_toy';
      Color? backgroundColor;

      try {
        final iconJson = json.decode(iconDataStr);
        if (iconJson is Map) {
          iconName = iconJson['icon_name'] ?? 'smart_toy';
          final colorStr = iconJson['color'];
          if (colorStr != null) {
            backgroundColor = Color(
              int.parse(colorStr.replaceFirst('#', '0xFF')),
            );
          }
          // logger.d(
          //   '[AgentIcon] Parsed for "$agentName": icon=$iconName, color=$colorStr',
          // );
        }
      } catch (e) {
        // Fall back to treating it as just an icon name (old format)
        iconName = iconDataStr;
        logger.w(
          '[AgentIcon] Failed to parse JSON for "$agentName", using as icon name: $iconName',
        );
      }

      // Dynamically get the icon using SymbolsGet with rounded style for better visibility
      final iconData = SymbolsGet.get(iconName, SymbolStyle.rounded);
      // logger.i('[AgentIcon] Got icon data for "$iconName": success');

      // Build the icon with or without background
      if (showBackground && backgroundColor != null) {
        // logger.i(
        //   '[AgentIcon] Creating icon with background color for "$agentName"',
        // );
        return Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color:
                isSelected
                    ? backgroundColor.withValues(alpha: 0.8)
                    : backgroundColor,
            border:
                isSelected
                    ? Border.all(color: colorScheme.primary, width: 2)
                    : null,
          ),
          child: Icon(iconData, size: size * 0.54, color: Colors.white),
        );
      } else if (showBackground) {
        // Show background without custom color
        return Container(
          width: size,
          height: size,
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
          child: Icon(
            iconData,
            size: size * 0.6,
            color:
                isSelected ? colorScheme.primary : colorScheme.onSurfaceVariant,
          ),
        );
      } else {
        // No background
        // logger.i(
        //   '[AgentIcon] Creating icon without background for "$agentName"',
        // );
        return Icon(
          iconData,
          size: size * 0.6,
          color: colorScheme.onSurfaceVariant,
        );
      }
    } catch (e) {
      // Fallback to smart_toy icon if parsing fails
      logger.e('[AgentIcon] Error building icon for "$agentName": $e');
      return Icon(
        Symbols.smart_toy,
        size: size * 0.6,
        color: isSelected ? colorScheme.primary : colorScheme.onSurfaceVariant,
      );
    }
  }

  Widget _buildTextIcon(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final abbreviation = _getAgentAbbreviation(agentName);

    if (showBackground) {
      return Container(
        width: size,
        height: size,
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
            abbreviation,
            style: TextStyle(
              color:
                  isSelected
                      ? colorScheme.primary
                      : colorScheme.onSurfaceVariant,
              fontSize: size * 0.3,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      );
    } else {
      return Text(
        abbreviation,
        style: TextStyle(
          color: colorScheme.onSurfaceVariant,
          fontSize: size * 0.3,
          fontWeight: FontWeight.w600,
        ),
      );
    }
  }

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
}
