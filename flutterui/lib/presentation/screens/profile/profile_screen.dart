import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../providers/auth_provider.dart';
import 'widgets/profile_app_bar.dart';
import '../../widgets/app_drawer.dart';

class ProfileScreen extends ConsumerWidget {
  static const String routeName = '/profile';

  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authNotifierProvider);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    if (authState is! Authenticated) {
      return Scaffold(
        appBar: const ProfileAppBar(),
        body: const Center(
          child: Text('Not authenticated'),
        ),
      );
    }

    final user = authState.user;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      drawer: const AppDrawer(),
      appBar: const ProfileAppBar(),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Profile header
            Center(
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 50,
                    backgroundColor: colorScheme.primaryContainer,
                    child: Text(
                      (user.name ?? user.email).substring(0, 1).toUpperCase(),
                      style: textTheme.headlineLarge?.copyWith(
                        color: colorScheme.onPrimaryContainer,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    user.name ?? 'User',
                    style: textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    user.email,
                    style: textTheme.bodyLarge?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),

            // User details
            _ProfileInfoCard(
              title: 'Account Information',
              children: [
                _ProfileInfoRow(
                  label: 'Email',
                  value: user.email,
                  icon: Icons.email_outlined,
                ),
                _ProfileInfoRow(
                  label: 'User ID',
                  value: user.userId,
                  icon: Icons.fingerprint,
                  onCopy: () {
                    Clipboard.setData(ClipboardData(text: user.userId));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('User ID copied to clipboard'),
                        duration: Duration(seconds: 2),
                      ),
                    );
                  },
                ),
                _ProfileInfoRow(
                  label: 'Provider',
                  value: user.provider.toUpperCase(),
                  icon: Icons.security_outlined,
                ),
              ],
            ),

            const SizedBox(height: 16),

            // Debug info card (only in debug mode)
            if (const bool.fromEnvironment('dart.vm.product') == false)
              _ProfileInfoCard(
                title: 'Debug Information',
                children: [
                  _ProfileInfoRow(
                    label: 'For Firestore Testing',
                    value: 'Use the User ID above in the userId field when creating test documents',
                    icon: Icons.bug_report_outlined,
                    isMultiline: true,
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _ProfileInfoCard extends StatelessWidget {
  final String title;
  final List<Widget> children;

  const _ProfileInfoCard({
    required this.title,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: colorScheme.outlineVariant,
          width: 1,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 16),
            ...children,
          ],
        ),
      ),
    );
  }
}

class _ProfileInfoRow extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final VoidCallback? onCopy;
  final bool isMultiline;

  const _ProfileInfoRow({
    required this.label,
    required this.value,
    required this.icon,
    this.onCopy,
    this.isMultiline = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        crossAxisAlignment: isMultiline ? CrossAxisAlignment.start : CrossAxisAlignment.center,
        children: [
          Icon(
            icon,
            size: 20,
            color: colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: textTheme.bodyLarge?.copyWith(
                    fontFamily: label == 'User ID' ? 'monospace' : null,
                  ),
                ),
              ],
            ),
          ),
          if (onCopy != null)
            IconButton(
              icon: const Icon(Icons.copy, size: 18),
              onPressed: onCopy,
              tooltip: 'Copy to clipboard',
              color: colorScheme.primary,
            ),
        ],
      ),
    );
  }
}
