import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutterui/firebase_options.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/presentation/screens/auth/login_screen.dart';
import 'package:flutterui/presentation/screens/auth/auth_callback_screen.dart';
import 'package:flutterui/presentation/screens/chat/chat_screen.dart';
import 'package:flutterui/presentation/screens/threads/threads_screen.dart';
import 'package:flutterui/presentation/screens/profile/profile_screen.dart';
import 'package:flutterui/core/constants/mobile_api_config.dart';
import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/core/utils/logger.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
//import 'package:web/web.dart' as web if (dart.library.io) 'dart:io';
import 'package:flutterui/presentation/widgets/firestore_listener.dart';
import 'package:flutterui/presentation/widgets/message_notification_banner.dart';
import 'package:flutterui/providers/notification_provider.dart';
import 'package:flutterui/providers/config_provider.dart';
import 'package:flutterui/presentation/screens/agents/agents_screen.dart';
import 'package:flutterui/presentation/screens/agents/create_agent_screen.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/data/models/agent_model.dart';

// Provider to control the bottom navigation index
final navigationIndexProvider = StateProvider<int>((ref) {
  final navItems = ref.watch(bottomNavItemsProvider);
  final isAgentsEnabled = ref.watch(isAgentsEnabledProvider);

  // Default to chat screen if agents are enabled (index 1), otherwise chat is at index 0
  if (isAgentsEnabled && navItems.length > 1) {
    final chatIndex = navItems.indexWhere((item) => item.label == 'Chat');
    return chatIndex != -1 ? chatIndex : 0;
  }
  return 0;
});

// Provider to track if user is manually navigating
final isUserNavigatingProvider = StateProvider<bool>((ref) => false);

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Load environment variables
  await dotenv.load(fileName: ".env");

  // Override API base URL from environment
  final apiBaseUrl = dotenv.env['API_BASE_URL'];
  if (apiBaseUrl != null && apiBaseUrl.isNotEmpty) {
    ApiConstants.baseUrl = apiBaseUrl;
  }

  // Initialize Firebase
  try {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
    logger.i('[MobileApp] Firebase initialized successfully');
  } catch (e) {
    logger.e('[MobileApp] Error initializing Firebase: $e');
  }

  // Initialize SharedPreferences
  final sharedPreferences = await SharedPreferences.getInstance();

  runApp(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(sharedPreferences),
      ],
      child: const MobileApp(),
    ),
  );
}

class MobileApp extends ConsumerWidget {
  const MobileApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appTheme = ref.watch(appThemeProvider);

    // Determine initial route based on current URL
    String initialRoute = '/';
    if (kIsWeb) {
      final currentUrl = Uri.parse(web.window.location.href);
      logger.i('[MobileApp] Current URL on startup: $currentUrl');

      // Check if we're on the auth callback page
      if (currentUrl.path.endsWith('/auth-callback') ||
          currentUrl.queryParameters.containsKey('token')) {
        initialRoute = '/auth-callback';
        logger.i('[MobileApp] Starting with auth-callback route');
      }
    }

    return MaterialApp(
      title: 'Bond AI Mobile',
      debugShowCheckedModeBanner: false,
      theme: appTheme.themeData,
      initialRoute: initialRoute,
      onGenerateRoute: (settings) {
        logger.i('[MobileApp] Route requested: ${settings.name}');
        logger.i('[MobileApp] Route arguments: ${settings.arguments}');

        // Handle auth callback route
        if (settings.name == '/auth-callback') {
          logger.i('[MobileApp] Navigating to AuthCallbackScreen');
          return MaterialPageRoute(
            builder: (context) => const AuthCallbackScreen(),
            settings: settings,
          );
        }

        // Handle profile route by switching to profile tab
        if (settings.name == ProfileScreen.routeName) {
          logger.i(
            '[MobileApp] Profile route requested, switching to profile tab',
          );
          return MaterialPageRoute(
            builder:
                (context) => Consumer(
                  builder: (context, ref, _) {
                    // Find profile tab index
                    final navItems = ref.read(bottomNavItemsProvider);
                    final profileIndex = navItems.indexWhere(
                      (item) => item.label == 'Profile',
                    );
                    if (profileIndex != -1) {
                      WidgetsBinding.instance.addPostFrameCallback((_) {
                        ref.read(navigationIndexProvider.notifier).state =
                            profileIndex;
                      });
                    }
                    return const MobileAuthWrapper();
                  },
                ),
            settings: settings,
          );
        }

        // Handle create/edit agent routes
        if (settings.name?.startsWith('/edit-agent/') == true) {
          final agentId = settings.name!.replaceFirst('/edit-agent/', '');
          logger.i('[MobileApp] Edit agent route requested for: $agentId');
          return MaterialPageRoute(
            builder: (context) => CreateAgentScreen(agentId: agentId),
            settings: settings,
          );
        }

        // Handle chat with agent routes
        if (settings.name?.startsWith('/chat/') == true) {
          final agentId = settings.name!.replaceFirst('/chat/', '');
          logger.i('[MobileApp] Chat with agent route requested for: $agentId');

          // Get the agent data from arguments
          final agent = settings.arguments as AgentListItemModel?;

          return MaterialPageRoute(
            builder:
                (context) => Consumer(
                  builder: (context, ref, _) {
                    // Set the selected agent if provided
                    if (agent != null) {
                      WidgetsBinding.instance.addPostFrameCallback((_) {
                        ref
                            .read(selectedAgentProvider.notifier)
                            .selectAgent(agent);
                      });
                    }

                    // Navigate to the chat tab
                    final navItems = ref.read(bottomNavItemsProvider);
                    final chatIndex = navItems.indexWhere(
                      (item) => item.label == 'Chat',
                    );
                    if (chatIndex != -1) {
                      WidgetsBinding.instance.addPostFrameCallback((_) {
                        ref.read(navigationIndexProvider.notifier).state =
                            chatIndex;
                      });
                    }
                    return const MobileAuthWrapper();
                  },
                ),
            settings: settings,
          );
        }

        // Default route
        logger.i('[MobileApp] Navigating to MobileAuthWrapper (default)');
        return MaterialPageRoute(
          builder: (context) => const MobileAuthWrapper(),
          settings: settings,
        );
      },
    );
  }
}

class MobileAuthWrapper extends ConsumerWidget {
  const MobileAuthWrapper({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authNotifierProvider);

    // Log state changes
    // logger.d('[MobileAuthWrapper] Current auth state: ${authState.runtimeType}');
    if (authState is Authenticated) {
      // logger.d('[MobileAuthWrapper] User authenticated: ${authState.user.email}');
    } else if (authState is Unauthenticated) {
      // logger.d('[MobileAuthWrapper] User unauthenticated: ${authState.message}');
    } else if (authState is AuthError) {
      logger.e('[MobileAuthWrapper] Auth error: ${authState.error}');
    }

    if (authState is AuthInitial || authState is AuthLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    } else if (authState is Authenticated) {
      return const MobileNavigationShell();
    } else if (authState is AuthError) {
      return Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('Error: ${authState.error}'),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  ref.read(authNotifierProvider.notifier).initiateLogin();
                },
                child: const Text('Try Again'),
              ),
            ],
          ),
        ),
      );
    } else {
      // Unauthenticated
      return const LoginScreen();
    }
  }
}

class MobileNavigationShell extends ConsumerStatefulWidget {
  const MobileNavigationShell({super.key});

  @override
  ConsumerState<MobileNavigationShell> createState() =>
      _MobileNavigationShellState();
}

class _MobileNavigationShellState extends ConsumerState<MobileNavigationShell> {
  late PageController _pageController;

  @override
  void initState() {
    super.initState();
    final navItems = ref.read(bottomNavItemsProvider);
    final isAgentsEnabled = ref.read(isAgentsEnabledProvider);

    // Default to chat screen if agents are enabled (index 1), otherwise chat is at index 0
    int initialIndex = 0;
    if (isAgentsEnabled && navItems.length > 1) {
      // Find chat index (should be 1 when agents are enabled)
      final chatIndex = navItems.indexWhere((item) => item.label == 'Chat');
      if (chatIndex != -1) {
        initialIndex = chatIndex;
      }
    }

    _pageController = PageController(initialPage: initialIndex);

    // Set the navigation index after the first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        ref.read(navigationIndexProvider.notifier).state = initialIndex;
      }
    });
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final selectedThread = ref.watch(selectedThreadProvider);
    final currentIndex = ref.watch(navigationIndexProvider);
    final navItems = ref.watch(bottomNavItemsProvider);
    final selectedAgent = ref.watch(selectedAgentProvider);

    // Listen for navigation index changes to update PageView
    ref.listen<int>(navigationIndexProvider, (previous, next) {
      if (_pageController.hasClients && previous != next) {
        _pageController.jumpToPage(next);
      }
    });

    // Listen for thread selection changes
    ref.listen<Thread?>(selectedThreadProvider, (previous, next) {
      final isUserNavigating = ref.read(isUserNavigatingProvider);

      // Don't auto-navigate if user is manually navigating
      if (isUserNavigating) {
        return;
      }

      // Navigate to chat when a thread is selected from the threads tab
      if (next != null && previous?.id != next.id) {
        // Find the chat tab index (it might be 0 or 1 depending on agents)
        final chatIndex = navItems.indexWhere((item) => item.label == 'Chat');
        if (chatIndex != -1 && currentIndex != chatIndex) {
          ref.read(navigationIndexProvider.notifier).state = chatIndex;
        }
      }
    });

    final List<Widget> pages = [];

    // Build pages based on navigation items
    for (final item in navItems) {
      switch (item.label) {
        case 'Agents':
          pages.add(const AgentsScreen());
          break;
        case 'Chat':
          pages.add(
            ChatScreen(
              agentId: selectedAgent?.id ?? MobileApiConfig.defaultAgentId,
              agentName:
                  selectedAgent?.name ?? MobileApiConfig.defaultAgentName,
              initialThreadId: selectedThread?.id,
            ),
          );
          break;
        case 'Threads':
          pages.add(const ThreadsScreen());
          break;
        case 'Profile':
          pages.add(const ProfileScreen());
          break;
      }
    }

    final notificationState = ref.watch(notificationProvider);

    return FirestoreListener(
      child: Scaffold(
        body: Stack(
          children: [
            PageView(
              controller: _pageController,
              physics: const NeverScrollableScrollPhysics(), // Disable swipe
              children: pages,
            ),
            // Notification banner overlay
            if (notificationState.isVisible &&
                notificationState.messageContent != null) ...[
              Builder(
                builder: (context) {
                  final agentId =
                      notificationState.agentId ??
                      MobileApiConfig.defaultAgentId;
                  print('[MobileHomePage] Creating MessageNotificationBanner');
                  print(
                    '[MobileHomePage] Notification agentId: ${notificationState.agentId}',
                  );
                  print('[MobileHomePage] Using agentId: $agentId');
                  print(
                    '[MobileHomePage] Default agentId: ${MobileApiConfig.defaultAgentId}',
                  );

                  return MessageNotificationBanner(
                    threadName: notificationState.threadName ?? 'New Message',
                    messageContent: notificationState.messageContent!,
                    agentId: agentId,
                    subject: notificationState.subject,
                    duration: notificationState.duration,
                    onDismiss: () {
                      ref
                          .read(notificationProvider.notifier)
                          .hideNotification();
                    },
                  );
                },
              ),
            ],
          ],
        ),
        bottomNavigationBar: Container(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.1),
                blurRadius: 4,
                offset: const Offset(0, -2),
              ),
            ],
          ),
          child: SafeArea(
            top: false,
            child: BottomNavigationBar(
              currentIndex: currentIndex.clamp(0, navItems.length - 1),
              type: BottomNavigationBarType.fixed,
              backgroundColor: Colors.transparent,
              elevation: 0,
              selectedItemColor: Theme.of(context).colorScheme.primary,
              unselectedItemColor:
                  Theme.of(context).colorScheme.onSurfaceVariant,
              selectedFontSize: 12,
              unselectedFontSize: 12,
              onTap: (index) {
                // Set flag to indicate user-initiated navigation
                ref.read(isUserNavigatingProvider.notifier).state = true;
                ref.read(navigationIndexProvider.notifier).state = index;

                // Clear the flag after a short delay to allow navigation to complete
                Future.delayed(const Duration(milliseconds: 500), () {
                  ref.read(isUserNavigatingProvider.notifier).state = false;
                });
              },
              items:
                  navItems
                      .map(
                        (item) => BottomNavigationBarItem(
                          icon: Icon(item.icon),
                          label: item.label,
                        ),
                      )
                      .toList(),
            ),
          ),
        ),
      ),
    );
  }
}
