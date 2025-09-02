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
import 'package:flutterui/presentation/screens/agents/create_agent_screen.dart';
import 'package:flutterui/presentation/screens/groups/groups_screen.dart';
import 'package:flutterui/presentation/screens/groups/edit_group_screen.dart';
import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/core/utils/logger.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:universal_html/html.dart' as html;
import 'package:flutterui/presentation/widgets/firestore_listener.dart';
import 'package:flutterui/presentation/widgets/message_notification_banner.dart';
import 'package:flutterui/providers/notification_provider.dart';
import 'package:flutterui/providers/config_provider.dart';
import 'package:flutterui/presentation/screens/agents/agents_screen.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/core/services/deep_link_service.dart';

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

  // Initialize dotenv - this ensures dotenv.env is always safe to access
  // If .env file doesn't exist, dotenv will have an empty map but won't throw errors
  try {
    await dotenv.load(fileName: ".env");
    logger.i('.env file loaded successfully');
  } catch (e) {
    // .env file not found - initialize with empty map to prevent errors
    dotenv.testLoad(fileInput: '');
    logger.i('No .env file found, initialized with empty configuration');
  }
  
  // Set API base URL from .env or compile-time constants
  if (ApiConstants.baseUrl.isEmpty) {
    final apiBaseUrl = dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';
    ApiConstants.baseUrl = apiBaseUrl;
    logger.i('Using API base URL: $apiBaseUrl');
  } else {
    logger.i('Using compile-time API base URL: ${ApiConstants.baseUrl}');
  }

  // Use compile-time API_BASE_URL if provided (for deployed environments)
  const apiBaseUrlFromEnv = String.fromEnvironment('API_BASE_URL', defaultValue: '');
  if (apiBaseUrlFromEnv.isNotEmpty) {
    ApiConstants.baseUrl = apiBaseUrlFromEnv;
    logger.i('Using API_BASE_URL from compile-time constant: $apiBaseUrlFromEnv');
  }
  // Otherwise, baseUrl is already set from .env file or defaults above

  // Initialize Firebase
  try {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
    logger.i('Firebase initialized successfully');
  } catch (e) {
    logger.e('Error initializing Firebase: $e');
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
      final currentUrl = Uri.parse(html.window.location.href);
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
        logger.i(
          "[onGenerateRoute] Name: '${settings.name}', Args: ${settings.arguments}",
        );
        Widget? pageWidget;

        String effectivePath = settings.name ?? '/';
        if (effectivePath.startsWith('/#/')) {
          effectivePath = effectivePath.substring(2);
        }
        if (!effectivePath.startsWith('/')) {
          effectivePath = '/$effectivePath';
        }

        final Uri uri = Uri.parse(effectivePath);
        effectivePath = uri.path;

        // Handle root route with token parameter (mobile OAuth callback)
        if ((effectivePath == '/' || effectivePath.isEmpty) &&
            uri.queryParameters.containsKey('token')) {
          final token = uri.queryParameters['token'];
          logger.i(
            '[MobileApp] Found token in route, processing authentication',
          );

          return MaterialPageRoute(
            builder:
                (context) => Consumer(
                  builder: (context, ref, _) {
                    // Process the token immediately
                    WidgetsBinding.instance.addPostFrameCallback((_) async {
                      if (token != null && token.isNotEmpty) {
                        logger.i(
                          '[MobileApp] Processing OAuth token from route',
                        );
                        await ref
                            .read(authNotifierProvider.notifier)
                            .loginWithToken(token);
                      }
                    });

                    return const MobileAuthWrapper();
                  },
                ),
            settings: settings,
          );
        }

        logger.i(
          "[onGenerateRoute] Effective Path for switch: '$effectivePath'",
        );

        switch (effectivePath) {
          case '/login':
            pageWidget = const LoginScreen();
            break;
          case '/auth-callback':
            pageWidget = const AuthCallbackScreen();
            break;
          case '/threads':
            pageWidget = const ThreadsScreen();
            break;
          case CreateAgentScreen.routeName:
            pageWidget = const CreateAgentScreen();
            break;
          case GroupsScreen.routeName:
            pageWidget = const GroupsScreen();
            break;
          case ProfileScreen.routeName:
            pageWidget = const ProfileScreen();
            break;
          default:
            if (effectivePath.startsWith('/groups/') &&
                effectivePath.endsWith('/edit')) {
              final parts = effectivePath.split('/');
              if (parts.length >= 3 && settings.arguments is Group) {
                final group = settings.arguments as Group;
                pageWidget = EditGroupScreen(group: group);
              } else {
                logger.e(
                  '[onGenerateRoute] Error: EditGroupScreen called without Group argument',
                );
                pageWidget = const GroupsScreen();
              }
            } else if (effectivePath.startsWith('/chat/')) {
              final parts = effectivePath.split('/');
              if (parts.length >= 3) {
                if (settings.arguments is AgentListItemModel) {
                  final agent = settings.arguments as AgentListItemModel;
                  logger.i(
                    "[onGenerateRoute] Navigating to ChatScreen for agent: ${agent.name} (ID: ${agent.id})",
                  );
                  pageWidget = ChatScreen(
                    agentId: agent.id,
                    agentName: agent.name,
                  );
                } else {
                  logger.i(
                    '[onGenerateRoute] Error: ChatScreen /chat/:id called without AgentListItemModel object as argument. Args: ${settings.arguments}',
                  );
                  // Handle missing agent data
                  logger.e(
                    '[onGenerateRoute] Missing agent data for chat route',
                  );
                  pageWidget = const MobileAuthWrapper();
                }
              }
            } else if (effectivePath.startsWith('/edit-agent/')) {
              final agentId = effectivePath.replaceFirst('/edit-agent/', '');
              logger.i('[MobileApp] Edit agent route requested for: $agentId');
              pageWidget = CreateAgentScreen(agentId: agentId);
            }
            break;
        }

        if (pageWidget != null) {
          return MaterialPageRoute(
            builder: (context) => pageWidget!,
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
  DeepLinkService? _deepLinkService;

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

    // Initialize deep link service only for mobile platforms
    if (!kIsWeb) {
      _deepLinkService = DeepLinkService();
    }

    // Set the navigation index after the first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        ref.read(navigationIndexProvider.notifier).state = initialIndex;
        // Initialize deep links after the first frame
        if (!kIsWeb && _deepLinkService != null) {
          _deepLinkService!.initDeepLinks(context, ref);
        }
      }
    });
  }

  @override
  void dispose() {
    _pageController.dispose();
    _deepLinkService?.dispose();
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
          // Use ref.watch here to get the default agent
          final defaultAgentAsync = ref.watch(defaultAgentProvider);
          pages.add(
            defaultAgentAsync.when(
              data: (defaultAgent) => ChatScreen(
                agentId: selectedAgent?.id ?? defaultAgent.id,
                agentName: selectedAgent?.name ?? defaultAgent.name,
                initialThreadId: selectedThread?.id,
              ),
              loading: () => const Scaffold(
                body: Center(child: CircularProgressIndicator()),
              ),
              error: (error, _) => Scaffold(
                body: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, size: 48, color: Colors.red),
                      const SizedBox(height: 16),
                      Text('Failed to load default agent: ${error.toString()}'),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: () => ref.refresh(defaultAgentProvider),
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
          break;
        case 'Threads':
          pages.add(const ThreadsScreen());
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
                  final defaultAgentAsync = ref.watch(defaultAgentProvider);
                  
                  return defaultAgentAsync.when(
                    data: (defaultAgent) {
                      final agentId = notificationState.agentId ?? defaultAgent.id;
                      logger.d(
                        '[MobileHomePage] Creating MessageNotificationBanner',
                      );
                      logger.d(
                        '[MobileHomePage] Notification agentId: ${notificationState.agentId}',
                      );
                      logger.d('[MobileHomePage] Using agentId: $agentId');
                      logger.d(
                        '[MobileHomePage] Default agentId: ${defaultAgent.id}',
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
                    loading: () => const SizedBox.shrink(),
                    error: (_, __) => const SizedBox.shrink(),
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
