/// Abstract interface for handling auth callbacks
abstract class CallbackHandler {
  /// Get the current URL if available (web only)
  String? getCurrentUrl();

  /// Check if we're on the auth callback page
  bool isAuthCallbackRoute();

  /// Extract token from current context
  String? extractToken();
}
