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
  late Animation<double> _animation1;
  late Animation<double> _animation2;
  late Animation<double> _animation3;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat();

    _animation1 = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _animationController,
        curve: const Interval(0.0, 0.6, curve: Curves.easeInOut),
      ),
    );

    _animation2 = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _animationController,
        curve: const Interval(0.2, 0.8, curve: Curves.easeInOut),
      ),
    );

    _animation3 = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _animationController,
        curve: const Interval(0.4, 1.0, curve: Curves.easeInOut),
      ),
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  Widget _buildDot(Animation<double> animation, Color color) {
    return AnimatedBuilder(
      animation: animation,
      builder: (context, child) {
        // Calculate the opacity based on animation value (0.3 to 1.0 range for better visibility)
        final opacity = 0.3 + (0.7 * animation.value);
        return Container(
          width: widget.dotSize,
          height: widget.dotSize,
          margin: const EdgeInsets.symmetric(horizontal: 2.0),
          decoration: BoxDecoration(
            color: color.withValues(alpha: opacity),
            shape: BoxShape.circle,
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final dotColor = widget.dotColor ?? Theme.of(context).colorScheme.onSurfaceVariant;
    return SizedBox(
      height: widget.dotSize * 2.5,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _buildDot(_animation1, dotColor),
          _buildDot(_animation2, dotColor),
          _buildDot(_animation3, dotColor),
        ],
      ),
    );
  }
}
