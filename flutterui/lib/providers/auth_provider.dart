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
    logger.i("[AuthNotifier] _checkInitialAuthStatus called.");
    state = const AuthLoading();
    try {
      final token = await _authService.retrieveToken();
      logger.i("[AuthNotifier] Retrieved token: $token");
      if (token != null && token.isNotEmpty) {
        logger.i("[AuthNotifier] Token found, attempting to get current user.");
        final user = await _authService.getCurrentUser();
        logger.i(
          "[AuthNotifier] Got user: ${user.email}. Setting state to Authenticated.",
        );
        state = Authenticated(user);
      } else {
        logger.i(
          "[AuthNotifier] No token found. Setting state to Unauthenticated.",
        );
        state = const Unauthenticated();
      }
    } catch (e) {
      logger.i("[AuthNotifier] Error in _checkInitialAuthStatus: ${e.toString()}");
      await _authService.clearToken();
      state = Unauthenticated(message: "Session error. Please log in again.");
    }
  }

  Future<void> initiateLogin() async {
    try {
      await _authService.launchLoginUrl();
    } catch (e) {
      state = AuthError(e.toString());
    }
  }

  Future<bool> loginWithToken(String token) async {
    logger.i("[AuthNotifier] loginWithToken called with token: $token");
    state = const AuthLoading();
    try {
      logger.i("[AuthNotifier] Storing token...");
      await _authService.storeToken(token);
      logger.i("[AuthNotifier] Token stored. Getting current user...");
      final user = await _authService.getCurrentUser();
      logger.i(
        "[AuthNotifier] Got user: ${user.email}. Setting state to Authenticated.",
      );
      state = Authenticated(user);
      return true;
    } catch (e) {
      logger.i("[AuthNotifier] Error in loginWithToken: ${e.toString()}");
      await _authService.clearToken();
      state = AuthError("Login failed: ${e.toString()}");
      return false;
    }
  }

  Future<void> logout() async {
    logger.i("[AuthNotifier] logout called.");
    state = const AuthLoading();
    try {
      await _authService.clearToken();
      state = const Unauthenticated(message: "Successfully logged out.");
    } catch (e) {
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
