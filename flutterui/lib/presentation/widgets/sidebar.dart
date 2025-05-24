import 'package:flutter/material.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart'; // For logout
import 'package:flutterui/providers/agent_provider.dart'; // Import the agents provider
import 'package:flutterui/data/models/agent_model.dart'; // Import the AgentListItemModel
import 'package:flutterui/presentation/screens/agents/create_agent_screen.dart'; // Import CreateAgentScreen

class AppSidebar extends ConsumerWidget {
  const AppSidebar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final agentsAsyncValue = ref.watch(agentsProvider);

    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: <Widget>[
          DrawerHeader(
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primaryContainer,
            ),
            child: Text(
              'BondAI Menu',
              style: TextStyle(
                color: Theme.of(context).colorScheme.onPrimaryContainer,
                fontSize: 24,
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.home),
            title: const Text('Home'),
            onTap: () {
              Navigator.pop(context); // Close the drawer
              // If already on home, no action needed.
              // If on a different screen, use: Navigator.pushReplacementNamed(context, '/home');
            },
          ),
          ListTile(
            leading: const Icon(
              Icons.forum_outlined,
            ), // Changed icon for consistency if desired, or keep Icons.forum
            title: const Text('Threads'),
            onTap: () {
              Navigator.pop(context); // Close drawer
              // Navigate to ThreadsScreen. Assumes route name '/threads' is or will be defined.
              if (ModalRoute.of(context)?.settings.name != '/threads') {
                Navigator.pushNamed(context, '/threads');
              }
            },
          ),
          ListTile(
            leading: const Icon(Icons.add_circle_outline),
            title: const Text('Create Agent'),
            onTap: () {
              Navigator.pop(context);
              Navigator.pushNamed(context, CreateAgentScreen.routeName);
            },
          ),
          // TODO: Add an "Edit Agent" option, perhaps on long-press of agent items or an edit icon
          const Divider(),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: Text(
              'Agents',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
          agentsAsyncValue.when(
            data: (agents) {
              if (agents.isEmpty) {
                return const ListTile(
                  leading: Icon(Icons.info_outline),
                  title: Text('No agents found.'),
                );
              }
              return Column(
                children:
                    agents
                        .where(
                          (agent) => agent != null,
                        ) // Filter out potential nulls
                        .map((agent) {
                          // agent is now AgentListItemModel (non-nullable after filter)
                          return ListTile(
                            leading: const Icon(Icons.person),
                            title: Text(
                              agent.name,
                            ), // Accessing name on non-null agent
                            onTap: () {
                              Navigator.pop(context);
                              Navigator.pushNamed(
                                context,
                                '/chat/${agent.id}', // Accessing id on non-null agent
                                arguments: agent,
                              );
                            },
                          );
                        })
                        .toList(),
              );
            },
            loading:
                () => const ListTile(
                  leading: CircularProgressIndicator(),
                  title: Text('Loading agents...'),
                ),
            error:
                (err, stack) => ListTile(
                  leading: const Icon(Icons.error_outline, color: Colors.red),
                  title: Text(
                    'Error loading agents: ${err.toString()}',
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Logout'),
            onTap: () {
              Navigator.pop(context);
              ref.read(authNotifierProvider.notifier).logout();
              // Navigation to LoginScreen is handled by MyApp listening to AuthState
            },
          ),
        ],
      ),
    );
  }
}
