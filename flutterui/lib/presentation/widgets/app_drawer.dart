import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/main.dart' show navigationIndexProvider;
import 'package:flutterui/presentation/screens/profile/profile_screen.dart';
import 'package:flutterui/presentation/screens/connections/connections_screen.dart';
import 'package:flutterui/providers/config_provider.dart';
import 'package:flutterui/providers/connections_provider.dart';

class AppDrawer extends ConsumerWidget {
  const AppDrawer({super.key});

  Widget _buildConnectionsListTile(BuildContext context, WidgetRef ref, ThemeData theme) {
    final connectionsState = ref.watch(connectionsNotifierProvider);
    final needsAttention = connectionsState.connectionsNeedingAttention.isNotEmpty ||
        connectionsState.expired.isNotEmpty;

    return ListTile(
      leading: Stack(
        clipBehavior: Clip.none,
        children: [
          Icon(
            Icons.link,
            color: theme.colorScheme.onSurface,
          ),
          if (needsAttention)
            Positioned(
              right: -4,
              top: -4,
              child: Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  color: theme.colorScheme.error,
                  shape: BoxShape.circle,
                ),
              ),
            ),
        ],
      ),
      title: Text(
        'Connections',
        style: TextStyle(
          color: theme.colorScheme.onSurface,
          fontSize: 16,
        ),
      ),
      trailing: needsAttention
          ? Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: theme.colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                'Action needed',
                style: TextStyle(
                  color: theme.colorScheme.onErrorContainer,
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                ),
              ),
            )
          : null,
      onTap: () {
        Navigator.pop(context); // Close drawer
        Navigator.pushNamed(context, ConnectionsScreen.routeName);
      },
    );
  }

  void _showLogoutDialog(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder:
          (context) => AlertDialog(
            title: const Text('Logout'),
            content: const Text('Are you sure you want to logout?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () {
                  Navigator.of(context).pop();
                  Navigator.of(context).pop(); // Close drawer
                  ref.read(authNotifierProvider.notifier).logout();
                },
                child: Text(
                  'Logout',
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ],
          ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authNotifierProvider);
    final appTheme = ref.watch(appThemeProvider);
    final theme = Theme.of(context);
    final isAgentsEnabled = ref.watch(isAgentsEnabledProvider);
    final navItems = ref.watch(bottomNavItemsProvider);

    String userEmail = '';
    if (authState is Authenticated) {
      userEmail = authState.user.email;
    }

    return Drawer(
      width: 280,
      child: Container(
        color: theme.colorScheme.surface,
        child: SafeArea(
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 24,
                ),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: theme.dividerColor.withValues(alpha: 0.3),
                      width: 1,
                    ),
                  ),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: theme.colorScheme.onSurface.withValues(
                          alpha: 0.1,
                        ),
                      ),
                      child: Image.asset(
                        appTheme.logoIcon,
                        height: 36,
                        width: 36,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      '${appTheme.name} Companion',
                      style: TextStyle(
                        color: theme.colorScheme.onSurface,
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 4),
                    if (userEmail.isNotEmpty)
                      Text(
                        userEmail,
                        style: TextStyle(
                          color: theme.colorScheme.onSurface.withValues(
                            alpha: 0.7,
                          ),
                          fontSize: 13,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                  ],
                ),
              ),
              // Navigation section
              if (isAgentsEnabled)
                ListTile(
                  leading: Icon(
                    Icons.smart_toy_outlined,
                    color: theme.colorScheme.onSurface,
                  ),
                  title: Text(
                    'Agents',
                    style: TextStyle(
                      color: theme.colorScheme.onSurface,
                      fontSize: 16,
                    ),
                  ),
                  onTap: () {
                    // Capture the route BEFORE popping the drawer
                    final currentRoute = ModalRoute.of(context)?.settings.name;
                    final isOnSubScreen = currentRoute == ProfileScreen.routeName ||
                        currentRoute == ConnectionsScreen.routeName;

                    Navigator.pop(context); // Close drawer

                    // Find the target index
                    final agentsIndex = navItems.indexWhere(
                      (item) => item.label == 'Agents',
                    );

                    // Set the navigation index BEFORE navigating so the shell picks it up
                    if (agentsIndex != -1) {
                      ref.read(navigationIndexProvider.notifier).state = agentsIndex;
                    }

                    if (isOnSubScreen) {
                      // Navigate back to main shell
                      Navigator.pushNamedAndRemoveUntil(
                        context,
                        '/',
                        (route) => false,
                      );
                    }
                  },
                ),
              ListTile(
                leading: Icon(
                  Icons.chat_bubble_outline,
                  color: theme.colorScheme.onSurface,
                ),
                title: Text(
                  'Chat',
                  style: TextStyle(
                    color: theme.colorScheme.onSurface,
                    fontSize: 16,
                  ),
                ),
                onTap: () {
                  // Capture the route BEFORE popping the drawer
                  final currentRoute = ModalRoute.of(context)?.settings.name;
                  final isOnSubScreen = currentRoute == ProfileScreen.routeName ||
                      currentRoute == ConnectionsScreen.routeName;

                  Navigator.pop(context); // Close drawer

                  // Find the target index
                  final chatIndex = navItems.indexWhere(
                    (item) => item.label == 'Chat',
                  );

                  // Set the navigation index BEFORE navigating so the shell picks it up
                  if (chatIndex != -1) {
                    ref.read(navigationIndexProvider.notifier).state = chatIndex;
                  }

                  if (isOnSubScreen) {
                    // Navigate back to main shell
                    Navigator.pushNamedAndRemoveUntil(
                      context,
                      '/',
                      (route) => false,
                    );
                  }
                },
              ),
              ListTile(
                leading: Icon(
                  Icons.forum_outlined,
                  color: theme.colorScheme.onSurface,
                ),
                title: Text(
                  'Threads',
                  style: TextStyle(
                    color: theme.colorScheme.onSurface,
                    fontSize: 16,
                  ),
                ),
                onTap: () {
                  // Capture the route BEFORE popping the drawer
                  final currentRoute = ModalRoute.of(context)?.settings.name;
                  final isOnSubScreen = currentRoute == ProfileScreen.routeName ||
                      currentRoute == ConnectionsScreen.routeName;

                  Navigator.pop(context); // Close drawer

                  // Find the target index
                  final threadsIndex = navItems.indexWhere(
                    (item) => item.label == 'Threads',
                  );

                  // Set the navigation index BEFORE navigating so the shell picks it up
                  if (threadsIndex != -1) {
                    ref.read(navigationIndexProvider.notifier).state = threadsIndex;
                  }

                  if (isOnSubScreen) {
                    // Navigate back to main shell
                    Navigator.pushNamedAndRemoveUntil(
                      context,
                      '/',
                      (route) => false,
                    );
                  }
                },
              ),
              _buildConnectionsListTile(context, ref, theme),
              const Divider(indent: 16, endIndent: 16),
              ListTile(
                leading: Icon(
                  Icons.person_outline,
                  color: theme.colorScheme.onSurface,
                ),
                title: Text(
                  'Profile',
                  style: TextStyle(
                    color: theme.colorScheme.onSurface,
                    fontSize: 16,
                  ),
                ),
                onTap: () {
                  Navigator.pop(context); // Close drawer

                  // Check if we're currently on Connections screen
                  final currentRoute = ModalRoute.of(context)?.settings.name;
                  if (currentRoute == ConnectionsScreen.routeName) {
                    // Navigate back to main shell first, then to profile
                    Navigator.pushNamedAndRemoveUntil(
                      context,
                      '/',
                      (route) => false,
                    );
                  }

                  // Check if we're in mobile navigation shell
                  final isMobile =
                      context
                          .findAncestorWidgetOfExactType<Scaffold>()
                          ?.bottomNavigationBar !=
                      null;
                  if (isMobile) {
                    // For mobile, find the profile tab index dynamically
                    final profileIndex = navItems.indexWhere(
                      (item) => item.label == 'Profile',
                    );
                    if (profileIndex != -1) {
                      ref.read(navigationIndexProvider.notifier).state =
                          profileIndex;
                    }
                  } else {
                    // For desktop/web, use regular navigation
                    Navigator.pushNamed(context, ProfileScreen.routeName);
                  }
                },
              ),
              const Divider(indent: 16, endIndent: 16),
              ListTile(
                leading: Icon(Icons.logout, color: theme.colorScheme.onSurface),
                title: Text(
                  'Logout',
                  style: TextStyle(
                    color: theme.colorScheme.onSurface,
                    fontSize: 16,
                  ),
                ),
                onTap: () => _showLogoutDialog(context, ref),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
