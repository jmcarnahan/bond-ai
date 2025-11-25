import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/connections_provider.dart';
import 'package:flutterui/presentation/screens/connections/connections_screen.dart';

/// A banner that appears when connections need attention (not connected or expired).
/// Users can tap to go to connections screen to connect.
class ConnectionAttentionBanner extends ConsumerWidget {
  const ConnectionAttentionBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final connectionsState = ref.watch(connectionsNotifierProvider);
    final needingAttention = connectionsState.connectionsNeedingAttention;
    final expired = connectionsState.expired;

    // Show banner if any connections need attention
    if (needingAttention.isEmpty && expired.isEmpty) {
      return const SizedBox.shrink();
    }

    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    // Build message based on what needs attention
    final String message;
    final String actionText;

    if (expired.isNotEmpty) {
      // Expired connections take priority
      if (expired.length == 1) {
        message = 'Your ${expired.first.displayName} connection has expired.';
      } else {
        message = '${expired.length} connections have expired.';
      }
      actionText = 'Reconnect';
    } else {
      // Not connected
      final notConnected = needingAttention.where((c) => !c.connected).toList();
      if (notConnected.length == 1) {
        message = '${notConnected.first.displayName} is available but not connected.';
      } else {
        message = '${notConnected.length} connections are available.';
      }
      actionText = 'Connect';
    }

    return Material(
      color: expired.isNotEmpty ? colorScheme.errorContainer : colorScheme.primaryContainer,
      child: SafeArea(
        bottom: false,
        child: InkWell(
          onTap: () {
            Navigator.of(context).pushNamed(ConnectionsScreen.routeName);
          },
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Row(
              children: [
                Icon(
                  expired.isNotEmpty ? Icons.warning_amber_rounded : Icons.link,
                  color: expired.isNotEmpty
                      ? colorScheme.onErrorContainer
                      : colorScheme.onPrimaryContainer,
                  size: 20,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    message,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: expired.isNotEmpty
                          ? colorScheme.onErrorContainer
                          : colorScheme.onPrimaryContainer,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  actionText,
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: expired.isNotEmpty
                        ? colorScheme.onErrorContainer
                        : colorScheme.onPrimaryContainer,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(width: 4),
                Icon(
                  Icons.chevron_right,
                  color: expired.isNotEmpty
                      ? colorScheme.onErrorContainer
                      : colorScheme.onPrimaryContainer,
                  size: 20,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Legacy alias for backward compatibility
typedef ExpiredConnectionBanner = ConnectionAttentionBanner;

/// A dismissible version of the connection attention banner
class DismissibleConnectionAttentionBanner extends ConsumerStatefulWidget {
  const DismissibleConnectionAttentionBanner({super.key});

  @override
  ConsumerState<DismissibleConnectionAttentionBanner> createState() =>
      _DismissibleConnectionAttentionBannerState();
}

class _DismissibleConnectionAttentionBannerState
    extends ConsumerState<DismissibleConnectionAttentionBanner> {
  bool _dismissed = false;

  @override
  Widget build(BuildContext context) {
    if (_dismissed) {
      return const SizedBox.shrink();
    }

    final connectionsState = ref.watch(connectionsNotifierProvider);
    final needingAttention = connectionsState.connectionsNeedingAttention;
    final expired = connectionsState.expired;

    // Show banner if any connections need attention
    if (needingAttention.isEmpty && expired.isEmpty) {
      return const SizedBox.shrink();
    }

    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    // Build message based on what needs attention
    final String message;
    final String actionText;
    final bool isError = expired.isNotEmpty;

    if (expired.isNotEmpty) {
      if (expired.length == 1) {
        message = 'Your ${expired.first.displayName} connection has expired.';
      } else {
        message = '${expired.length} connections have expired.';
      }
      actionText = 'Reconnect';
    } else {
      final notConnected = needingAttention.where((c) => !c.connected).toList();
      if (notConnected.length == 1) {
        message = '${notConnected.first.displayName} is available but not connected.';
      } else {
        message = '${notConnected.length} connections are available.';
      }
      actionText = 'Connect';
    }

    final bgColor = isError ? colorScheme.errorContainer : colorScheme.primaryContainer;
    final fgColor = isError ? colorScheme.onErrorContainer : colorScheme.onPrimaryContainer;

    return Material(
      color: bgColor,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(
                isError ? Icons.warning_amber_rounded : Icons.link,
                color: fgColor,
                size: 20,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  message,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: fgColor,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              TextButton(
                onPressed: () {
                  Navigator.of(context).pushNamed(ConnectionsScreen.routeName);
                },
                style: TextButton.styleFrom(
                  foregroundColor: fgColor,
                ),
                child: Text(actionText),
              ),
              IconButton(
                icon: Icon(
                  Icons.close,
                  color: fgColor,
                  size: 18,
                ),
                onPressed: () {
                  setState(() {
                    _dismissed = true;
                  });
                },
                tooltip: 'Dismiss',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Legacy alias for backward compatibility
typedef DismissibleExpiredConnectionBanner = DismissibleConnectionAttentionBanner;
