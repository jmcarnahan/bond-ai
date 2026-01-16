import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/connections_provider.dart';
import 'package:flutterui/presentation/screens/connections/connections_screen.dart';

/// A compact indicator showing connection status in the app header.
/// Shows a visual bar representing connected vs total connections.
/// Green when all connected, red/amber when some need attention.
/// Clickable to navigate to connections screen.
class ConnectionStatusIndicator extends ConsumerStatefulWidget {
  const ConnectionStatusIndicator({super.key});

  @override
  ConsumerState<ConnectionStatusIndicator> createState() =>
      _ConnectionStatusIndicatorState();
}

class _ConnectionStatusIndicatorState
    extends ConsumerState<ConnectionStatusIndicator> {
  @override
  void initState() {
    super.initState();
    // Ensure connections are loaded when indicator is first shown
    Future.microtask(() {
      final state = ref.read(connectionsNotifierProvider);
      if (state.connections.isEmpty && !state.isLoading) {
        ref.read(connectionsNotifierProvider.notifier).loadConnections();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final connectionsState = ref.watch(connectionsNotifierProvider);
    final colorScheme = Theme.of(context).colorScheme;

    // Calculate connected count (connected AND valid)
    final connectedCount = connectionsState.connections
        .where((c) => c.connected && c.valid)
        .length;
    final totalCount = connectionsState.connections.length;

    // Determine status color
    final bool allConnected = totalCount > 0 && connectedCount == totalCount;
    final bool noneConnected = connectedCount == 0;

    Color statusColor;
    if (totalCount == 0) {
      statusColor = colorScheme.outline; // Gray when no connections available
    } else if (allConnected) {
      statusColor = Colors.green;
    } else if (noneConnected) {
      statusColor = colorScheme.error;
    } else {
      statusColor = Colors.amber.shade700; // Partial - amber/orange
    }

    // Don't show if no connections are configured
    if (totalCount == 0 && !connectionsState.isLoading) {
      return const SizedBox.shrink();
    }

    return Tooltip(
      message: 'Connections: $connectedCount/$totalCount connected',
      child: InkWell(
        onTap: () {
          Navigator.pushNamed(context, ConnectionsScreen.routeName);
        },
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Connection icon
              Icon(
                Icons.link,
                size: 18,
                color: statusColor,
              ),
              const SizedBox(width: 6),
              // Visual bar + count
              Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Progress bar
                  _buildConnectionBar(
                    connectedCount: connectedCount,
                    totalCount: totalCount,
                    statusColor: statusColor,
                    colorScheme: colorScheme,
                  ),
                  const SizedBox(height: 2),
                  // Count text
                  Text(
                    '$connectedCount/$totalCount',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: statusColor,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildConnectionBar({
    required int connectedCount,
    required int totalCount,
    required Color statusColor,
    required ColorScheme colorScheme,
  }) {
    const double barWidth = 40;
    const double barHeight = 6;

    if (totalCount == 0) {
      return Container(
        width: barWidth,
        height: barHeight,
        decoration: BoxDecoration(
          color: colorScheme.outline.withValues(alpha: 0.3),
          borderRadius: BorderRadius.circular(3),
        ),
      );
    }

    final double fillRatio = connectedCount / totalCount;

    return Container(
      width: barWidth,
      height: barHeight,
      decoration: BoxDecoration(
        color: colorScheme.outline.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Stack(
        children: [
          // Filled portion
          FractionallySizedBox(
            widthFactor: fillRatio,
            child: Container(
              decoration: BoxDecoration(
                color: statusColor,
                borderRadius: BorderRadius.circular(3),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
