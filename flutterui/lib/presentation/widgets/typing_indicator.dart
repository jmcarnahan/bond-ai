import 'package:flutter/material.dart';
import 'dart:async';

class TypingIndicator extends StatefulWidget {
  final Color? dotColor;
  final double dotSize;

  const TypingIndicator({
    super.key,
    this.dotColor,
    this.dotSize = 8.0,
  });

  @override
  State<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<TypingIndicator>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  Timer? _timer;
  int _dotCount = 0;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600), // Reduced overall duration, though timer is main driver
    )..repeat();

    _timer = Timer.periodic(const Duration(milliseconds: 200), (timer) { // Reduced dot interval
      if (!mounted) {
        timer.cancel();
        return;
      }
      setState(() {
        _dotCount = (_dotCount + 1) % 4; // 0, 1, 2, 3 (0 means no dots)
      });
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _animationController.dispose();
    super.dispose();
  }

  Widget _buildDot(int index, Color color) {
    return Container(
      width: widget.dotSize,
      height: widget.dotSize,
      margin: const EdgeInsets.symmetric(horizontal: 2.0),
      decoration: BoxDecoration(
        color: index < _dotCount ? color : Colors.transparent,
        shape: BoxShape.circle,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final dotColor = widget.dotColor ?? Theme.of(context).colorScheme.onSurfaceVariant.withOpacity(0.7);
    return SizedBox(
      height: widget.dotSize * 2.5, // Provide some vertical space
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: List.generate(3, (index) => _buildDot(index, dotColor)),
      ),
    );
  }
}
