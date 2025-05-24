import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/main.dart';
import 'package:flutterui/core/theme/mcafee_theme.dart'; // Import for CustomColors

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authNotifierProvider);
    final appTheme = ref.watch(appThemeProvider); // Renamed for clarity from currentTheme
    final themeData = Theme.of(context);
    // Access custom colors. Ensure CustomColors is part of your theme extensions.
    final customColors = themeData.extension<CustomColors>();
    final brandingSurfaceColor = customColors?.brandingSurface ?? McAfeeTheme.mcafeeDarkBrandingSurface; // Fallback

    ref.listen<AuthState>(authNotifierProvider, (previous, next) {
      if (next is AuthError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Login Error: ${next.error}')),
        );
      }
    });

    // Define the content of the login form
    Widget loginFormContent = Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Image.asset(
          appTheme.logo, // Use appTheme
          height: 80,
        ),
        const SizedBox(height: 30),
        Text(
          'Welcome to ${appTheme.name}', // Use appTheme
          textAlign: TextAlign.center,
          style: themeData.textTheme.headlineMedium?.copyWith(
            color: themeData.colorScheme.onSurface,
          ),
        ),
        const SizedBox(height: 40),
        if (authState is AuthLoading)
          const Center(child: CircularProgressIndicator())
        else
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: Colors.black87,
              padding: const EdgeInsets.symmetric(vertical: 15),
              textStyle:
                  const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8.0),
                side: BorderSide(color: Colors.grey.shade300),
              ),
              elevation: 2.0,
            ),
            onPressed: () {
              ref.read(authNotifierProvider.notifier).initiateLogin();
            },
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: <Widget>[
                Image.asset(
                  'assets/google_logo.png',
                  height: 24.0,
                  width: 24.0,
                ),
                const SizedBox(width: 12),
                const Text(
                  'Sign in with Google',
                  style: TextStyle(color: Colors.black87),
                ),
              ],
            ),
          ),
        const SizedBox(height: 20),
        if (authState is Unauthenticated && authState.message != null)
          Padding(
            padding: const EdgeInsets.only(top: 8.0),
            child: Text(
              authState.message!,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: themeData.colorScheme.error,
              ),
            ),
          ),
      ],
    );

    // Card widget for the login form
    Widget loginFormCard = Card(
      elevation: 4.0,
      margin: EdgeInsets.zero, // Margin handled by parent container in two-column
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12.0)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32.0, vertical: 48.0),
        child: loginFormContent,
      ),
    );

    return Scaffold(
      backgroundColor: themeData.colorScheme.surface,
      body: LayoutBuilder(
        builder: (context, constraints) {
          const double breakpoint = 768.0;

          if (constraints.maxWidth < breakpoint) {
            // Narrow screen layout (single column, centered card)
            return Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 400),
                child: SingleChildScrollView( // Ensure content scrolls if too tall
                  padding: const EdgeInsets.all(20.0),
                  child: Card( // Re-carding for mobile view with its own margin
                    elevation: 4.0,
                    margin: const EdgeInsets.all(0), // Padding handled by SingleChildScrollView
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12.0)),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 32.0),
                      child: loginFormContent, // Use the extracted content
                    ),
                  ),
                ),
              ),
            );
          } else {
            // Wide screen layout (two columns)
            return Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1100, maxHeight: 700), // Max height for the card
                child: Card( // Outer card for the two-column effect with shadow
                  elevation: 6.0,
                  margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 32), // Margin for the whole 2-col layout
                  clipBehavior: Clip.antiAlias, // Ensures Row children respect Card's rounded corners
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16.0)),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      Expanded(
                        flex: 2,
                        child: Container(
                          color: brandingSurfaceColor, // Use themed branding color
                          padding: const EdgeInsets.symmetric(horizontal: 32.0, vertical: 48.0),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: <Widget>[
                              Image.asset(
                                appTheme.logo, // Use appTheme
                                height: 120,
                              ),
                              const SizedBox(height: 24),
                              Text(
                                appTheme.brandingMessage, // Use appTheme
                                textAlign: TextAlign.center,
                                style: themeData.textTheme.titleLarge?.copyWith(
                                  color: Colors.white, // Text on dark branding panel
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      Expanded(
                        flex: 3,
                        child: Container(
                          color: themeData.colorScheme.background,
                          padding: const EdgeInsets.symmetric(horizontal: 32.0, vertical: 24.0),
                          child: Center(
                            child: ConstrainedBox(
                              constraints: const BoxConstraints(maxWidth: 400),
                              child: SingleChildScrollView(
                                child: loginFormCard,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          }
        },
      ),
    );
  }
}
