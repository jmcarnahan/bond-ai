import 'package:flutter/foundation.dart';

@immutable
class AsyncState<T> {
  final T? data;
  final bool isLoading;
  final String? error;
  final DateTime? lastUpdated;

  const AsyncState({
    this.data,
    this.isLoading = false,
    this.error,
    this.lastUpdated,
  });

  AsyncState<T> copyWith({
    T? data,
    bool? isLoading,
    String? error,
    DateTime? lastUpdated,
    bool clearError = false,
  }) {
    return AsyncState<T>(
      data: data ?? this.data,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }

  bool get hasData => data != null;
  bool get hasError => error != null;
  bool get isIdle => !isLoading && !hasError;
  bool get isSuccess => hasData && !isLoading && !hasError;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AsyncState<T> &&
        other.data == data &&
        other.isLoading == isLoading &&
        other.error == error &&
        other.lastUpdated == lastUpdated;
  }

  @override
  int get hashCode {
    return Object.hash(data, isLoading, error, lastUpdated);
  }

  @override
  String toString() {
    return 'AsyncState<$T>(data: $data, isLoading: $isLoading, error: $error, lastUpdated: $lastUpdated)';
  }
}

extension AsyncStateExtensions<T> on AsyncState<T> {
  AsyncState<T> toLoading() => copyWith(isLoading: true, clearError: true);

  AsyncState<T> toSuccess(T data) => copyWith(
    data: data,
    isLoading: false,
    clearError: true,
    lastUpdated: DateTime.now(),
  );

  AsyncState<T> toError(String error) => copyWith(
    isLoading: false,
    error: error,
  );

  AsyncState<T> clearError() => copyWith(clearError: true);
}
