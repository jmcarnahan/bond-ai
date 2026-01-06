import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/core_providers.dart';
import '../../../core/utils/logger.dart';
import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen>
    with ErrorHandlingMixin, TickerProviderStateMixin {
  List<Map<String, dynamic>> _providers = [];
  bool _loadingProviders = true;
  late AnimationController _fadeController;
  late AnimationController _logoController;
  late Animation<double> _fadeAnimation;
  late Animation<double> _logoAnimation;
  bool _isHovering = false;

  @override
  void initState() {
    super.initState();
    _loadProviders();

    // Initialize animations
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    );

    _logoController = AnimationController(
      duration: const Duration(seconds: 2),
      vsync: this,
    );

    _fadeAnimation = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeInOut,
    );

    _logoAnimation = CurvedAnimation(
      parent: _logoController,
      curve: Curves.easeInOut,
    );

    _fadeController.forward();
    _logoController.repeat(reverse: true);
  }

  @override
  void dispose() {
    _fadeController.dispose();
    _logoController.dispose();
    super.dispose();
  }

  Future<void> _loadProviders() async {
    try {
      final providers =
          await ref.read(authNotifierProvider.notifier).getAvailableProviders();
      logger.i(
        '[LoginScreen] Loaded auth providers: ${providers.length} -> ${providers.map((p) => p['name']).join(', ')}',
      );
      if (mounted) {
        setState(() {
          _providers = providers;
          _loadingProviders = false;
        });
      }
    } catch (e) {
      if (mounted) {
        handleServiceError(
          e,
          ref,
          customMessage: 'Failed to load auth providers',
        );
        setState(() {
          _providers = [
            {
              'name': 'google',
              'login_url': '/login/google',
              'callback_url': '/auth/google/callback',
            },
          ];
          _loadingProviders = false;
        });
      }
    }
  }

  Widget _buildProviderButton(
    Map<String, dynamic> provider,
    AuthState authState,
    AppTheme appTheme,
  ) {
    final providerName = provider['name'] as String;
    final isLoading = authState is AuthLoading;

    // Get provider-specific details
    String displayName;
    String? iconPath;
    Color? backgroundColor;
    Color? textColor;

    switch (providerName.toLowerCase()) {
      case 'google':
        displayName = 'Sign in with Google';
        iconPath = 'assets/google_logo.png';
        break;
      case 'okta':
        displayName = 'Sign in with Okta';
        backgroundColor = const Color(0xFF007DC1); // Okta blue
        textColor = Colors.white;
        break;
      default:
        displayName = 'Sign in with ${providerName[0].toUpperCase()}${providerName.substring(1)}';
        break;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: MouseRegion(
        onEnter: (_) => setState(() => _isHovering = true),
        onExit: (_) => setState(() => _isHovering = false),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          transform: Matrix4.identity()..scale(_isHovering ? 1.02 : 1.0),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(28.0),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: _isHovering ? 0.3 : 0.2),
                  blurRadius: _isHovering ? 12 : 8,
                  offset: Offset(0, _isHovering ? 6 : 4),
                ),
              ],
            ),
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: backgroundColor ?? appTheme.themeData.colorScheme.surface,
                foregroundColor: textColor ?? appTheme.themeData.colorScheme.onSurface,
                padding: const EdgeInsets.symmetric(
                  vertical: 16,
                  horizontal: 32,
                ),
                minimumSize: const Size(double.infinity, 56),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(28.0),
                  side: BorderSide(
                    color: appTheme.themeData.dividerColor.withValues(alpha: 0.2),
                    width: 1,
                  ),
                ),
                elevation: 0,
              ),
              onPressed:
                  isLoading
                      ? null
                      : () {
                        ref
                            .read(authNotifierProvider.notifier)
                            .initiateLogin(provider: providerName);
                      },
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: <Widget>[
                  if (iconPath != null) ...[
                    Image.asset(
                      iconPath,
                      height: 24.0,
                      width: 24.0,
                      errorBuilder: (context, error, stackTrace) {
                        // Fallback if icon not found
                        return Icon(
                          Icons.login,
                          size: 24.0,
                          color: textColor ?? appTheme.themeData.colorScheme.onSurface,
                        );
                      },
                    ),
                    const SizedBox(width: 16),
                  ] else ...[
                    Icon(
                      Icons.login,
                      size: 24.0,
                      color: textColor ?? appTheme.themeData.colorScheme.onSurface,
                    ),
                    const SizedBox(width: 16),
                  ],
                  Text(
                    displayName,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.5,
                      color: textColor ?? appTheme.themeData.colorScheme.onSurface,
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

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authNotifierProvider);
    final appTheme = ref.watch(appThemeProvider);

    ref.listen<AuthState>(authNotifierProvider, (previous, next) {
      if (next is AuthError) {
        handleServiceError(next.error, ref, customMessage: 'Login failed');
      }
    });

    return Scaffold(
      body: Stack(
        children: [
          // Subtle gradient background
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  appTheme.themeData.colorScheme.surface,
                  appTheme.themeData.colorScheme.surface.withValues(alpha: 0.95),
                  appTheme.themeData.colorScheme.surfaceContainerHighest,
                ],
              ),
            ),
          ),

          // Subtle geometric pattern overlay
          Positioned.fill(
            child: CustomPaint(painter: GeometricPatternPainter(opacity: 0.03)),
          ),

          // Accent bar at top
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: Container(
              height: 4,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    appTheme.themeData.colorScheme.primary.withValues(alpha: 0.6),
                    appTheme.themeData.colorScheme.primary,
                    appTheme.themeData.colorScheme.primary.withValues(alpha: 0.6),
                  ],
                ),
              ),
            ),
          ),

          // Main content
          SafeArea(
            top: false,
            child: FadeTransition(
              opacity: _fadeAnimation,
              child: Column(
                children: [
                  Expanded(
                    child: Center(
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.symmetric(horizontal: 24.0),
                        child: Container(
                          constraints: const BoxConstraints(maxWidth: 400),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const SizedBox(height: 80), // Top spacing
                              // Animated logo with glow effect
                              AnimatedBuilder(
                                animation: _logoAnimation,
                                builder: (context, child) {
                                  return Container(
                                    padding: const EdgeInsets.all(24),
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color:
                                          appTheme
                                              .themeData
                                              .colorScheme
                                              .surface,
                                      boxShadow: [
                                        BoxShadow(
                                          color: appTheme
                                              .themeData
                                              .colorScheme
                                              .primary
                                              .withValues(
                                                alpha: 0.2 * _logoAnimation.value,
                                              ),
                                          blurRadius: 30,
                                          spreadRadius: 5,
                                        ),
                                        BoxShadow(
                                          color: Colors.black.withValues(alpha: 0.1),
                                          blurRadius: 10,
                                          offset: const Offset(0, 4),
                                        ),
                                      ],
                                    ),
                                    child: Image.asset(
                                      appTheme.logo,
                                      height: 100,
                                    ),
                                  );
                                },
                              ),

                              const SizedBox(
                                height: 64,
                              ), // Logo to text spacing
                              // Welcome text
                              Text(
                                'Welcome to ${appTheme.name}',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color:
                                      appTheme.themeData.colorScheme.onSurface,
                                  fontSize: 28,
                                  fontWeight: FontWeight.w600,
                                  letterSpacing: 1.2,
                                ),
                              ),

                              const SizedBox(height: 8),

                              // Tagline
                              Text(
                                appTheme.brandingMessage,
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color:
                                      appTheme
                                          .themeData
                                          .colorScheme
                                          .onSurfaceVariant,
                                  fontSize: 16,
                                  fontWeight: FontWeight.w400,
                                  letterSpacing: 0.5,
                                ),
                              ),

                              const SizedBox(
                                height: 64,
                              ), // Text to button spacing
                              // Auth content
                              if (authState is AuthLoading || _loadingProviders)
                                AnimatedBuilder(
                                  animation: _logoAnimation,
                                  builder: (context, child) {
                                    return CircularProgressIndicator(
                                      valueColor: AlwaysStoppedAnimation<Color>(
                                        appTheme.themeData.colorScheme.primary,
                                      ),
                                    );
                                  },
                                )
                              else
                                ..._providers.map(
                                      (provider) => _buildProviderButton(
                                        provider,
                                        authState,
                                        appTheme,
                                      ),
                                    ),

                              const SizedBox(height: 24),

                              // Security badge
                              Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.lock_outline,
                                    size: 16,
                                    color:
                                        appTheme
                                            .themeData
                                            .colorScheme
                                            .onSurfaceVariant,
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'Secured by ${appTheme.name}',
                                    style: TextStyle(
                                      color:
                                          appTheme
                                              .themeData
                                              .colorScheme
                                              .onSurfaceVariant,
                                      fontSize: 12,
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                ],
                              ),

                              const SizedBox(height: 32),

                              // Error message
                              if (authState is Unauthenticated &&
                                  authState.message != null)
                                Container(
                                  padding: const EdgeInsets.all(16.0),
                                  decoration: BoxDecoration(
                                    color: appTheme.themeData.colorScheme.error
                                        .withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(12.0),
                                    border: Border.all(
                                      color: appTheme
                                          .themeData
                                          .colorScheme
                                          .error
                                          .withValues(alpha: 0.3),
                                      width: 1,
                                    ),
                                  ),
                                  child: Text(
                                    authState.message!,
                                    textAlign: TextAlign.center,
                                    style: TextStyle(
                                      color:
                                          appTheme.themeData.colorScheme.error,
                                      fontSize: 14,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ),

                              const SizedBox(height: 80), // Bottom spacing
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),

                  // Footer
                  Container(
                    padding: const EdgeInsets.symmetric(
                      vertical: 24,
                      horizontal: 24,
                    ),
                    child: Column(
                      children: [
                        Text(
                          '(c) ${DateTime.now().year} ${appTheme.name}. All rights reserved.',
                          style: TextStyle(
                            color:
                                appTheme
                                    .themeData
                                    .colorScheme
                                    .onSurfaceVariant,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            _buildFooterLink('Privacy Policy'),
                            Container(
                              margin: const EdgeInsets.symmetric(
                                horizontal: 16,
                              ),
                              width: 1,
                              height: 12,
                              color: appTheme.themeData.dividerColor,
                            ),
                            _buildFooterLink('Terms of Service'),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooterLink(String text) {
    final appTheme = ref.watch(appThemeProvider);

    return InkWell(
      onTap: () {
        // Handle link tap
      },
      child: Text(
        text,
        style: TextStyle(
          color: appTheme.themeData.colorScheme.primary,
          fontSize: 12,
          decoration: TextDecoration.underline,
        ),
      ),
    );
  }
}

// Custom painter for geometric pattern
class GeometricPatternPainter extends CustomPainter {
  final double opacity;

  GeometricPatternPainter({required this.opacity});

  @override
  void paint(Canvas canvas, Size size) {
    final paint =
        Paint()
          ..color = Colors.white.withValues(alpha: opacity)
          ..strokeWidth = 1
          ..style = PaintingStyle.stroke;

    // Draw hexagonal pattern
    const double hexSize = 50;
    const double hexHeight = hexSize * 1.732;

    for (double y = 0; y < size.height + hexHeight; y += hexHeight * 0.75) {
      for (double x = 0; x < size.width + hexSize * 2; x += hexSize * 3) {
        final offsetX = (y % (hexHeight * 1.5) == 0) ? 0.0 : hexSize * 1.5;
        _drawHexagon(canvas, Offset(x + offsetX, y), hexSize, paint);
      }
    }
  }

  void _drawHexagon(Canvas canvas, Offset center, double size, Paint paint) {
    final path = Path();
    for (int i = 0; i < 6; i++) {
      final angle = (i * 60 - 30) * 3.14159 / 180;
      final x = center.dx + size * cos(angle);
      final y = center.dy + size * sin(angle);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    path.close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
