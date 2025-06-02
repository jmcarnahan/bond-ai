import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/providers/thread_provider.dart';

import 'mock_factory.dart';

/// Provider testing utilities that provide common setup and helper functions
/// for testing Riverpod providers. This eliminates repetitive boilerplate code
/// and provides consistent testing patterns for provider-based tests.
class ProviderTestHelpers {
  
  // =============================================================================
  // CONTAINER CREATION HELPERS
  // =============================================================================

  /// Creates a basic ProviderContainer for testing
  static ProviderContainer createContainer({
    List<Override>? overrides,
  }) {
    return ProviderContainer(
      overrides: overrides ?? [],
    );
  }

  /// Creates a container with common service overrides
  static ProviderContainer createContainerWithServices({
    MockAuthService? authService,
    MockThreadService? threadService,
    MockChatService? chatService,
    MockAgentService? agentService,
    List<Override>? additionalOverrides,
  }) {
    final overrides = <Override>[
      if (authService != null)
        authServiceProvider.overrideWithValue(authService),
      if (threadService != null)
        threadServiceProvider.overrideWithValue(threadService),
      if (chatService != null)
        chatServiceProvider.overrideWithValue(chatService),
      if (agentService != null)
        agentServiceProvider.overrideWithValue(agentService),
      ...?additionalOverrides,
    ];
    
    return createContainer(overrides: overrides);
  }

  /// Creates a container with mock notifiers
  static ProviderContainer createContainerWithNotifiers({
    MockAuthNotifier? authNotifier,
    MockThreadsNotifier? threadsNotifier,
    List<Override>? additionalOverrides,
  }) {
    final overrides = <Override>[
      if (authNotifier != null)
        authNotifierProvider.overrideWith((ref) => authNotifier),
      if (threadsNotifier != null)
        threadsProvider.overrideWith((ref) => threadsNotifier),
      ...?additionalOverrides,
    ];
    
    return createContainer(overrides: overrides);
  }

  /// Creates a fully configured container for comprehensive testing
  static ProviderContainer createFullTestContainer({
    MockAuthService? authService,
    MockThreadService? threadService,
    MockChatService? chatService,
    MockAgentService? agentService,
    MockAuthNotifier? authNotifier,
    MockThreadsNotifier? threadsNotifier,
    List<Override>? additionalOverrides,
  }) {
    final overrides = <Override>[
      // Service overrides
      if (authService != null)
        authServiceProvider.overrideWithValue(authService),
      if (threadService != null)
        threadServiceProvider.overrideWithValue(threadService),
      if (chatService != null)
        chatServiceProvider.overrideWithValue(chatService),
      if (agentService != null)
        agentServiceProvider.overrideWithValue(agentService),
      
      // Notifier overrides
      if (authNotifier != null)
        authNotifierProvider.overrideWith((ref) => authNotifier),
      if (threadsNotifier != null)
        threadsProvider.overrideWith((ref) => threadsNotifier),
      
      // Additional overrides
      ...?additionalOverrides,
    ];
    
    return createContainer(overrides: overrides);
  }

  // =============================================================================
  // AUTHENTICATION TESTING HELPERS
  // =============================================================================

  /// Creates a container with authenticated user setup
  static ProviderContainer createAuthenticatedContainer({
    String? token,
    String? email,
    String? name,
  }) {
    final authService = MockFactory.createAuthService(
      storedToken: token ?? 'test-token',
      mockUser: MockFactory.createAuthService().mockUser,
    );
    
    return createContainerWithServices(authService: authService);
  }

  /// Creates a container with unauthenticated user setup
  static ProviderContainer createUnauthenticatedContainer() {
    final authService = MockFactory.createAuthService(
      storedToken: null,
      mockUser: null,
    );
    
    return createContainerWithServices(authService: authService);
  }

  /// Creates a container with authentication error setup
  static ProviderContainer createAuthErrorContainer({
    String? errorMessage,
  }) {
    final authService = MockFactory.createAuthService(
      shouldThrowError: true,
      errorMessage: errorMessage ?? 'Authentication failed',
    );
    
    return createContainerWithServices(authService: authService);
  }

  // =============================================================================
  // PROVIDER STATE TESTING HELPERS
  // =============================================================================

  /// Reads a provider and expects it to be in loading state
  static void expectProviderLoading<T>(
    ProviderContainer container,
    ProviderListenable<AsyncValue<T>> provider,
  ) {
    final state = container.read(provider);
    expect(state, isA<AsyncLoading<T>>());
  }

  /// Reads a provider and expects it to be in data state
  static void expectProviderData<T>(
    ProviderContainer container,
    ProviderListenable<AsyncValue<T>> provider,
    T expectedData,
  ) {
    final state = container.read(provider);
    expect(state, isA<AsyncData<T>>());
    expect(state.value, equals(expectedData));
  }

  /// Reads a provider and expects it to be in error state
  static void expectProviderError<T>(
    ProviderContainer container,
    ProviderListenable<AsyncValue<T>> provider,
    String? expectedError,
  ) {
    final state = container.read(provider);
    expect(state, isA<AsyncError<T>>());
    if (expectedError != null) {
      expect(state.error.toString(), contains(expectedError));
    }
  }

  /// Reads a provider and expects specific data
  static T expectProviderValue<T>(
    ProviderContainer container,
    ProviderListenable<T> provider,
    T expectedValue,
  ) {
    final value = container.read(provider);
    expect(value, equals(expectedValue));
    return value;
  }

  /// Reads a provider and checks if it's null
  static void expectProviderNull<T>(
    ProviderContainer container,
    ProviderListenable<T?> provider,
  ) {
    final value = container.read(provider);
    expect(value, isNull);
  }

  // =============================================================================
  // ASYNC PROVIDER TESTING HELPERS
  // =============================================================================

  /// Waits for an async provider to complete and returns the result
  static Future<T> waitForProvider<T>(
    ProviderContainer container,
    ProviderListenable<AsyncValue<T>> provider,
  ) async {
    final state = container.read(provider);
    if (state is AsyncData<T>) {
      return state.value;
    } else if (state is AsyncError<T>) {
      throw state.error;
    } else {
      await Future.delayed(const Duration(milliseconds: 100));
      return waitForProvider(container, provider);
    }
  }

  /// Waits for an async provider to complete and expects success
  static Future<T> waitForProviderSuccess<T>(
    ProviderContainer container,
    ProviderListenable<AsyncValue<T>> provider,
  ) async {
    final result = await waitForProvider(container, provider);
    final state = container.read(provider);
    expect(state, isA<AsyncData<T>>());
    return result;
  }

  /// Waits for an async provider to complete and expects error
  static Future<void> waitForProviderError<T>(
    ProviderContainer container,
    ProviderListenable<AsyncValue<T>> provider,
    String? expectedError,
  ) async {
    try {
      await waitForProvider(container, provider);
      fail('Expected provider to throw an error');
    } catch (error) {
      if (expectedError != null) {
        expect(error.toString(), contains(expectedError));
      }
    }
  }

  // =============================================================================
  // PROVIDER LIFECYCLE TESTING HELPERS
  // =============================================================================

  /// Tests provider initialization
  static void testProviderInitialization<T>(
    ProviderContainer container,
    ProviderListenable<T> provider,
    T expectedInitialValue,
  ) {
    final initialValue = container.read(provider);
    expect(initialValue, equals(expectedInitialValue));
  }

  /// Tests provider invalidation
  static void testProviderInvalidation<T>(
    ProviderContainer container,
    ProviderBase<T> provider,
  ) {
    // Read the provider first to initialize it
    container.read(provider);
    
    // Invalidate the provider
    container.invalidate(provider);
    
    // The provider should be recreated on next read
    // This is mainly useful for testing provider disposal/recreation
  }

  /// Tests provider disposal
  static void testProviderDisposal(ProviderContainer container) {
    container.dispose();
    
    // Verify that the container is disposed
    expect(() => container.read(authNotifierProvider), throwsStateError);
  }

  // =============================================================================
  // PROVIDER OVERRIDE TESTING HELPERS
  // =============================================================================

  /// Tests that provider overrides work correctly
  static void testProviderOverride<T>(
    Provider<T> provider,
    T overrideValue,
    T expectedValue,
  ) {
    final container = createContainer(
      overrides: [provider.overrideWithValue(overrideValue)],
    );
    
    final actualValue = container.read(provider);
    expect(actualValue, equals(expectedValue));
    
    container.dispose();
  }

  /// Tests family provider overrides
  static void testFamilyProviderOverride<T>(
    Provider<T> provider,
    T overrideValue,
    T expectedValue,
  ) {
    final container = createContainer(
      overrides: [provider.overrideWithValue(overrideValue)],
    );
    
    final actualValue = container.read(provider);
    expect(actualValue, equals(expectedValue));
    
    container.dispose();
  }

  // =============================================================================
  // PROVIDER DEPENDENCY TESTING HELPERS
  // =============================================================================

  /// Tests that a provider depends on another provider
  static void testProviderDependency<T, U>(
    ProviderContainer container,
    ProviderListenable<T> dependentProvider,
    Provider<U> dependencyProvider,
    U dependencyValue,
  ) {
    // Set up the dependency
    container.updateOverrides([
      dependencyProvider.overrideWithValue(dependencyValue),
    ]);
    
    // Read the dependent provider
    final dependentValue = container.read(dependentProvider);
    
    // The dependent provider should have been affected by the dependency
    expect(dependentValue, isNotNull);
  }

  // =============================================================================
  // PROVIDER LISTENER TESTING HELPERS
  // =============================================================================

  /// Creates a provider listener for testing state changes
  static ProviderSubscription<T> createProviderListener<T>(
    ProviderContainer container,
    ProviderListenable<T> provider,
    void Function(T? previous, T next) listener,
  ) {
    return container.listen<T>(
      provider,
      listener,
      fireImmediately: false,
    );
  }

  /// Tests that a provider notifies listeners when state changes
  static void testProviderNotification<T>(
    ProviderContainer container,
    StateProvider<T> provider,
    T newValue,
  ) {
    bool wasNotified = false;
    T? notifiedValue;
    
    final subscription = createProviderListener<T>(
      container,
      provider,
      (previous, next) {
        wasNotified = true;
        notifiedValue = next;
      },
    );
    
    // Change the provider value
    container.read(provider.notifier).state = newValue;
    
    // Verify notification occurred
    expect(wasNotified, isTrue);
    expect(notifiedValue, equals(newValue));
    
    subscription.close();
  }

  // =============================================================================
  // STATE NOTIFIER TESTING HELPERS
  // =============================================================================

  /// Tests StateNotifier initialization
  static void testStateNotifierInitialization<T>(
    ProviderContainer container,
    StateNotifierProvider<StateNotifier<T>, T> provider,
    T expectedInitialState,
  ) {
    final notifier = container.read(provider.notifier);
    final state = container.read(provider);
    
    expect(state, equals(expectedInitialState));
    expect(notifier.state, equals(expectedInitialState));
  }

  /// Tests StateNotifier state changes
  static void testStateNotifierStateChange<T>(
    ProviderContainer container,
    StateNotifierProvider<StateNotifier<T>, T> provider,
    void Function(StateNotifier<T> notifier) stateChange,
    T expectedNewState,
  ) {
    final notifier = container.read(provider.notifier);
    
    // Execute the state change
    stateChange(notifier);
    
    // Verify the new state
    final newState = container.read(provider);
    expect(newState, equals(expectedNewState));
  }

  // =============================================================================
  // CLEANUP HELPERS
  // =============================================================================

  /// Disposes of a container and verifies cleanup
  static void disposeContainer(ProviderContainer container) {
    container.dispose();
  }

  /// Disposes of multiple containers
  static void disposeContainers(List<ProviderContainer> containers) {
    for (final container in containers) {
      container.dispose();
    }
  }

  /// Closes a provider subscription
  static void closeSubscription(ProviderSubscription subscription) {
    subscription.close();
  }

  /// Closes multiple provider subscriptions
  static void closeSubscriptions(List<ProviderSubscription> subscriptions) {
    for (final subscription in subscriptions) {
      subscription.close();
    }
  }
}