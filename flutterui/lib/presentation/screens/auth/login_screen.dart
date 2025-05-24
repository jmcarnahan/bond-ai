import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart'; // Ensure this path is correct
import 'package:flutterui/core/theme/app_theme.dart'; // Import AppTheme
import 'package:flutterui/main.dart'; // Import appTheme provider

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authNotifierProvider);
    final currentTheme = ref.watch(appThemeProvider); // Get current theme
    final themeData = Theme.of(context); // More convenient access to theme data

    // Listen to the auth state for navigation or error messages
    ref.listen<AuthState>(authNotifierProvider, (previous, next) {
      if (next is AuthError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Login Error: ${next.error}')),
        );
      }
    });

    return Scaffold(
      backgroundColor: themeData.colorScheme.surface, // Use light grey from theme
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 400),
          child: Card(
            elevation: 4.0, // Add a bit more shadow to the card
            margin: const EdgeInsets.all(20.0),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 32.0), // Increased padding
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                mainAxisSize: MainAxisSize.min, // Important for Card sizing
                children: <Widget>[
                  Image.asset(
                    'assets/mcafee_logo.png', // Directly use asset with custom height
                    height: 80, // Increased logo size
                  ),
                  const SizedBox(height: 30), // Increased space
                  Text(
                    'Welcome to ${currentTheme.name}',
                    textAlign: TextAlign.center,
                    style: themeData.textTheme.headlineMedium?.copyWith(
                      color: themeData.colorScheme.onSurface, // Ensure text color contrasts with card
                    ),
                  ),
                  const SizedBox(height: 40), // Increased space
                  if (authState is AuthLoading)
                    const Center(child: CircularProgressIndicator())
                  else
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: Colors.black87,
                        padding: const EdgeInsets.symmetric(vertical: 15), // Slightly taller button
                        textStyle: const TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w600), // Slightly bolder text
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8.0), // More rounded corners
                          side: BorderSide(color: Colors.grey.shade300), // Lighter border
                        ),
                        elevation: 2.0, // Standard elevation for such buttons
                      ),
                      onPressed: () {
                        ref.read(authNotifierProvider.notifier).initiateLogin();
                      },
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: <Widget>[
                          Image.asset(
                            'assets/google_logo.png',
                            height: 24.0, // Keep Google logo size standard
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
                          color: themeData.colorScheme.error, // Use error color from theme
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
