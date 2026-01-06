import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/core/utils/logger.dart';

enum ErrorType {
  authentication,
  network,
  validation,
  general,
  serviceError,  // Normal API/service errors
  critical,      // Critical errors that break the app flow
}

enum ErrorAction {
  showSnackbar,
  showErrorWidget,  // Show error in-place
  navigateToHome,   // Only for critical errors
  navigateToLogin,  // Only for auth errors
  showDialog,
}

class AppError {
  final String message;
  final ErrorType type;
  final ErrorAction action;
  final String? details;
  final Exception? exception;

  const AppError({
    required this.message,
    required this.type,
    required this.action,
    this.details,
    this.exception,
  });

  factory AppError.authentication(String message, {String? details}) {
    return AppError(
      message: message,
      type: ErrorType.authentication,
      action: ErrorAction.navigateToLogin,
      details: details,
    );
  }

  factory AppError.network(String message, {String? details}) {
    return AppError(
      message: message,
      type: ErrorType.network,
      action: ErrorAction.showSnackbar,
      details: details,
    );
  }

  factory AppError.critical(String message, {String? details, Exception? exception}) {
    return AppError(
      message: message,
      type: ErrorType.critical,
      action: ErrorAction.navigateToHome,
      details: details,
      exception: exception,
    );
  }

  factory AppError.service(String message, {String? details, Exception? exception}) {
    return AppError(
      message: message,
      type: ErrorType.serviceError,
      action: ErrorAction.showSnackbar,
      details: details,
      exception: exception,
    );
  }

  factory AppError.general(String message, {String? details}) {
    return AppError(
      message: message,
      type: ErrorType.general,
      action: ErrorAction.showSnackbar,
      details: details,
    );
  }

  factory AppError.fromException(Exception exception) {
    final String errorMessage = exception.toString();

    // Check for authentication errors
    if (errorMessage.contains('401') ||
        errorMessage.contains('Unauthorized') ||
        errorMessage.contains('token') ||
        errorMessage.contains('authentication')) {
      return AppError.authentication(
        'Your session has expired. Please log in again.',
        details: errorMessage,
      );
    }

    // Critical errors - these break the app flow and require navigation to home
    if (errorMessage.contains('Missing agent details') ||
        errorMessage.contains('Invalid route') ||
        errorMessage.contains('Invalid chat route') ||
        errorMessage.contains('Invalid edit agent route') ||
        errorMessage.contains('called without') ||  // Missing required arguments
        errorMessage.contains('No route')) {
      return AppError.critical(
        'The requested page could not be loaded. Returning to home.',
        details: errorMessage,
        exception: exception,
      );
    }

    // Service errors - API calls that failed but don't break the app
    if (errorMessage.contains('404') ||
        errorMessage.contains('500') ||
        errorMessage.contains('Failed to load') ||
        errorMessage.contains('Could not fetch') ||
        errorMessage.contains('API') ||
        errorMessage.contains('Service')) {
      return AppError.service(
        'Failed to load data. Please try again.',
        details: errorMessage,
        exception: exception,
      );
    }

    // Network errors - usually recoverable
    if (errorMessage.contains('network') ||
        errorMessage.contains('connection') ||
        errorMessage.contains('timeout') ||
        errorMessage.contains('SocketException')) {
      return AppError.network(
        'Network error. Please check your connection and try again.',
        details: errorMessage,
      );
    }

    // Default to service error for unknown exceptions
    return AppError.service(
      'An error occurred. Please try again.',
      details: errorMessage,
    );
  }
}

class ErrorHandlerService {
  static final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();
  static final GlobalKey<ScaffoldMessengerState> scaffoldMessengerKey = GlobalKey<ScaffoldMessengerState>();

  static void handleError(AppError error, {WidgetRef? ref}) {
    logger.e('[ErrorHandler] ${error.type.name}: ${error.message}');
    if (error.exception != null) {
      logger.e('Exception: ${error.exception}');
    }
    if (error.details != null) {
      logger.d('Details: ${error.details}');
    }

    switch (error.action) {
      case ErrorAction.navigateToLogin:
        _handleAuthError(error, ref);
        break;
      case ErrorAction.navigateToHome:
        _handleCriticalError(error);
        break;
      case ErrorAction.showSnackbar:
        _showErrorSnackbar(error.message);
        break;
      case ErrorAction.showDialog:
        _showErrorDialog(error);
        break;
      case ErrorAction.showErrorWidget:
        // For now, treat this the same as showSnackbar
        // In the future, this could trigger an error widget overlay
        _showErrorSnackbar(error.message);
        break;
    }
  }

  static void _handleAuthError(AppError error, WidgetRef? ref) {
    // Clear auth state if ref is available
    if (ref != null) {
      try {
        ref.read(authNotifierProvider.notifier).logout();
      } catch (e) {
        logger.w('[ErrorHandler] Could not logout via auth notifier: $e');
      }
    }

    // Navigate to login
    navigatorKey.currentState?.pushNamedAndRemoveUntil('/login', (route) => false);

    // Show error message
    _showErrorSnackbar(error.message);
  }

  static void _handleCriticalError(AppError error) {
    // Navigate to home
    navigatorKey.currentState?.pushNamedAndRemoveUntil('/home', (route) => false);

    // Show error message
    _showErrorSnackbar(error.message);
  }

  static void _showErrorSnackbar(String message) {
    scaffoldMessengerKey.currentState?.showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        duration: const Duration(seconds: 4),
        action: SnackBarAction(
          label: 'OK',
          textColor: Colors.white,
          onPressed: () {
            scaffoldMessengerKey.currentState?.hideCurrentSnackBar();
          },
        ),
      ),
    );
  }

  static void _showErrorDialog(AppError error) {
    final context = navigatorKey.currentContext;
    if (context != null) {
      showDialog(
        context: context,
        builder: (BuildContext context) {
          return AlertDialog(
            title: const Text('Error'),
            content: Text(error.message),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('OK'),
              ),
            ],
          );
        },
      );
    }
  }
}

// Provider for accessing error handler in widgets
final errorHandlerProvider = Provider<ErrorHandlerService>((ref) {
  return ErrorHandlerService();
});

// Extension to easily handle errors from exceptions
extension ExceptionErrorHandling on Exception {
  void handle({WidgetRef? ref}) {
    final error = AppError.fromException(this);
    ErrorHandlerService.handleError(error, ref: ref);
  }
}
