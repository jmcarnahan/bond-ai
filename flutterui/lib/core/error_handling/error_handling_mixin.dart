import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/error_handling/error_handler.dart';

/// Mixin to provide error handling capabilities to widgets
mixin ErrorHandlingMixin {
  /// Handle a service error (non-critical)
  void handleServiceError(dynamic error, WidgetRef ref, {String? customMessage}) {
    final appError = error is AppError
        ? error
        : error is Exception
            ? AppError.service(
                customMessage ?? 'Failed to load data. Please try again.',
                exception: error,
              )
            : AppError.service(
                customMessage ?? 'An error occurred. Please try again.',
                details: error.toString(),
              );

    ErrorHandlerService.handleError(appError, ref: ref);
  }

  /// Handle a critical error (requires navigation)
  void handleCriticalError(dynamic error, WidgetRef ref, {String? customMessage}) {
    final appError = error is AppError
        ? error
        : error is Exception
            ? AppError.critical(
                customMessage ?? 'A critical error occurred. Returning to home.',
                exception: error,
              )
            : AppError.critical(
                customMessage ?? 'A critical error occurred. Returning to home.',
                details: error.toString(),
              );

    ErrorHandlerService.handleError(appError, ref: ref);
  }

  /// Handle an authentication error
  void handleAuthError(dynamic error, WidgetRef ref) {
    final appError = error is AppError
        ? error
        : AppError.authentication(
            'Your session has expired. Please log in again.',
            details: error.toString(),
          );

    ErrorHandlerService.handleError(appError, ref: ref);
  }

  /// Automatically detect error type and handle appropriately
  void handleAutoError(dynamic error, WidgetRef ref, {String? serviceErrorMessage}) {
    // Convert to AppError using the factory method that detects error types
    final appError = error is AppError
        ? error
        : error is Exception
            ? AppError.fromException(error)
            : AppError.general(
                serviceErrorMessage ?? 'An error occurred. Please try again.',
                details: error.toString(),
              );

    // If it's a service error and we have a custom message, update it
    if (appError.type == ErrorType.serviceError && serviceErrorMessage != null) {
      final updatedError = AppError(
        message: serviceErrorMessage,
        type: appError.type,
        action: appError.action,
        details: appError.details,
        exception: appError.exception,
      );
      ErrorHandlerService.handleError(updatedError, ref: ref);
    } else {
      ErrorHandlerService.handleError(appError, ref: ref);
    }
  }

  /// Wrap an async operation with error handling
  Future<T?> withErrorHandling<T>({
    required Future<T> Function() operation,
    required WidgetRef ref,
    String? errorMessage,
    bool isCritical = false,
  }) async {
    try {
      return await operation();
    } catch (error) {
      if (isCritical) {
        handleCriticalError(error, ref, customMessage: errorMessage);
      } else {
        handleServiceError(error, ref, customMessage: errorMessage);
      }
      return null;
    }
  }
}

/// Widget wrapper for error boundaries
class ErrorBoundary extends ConsumerWidget {
  final Widget child;
  final String? fallbackMessage;

  const ErrorBoundary({
    super.key,
    required this.child,
    this.fallbackMessage,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _ErrorBoundaryWidget(
      fallbackMessage: fallbackMessage,
      ref: ref,
      child: child,
    );
  }
}

class _ErrorBoundaryWidget extends StatefulWidget {
  final Widget child;
  final String? fallbackMessage;
  final WidgetRef ref;

  const _ErrorBoundaryWidget({
    required this.child,
    this.fallbackMessage,
    required this.ref,
  });

  @override
  State<_ErrorBoundaryWidget> createState() => _ErrorBoundaryWidgetState();
}

class _ErrorBoundaryWidgetState extends State<_ErrorBoundaryWidget> {
  bool hasError = false;

  @override
  Widget build(BuildContext context) {
    if (hasError) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: Colors.red,
            ),
            const SizedBox(height: 16),
            Text(
              widget.fallbackMessage ?? 'Something went wrong',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                setState(() {
                  hasError = false;
                });
              },
              child: const Text('Try Again'),
            ),
          ],
        ),
      );
    }

    return widget.child;
  }
}
