import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/presentation/screens/agents/create_agent_screen.dart';
import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/main.dart';

class AppSidebar extends ConsumerWidget {
  const AppSidebar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final agentsAsyncValue = ref.watch(agentsProvider);
    final theme = Theme.of(context);
    final appTheme = ref.watch(appThemeProvider);
    final customColors = theme.extension<CustomColors>();
    
    final currentPrimaryColor = theme.primaryColor;
    final currentOnPrimaryColor = theme.colorScheme.onPrimary;
    final currentSurfaceColor = theme.colorScheme.surface;
    final currentOnSurfaceColor = theme.colorScheme.onSurface;

    return Drawer(
      backgroundColor: currentSurfaceColor,
      child: ListView(
        padding: EdgeInsets.zero,
        children: <Widget>[
          DrawerHeader(
            decoration: BoxDecoration(
              color: customColors?.brandingSurface ?? theme.colorScheme.primaryContainer,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Image.asset(
                      appTheme.logoIcon,
                      height: 40,
                      width: 40,
                    ),
                    const SizedBox(width: 12),
                    Text(
                      'My Agents',
                      style: TextStyle(
                        color: currentOnPrimaryColor,
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          ListTile(
            leading: Icon(Icons.home, color: currentPrimaryColor),
            title: Text('Home', style: TextStyle(color: currentOnSurfaceColor)),
            onTap: () {
              Navigator.pop(context);
              if (ModalRoute.of(context)?.settings.name != '/home') {
                if (Navigator.canPop(context)) {
                    Navigator.popUntil(context, ModalRoute.withName('/'));
                }
                if (ModalRoute.of(context)?.settings.name != '/home') {
                     Navigator.pushNamed(context, '/home');
                }
              }
            },
          ),
          ListTile(
            leading: Icon(Icons.forum_outlined, color: currentPrimaryColor),
            title: Text('Threads', style: TextStyle(color: currentOnSurfaceColor)),
            onTap: () {
              Navigator.pop(context);
              if (ModalRoute.of(context)?.settings.name != '/threads') {
                Navigator.pushNamed(context, '/threads');
              }
            },
          ),
          ListTile(
            leading: Icon(Icons.group, color: currentPrimaryColor),
            title: Text('Groups', style: TextStyle(color: currentOnSurfaceColor)),
            onTap: () {
              Navigator.pop(context);
              Navigator.pushNamed(context, '/groups');
            },
          ),
          ListTile(
            leading: Icon(Icons.add_circle_outline, color: currentPrimaryColor),
            title: Text('Create Agent', style: TextStyle(color: currentOnSurfaceColor)),
            onTap: () {
              Navigator.pop(context);
              Navigator.pushNamed(context, CreateAgentScreen.routeName);
            },
          ),
          const Divider(),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: Text(
              'Agents',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: currentPrimaryColor,
                fontSize: 16,
              ),
            ),
          ),
          agentsAsyncValue.when(
            data: (agents) {
              if (agents.isEmpty) {
                return ListTile(
                  leading: Icon(Icons.info_outline, color: currentOnSurfaceColor),
                  title: Text('No agents found.', style: TextStyle(color: currentOnSurfaceColor)),
                );
              }
              return Column(
                children: agents
                    .map((agent) {
                      return ListTile(
                        leading: Icon(Icons.person, color: currentPrimaryColor),
                        title: Text(
                          agent.name,
                          style: TextStyle(color: currentOnSurfaceColor),
                        ),
                        onTap: () {
                          Navigator.pop(context);
                          Navigator.pushNamed(
                            context,
                            '/chat/${agent.id}',
                            arguments: agent,
                          );
                        },
                      );
                    })
                    .toList(),
              );
            },
            loading: () => ListTile(
              leading: CircularProgressIndicator(color: currentPrimaryColor),
              title: Text('Loading agents...', style: TextStyle(color: currentOnSurfaceColor)),
            ),
            error: (err, stack) => ListTile(
              leading: Icon(Icons.error_outline, color: theme.colorScheme.error),
              title: Text(
                'Error loading agents: ${err.toString()}',
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ),
          ),
          const Divider(),
          ListTile(
            leading: Icon(Icons.logout, color: currentPrimaryColor),
            title: Text('Logout', style: TextStyle(color: currentOnSurfaceColor)),
            onTap: () async {
              Navigator.pop(context);
              await ref.read(authNotifierProvider.notifier).logout();
              // Navigate to login screen after logout
              if (context.mounted) {
                Navigator.pushNamedAndRemoveUntil(context, '/login', (route) => false);
              }
            },
          ),
        ],
      ),
    );
  }
}
