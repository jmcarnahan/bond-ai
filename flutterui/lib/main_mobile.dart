import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutterui/firebase_options.dart';
import 'package:flutterui/main.dart' show sharedPreferencesProvider, appThemeProvider;
import 'package:flutterui/providers/auth_provider.dart';
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
import 'package:web/web.dart' as web if (dart.library.io) 'dart:io';
import 'package:flutterui/presentation/widgets/firestore_listener.dart';
import 'package:flutterui/presentation/widgets/message_notification_banner.dart';
import 'package:flutterui/providers/notification_provider.dart';

// Provider to control the bottom navigation index
final navigationIndexProvider = StateProvider<int>((ref) => 0);

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
          logger.i('[MobileApp] Profile route requested, switching to profile tab');
          return MaterialPageRoute(
            builder: (context) => Consumer(
              builder: (context, ref, _) {
                // Set navigation to profile tab
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  ref.read(navigationIndexProvider.notifier).state = 2;
                });
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
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
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
  ConsumerState<MobileNavigationShell> createState() => _MobileNavigationShellState();
}

class _MobileNavigationShellState extends ConsumerState<MobileNavigationShell> {
  late PageController _pageController;
  
  @override
  void initState() {
    super.initState();
    _pageController = PageController();
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
      if (next != null && 
          currentIndex == 1 && 
          previous?.id != next.id) {
        ref.read(navigationIndexProvider.notifier).state = 0;
      }
    });

    final List<Widget> pages = [
      ChatScreen(
        agentId: MobileApiConfig.mobileAgentId,
        agentName: MobileApiConfig.mobileAgentName,
        initialThreadId: selectedThread?.id,
      ),
      const ThreadsScreen(),
      const ProfileScreen(),
    ];

    final notificationState = ref.watch(notificationProvider);
    
    return FirestoreListener(
      child: Stack(
        children: [
          Scaffold(
            body: PageView(
              controller: _pageController,
              physics: const NeverScrollableScrollPhysics(), // Disable swipe
              children: pages,
            ),
            bottomNavigationBar: BottomNavigationBar(
              currentIndex: currentIndex,
              onTap: (index) {
                // Set flag to indicate user-initiated navigation
                ref.read(isUserNavigatingProvider.notifier).state = true;
                ref.read(navigationIndexProvider.notifier).state = index;
                
                // Clear the flag after a short delay to allow navigation to complete
                Future.delayed(const Duration(milliseconds: 500), () {
                  ref.read(isUserNavigatingProvider.notifier).state = false;
                });
              },
              items: const [
                BottomNavigationBarItem(
                  icon: Icon(Icons.chat),
                  label: 'Chat',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.list),
                  label: 'Threads',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.person),
                  label: 'Profile',
                ),
              ],
            ),
          ),
          // Notification banner overlay
          if (notificationState.isVisible && notificationState.messageContent != null)
            MessageNotificationBanner(
              threadName: notificationState.threadName ?? 'New Message',
              messageContent: notificationState.messageContent!,
              agentId: notificationState.agentId ?? MobileApiConfig.mobileAgentId,
              subject: notificationState.subject,
              duration: notificationState.duration,
              onDismiss: () {
                ref.read(notificationProvider.notifier).hideNotification();
              },
            ),
        ],
      ),
    );
  }
}