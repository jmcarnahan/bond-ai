import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web/web.dart' as web;

import 'package:flutterui/presentation/screens/home/home_screen.dart';
import 'package:flutterui/presentation/screens/auth/login_screen.dart';
import 'package:flutterui/presentation/screens/auth/auth_callback_screen.dart';
import 'package:flutterui/presentation/screens/chat/chat_screen.dart';
import 'package:flutterui/presentation/screens/threads/threads_screen.dart';
import 'package:flutterui/presentation/screens/agents/create_agent_screen.dart';
import 'package:flutterui/presentation/screens/groups/groups_screen.dart';
import 'package:flutterui/presentation/screens/groups/edit_group_screen.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/core/theme/generated_theme.dart';
import 'package:flutterui/core/utils/logger.dart';
import 'package:flutterui/presentation/widgets/selected_thread_banner.dart';
import 'package:flutterui/providers/ui_providers.dart';

final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('SharedPreferences not initialized');
});

final appThemeProvider = Provider<AppTheme>((ref) {
  return AppGeneratedTheme(); 
});

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();

  runApp(
    ProviderScope(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      child: const MyApp(),
    ),
  );
}

class MyApp extends ConsumerWidget {
  const MyApp({super.key});

  // Add a static GlobalKey to prevent conflicts
  static final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authNotifierProvider);

    Widget homeWidget;
    if (authState is Authenticated) {
      homeWidget = const HomeScreen();
    } else if (authState is Unauthenticated || authState is AuthError) {
      homeWidget = const LoginScreen();
    } else {
      homeWidget = const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    final AppTheme currentTheme = ref.watch(appThemeProvider);

    if (kIsWeb) {
      try {
        web.document.title = currentTheme.name;
      } catch (e) {
        logger.w("Could not set document.title: $e");
      }
    }

    return MaterialApp(
      navigatorKey: _navigatorKey,
      debugShowCheckedModeBanner: false,
      title: currentTheme.name,
      theme: currentTheme.themeData,
      home: homeWidget,
      navigatorObservers: [RouteObserverForBanner(ref)],
      builder: (context, child) {
        final bool showBanner = ref.watch(showThreadBannerProvider);

        return Stack(
          children: [
            if (child != null) child,
            if (showBanner)
              Positioned(
                bottom: 0,
                left: 0,
                right: 0,
                child: SelectedThreadBanner(),
              ),
          ],
        );
      },
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

        logger.i("[onGenerateRoute] Effective Path for switch: '$effectivePath'");

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
            bool isFromAgentChat = false;
            if (settings.arguments is Map<String, dynamic>) {
              isFromAgentChat = (settings.arguments as Map<String, dynamic>)['isFromAgentChat'] ?? false;
            }
            pageWidget = ThreadsScreen(isFromAgentChat: isFromAgentChat);
            break;
          case CreateAgentScreen.routeName:
            pageWidget = const CreateAgentScreen();
            break;
          case GroupsScreen.routeName:
            pageWidget = const GroupsScreen();
            break;
          default:
            if (effectivePath.startsWith('/groups/') && effectivePath.endsWith('/edit')) {
              final parts = effectivePath.split('/');
              if (parts.length >= 3 && settings.arguments is Group) {
                final group = settings.arguments as Group;
                pageWidget = EditGroupScreen(group: group);
              } else {
                logger.e('[onGenerateRoute] Error: EditGroupScreen called without Group argument');
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
                  pageWidget = const Scaffold(
                    body: Center(
                      child: Text('Error: Missing agent details for chat.'),
                    ),
                  );
                }
              } else {
                logger.i(
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
              final parts = effectivePath.split('/');
              if (parts.length >= 3) {
                final agentIdForEdit = parts[2];
                pageWidget = CreateAgentScreen(agentId: agentIdForEdit);
              } else {
                logger.i(
                  '[onGenerateRoute] Error: Invalid /edit-agent/ route format: $effectivePath',
                );
                pageWidget = const Scaffold(
                  body: Center(
                    child: Text('Error: Invalid edit agent route format.'),
                  ),
                );
              }
            } else {
              logger.i(
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

        logger.i(
          "[onGenerateRoute] Fallback: Unknown route. Name='${settings.name}', EffectivePath='$effectivePath'. Showing homeWidget.",
        );
        return MaterialPageRoute(builder: (_) => homeWidget);
      },
    );
  }
}
