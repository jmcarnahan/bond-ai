import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart'; // Ensure this path is correct

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authNotifierProvider);
    // Listen to the auth state for navigation or error messages that are not part of the main UI
    ref.listen<AuthState>(authNotifierProvider, (previous, next) {
      if (next is AuthError) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Login Error: ${next.error}')));
      }
      // Navigation to HomeScreen upon successful authentication will be handled
      // by the logic in main.dart or a root wrapper widget.
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Login to BondAI')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Text(
                'Welcome to BondAI',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 30),
              if (authState is AuthLoading)
                const Center(child: CircularProgressIndicator())
              else
                ElevatedButton.icon(
                  icon: const Icon(
                    Icons.login,
                  ), // Placeholder, could be Google icon
                  label: const Text('Login with Google'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 15),
                    textStyle: const TextStyle(fontSize: 18),
                  ),
                  onPressed: () {
                    ref.read(authNotifierProvider.notifier).initiateLogin();
                  },
                ),
              const SizedBox(height: 20),
              if (authState is Unauthenticated && authState.message != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8.0),
                  child: Text(
                    authState.message!,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
