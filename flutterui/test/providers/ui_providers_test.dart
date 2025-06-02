import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/providers/ui_providers.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:mockito/mockito.dart';

class MockAuthNotifier extends AuthNotifier {
  AuthState _currentState = const AuthInitial();

  MockAuthNotifier() : super(MockAuthService());

  void setState(AuthState state) {
    _currentState = state;
  }

  @override
  AuthState get state => _currentState;
}

class MockAuthService implements AuthService {
  @override
  Future<String?> retrieveToken() async => null;

  @override
  Future<User> getCurrentUser() async => throw Exception('No user');

  @override
  Future<void> storeToken(String token) async {}

  @override
  Future<void> clearToken() async {}

  @override
  Future<void> launchLoginUrl() async {}

  @override
  Future<Map<String, String>> get authenticatedHeaders async => {
    'Authorization': 'Bearer mock-token',
    'Content-Type': 'application/json',
  };
}

class MockWidgetRef extends Mock implements WidgetRef {
  final ProviderContainer container;
  
  MockWidgetRef(this.container);
  
  @override
  T read<T>(ProviderListenable<T> provider) {
    return container.read(provider);
  }
}

class TestPageRoute extends PageRoute<void> {
  final String? routeName;

  TestPageRoute({required this.routeName}) : super(settings: RouteSettings(name: routeName));
  
  TestPageRoute.withNullName() : routeName = null, super(settings: const RouteSettings(name: null));

  @override
  Color get barrierColor => Colors.transparent;

  @override
  String? get barrierLabel => null;

  @override
  Widget buildPage(BuildContext context, Animation<double> animation, Animation<double> secondaryAnimation) {
    return Container();
  }

  @override
  bool get maintainState => true;

  @override
  Duration get transitionDuration => Duration.zero;
}

class TestPopupRoute extends PopupRoute<void> {
  @override
  Color get barrierColor => Colors.black54;

  @override
  bool get barrierDismissible => true;

  @override
  String get barrierLabel => 'Test Popup';

  @override
  Duration get transitionDuration => const Duration(milliseconds: 200);

  @override
  Widget buildPage(BuildContext context, Animation<double> animation, Animation<double> secondaryAnimation) {
    return Container();
  }

  @override
  Widget buildTransitions(BuildContext context, Animation<double> animation, Animation<double> secondaryAnimation, Widget child) {
    return child;
  }
}

void main() {
  group('UI Providers Tests', () {
    late ProviderContainer container;
    late MockAuthNotifier mockAuthNotifier;

    setUp(() {
      mockAuthNotifier = MockAuthNotifier();
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    group('showThreadBannerProvider', () {
      test('should start with false state', () {
        final showBanner = container.read(showThreadBannerProvider);
        expect(showBanner, isFalse);
      });

      test('should update banner visibility state', () {
        container.read(showThreadBannerProvider.notifier).state = true;
        
        final showBanner = container.read(showThreadBannerProvider);
        expect(showBanner, isTrue);
      });

      test('should toggle banner state correctly', () {
        container.read(showThreadBannerProvider.notifier).state = true;
        expect(container.read(showThreadBannerProvider), isTrue);

        container.read(showThreadBannerProvider.notifier).state = false;
        expect(container.read(showThreadBannerProvider), isFalse);
      });

      test('should handle multiple state changes', () {
        final states = [true, false, true, false, true];
        
        for (final state in states) {
          container.read(showThreadBannerProvider.notifier).state = state;
          expect(container.read(showThreadBannerProvider), equals(state));
        }
      });
    });

    group('RouteObserverForBanner', () {
      late RouteObserverForBanner routeObserver;
      late MockWidgetRef mockWidgetRef;

      setUp(() {
        mockWidgetRef = MockWidgetRef(container);
        routeObserver = RouteObserverForBanner(mockWidgetRef);
      });

      group('_updateBannerVisibility', () {
        test('should show banner for /home route', () {
          final route = TestPageRoute(routeName: '/home');
          
          routeObserver.didPush(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should show banner for root route when authenticated', () {
          final user = User(email: 'test@example.com', name: 'Test User');
          mockAuthNotifier.setState(Authenticated(user));
          
          final route = TestPageRoute(routeName: '/');
          
          routeObserver.didPush(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should not show banner for root route when unauthenticated', () {
          mockAuthNotifier.setState(const Unauthenticated());
          
          final route = TestPageRoute(routeName: '/');
          
          routeObserver.didPush(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isFalse);
        });

        test('should not show banner for other routes', () {
          final routes = ['/login', '/chat', '/agents', '/settings'];
          
          for (final routeName in routes) {
            final route = TestPageRoute(routeName: routeName);
            
            routeObserver.didPush(route, null);
            
            final showBanner = container.read(showThreadBannerProvider);
            expect(showBanner, isFalse, reason: 'Banner should not show for route: $routeName');
          }
        });

        test('should handle routes starting with /#/', () {
          final route = TestPageRoute(routeName: '/#/home');
          
          routeObserver.didPush(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should handle routes without leading slash', () {
          final route = TestPageRoute(routeName: 'home');
          
          routeObserver.didPush(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should handle null route name', () {
          final route = TestPageRoute.withNullName();
          
          routeObserver.didPush(route, null);
          
          final user = User(email: 'test@example.com', name: 'Test User');
          mockAuthNotifier.setState(Authenticated(user));
          
          routeObserver.didPush(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should handle complex URI parsing', () {
          final routes = [
            '/#/home?param=value',
            '/home#section',
            '/#/home?param1=value1&param2=value2',
          ];
          
          for (final routeName in routes) {
            final route = TestPageRoute(routeName: routeName);
            
            routeObserver.didPush(route, null);
            
            final showBanner = container.read(showThreadBannerProvider);
            expect(showBanner, isTrue, reason: 'Banner should show for route: $routeName');
          }
        });

        test('should handle malformed URIs gracefully', () {
          final malformedRoutes = [
            '://invalid-uri',
            'http://[invalid',
            '/%invalid%uri',
          ];
          
          for (final routeName in malformedRoutes) {
            final route = TestPageRoute(routeName: routeName);
            
            expect(() => routeObserver.didPush(route, null), returnsNormally);
            
            final showBanner = container.read(showThreadBannerProvider);
            expect(showBanner, isFalse);
          }
        });

        test('should only update state when value changes', () {
          int stateChanges = 0;
          container.listen<bool>(
            showThreadBannerProvider,
            (previous, next) => stateChanges++,
          );

          final homeRoute = TestPageRoute(routeName: '/home');
          
          routeObserver.didPush(homeRoute, null);
          expect(stateChanges, equals(1));
          
          routeObserver.didPush(homeRoute, null);
          expect(stateChanges, equals(1));
          
          final loginRoute = TestPageRoute(routeName: '/login');
          routeObserver.didPush(loginRoute, null);
          expect(stateChanges, equals(2));
        });
      });

      group('didPush', () {
        test('should update banner visibility for PageRoute', () {
          final route = TestPageRoute(routeName: '/home');
          
          routeObserver.didPush(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should not update banner for non-PageRoute', () {
          container.read(showThreadBannerProvider.notifier).state = true;
          
          final route = TestPopupRoute();
          routeObserver.didPush(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should handle push with previous route', () {
          final previousRoute = TestPageRoute(routeName: '/login');
          final newRoute = TestPageRoute(routeName: '/home');
          
          routeObserver.didPush(newRoute, previousRoute);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });
      });

      group('didPop', () {
        test('should update banner visibility when popping to PageRoute', () {
          final currentRoute = TestPageRoute(routeName: '/chat');
          final previousRoute = TestPageRoute(routeName: '/home');
          
          routeObserver.didPop(currentRoute, previousRoute);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should hide banner when popping to null route', () {
          container.read(showThreadBannerProvider.notifier).state = true;
          
          final route = TestPageRoute(routeName: '/home');
          routeObserver.didPop(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isFalse);
        });

        test('should hide banner when popping to non-PageRoute', () {
          container.read(showThreadBannerProvider.notifier).state = true;
          
          final currentRoute = TestPageRoute(routeName: '/home');
          final previousRoute = TestPopupRoute();
          
          routeObserver.didPop(currentRoute, previousRoute);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isFalse);
        });

        test('should not change banner when already false', () {
          container.read(showThreadBannerProvider.notifier).state = false;
          
          final route = TestPageRoute(routeName: '/home');
          routeObserver.didPop(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isFalse);
        });
      });

      group('didReplace', () {
        test('should update banner visibility for new PageRoute', () {
          final oldRoute = TestPageRoute(routeName: '/login');
          final newRoute = TestPageRoute(routeName: '/home');
          
          routeObserver.didReplace(newRoute: newRoute, oldRoute: oldRoute);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should not update banner for non-PageRoute replacement', () {
          container.read(showThreadBannerProvider.notifier).state = true;
          
          final oldRoute = TestPageRoute(routeName: '/home');
          final newRoute = TestPopupRoute();
          
          routeObserver.didReplace(newRoute: newRoute, oldRoute: oldRoute);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should handle replacement with null routes', () {
          expect(() => routeObserver.didReplace(newRoute: null, oldRoute: null), returnsNormally);
        });
      });

      group('Navigation Scenarios', () {
        test('should handle complete navigation flow', () {
          mockAuthNotifier.setState(const Unauthenticated());
          
          final loginRoute = TestPageRoute(routeName: '/login');
          routeObserver.didPush(loginRoute, null);
          expect(container.read(showThreadBannerProvider), isFalse);
          
          final user = User(email: 'test@example.com', name: 'Test User');
          mockAuthNotifier.setState(Authenticated(user));
          
          final homeRoute = TestPageRoute(routeName: '/home');
          routeObserver.didReplace(newRoute: homeRoute, oldRoute: loginRoute);
          expect(container.read(showThreadBannerProvider), isTrue);
          
          final chatRoute = TestPageRoute(routeName: '/chat');
          routeObserver.didPush(chatRoute, homeRoute);
          expect(container.read(showThreadBannerProvider), isFalse);
          
          routeObserver.didPop(chatRoute, homeRoute);
          expect(container.read(showThreadBannerProvider), isTrue);
        });

        test('should handle authentication state changes during navigation', () {
          final rootRoute = TestPageRoute(routeName: '/');
          
          mockAuthNotifier.setState(const Unauthenticated());
          routeObserver.didPush(rootRoute, null);
          expect(container.read(showThreadBannerProvider), isFalse);
          
          final user = User(email: 'test@example.com', name: 'Test User');
          mockAuthNotifier.setState(Authenticated(user));
          routeObserver.didPush(rootRoute, null);
          expect(container.read(showThreadBannerProvider), isTrue);
          
          mockAuthNotifier.setState(const Unauthenticated());
          routeObserver.didPush(rootRoute, null);
          expect(container.read(showThreadBannerProvider), isFalse);
        });

        test('should handle rapid navigation changes', () {
          final routes = [
            '/home',
            '/chat',
            '/agents',
            '/home',
            '/settings',
            '/home',
          ];
          
          for (int i = 0; i < routes.length; i++) {
            final route = TestPageRoute(routeName: routes[i]);
            final previousRoute = i > 0 ? TestPageRoute(routeName: routes[i - 1]) : null;
            
            routeObserver.didPush(route, previousRoute);
            
            final expectedBanner = routes[i] == '/home';
            expect(container.read(showThreadBannerProvider), equals(expectedBanner));
          }
        });

        test('should handle special characters in route names', () {
          final specialRoutes = [
            '/home?param=value&other=test',
            '/#/home#section',
            '/home%20with%20spaces',
            '/home-with-dashes',
            '/home_with_underscores',
          ];
          
          for (final routeName in specialRoutes) {
            final route = TestPageRoute(routeName: routeName);
            
            routeObserver.didPush(route, null);
            
            final showBanner = container.read(showThreadBannerProvider);
            expect(showBanner, isTrue, reason: 'Banner should show for route: $routeName');
          }
        });

        test('should handle empty and whitespace route names', () {
          final emptyRoutes = ['', ' ', '\t', '\n'];
          
          for (final routeName in emptyRoutes) {
            final route = TestPageRoute(routeName: routeName);
            
            final user = User(email: 'test@example.com', name: 'Test User');
            mockAuthNotifier.setState(Authenticated(user));
            
            routeObserver.didPush(route, null);
            
            final showBanner = container.read(showThreadBannerProvider);
            expect(showBanner, isTrue, reason: 'Banner should show for authenticated user on empty route: "$routeName"');
          }
        });
      });

      group('Error Handling', () {
        test('should handle NavigatorObserver method calls gracefully', () {
          final route = TestPageRoute(routeName: '/home');
          
          expect(() => routeObserver.didPush(route, null), returnsNormally);
          expect(() => routeObserver.didPop(route, null), returnsNormally);
          expect(() => routeObserver.didReplace(newRoute: route, oldRoute: null), returnsNormally);
        });

        test('should handle multiple observers on same route', () {
          final mockRef1 = MockWidgetRef(container);
          final mockRef2 = MockWidgetRef(container);
          final observer1 = RouteObserverForBanner(mockRef1);
          final observer2 = RouteObserverForBanner(mockRef2);
          
          final route = TestPageRoute(routeName: '/home');
          
          observer1.didPush(route, null);
          observer2.didPush(route, null);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isTrue);
        });

        test('should handle auth state errors gracefully', () {
          mockAuthNotifier.setState(const AuthError('Test error'));
          
          final route = TestPageRoute(routeName: '/');
          
          expect(() => routeObserver.didPush(route, null), returnsNormally);
          
          final showBanner = container.read(showThreadBannerProvider);
          expect(showBanner, isFalse);
        });
      });

      group('State Consistency', () {
        test('should maintain state consistency across operations', () {
          final initialState = container.read(showThreadBannerProvider);
          expect(initialState, isFalse);
          
          final homeRoute = TestPageRoute(routeName: '/home');
          routeObserver.didPush(homeRoute, null);
          expect(container.read(showThreadBannerProvider), isTrue);
          
          final chatRoute = TestPageRoute(routeName: '/chat');
          routeObserver.didPush(chatRoute, homeRoute);
          expect(container.read(showThreadBannerProvider), isFalse);
          
          routeObserver.didPop(chatRoute, homeRoute);
          expect(container.read(showThreadBannerProvider), isTrue);
          
          routeObserver.didPop(homeRoute, null);
          expect(container.read(showThreadBannerProvider), isFalse);
        });

        test('should handle provider disposal gracefully', () {
          final route = TestPageRoute(routeName: '/home');
          
          routeObserver.didPush(route, null);
          expect(container.read(showThreadBannerProvider), isTrue);
          
          container.dispose();
          
          expect(() => routeObserver.didPush(route, null), returnsNormally);
        });
      });
    });
  });
}