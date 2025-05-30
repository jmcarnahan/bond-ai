import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/utils/logger.dart';

@immutable
class AppError {
  final String message;
  final String? code;
  final dynamic originalError;
  final StackTrace? stackTrace;

  const AppError({
    required this.message,
    this.code,
    this.originalError,
    this.stackTrace,
  });

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AppError &&
        other.message == message &&
        other.code == code &&
        other.originalError == originalError &&
        other.stackTrace == stackTrace;
  }

  @override
  int get hashCode {
    return Object.hash(message, code, originalError, stackTrace);
  }

  @override
  String toString() {
    return 'AppError(message: $message, code: $code)';
  }
}

mixin ErrorHandlerMixin<T> on StateNotifier<T> {
  void handleError(dynamic error, StackTrace? stackTrace) {
    final appError = _convertToAppError(error, stackTrace);
    logger.e('[$runtimeType] Error: ${appError.message}', 
        error: appError.originalError, 
        stackTrace: appError.stackTrace);
    handleAppError(appError);
  }

  void handleAppError(AppError error);

  AppError _convertToAppError(dynamic error, StackTrace? stackTrace) {
    if (error is AppError) {
      return error;
    }
    
    if (error is Exception) {
      return AppError(
        message: error.toString().replaceFirst('Exception: ', ''),
        originalError: error,
        stackTrace: stackTrace,
      );
    }

    return AppError(
      message: error?.toString() ?? 'Unknown error occurred',
      originalError: error,
      stackTrace: stackTrace,
    );
  }
}

extension ErrorUtils on Object {
  AppError toAppError([StackTrace? stackTrace]) {
    if (this is AppError) {
      return this as AppError;
    }
    
    if (this is Exception) {
      return AppError(
        message: toString().replaceFirst('Exception: ', ''),
        originalError: this,
        stackTrace: stackTrace,
      );
    }

    return AppError(
      message: toString(),
      originalError: this,
      stackTrace: stackTrace,
    );
  }
}