import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/chat/widgets/image_message_widget.dart';

void main() {
  group('ImageMessageWidget Tests', () {
    String createValidBase64Image() {
      final List<int> imageBytes = [
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0x57, 0x63, 0xF8, 0x0F, 0x00, 0x00,
        0x01, 0x00, 0x01, 0x14, 0x6D, 0xD3, 0x8D, 0xB0,
        0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
        0xAE, 0x42, 0x60, 0x82
      ];
      return base64Encode(imageBytes);
    }

    Widget createTestWidget({
      required String base64ImageData,
      double? maxWidth,
      double? maxHeight,
    }) {
      return MaterialApp(
        home: Scaffold(
          body: ImageMessageWidget(
            base64ImageData: base64ImageData,
            maxWidth: maxWidth,
            maxHeight: maxHeight,
          ),
        ),
      );
    }

    testWidgets('should display image with valid base64 data', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      expect(find.byType(Image), findsOneWidget);
      expect(find.byType(Container), findsOneWidget);
      expect(find.byType(ClipRRect), findsOneWidget);
      expect(find.byType(GestureDetector), findsOneWidget);
    });

    testWidgets('should display error message with invalid base64 data', (tester) async {
      await tester.pumpWidget(createTestWidget(base64ImageData: 'invalid_base64'));

      expect(find.text('Invalid image data'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.byType(Container), findsOneWidget);
    });

    testWidgets('should apply default constraints when no dimensions specified', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      final container = tester.widget<Container>(find.byType(Container));
      final constraints = container.constraints!;
      expect(constraints.maxWidth, equals(300));
      expect(constraints.maxHeight, equals(300));
    });

    testWidgets('should apply custom constraints when dimensions specified', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(
        base64ImageData: validBase64,
        maxWidth: 200,
        maxHeight: 150,
      ));

      final container = tester.widget<Container>(find.byType(Container));
      final constraints = container.constraints!;
      expect(constraints.maxWidth, equals(200));
      expect(constraints.maxHeight, equals(150));
    });

    testWidgets('should apply correct border radius', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      final clipRRect = tester.widget<ClipRRect>(find.byType(ClipRRect));
      expect(clipRRect.borderRadius, equals(BorderRadius.circular(8.0)));
    });

    testWidgets('should open fullscreen dialog when tapped', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      expect(find.byType(Dialog), findsOneWidget);
      expect(find.byType(InteractiveViewer), findsOneWidget);
      expect(find.byIcon(Icons.close), findsOneWidget);
    });

    testWidgets('should close fullscreen dialog when close button tapped', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      expect(find.byType(Dialog), findsOneWidget);

      await tester.tap(find.byIcon(Icons.close));
      await tester.pumpAndSettle();

      expect(find.byType(Dialog), findsNothing);
    });

    testWidgets('should handle empty base64 string', (tester) async {
      await tester.pumpWidget(createTestWidget(base64ImageData: ''));

      expect(find.text('Invalid image data'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should apply correct image fit', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      final image = tester.widget<Image>(find.byType(Image));
      expect(image.fit, equals(BoxFit.contain));
    });

    testWidgets('should handle error state correctly', (tester) async {
      await tester.pumpWidget(createTestWidget(base64ImageData: 'invalid'));

      final errorContainer = tester.widget<Container>(find.byType(Container));
      final decoration = errorContainer.decoration as BoxDecoration;
      expect(decoration.borderRadius, equals(BorderRadius.circular(8.0)));
      expect(decoration.color, equals(Colors.grey.shade200));
    });

    testWidgets('should display fullscreen image with correct properties', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      final dialog = tester.widget<Dialog>(find.byType(Dialog));
      expect(dialog.backgroundColor, equals(Colors.black));

      final fullscreenImage = tester.widget<Image>(find.byType(Image).last);
      expect(fullscreenImage.fit, equals(BoxFit.contain));
    });

    testWidgets('should handle dialog barrier dismissible correctly', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      expect(find.byType(Dialog), findsOneWidget);

      await tester.tapAt(const Offset(10, 10));
      await tester.pumpAndSettle();

      expect(find.byType(Dialog), findsNothing);
    });

    testWidgets('should work with different screen sizes', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      expect(find.byType(Image), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.byType(Image), findsOneWidget);

      addTearDown(() {
        tester.binding.setSurfaceSize(const Size(800, 600));
      });
    });

    testWidgets('should handle very small dimensions', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(
        base64ImageData: validBase64,
        maxWidth: 50,
        maxHeight: 50,
      ));

      final container = tester.widget<Container>(find.byType(Container));
      final constraints = container.constraints!;
      expect(constraints.maxWidth, equals(50));
      expect(constraints.maxHeight, equals(50));
    });

    testWidgets('should handle very large dimensions', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(
        base64ImageData: validBase64,
        maxWidth: 1000,
        maxHeight: 1000,
      ));

      final container = tester.widget<Container>(find.byType(Container));
      final constraints = container.constraints!;
      expect(constraints.maxWidth, equals(1000));
      expect(constraints.maxHeight, equals(1000));
    });

    testWidgets('should maintain proper layout structure', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      expect(find.byType(Container), findsOneWidget);
      expect(find.byType(ClipRRect), findsOneWidget);
      expect(find.byType(GestureDetector), findsOneWidget);
      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('should handle corrupted PNG data gracefully', (tester) async {
      final corruptedData = base64Encode([0x89, 0x50, 0x4E, 0x47, 0x00, 0x00]);
      
      await tester.pumpWidget(createTestWidget(base64ImageData: corruptedData));

      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('should work in different container layouts', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                Container(height: 100),
                ImageMessageWidget(base64ImageData: validBase64),
                Container(height: 100),
              ],
            ),
          ),
        ),
      );

      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('should handle animation frame builder correctly', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      final image = tester.widget<Image>(find.byType(Image));
      expect(image.frameBuilder, isNotNull);
    });

    testWidgets('should handle error builder correctly', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      final image = tester.widget<Image>(find.byType(Image));
      expect(image.errorBuilder, isNotNull);
    });

    testWidgets('should position close button correctly in fullscreen', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      final positioned = tester.widget<Positioned>(find.byType(Positioned));
      expect(positioned.top, equals(16));
      expect(positioned.right, equals(16));
    });

    testWidgets('should style close button correctly', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      final closeIcon = tester.widget<Icon>(find.byIcon(Icons.close));
      expect(closeIcon.color, equals(Colors.white));
      expect(closeIcon.size, equals(30));
    });

    testWidgets('should handle accessibility requirements', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      expect(find.byType(GestureDetector), findsOneWidget);
      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('should handle asymmetric dimensions', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(
        base64ImageData: validBase64,
        maxWidth: 400,
        maxHeight: 100,
      ));

      final container = tester.widget<Container>(find.byType(Container));
      final constraints = container.constraints!;
      expect(constraints.maxWidth, equals(400));
      expect(constraints.maxHeight, equals(100));
    });

    testWidgets('should handle partial base64 padding', (tester) async {
      const partialBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg';
      
      await tester.pumpWidget(createTestWidget(base64ImageData: partialBase64));

      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('should handle special characters in base64', (tester) async {
      const specialChars = 'ABC+/123=';
      
      await tester.pumpWidget(createTestWidget(base64ImageData: specialChars));

      expect(find.text('Invalid image data'), findsOneWidget);
    });

    testWidgets('should handle dialog navigation correctly', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      expect(find.byType(Dialog), findsOneWidget);

      final navigator = tester.state<NavigatorState>(find.byType(Navigator));
      expect(navigator.canPop(), isTrue);

      await tester.tap(find.byIcon(Icons.close));
      await tester.pumpAndSettle();

      expect(find.byType(Dialog), findsNothing);
    });

    testWidgets('should maintain interactive viewer functionality', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      expect(find.byType(InteractiveViewer), findsOneWidget);
      
      final interactiveViewer = tester.widget<InteractiveViewer>(find.byType(InteractiveViewer));
      expect(interactiveViewer.child, isA<Image>());
    });

    testWidgets('should handle stack layout correctly in fullscreen', (tester) async {
      final validBase64 = createValidBase64Image();
      
      await tester.pumpWidget(createTestWidget(base64ImageData: validBase64));

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      expect(find.byType(Stack), findsOneWidget);
      expect(find.byType(Center), findsOneWidget);
      expect(find.byType(Positioned), findsOneWidget);
    });

    testWidgets('should handle long base64 strings', (tester) async {
      final longBase64 = createValidBase64Image() * 10;
      
      await tester.pumpWidget(createTestWidget(base64ImageData: longBase64));

      expect(find.text('Invalid image data'), findsOneWidget);
    });

    testWidgets('should maintain error styling consistency', (tester) async {
      await tester.pumpWidget(createTestWidget(base64ImageData: 'invalid'));

      expect(find.text('Invalid image data'), findsOneWidget);
      
      final errorText = tester.widget<Text>(find.text('Invalid image data'));
      expect(errorText.style?.color, equals(Colors.grey));
      expect(errorText.style?.fontSize, equals(12));
    });
  });
}