import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import '../core/utils/logger.dart';

abstract class AuthState {
  const AuthState();
}

class AuthInitial extends AuthState {
  const AuthInitial();
}

class AuthLoading extends AuthState {
  const AuthLoading();
}

class Authenticated extends AuthState {
  final User user;
  const Authenticated(this.user);

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is Authenticated && other.user == user;
  }

  @override
  int get hashCode => user.hashCode;
}

class Unauthenticated extends AuthState {
  final String? message;
  const Unauthenticated({this.message});
}

class AuthError extends AuthState {
  final String error;
  const AuthError(this.error);
}

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthService _authService;

  AuthNotifier(this._authService) : super(const AuthInitial()) {
    _checkInitialAuthStatus();
  }

  Future<void> _checkInitialAuthStatus() async {
    state = const AuthLoading();
    try {
      final token = await _authService.retrieveToken();
      if (token != null && token.isNotEmpty) {
        final user = await _authService.getCurrentUser();
        state = Authenticated(user);
      } else {
        state = const Unauthenticated();
      }
    } catch (e) {
      logger.e("[AuthNotifier] Session error: ${e.toString()}");
      await _authService.clearToken();
      state = Unauthenticated(message: "Session error. Please log in again.");
    }
  }

  Future<void> initiateLogin({String provider = 'google'}) async {
    try {
      await _authService.launchLoginUrl(provider: provider);
    } catch (e) {
      state = AuthError(e.toString());
    }
  }

  Future<List<Map<String, dynamic>>> getAvailableProviders() async {
    try {
      return await _authService.getAvailableProviders();
    } catch (e) {
      logger.e("[AuthNotifier] Failed to get providers: ${e.toString()}");
      return [];
    }
  }

  Future<bool> loginWithToken(String token) async {
    state = const AuthLoading();
    try {
      await _authService.storeToken(token);
      final user = await _authService.getCurrentUser();
      state = Authenticated(user);
      return true;
    } catch (e) {
      logger.e("[AuthNotifier] Login failed: ${e.toString()}");
      await _authService.clearToken();
      state = AuthError("Login failed: ${e.toString()}");
      return false;
    }
  }

  Future<void> logout() async {
    logger.i("[AuthNotifier] Logout initiated");
    state = const AuthLoading();
    try {
      await _authService.performFullLogout();
      logger.i("[AuthNotifier] Full logout completed");
      // Note: On web, performFullLogout will redirect the page to login,
      // so this state change may not be visible
      state = const Unauthenticated(message: "Successfully logged out.");
    } catch (e) {
      logger.e("[AuthNotifier] Error during logout: $e");
      state = AuthError(e.toString());
      await _authService.clearToken();
      state = const Unauthenticated(
        message: "Logged out, but encountered an issue clearing session.",
      );
    }
  }
}

final authNotifierProvider = StateNotifierProvider<AuthNotifier, AuthState>((
  ref,
) {
  final authService = ref.watch(authServiceProvider);
  return AuthNotifier(authService);
});
