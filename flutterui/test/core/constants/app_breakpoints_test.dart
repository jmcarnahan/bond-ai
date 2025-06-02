import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/core/constants/app_breakpoints.dart';

Widget _createTestWidget(Widget child, Size size) {
  return MediaQuery(
    data: MediaQueryData(size: size),
    child: MaterialApp(home: child),
  );
}

void main() {
  group('AppBreakpoints Tests', () {
    group('Constants', () {
      test('should have correct breakpoint values', () {
        expect(AppBreakpoints.mobile, equals(480.0));
        expect(AppBreakpoints.tablet, equals(768.0));
        expect(AppBreakpoints.desktop, equals(1024.0));
        expect(AppBreakpoints.wide, equals(1440.0));
        expect(AppBreakpoints.ultraWide, equals(1920.0));
      });

      test('breakpoints should be in ascending order', () {
        expect(AppBreakpoints.mobile < AppBreakpoints.tablet, isTrue);
        expect(AppBreakpoints.tablet < AppBreakpoints.desktop, isTrue);
        expect(AppBreakpoints.desktop < AppBreakpoints.wide, isTrue);
        expect(AppBreakpoints.wide < AppBreakpoints.ultraWide, isTrue);
      });
    });

    group('Device Detection', () {
      testWidgets('isMobile should detect mobile screens correctly', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isMobile(context), isTrue);
            return Container();
          }),
          const Size(400, 800),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isMobile(context), isFalse);
            return Container();
          }),
          const Size(800, 600),
        ));
      });

      testWidgets('isTablet should detect tablet screens correctly', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isTablet(context), isTrue);
            return Container();
          }),
          const Size(800, 600),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isTablet(context), isFalse);
            return Container();
          }),
          const Size(400, 800),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isTablet(context), isFalse);
            return Container();
          }),
          const Size(1200, 800),
        ));
      });

      testWidgets('isDesktop should detect desktop screens correctly', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isDesktop(context), isTrue);
            return Container();
          }),
          const Size(1200, 800),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isDesktop(context), isFalse);
            return Container();
          }),
          const Size(600, 800),
        ));
      });

      testWidgets('isWide should detect wide screens correctly', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isWide(context), isTrue);
            return Container();
          }),
          const Size(1600, 1000),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isWide(context), isFalse);
            return Container();
          }),
          const Size(1200, 800),
        ));
      });

      testWidgets('isUltraWide should detect ultra-wide screens correctly', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isUltraWide(context), isTrue);
            return Container();
          }),
          const Size(2000, 1200),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isUltraWide(context), isFalse);
            return Container();
          }),
          const Size(1600, 1000),
        ));
      });
    });

    group('Combination Detection', () {
      testWidgets('isMobileOrTablet should work correctly', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isMobileOrTablet(context), isTrue);
            return Container();
          }),
          const Size(400, 800),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isMobileOrTablet(context), isTrue);
            return Container();
          }),
          const Size(800, 600),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isMobileOrTablet(context), isFalse);
            return Container();
          }),
          const Size(1200, 800),
        ));
      });

      testWidgets('isTabletOrDesktop should work correctly', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isTabletOrDesktop(context), isFalse);
            return Container();
          }),
          const Size(400, 800),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isTabletOrDesktop(context), isTrue);
            return Container();
          }),
          const Size(800, 600),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isTabletOrDesktop(context), isTrue);
            return Container();
          }),
          const Size(1200, 800),
        ));
      });
    });

    group('Responsive Methods', () {
      testWidgets('responsive should return correct values', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            final value = AppBreakpoints.responsive<String>(
              context,
              mobile: 'mobile',
              tablet: 'tablet',
              desktop: 'desktop',
              wide: 'wide',
              ultraWide: 'ultraWide',
            );
            expect(value, equals('mobile'));
            return Container();
          }),
          const Size(400, 800),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            final value = AppBreakpoints.responsive<String>(
              context,
              mobile: 'mobile',
              tablet: 'tablet',
              desktop: 'desktop',
              wide: 'wide',
              ultraWide: 'ultraWide',
            );
            expect(value, equals('tablet'));
            return Container();
          }),
          const Size(800, 600),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            final value = AppBreakpoints.responsive<String>(
              context,
              mobile: 'mobile',
              tablet: 'tablet',
              desktop: 'desktop',
              wide: 'wide',
              ultraWide: 'ultraWide',
            );
            expect(value, equals('ultraWide'));
            return Container();
          }),
          const Size(2000, 1200),
        ));
      });

      testWidgets('responsive should fall back to mobile when optional values are null', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            final value = AppBreakpoints.responsive<String>(
              context,
              mobile: 'mobile',
            );
            expect(value, equals('mobile'));
            return Container();
          }),
          const Size(800, 600),
        ));
      });

      testWidgets('responsiveColumns should return correct column counts', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.responsiveColumns(context), equals(1));
            return Container();
          }),
          const Size(400, 800),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.responsiveColumns(context), equals(2));
            return Container();
          }),
          const Size(800, 600),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.responsiveColumns(context), equals(5));
            return Container();
          }),
          const Size(2000, 1200),
        ));
      });

      testWidgets('responsivePadding should return correct padding values', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.responsivePadding(context), equals(16.0));
            return Container();
          }),
          const Size(400, 800),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.responsivePadding(context), equals(48.0));
            return Container();
          }),
          const Size(2000, 1200),
        ));
      });

      testWidgets('responsiveMaxWidth should return correct max width values', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.responsiveMaxWidth(context), equals(double.infinity));
            return Container();
          }),
          const Size(400, 800),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.responsiveMaxWidth(context), equals(1400.0));
            return Container();
          }),
          const Size(2000, 1200),
        ));
      });
    });

    group('Edge Cases', () {
      testWidgets('should handle exact breakpoint values', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isMobile(context), isFalse);
            expect(AppBreakpoints.isTablet(context), isTrue);
            return Container();
          }),
          const Size(768, 600),
        ));

        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isTablet(context), isFalse);
            expect(AppBreakpoints.isDesktop(context), isTrue);
            return Container();
          }),
          const Size(1024, 800),
        ));
      });

      testWidgets('should handle very small screens', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isMobile(context), isTrue);
            expect(AppBreakpoints.responsiveColumns(context), equals(1));
            return Container();
          }),
          const Size(200, 400),
        ));
      });

      testWidgets('should handle very large screens', (tester) async {
        await tester.pumpWidget(_createTestWidget(
          Builder(builder: (context) {
            expect(AppBreakpoints.isUltraWide(context), isTrue);
            expect(AppBreakpoints.responsiveColumns(context), equals(5));
            return Container();
          }),
          const Size(3000, 2000),
        ));
      });
    });
  });
}