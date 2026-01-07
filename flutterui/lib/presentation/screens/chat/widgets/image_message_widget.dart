import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';

class ImageMessageWidget extends StatelessWidget {
  final String base64ImageData;
  final double? maxWidth;
  final double? maxHeight;

  const ImageMessageWidget({
    super.key,
    required this.base64ImageData,
    this.maxWidth,
    this.maxHeight,
  });

  @override
  Widget build(BuildContext context) {
    try {
      final Uint8List imageBytes = base64Decode(base64ImageData);

      return Container(
        constraints: BoxConstraints(
          maxWidth: maxWidth ?? 300,
          maxHeight: maxHeight ?? 300,
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(8.0),
          child: GestureDetector(
            onTap: () => _showFullScreenImage(context, imageBytes),
            child: Image.memory(
              imageBytes,
              fit: BoxFit.contain,
              frameBuilder: (context, child, frame, wasSynchronouslyLoaded) {
                if (wasSynchronouslyLoaded) return child;
                return AnimatedOpacity(
                  opacity: frame == null ? 0 : 1,
                  duration: const Duration(milliseconds: 200),
                  curve: Curves.easeOut,
                  child: child,
                );
              },
              errorBuilder: (context, error, stackTrace) {
                return Container(
                  width: 200,
                  height: 100,
                  decoration: BoxDecoration(
                    color: Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(8.0),
                    border: Border.all(color: Colors.grey.shade300),
                  ),
                  child: const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.broken_image, color: Colors.grey, size: 32),
                        SizedBox(height: 4),
                        Text(
                          'Failed to load image',
                          style: TextStyle(color: Colors.grey, fontSize: 12),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      );
    } catch (e) {
      // Handle base64 decode errors
      return Container(
        width: 200,
        height: 100,
        decoration: BoxDecoration(
          color: Colors.grey.shade200,
          borderRadius: BorderRadius.circular(8.0),
        ),
        child: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error_outline, color: Colors.grey),
              SizedBox(height: 4),
              Text(
                'Invalid image data',
                style: TextStyle(color: Colors.grey, fontSize: 12),
              ),
            ],
          ),
        ),
      );
    }
  }

  void _showFullScreenImage(BuildContext context, Uint8List imageBytes) {
    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (BuildContext context) {
        return Dialog(
          backgroundColor: Colors.black,
          child: Stack(
            children: [
              Center(
                child: InteractiveViewer(
                  child: Image.memory(
                    imageBytes,
                    fit: BoxFit.contain,
                  ),
                ),
              ),
              Positioned(
                top: 16,
                right: 16,
                child: IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(
                    Icons.close,
                    color: Colors.white,
                    size: 30,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
