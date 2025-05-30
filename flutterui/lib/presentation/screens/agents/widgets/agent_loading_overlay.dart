import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';

class AgentLoadingOverlay extends StatelessWidget {
  final bool isVisible;

  const AgentLoadingOverlay({
    super.key,
    required this.isVisible,
  });

  @override
  Widget build(BuildContext context) {
    if (!isVisible) return const SizedBox.shrink();

    return Container(
      color: Colors.black.withOpacity(0.3),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            SizedBox(height: AppSpacing.xl),
            const Text(
              'Saving agent...',
              style: TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }
}