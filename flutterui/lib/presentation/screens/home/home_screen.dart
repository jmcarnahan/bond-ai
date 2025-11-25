import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/presentation/widgets/app_drawer.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/providers/connections_provider.dart';
import 'package:flutterui/presentation/screens/agents/widgets/agent_card.dart';
import 'package:flutterui/presentation/widgets/expired_connection_banner.dart';
import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';
import 'package:flutterui/core/error_handling/error_handler.dart';
import 'package:flutterui/presentation/widgets/firestore_listener.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> with ErrorHandlingMixin {
  @override
  void initState() {
    super.initState();
    // Load connections after login to show banner for connections needing attention
    Future.microtask(() {
      ref.read(connectionsNotifierProvider.notifier).loadConnections();
    });
  }

  @override
  Widget build(BuildContext context) {
    final agentsAsyncValue = ref.watch(agentsProvider);
    final appTheme = ref.watch(appThemeProvider);
    
    final ThemeData currentThemeData = Theme.of(context);
    final TextTheme textTheme = currentThemeData.textTheme;
    final ColorScheme colorScheme = currentThemeData.colorScheme;
    final CustomColors? customColors = currentThemeData.extension<CustomColors>();
    final Color appBarBackgroundColor = customColors?.brandingSurface ?? currentThemeData.appBarTheme.backgroundColor ?? currentThemeData.colorScheme.surface; // Generic fallback

    // Check if any connections need attention for the hamburger menu indicator
    final connectionsState = ref.watch(connectionsNotifierProvider);
    final hasConnectionIssues = connectionsState.connectionsNeedingAttention.isNotEmpty ||
        connectionsState.expired.isNotEmpty;

    return FirestoreListener(
      child: Scaffold(
        backgroundColor: colorScheme.surface,
        appBar: AppBar(
        iconTheme: IconThemeData(color: Colors.white),
        leading: Builder(
          builder: (context) => IconButton(
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                const Icon(Icons.menu, color: Colors.white),
                if (hasConnectionIssues)
                  Positioned(
                    right: -2,
                    top: -2,
                    child: Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        color: colorScheme.error,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: appBarBackgroundColor,
                          width: 1.5,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            onPressed: () => Scaffold.of(context).openDrawer(),
          ),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset(
              appTheme.logoIcon,
              height: 30,
            ),
            const SizedBox(width: 10),
            Text(
              '${appTheme.name} Agents',
              style: currentThemeData.appBarTheme.titleTextStyle?.copyWith(color: Colors.white) ??
                   textTheme.titleLarge?.copyWith(color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        backgroundColor: appBarBackgroundColor,
        elevation: currentThemeData.appBarTheme.elevation ?? 2.0,
      ),
      drawer: const AppDrawer(),
      body: Column(
        children: [
          // Expired connection banner
          const DismissibleExpiredConnectionBanner(),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(top: 24.0, left: 24.0, right: 24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
            Text(
              'Your AI Agents',
              style: textTheme.displaySmall?.copyWith( 
                color: colorScheme.onSurface,
                fontWeight: FontWeight.w600, 
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Manage and interact with your configured agents.',
              style: textTheme.bodyLarge?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16), 
            Divider(
              color: colorScheme.outlineVariant.withValues(alpha: 0.5),
              height: 1,
            ),
            const SizedBox(height: 24), 
            Expanded(
              child: agentsAsyncValue.when(
                data: (agents) {
                  if (agents.isEmpty) {
                    return Center(
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 32.0, vertical: 48.0),
                        decoration: BoxDecoration(
                          color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
                          borderRadius: BorderRadius.circular(12.0),
                          border: Border.all(
                            color: colorScheme.outlineVariant.withValues(alpha: 0.5),
                            width: 1,
                          ),
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              Icons.person_search_outlined, 
                              size: 64, 
                              color: colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
                            ),
                            const SizedBox(height: 24),
                            Text(
                              'No Agents Yet', 
                              style: textTheme.headlineSmall?.copyWith(
                                color: colorScheme.onSurface,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 12),
                            Text(
                              'Tap the menu and select "Create Agent" to build your first AI assistant.',
                              textAlign: TextAlign.center,
                              style: textTheme.bodyMedium?.copyWith( 
                                color: colorScheme.onSurfaceVariant,
                                height: 1.5, 
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  }
                  return LayoutBuilder(
                    builder: (context, constraints) {
                      int crossAxisCount;
                      if (constraints.maxWidth < 500) {
                        crossAxisCount = 1;
                      } else if (constraints.maxWidth < 800) {
                        crossAxisCount = 2;
                      } else if (constraints.maxWidth < 1100) {
                        crossAxisCount = 3;
                      } else if (constraints.maxWidth < 1400) {
                        crossAxisCount = 4;
                      } else {
                        crossAxisCount = 5;
                      }

                      return GridView.builder(
                        padding: const EdgeInsets.only(bottom: 24.0, top: 8.0),
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: crossAxisCount,
                          crossAxisSpacing: 12.0,
                          mainAxisSpacing: 12.0,
                          childAspectRatio: crossAxisCount == 1 ? (16 / 10) : (4 / 2.8),
                        ),
                        itemCount: agents.length,
                        itemBuilder: (context, index) {
                          final agent = agents[index];
                          return AgentCard(agent: agent);
                        },
                      );
                    },
                  );
                },
                loading: () => Center( 
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      CircularProgressIndicator(
                        valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
                      ),
                      const SizedBox(height: 20),
                      Text(
                        'Loading Agents...',
                        style: textTheme.bodyLarge?.copyWith(color: colorScheme.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
                error: (err, stack) { 
                  // Use automatic error detection and handling
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    handleAutoError(err, ref, serviceErrorMessage: 'Failed to load agents');
                  });
                  
                  // Check if this is an authentication error to show appropriate UI
                  final appError = err is Exception ? AppError.fromException(err) : null;
                  if (appError?.type == ErrorType.authentication) {
                    // Show loading while redirecting to login
                    return const Center(
                      child: CircularProgressIndicator(),
                    );
                  }
                  
                  // Show a fallback UI with retry button for other errors
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 40.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.refresh,
                            size: 64,
                            color: colorScheme.primary,
                          ),
                          const SizedBox(height: 20),
                          Text(
                            'Unable to Load Agents',
                            style: textTheme.headlineSmall?.copyWith(
                              color: colorScheme.onSurface,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Tap below to try again',
                            textAlign: TextAlign.center,
                            style: textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(height: 20),
                          ElevatedButton.icon(
                            icon: const Icon(Icons.refresh),
                            label: const Text('Retry'),
                            onPressed: () {
                              ref.invalidate(agentsProvider);
                            },
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
                ],
              ),
            ),
          ),
        ],
      ),
      ),
    );
  }
}
