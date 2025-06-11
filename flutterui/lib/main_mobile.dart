import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutterui/main.dart' show sharedPreferencesProvider, appThemeProvider;
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/presentation/screens/auth/login_screen.dart';
import 'package:flutterui/presentation/screens/chat/chat_screen.dart';
import 'package:flutterui/presentation/screens/threads/threads_screen.dart';
import 'package:flutterui/core/constants/mobile_api_config.dart';
import 'package:flutterui/core/constants/api_constants.dart';

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

    return MaterialApp(
      title: 'Bond AI Mobile',
      debugShowCheckedModeBanner: false,
      theme: appTheme.themeData,
      home: const MobileAuthWrapper(),
    );
  }
}

class MobileAuthWrapper extends ConsumerWidget {
  const MobileAuthWrapper({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authNotifierProvider);

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
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final selectedThread = ref.watch(selectedThreadProvider);
    
    // If a thread is selected, show chat screen
    if (selectedThread != null && _currentIndex == 1) {
      _currentIndex = 0; // Switch to chat tab
    }

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
        index: _currentIndex,
        children: pages,
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
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
        ],
      ),
    );
  }
}