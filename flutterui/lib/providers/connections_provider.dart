import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/connection_model.dart';
import 'package:flutterui/data/services/connections_service.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import '../core/utils/logger.dart';

/// State for connections
class ConnectionsState {
  final List<ConnectionStatus> connections;
  final List<ExpiredConnection> expired;
  final bool isLoading;
  final String? error;

  const ConnectionsState({
    this.connections = const [],
    this.expired = const [],
    this.isLoading = false,
    this.error,
  });

  ConnectionsState copyWith({
    List<ConnectionStatus>? connections,
    List<ExpiredConnection>? expired,
    bool? isLoading,
    String? error,
  }) {
    return ConnectionsState(
      connections: connections ?? this.connections,
      expired: expired ?? this.expired,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }

  /// Check if there are any connections that need attention
  bool get hasExpiredConnections => expired.isNotEmpty;

  /// Get connections that need attention (not connected or expired)
  List<ConnectionStatus> get connectionsNeedingAttention =>
      connections.where((c) => c.needsAttention).toList();
}

/// Notifier for managing connections state
class ConnectionsNotifier extends StateNotifier<ConnectionsState> {
  final ConnectionsService _service;

  ConnectionsNotifier(this._service) : super(const ConnectionsState());

  /// Load all connections
  Future<void> loadConnections() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final response = await _service.listConnections();
      state = state.copyWith(
        connections: response.connections,
        expired: response.expired,
        isLoading: false,
      );
      logger.i("[ConnectionsNotifier] Loaded ${response.connections.length} connections");
    } catch (e) {
      logger.e("[ConnectionsNotifier] Error loading connections: $e");
      state = state.copyWith(
        isLoading: false,
        error: e.toString(),
      );
    }
  }

  /// Get authorization URL for a connection
  Future<String?> getAuthorizationUrl(String connectionName) async {
    try {
      final response = await _service.authorize(connectionName);
      return response.authorizationUrl;
    } catch (e) {
      logger.e("[ConnectionsNotifier] Error getting auth URL: $e");
      state = state.copyWith(error: e.toString());
      return null;
    }
  }

  /// Disconnect from a connection
  Future<bool> disconnect(String connectionName) async {
    try {
      final success = await _service.disconnect(connectionName);
      if (success) {
        // Reload connections to reflect the change
        await loadConnections();
      }
      return success;
    } catch (e) {
      logger.e("[ConnectionsNotifier] Error disconnecting: $e");
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  /// Check for expired connections (called after login)
  Future<CheckExpiredResponse?> checkExpired() async {
    try {
      final response = await _service.checkExpiredConnections();
      if (response.hasExpired) {
        state = state.copyWith(
          expired: response.expiredConnections,
        );
      }
      return response;
    } catch (e) {
      logger.e("[ConnectionsNotifier] Error checking expired: $e");
      return null;
    }
  }

  /// Clear error
  void clearError() {
    state = state.copyWith(error: null);
  }

  /// Mark a connection as successfully connected (called after OAuth callback)
  void markConnected(String connectionName) {
    final updatedConnections = state.connections.map((c) {
      if (c.name == connectionName) {
        return ConnectionStatus(
          name: c.name,
          displayName: c.displayName,
          description: c.description,
          connected: true,
          valid: true,
          authType: c.authType,
          iconUrl: c.iconUrl,
          scopes: c.scopes,
          expiresAt: c.expiresAt,
          requiresAuthorization: false,
        );
      }
      return c;
    }).toList();

    // Remove from expired list
    final updatedExpired = state.expired
        .where((e) => e.name != connectionName)
        .toList();

    state = state.copyWith(
      connections: updatedConnections,
      expired: updatedExpired,
    );
  }

}

/// Provider for connections state
final connectionsNotifierProvider =
    StateNotifierProvider<ConnectionsNotifier, ConnectionsState>((ref) {
  final service = ref.watch(connectionsServiceProvider);
  return ConnectionsNotifier(service);
});

/// Provider for checking if there are expired connections (used for showing banner)
final hasExpiredConnectionsProvider = Provider<bool>((ref) {
  final state = ref.watch(connectionsNotifierProvider);
  return state.hasExpiredConnections;
});

/// Provider for getting expired connection names (for display)
final expiredConnectionsProvider = Provider<List<ExpiredConnection>>((ref) {
  final state = ref.watch(connectionsNotifierProvider);
  return state.expired;
});
