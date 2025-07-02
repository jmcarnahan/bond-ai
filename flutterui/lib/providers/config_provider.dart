import 'package:flutter/material.dart' show Icons, IconData;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Provider to check if agents feature is enabled in mobile interface
final isAgentsEnabledProvider = Provider<bool>((ref) {
  final enableAgents = dotenv.env['ENABLE_AGENTS']?.toLowerCase();
  return enableAgents == 'true';
});

/// Provider for bottom navigation items based on configuration
final bottomNavItemsProvider = Provider<List<BottomNavItem>>((ref) {
  final isAgentsEnabled = ref.watch(isAgentsEnabledProvider);

  final items = <BottomNavItem>[];

  // Always add agents first if enabled (far left)
  if (isAgentsEnabled) {
    items.add(const BottomNavItem(icon: Icons.group, label: 'Agents'));
  }

  // Then add the core items
  items.addAll(const [
    BottomNavItem(icon: Icons.chat, label: 'Chat'),
    BottomNavItem(icon: Icons.list, label: 'Threads'),
  ]);

  return items;
});

class BottomNavItem {
  final IconData icon;
  final String label;

  const BottomNavItem({required this.icon, required this.label});
}
