import 'callback_handler.dart';

/// Mobile implementation of CallbackHandler
class CallbackHandlerImpl implements CallbackHandler {
  @override
  String? getCurrentUrl() {
    // Mobile apps don't have URLs, they use deep links
    return null;
  }

  @override
  bool isAuthCallbackRoute() {
    // For mobile, auth callbacks come through deep links
    // This would be handled by the platform-specific code
    return false;
  }

  @override
  String? extractToken() {
    // On mobile, tokens come through deep links or custom URL schemes
    // This would be handled by platform-specific code (iOS/Android)
    return null;
  }
}

// Export the implementation
final CallbackHandler callbackHandler = CallbackHandlerImpl();
