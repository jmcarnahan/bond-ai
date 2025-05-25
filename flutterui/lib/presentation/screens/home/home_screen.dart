import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/main.dart'; // Import main.dart to access appThemeProvider
import 'package:flutterui/presentation/widgets/sidebar.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/presentation/widgets/agent_card.dart';
import 'package:flutterui/core/theme/mcafee_theme.dart'; // Import for CustomColors

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final agentsAsyncValue = ref.watch(agentsProvider);
    final appTheme = ref.watch(appThemeProvider);
    
    final ThemeData currentThemeData = Theme.of(context); // Use Theme.of(context) for current theme
    final TextTheme textTheme = currentThemeData.textTheme;
    final ColorScheme colorScheme = currentThemeData.colorScheme;
    final CustomColors? customColors = currentThemeData.extension<CustomColors>();
    final Color appBarBackgroundColor = customColors?.brandingSurface ?? McAfeeTheme.mcafeeDarkBrandingSurface; // Fallback

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        iconTheme: IconThemeData(color: Colors.white), // Ensure drawer icon is visible
        title: Row(
          // mainAxisAlignment: MainAxisAlignment.center, // Keep default (usually start) or adjust as needed
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset(
              appTheme.logoIcon, // Use the logo from the AppTheme interface
              height: 30, // Adjust height as needed
            ),
            const SizedBox(width: 10),
            Text(
              '${appTheme.name} Agents', // App name from AppTheme interface
              style: currentThemeData.appBarTheme.titleTextStyle?.copyWith(color: Colors.white) ??
                   textTheme.titleLarge?.copyWith(color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        backgroundColor: appBarBackgroundColor,
        elevation: currentThemeData.appBarTheme.elevation ?? 2.0,
        // titleTextStyle: themeData.appBarTheme.titleTextStyle?.copyWith(color: Colors.white) ?? textTheme.headlineSmall?.copyWith(color: Colors.white),
      ),
      drawer: const AppSidebar(),
      body: Padding(
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
              color: colorScheme.outlineVariant?.withOpacity(0.5) ?? colorScheme.outline.withOpacity(0.5),
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
                          color: colorScheme.surfaceVariant.withOpacity(0.3),
                          borderRadius: BorderRadius.circular(12.0),
                          border: Border.all(
                            color: colorScheme.outlineVariant?.withOpacity(0.5) ?? colorScheme.outline.withOpacity(0.5),
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
                              color: colorScheme.onSurfaceVariant.withOpacity(0.7),
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
                      if (constraints.maxWidth < 500) { // Adjusted breakpoint
                        crossAxisCount = 1;
                      } else if (constraints.maxWidth < 800) { // Adjusted breakpoint
                        crossAxisCount = 2;
                      } else if (constraints.maxWidth < 1100) { // Adjusted breakpoint
                        crossAxisCount = 3;
                      } else if (constraints.maxWidth < 1400) { // Adjusted breakpoint
                        crossAxisCount = 4;
                      } else {
                        crossAxisCount = 5; // Added a 5th column for very wide screens
                      }

                      return GridView.builder(
                        padding: const EdgeInsets.only(bottom: 24.0, top: 8.0),
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: crossAxisCount,
                          crossAxisSpacing: 12.0, // Reduced spacing
                          mainAxisSpacing: 12.0,  // Reduced spacing
                          childAspectRatio: crossAxisCount == 1 ? (16 / 10) : (4 / 2.8), // Made cards taller
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
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 40.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.error_outline_rounded,
                            size: 80,
                            color: colorScheme.error,
                          ),
                          const SizedBox(height: 20),
                          Text(
                            'Error Loading Agents',
                            style: textTheme.headlineSmall?.copyWith(
                              color: colorScheme.error,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            err.toString(),
                            textAlign: TextAlign.center,
                            style: textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onErrorContainer,
                            ),
                          ),
                          const SizedBox(height: 20),
                          ElevatedButton.icon(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: colorScheme.errorContainer,
                              foregroundColor: colorScheme.onErrorContainer,
                            ),
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
    );
  }
}
