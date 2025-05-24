import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/presentation/widgets/sidebar.dart'; // Import the sidebar
import 'package:flutterui/providers/agent_provider.dart'; // Import the agents provider
import 'package:flutterui/presentation/widgets/agent_card.dart'; // Import the AgentCard widget
import 'package:flutterui/data/models/agent_model.dart'; // Import the Agent model

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final agentsAsyncValue = ref.watch(agentsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('BondAI Agents')),
      drawer: const AppSidebar(),
      body: agentsAsyncValue.when(
        data: (agents) {
          if (agents.isEmpty) {
            return const Center(
              child: Text('No agents found. Create one from the sidebar!'),
            );
          }
          // Use a GridView for a card-like layout
          return GridView.builder(
            padding: const EdgeInsets.all(10.0),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2, // Number of columns
              crossAxisSpacing: 10.0, // Horizontal space between cards
              mainAxisSpacing: 10.0, // Vertical space between cards
              childAspectRatio: 3 / 2, // Aspect ratio of the cards
            ),
            itemCount: agents.length,
            itemBuilder: (context, index) {
              final agent = agents[index];
              return AgentCard(agent: agent);
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, stack) {
          // Optionally, add a refresh button or more detailed error UI
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  'Error loading agents: ${err.toString()}',
                  style: const TextStyle(color: Colors.red),
                ),
                const SizedBox(height: 10),
                ElevatedButton.icon(
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retry'),
                  onPressed: () {
                    ref.invalidate(agentsProvider); // Invalidate to refetch
                  },
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
