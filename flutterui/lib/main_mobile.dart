import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutterui/main.dart' show sharedPreferencesProvider, appThemeProvider;
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/presentation/screens/auth/login_screen.dart';
import 'package:flutterui/presentation/screens/auth/auth_callback_screen.dart';
import 'package:flutterui/presentation/screens/chat/chat_screen.dart';
import 'package:flutterui/presentation/screens/threads/threads_screen.dart';
import 'package:flutterui/core/constants/mobile_api_config.dart';
import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/core/utils/logger.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:web/web.dart' as web if (dart.library.io) 'dart:io';

// Provider to control the bottom navigation index
final navigationIndexProvider = StateProvider<int>((ref) => 0);

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Load environment variables
  await dotenv.load(fileName: ".env");
  
  // Override API base URL from environment
  final apiBaseUrl = dotenv.env['API_BASE_URL'];
  if (apiBaseUrl != null && apiBaseUrl.isNotEmpty) {
    ApiConstants.baseUrl = apiBaseUrl;
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
    logger.i('[MobileAuthWrapper] Current auth state: ${authState.runtimeType}');
    if (authState is Authenticated) {
      logger.i('[MobileAuthWrapper] User authenticated: ${authState.user.email}');
    } else if (authState is Unauthenticated) {
      logger.i('[MobileAuthWrapper] User unauthenticated: ${authState.message}');
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
  @override
  Widget build(BuildContext context) {
    final selectedThread = ref.watch(selectedThreadProvider);
    final currentIndex = ref.watch(navigationIndexProvider);
    
    // Listen for thread selection changes
    ref.listen<Thread?>(selectedThreadProvider, (previous, next) {
      if (previous == null && next != null) {
        // A thread was just selected, switch to chat tab
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
    ];

    return Scaffold(
      body: IndexedStack(
        index: currentIndex,
        children: pages,
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: currentIndex,
        onTap: (index) {
          ref.read(navigationIndexProvider.notifier).state = index;
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
        ],
      ),
    );
  }
}