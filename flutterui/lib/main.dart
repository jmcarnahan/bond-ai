import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutterui/presentation/screens/home/home_screen.dart';
import 'package:flutterui/presentation/screens/auth/login_screen.dart';
import 'package:flutterui/presentation/screens/auth/auth_callback_screen.dart';
import 'package:flutterui/presentation/screens/chat/chat_screen.dart';
import 'package:flutterui/presentation/screens/threads/threads_screen.dart';
import 'package:flutterui/presentation/screens/agents/create_agent_screen.dart'; // Import CreateAgentScreen
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/data/models/agent_model.dart';

// Provider for SharedPreferences
// We will override this in main() after SharedPreferences is initialized
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('SharedPreferences not initialized');
});

Future<void> main() async {
  // Ensure Flutter bindings are initialized before using plugins
  WidgetsFlutterBinding.ensureInitialized();
  // Initialize SharedPreferences
  final prefs = await SharedPreferences.getInstance();

  // Wrap the entire application in a ProviderScope
  // Override the sharedPreferencesProvider with the initialized instance
  runApp(
    ProviderScope(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      child: const MyApp(),
    ),
  );
}

class MyApp extends ConsumerWidget {
  // Changed to ConsumerWidget
  const MyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Added WidgetRef ref
    final authState = ref.watch(authNotifierProvider);

    Widget homeWidget;
    if (authState is Authenticated) {
      homeWidget = const HomeScreen();
    } else if (authState is Unauthenticated || authState is AuthError) {
      homeWidget = const LoginScreen();
    } else {
      // AuthInitial or AuthLoading
      homeWidget = const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return MaterialApp(
      title: 'BondAI Flutter UI',
      theme: ThemeData(
        // Using Material 3 design
        useMaterial3: true,
        // Define a color scheme. You can customize this further.
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blueAccent,
          brightness: Brightness.light, // Or Brightness.dark for a dark theme
        ),
        // You can define other theme properties like textTheme, appBarTheme, etc.
        textTheme: const TextTheme(
          displayLarge: TextStyle(fontSize: 72.0, fontWeight: FontWeight.bold),
          titleLarge: TextStyle(fontSize: 36.0, fontStyle: FontStyle.italic),
          bodyMedium: TextStyle(fontSize: 14.0, fontFamily: 'Hind'),
        ),
      ),
      // Initially, we'll point to a simple placeholder.
      // Later, this will be our LoginScreen or HomeScreen based on auth state.
      home: homeWidget,
      // Define routes for navigation
      onGenerateRoute: (settings) {
        print(
          "[onGenerateRoute] Name: '${settings.name}', Args: ${settings.arguments}",
        );
        Widget? pageWidget; // Use nullable Widget

        // Normalize path, especially for web hash routing where path might be in fragment
        String effectivePath = settings.name ?? '/';
        if (effectivePath.startsWith('/#/')) {
          // Handle hash prefix if present
          effectivePath = effectivePath.substring(2);
        }
        if (!effectivePath.startsWith('/')) {
          effectivePath = '/$effectivePath';
        }

        // Further parse just the path part of the effectivePath if it contains query params
        final Uri uri = Uri.parse(effectivePath);
        effectivePath = uri.path;

        print("[onGenerateRoute] Effective Path for switch: '$effectivePath'");

        switch (effectivePath) {
          case '/login':
            pageWidget = const LoginScreen();
            break;
          case '/home':
            pageWidget = const HomeScreen();
            break;
          case '/auth-callback':
            pageWidget = const AuthCallbackScreen();
            break;
          case '/threads':
            pageWidget = const ThreadsScreen();
            break;
          case CreateAgentScreen.routeName: // Route for creating new agent
            pageWidget = const CreateAgentScreen();
            break;
          default:
            // Handle patterned routes
            if (effectivePath.startsWith('/chat/')) {
              final parts = effectivePath.split('/');
              if (parts.length >= 3) {
                // e.g. /chat/agentId
                // final agentIdForChat = parts[2]; // This is how you'd get ID if passing it in path
                // For now, assuming agent object is passed as argument
                if (settings.arguments is AgentListItemModel) {
                  final agent = settings.arguments as AgentListItemModel;
                  print(
                    "[onGenerateRoute] Navigating to ChatScreen for agent: ${agent.name} (ID: ${agent.id})",
                  );
                  pageWidget = ChatScreen(
                    agentId: agent.id,
                    agentName: agent.name,
                  );
                } else {
                  print(
                    '[onGenerateRoute] Error: ChatScreen /chat/:id called without AgentListItemModel object as argument. Args: ${settings.arguments}',
                  );
                  pageWidget = const Scaffold(
                    body: Center(
                      child: Text('Error: Missing agent details for chat.'),
                    ),
                  );
                }
              } else {
                print(
                  '[onGenerateRoute] Error: Invalid /chat/ route format: $effectivePath',
                );
                pageWidget = const Scaffold(
                  body: Center(
                    child: Text('Error: Invalid chat route format.'),
                  ),
                );
              }
            } else if (effectivePath.startsWith(
              CreateAgentScreen.editRouteNamePattern.split(':')[0],
            )) {
              // e.g. /edit-agent/
              final parts = effectivePath.split('/');
              if (parts.length >= 3) {
                // e.g. /edit-agent/agentId
                final agentIdForEdit = parts[2];
                pageWidget = CreateAgentScreen(agentId: agentIdForEdit);
              } else {
                print(
                  '[onGenerateRoute] Error: Invalid /edit-agent/ route format: $effectivePath',
                );
                pageWidget = const Scaffold(
                  body: Center(
                    child: Text('Error: Invalid edit agent route format.'),
                  ),
                );
              }
            } else {
              // Fallback for unknown routes if not caught by other conditions
              print(
                '[onGenerateRoute] Warning: Unhandled effectivePath: $effectivePath. Args: ${settings.arguments}',
              );
            }
            break;
        }

        if (pageWidget != null) {
          return MaterialPageRoute(
            builder: (_) => pageWidget!,
            settings: settings,
          );
        }

        // If no route is matched by the switch or the if-block
        print(
          "[onGenerateRoute] Fallback: Unknown route. Name='${settings.name}', EffectivePath='$effectivePath'. Showing homeWidget.",
        );
        return MaterialPageRoute(builder: (_) => homeWidget);
      },
      // It's good practice to set an initialRoute if you are using named routes extensively,
      // or ensure `home` handles the default view correctly.
      // For web, ensure your web server is configured to redirect all paths to index.html
      // if using path-based routing (e.g. /home) instead of hash-based routing (e.g. /#/home).
      // Flutter web defaults to hash-based routing.
    );
  }
}
