import 'package:flutter/widgets.dart';

class AppBreakpoints {
  AppBreakpoints._();

  static const double mobile = 480.0;
  static const double tablet = 768.0;
  static const double desktop = 1024.0;
  static const double wide = 1440.0;
  static const double ultraWide = 1920.0;

  static bool isMobile(BuildContext context) {
    return MediaQuery.of(context).size.width < tablet;
  }

  static bool isTablet(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    return width >= tablet && width < desktop;
  }

  static bool isDesktop(BuildContext context) {
    return MediaQuery.of(context).size.width >= desktop;
  }

  static bool isWide(BuildContext context) {
    return MediaQuery.of(context).size.width >= wide;
  }

  static bool isUltraWide(BuildContext context) {
    return MediaQuery.of(context).size.width >= ultraWide;
  }

  static bool isMobileOrTablet(BuildContext context) {
    return MediaQuery.of(context).size.width < desktop;
  }

  static bool isTabletOrDesktop(BuildContext context) {
    return MediaQuery.of(context).size.width >= tablet;
  }

  static T responsive<T>(
    BuildContext context, {
    required T mobile,
    T? tablet,
    T? desktop,
    T? wide,
    T? ultraWide,
  }) {
    final width = MediaQuery.of(context).size.width;
    
    if (width >= AppBreakpoints.ultraWide && ultraWide != null) {
      return ultraWide;
    }
    if (width >= AppBreakpoints.wide && wide != null) {
      return wide;
    }
    if (width >= AppBreakpoints.desktop && desktop != null) {
      return desktop;
    }
    if (width >= AppBreakpoints.tablet && tablet != null) {
      return tablet;
    }
    return mobile;
  }

  static int responsiveColumns(BuildContext context) {
    return responsive<int>(
      context,
      mobile: 1,
      tablet: 2,
      desktop: 3,
      wide: 4,
      ultraWide: 5,
    );
  }

  static double responsivePadding(BuildContext context) {
    return responsive<double>(
      context,
      mobile: 16.0,
      tablet: 24.0,
      desktop: 32.0,
      wide: 40.0,
      ultraWide: 48.0,
    );
  }

  static double responsiveMaxWidth(BuildContext context) {
    return responsive<double>(
      context,
      mobile: double.infinity,
      tablet: 768.0,
      desktop: 1024.0,
      wide: 1200.0,
      ultraWide: 1400.0,
    );
  }
}