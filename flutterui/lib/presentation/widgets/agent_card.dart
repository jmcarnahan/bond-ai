import 'package:flutter/material.dart';
import 'package:flutterui/data/models/agent_model.dart'; // AgentListItemModel is here

class AgentCard extends StatelessWidget {
  final AgentListItemModel agent; // Changed from Agent to AgentListItemModel

  const AgentCard({super.key, required this.agent});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2.0,
      margin: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
      child: ListTile(
        leading: const Icon(
          Icons.person_outline,
          size: 40.0,
        ), // Icon for agent card
        title: Text(
          agent.name,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle:
            agent.description != null && agent.description!.isNotEmpty
                ? Text(agent.description!)
                : null,
        onTap: () {
          // Navigate to ChatScreen, passing the agent object as arguments
          // The router in main.dart will extract agentId and agentName from this.
          Navigator.pushNamed(
            context,
            '/chat/${agent.id}', // Route path includes agentId for uniqueness if needed by router
            arguments: agent, // Pass the whole agent object
          );
        },
        // isThreeLine: agent.description != null && agent.description!.isNotEmpty, // Adjust if needed
      ),
    );
  }
}
