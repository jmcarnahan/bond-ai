import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/main.dart'; // For sharedPreferencesProvider

// Define the states for authentication
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
  final String? message; // Optional message (e.g., after logout, or error)
  const Unauthenticated({this.message});
}

class AuthError extends AuthState {
  final String error;
  const AuthError(this.error);
}

// Provider for AuthService (depends on SharedPreferences)
final authServiceProvider = Provider<AuthService>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  return AuthService(sharedPreferences: prefs);
});

// AuthNotifier manages the authentication state
class AuthNotifier extends StateNotifier<AuthState> {
  final AuthService _authService;

  AuthNotifier(this._authService) : super(const AuthInitial()) {
    _checkInitialAuthStatus();
  }

  Future<void> _checkInitialAuthStatus() async {
    print("[AuthNotifier] _checkInitialAuthStatus called.");
    state = const AuthLoading();
    try {
      final token = await _authService.retrieveToken();
      print("[AuthNotifier] Retrieved token: $token");
      if (token != null && token.isNotEmpty) {
        print("[AuthNotifier] Token found, attempting to get current user.");
        final user = await _authService.getCurrentUser();
        print(
          "[AuthNotifier] Got user: ${user.email}. Setting state to Authenticated.",
        );
        state = Authenticated(user);
      } else {
        print(
          "[AuthNotifier] No token found. Setting state to Unauthenticated.",
        );
        state = const Unauthenticated();
      }
    } catch (e) {
      print("[AuthNotifier] Error in _checkInitialAuthStatus: ${e.toString()}");
      await _authService.clearToken();
      state = Unauthenticated(message: "Session error. Please log in again.");
    }
  }

  Future<void> initiateLogin() async {
    try {
      await _authService.launchLoginUrl();
      // After launch, the app will lose focus.
      // The user will be redirected back to the app after Google login.
      // The token will need to be captured from the URL on web.
      // For now, we don't change state here until token is confirmed.
    } catch (e) {
      state = AuthError(e.toString());
    }
  }

  // This method would be called after the app captures the token from the redirect
  Future<bool> loginWithToken(String token) async {
    // Changed to return Future<bool>
    print("[AuthNotifier] loginWithToken called with token: $token");
    state = const AuthLoading();
    try {
      print("[AuthNotifier] Storing token...");
      await _authService.storeToken(token);
      print("[AuthNotifier] Token stored. Getting current user...");
      final user = await _authService.getCurrentUser();
      print(
        "[AuthNotifier] Got user: ${user.email}. Setting state to Authenticated.",
      );
      state = Authenticated(user);
      return true; // Indicate success
    } catch (e) {
      print("[AuthNotifier] Error in loginWithToken: ${e.toString()}");
      await _authService.clearToken();
      state = AuthError("Login failed: ${e.toString()}");
      return false; // Indicate failure
    }
  }

  Future<void> logout() async {
    print("[AuthNotifier] logout called.");
    state = const AuthLoading();
    try {
      await _authService.clearToken();
      state = const Unauthenticated(message: "Successfully logged out.");
    } catch (e) {
      state = AuthError(e.toString());
      // Attempt to also clear local state to unauthenticated if service fails
      await _authService.clearToken();
      state = const Unauthenticated(
        message: "Logged out, but encountered an issue clearing session.",
      );
    }
  }
}

// StateNotifierProvider for AuthNotifier
final authNotifierProvider = StateNotifierProvider<AuthNotifier, AuthState>((
  ref,
) {
  final authService = ref.watch(authServiceProvider);
  return AuthNotifier(authService);
});
