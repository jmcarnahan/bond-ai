import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/core/constants/app_spacing.dart';

void main() {
  group('AppSpacing Tests', () {
    group('Spacing Constants', () {
      test('should have correct spacing values in ascending order', () {
        expect(AppSpacing.xs, equals(2.0));
        expect(AppSpacing.sm, equals(4.0));
        expect(AppSpacing.md, equals(8.0));
        expect(AppSpacing.lg, equals(12.0));
        expect(AppSpacing.xl, equals(16.0));
        expect(AppSpacing.xxl, equals(20.0));
        expect(AppSpacing.xxxl, equals(24.0));
        expect(AppSpacing.huge, equals(32.0));
        expect(AppSpacing.massive, equals(40.0));
        expect(AppSpacing.enormous, equals(48.0));
        expect(AppSpacing.giant, equals(64.0));
        
        expect(AppSpacing.xs < AppSpacing.sm, isTrue);
        expect(AppSpacing.sm < AppSpacing.md, isTrue);
        expect(AppSpacing.md < AppSpacing.lg, isTrue);
        expect(AppSpacing.lg < AppSpacing.xl, isTrue);
        expect(AppSpacing.xl < AppSpacing.xxl, isTrue);
        expect(AppSpacing.xxl < AppSpacing.xxxl, isTrue);
        expect(AppSpacing.xxxl < AppSpacing.huge, isTrue);
        expect(AppSpacing.huge < AppSpacing.massive, isTrue);
        expect(AppSpacing.massive < AppSpacing.enormous, isTrue);
        expect(AppSpacing.enormous < AppSpacing.giant, isTrue);
      });
    });

    group('EdgeInsets All', () {
      test('should have correct all padding values', () {
        expect(AppSpacing.allXs, equals(const EdgeInsets.all(2.0)));
        expect(AppSpacing.allSm, equals(const EdgeInsets.all(4.0)));
        expect(AppSpacing.allMd, equals(const EdgeInsets.all(8.0)));
        expect(AppSpacing.allLg, equals(const EdgeInsets.all(12.0)));
        expect(AppSpacing.allXl, equals(const EdgeInsets.all(16.0)));
        expect(AppSpacing.allXxl, equals(const EdgeInsets.all(20.0)));
        expect(AppSpacing.allXxxl, equals(const EdgeInsets.all(24.0)));
        expect(AppSpacing.allHuge, equals(const EdgeInsets.all(32.0)));
        expect(AppSpacing.allMassive, equals(const EdgeInsets.all(40.0)));
        expect(AppSpacing.allEnormous, equals(const EdgeInsets.all(48.0)));
        expect(AppSpacing.allGiant, equals(const EdgeInsets.all(64.0)));
      });
    });

    group('EdgeInsets Horizontal', () {
      test('should have correct horizontal padding values', () {
        expect(AppSpacing.horizontalXs, equals(const EdgeInsets.symmetric(horizontal: 2.0)));
        expect(AppSpacing.horizontalSm, equals(const EdgeInsets.symmetric(horizontal: 4.0)));
        expect(AppSpacing.horizontalMd, equals(const EdgeInsets.symmetric(horizontal: 8.0)));
        expect(AppSpacing.horizontalLg, equals(const EdgeInsets.symmetric(horizontal: 12.0)));
        expect(AppSpacing.horizontalXl, equals(const EdgeInsets.symmetric(horizontal: 16.0)));
        expect(AppSpacing.horizontalXxl, equals(const EdgeInsets.symmetric(horizontal: 20.0)));
        expect(AppSpacing.horizontalXxxl, equals(const EdgeInsets.symmetric(horizontal: 24.0)));
        expect(AppSpacing.horizontalHuge, equals(const EdgeInsets.symmetric(horizontal: 32.0)));
        expect(AppSpacing.horizontalMassive, equals(const EdgeInsets.symmetric(horizontal: 40.0)));
        expect(AppSpacing.horizontalEnormous, equals(const EdgeInsets.symmetric(horizontal: 48.0)));
        expect(AppSpacing.horizontalGiant, equals(const EdgeInsets.symmetric(horizontal: 64.0)));
      });
    });

    group('EdgeInsets Vertical', () {
      test('should have correct vertical padding values', () {
        expect(AppSpacing.verticalXs, equals(const EdgeInsets.symmetric(vertical: 2.0)));
        expect(AppSpacing.verticalSm, equals(const EdgeInsets.symmetric(vertical: 4.0)));
        expect(AppSpacing.verticalMd, equals(const EdgeInsets.symmetric(vertical: 8.0)));
        expect(AppSpacing.verticalLg, equals(const EdgeInsets.symmetric(vertical: 12.0)));
        expect(AppSpacing.verticalXl, equals(const EdgeInsets.symmetric(vertical: 16.0)));
        expect(AppSpacing.verticalXxl, equals(const EdgeInsets.symmetric(vertical: 20.0)));
        expect(AppSpacing.verticalXxxl, equals(const EdgeInsets.symmetric(vertical: 24.0)));
        expect(AppSpacing.verticalHuge, equals(const EdgeInsets.symmetric(vertical: 32.0)));
        expect(AppSpacing.verticalMassive, equals(const EdgeInsets.symmetric(vertical: 40.0)));
        expect(AppSpacing.verticalEnormous, equals(const EdgeInsets.symmetric(vertical: 48.0)));
        expect(AppSpacing.verticalGiant, equals(const EdgeInsets.symmetric(vertical: 64.0)));
      });
    });

    group('EdgeInsets Only Top', () {
      test('should have correct top-only padding values', () {
        expect(AppSpacing.onlyTopXs, equals(const EdgeInsets.only(top: 2.0)));
        expect(AppSpacing.onlyTopSm, equals(const EdgeInsets.only(top: 4.0)));
        expect(AppSpacing.onlyTopMd, equals(const EdgeInsets.only(top: 8.0)));
        expect(AppSpacing.onlyTopLg, equals(const EdgeInsets.only(top: 12.0)));
        expect(AppSpacing.onlyTopXl, equals(const EdgeInsets.only(top: 16.0)));
        expect(AppSpacing.onlyTopXxl, equals(const EdgeInsets.only(top: 20.0)));
        expect(AppSpacing.onlyTopXxxl, equals(const EdgeInsets.only(top: 24.0)));
        expect(AppSpacing.onlyTopHuge, equals(const EdgeInsets.only(top: 32.0)));
        expect(AppSpacing.onlyTopMassive, equals(const EdgeInsets.only(top: 40.0)));
        expect(AppSpacing.onlyTopEnormous, equals(const EdgeInsets.only(top: 48.0)));
        expect(AppSpacing.onlyTopGiant, equals(const EdgeInsets.only(top: 64.0)));
      });
    });

    group('EdgeInsets Only Bottom', () {
      test('should have correct bottom-only padding values', () {
        expect(AppSpacing.onlyBottomXs, equals(const EdgeInsets.only(bottom: 2.0)));
        expect(AppSpacing.onlyBottomSm, equals(const EdgeInsets.only(bottom: 4.0)));
        expect(AppSpacing.onlyBottomMd, equals(const EdgeInsets.only(bottom: 8.0)));
        expect(AppSpacing.onlyBottomLg, equals(const EdgeInsets.only(bottom: 12.0)));
        expect(AppSpacing.onlyBottomXl, equals(const EdgeInsets.only(bottom: 16.0)));
        expect(AppSpacing.onlyBottomXxl, equals(const EdgeInsets.only(bottom: 20.0)));
        expect(AppSpacing.onlyBottomXxxl, equals(const EdgeInsets.only(bottom: 24.0)));
        expect(AppSpacing.onlyBottomHuge, equals(const EdgeInsets.only(bottom: 32.0)));
        expect(AppSpacing.onlyBottomMassive, equals(const EdgeInsets.only(bottom: 40.0)));
        expect(AppSpacing.onlyBottomEnormous, equals(const EdgeInsets.only(bottom: 48.0)));
        expect(AppSpacing.onlyBottomGiant, equals(const EdgeInsets.only(bottom: 64.0)));
      });
    });

    group('EdgeInsets Only Left', () {
      test('should have correct left-only padding values', () {
        expect(AppSpacing.onlyLeftXs, equals(const EdgeInsets.only(left: 2.0)));
        expect(AppSpacing.onlyLeftSm, equals(const EdgeInsets.only(left: 4.0)));
        expect(AppSpacing.onlyLeftMd, equals(const EdgeInsets.only(left: 8.0)));
        expect(AppSpacing.onlyLeftLg, equals(const EdgeInsets.only(left: 12.0)));
        expect(AppSpacing.onlyLeftXl, equals(const EdgeInsets.only(left: 16.0)));
        expect(AppSpacing.onlyLeftXxl, equals(const EdgeInsets.only(left: 20.0)));
        expect(AppSpacing.onlyLeftXxxl, equals(const EdgeInsets.only(left: 24.0)));
        expect(AppSpacing.onlyLeftHuge, equals(const EdgeInsets.only(left: 32.0)));
        expect(AppSpacing.onlyLeftMassive, equals(const EdgeInsets.only(left: 40.0)));
        expect(AppSpacing.onlyLeftEnormous, equals(const EdgeInsets.only(left: 48.0)));
        expect(AppSpacing.onlyLeftGiant, equals(const EdgeInsets.only(left: 64.0)));
      });
    });

    group('EdgeInsets Only Right', () {
      test('should have correct right-only padding values', () {
        expect(AppSpacing.onlyRightXs, equals(const EdgeInsets.only(right: 2.0)));
        expect(AppSpacing.onlyRightSm, equals(const EdgeInsets.only(right: 4.0)));
        expect(AppSpacing.onlyRightMd, equals(const EdgeInsets.only(right: 8.0)));
        expect(AppSpacing.onlyRightLg, equals(const EdgeInsets.only(right: 12.0)));
        expect(AppSpacing.onlyRightXl, equals(const EdgeInsets.only(right: 16.0)));
        expect(AppSpacing.onlyRightXxl, equals(const EdgeInsets.only(right: 20.0)));
        expect(AppSpacing.onlyRightXxxl, equals(const EdgeInsets.only(right: 24.0)));
        expect(AppSpacing.onlyRightHuge, equals(const EdgeInsets.only(right: 32.0)));
        expect(AppSpacing.onlyRightMassive, equals(const EdgeInsets.only(right: 40.0)));
        expect(AppSpacing.onlyRightEnormous, equals(const EdgeInsets.only(right: 48.0)));
        expect(AppSpacing.onlyRightGiant, equals(const EdgeInsets.only(right: 64.0)));
      });
    });
  });

  group('AppBorderRadius Tests', () {
    group('Radius Constants', () {
      test('should have correct radius values', () {
        expect(AppBorderRadius.none, equals(0.0));
        expect(AppBorderRadius.xs, equals(2.0));
        expect(AppBorderRadius.sm, equals(4.0));
        expect(AppBorderRadius.md, equals(8.0));
        expect(AppBorderRadius.lg, equals(12.0));
        expect(AppBorderRadius.xl, equals(16.0));
        expect(AppBorderRadius.xxl, equals(20.0));
        expect(AppBorderRadius.xxxl, equals(24.0));
        expect(AppBorderRadius.huge, equals(32.0));
        expect(AppBorderRadius.circular, equals(999.0));
      });
    });

    group('BorderRadius All', () {
      test('should have correct all border radius values', () {
        expect(AppBorderRadius.allNone, equals(const BorderRadius.all(Radius.circular(0.0))));
        expect(AppBorderRadius.allXs, equals(const BorderRadius.all(Radius.circular(2.0))));
        expect(AppBorderRadius.allSm, equals(const BorderRadius.all(Radius.circular(4.0))));
        expect(AppBorderRadius.allMd, equals(const BorderRadius.all(Radius.circular(8.0))));
        expect(AppBorderRadius.allLg, equals(const BorderRadius.all(Radius.circular(12.0))));
        expect(AppBorderRadius.allXl, equals(const BorderRadius.all(Radius.circular(16.0))));
        expect(AppBorderRadius.allXxl, equals(const BorderRadius.all(Radius.circular(20.0))));
        expect(AppBorderRadius.allXxxl, equals(const BorderRadius.all(Radius.circular(24.0))));
        expect(AppBorderRadius.allHuge, equals(const BorderRadius.all(Radius.circular(32.0))));
        expect(AppBorderRadius.allCircular, equals(const BorderRadius.all(Radius.circular(999.0))));
      });
    });

    group('BorderRadius Specific Corners', () {
      test('should have correct top-left border radius values', () {
        expect(AppBorderRadius.onlyTopLeftXs, equals(const BorderRadius.only(topLeft: Radius.circular(2.0))));
        expect(AppBorderRadius.onlyTopLeftSm, equals(const BorderRadius.only(topLeft: Radius.circular(4.0))));
        expect(AppBorderRadius.onlyTopLeftMd, equals(const BorderRadius.only(topLeft: Radius.circular(8.0))));
        expect(AppBorderRadius.onlyTopLeftLg, equals(const BorderRadius.only(topLeft: Radius.circular(12.0))));
        expect(AppBorderRadius.onlyTopLeftXl, equals(const BorderRadius.only(topLeft: Radius.circular(16.0))));
      });

      test('should have correct top border radius values', () {
        expect(AppBorderRadius.topXs, equals(const BorderRadius.only(
          topLeft: Radius.circular(2.0),
          topRight: Radius.circular(2.0),
        )));
        expect(AppBorderRadius.topSm, equals(const BorderRadius.only(
          topLeft: Radius.circular(4.0),
          topRight: Radius.circular(4.0),
        )));
        expect(AppBorderRadius.topMd, equals(const BorderRadius.only(
          topLeft: Radius.circular(8.0),
          topRight: Radius.circular(8.0),
        )));
      });

      test('should have correct bottom border radius values', () {
        expect(AppBorderRadius.bottomXs, equals(const BorderRadius.only(
          bottomLeft: Radius.circular(2.0),
          bottomRight: Radius.circular(2.0),
        )));
        expect(AppBorderRadius.bottomSm, equals(const BorderRadius.only(
          bottomLeft: Radius.circular(4.0),
          bottomRight: Radius.circular(4.0),
        )));
        expect(AppBorderRadius.bottomMd, equals(const BorderRadius.only(
          bottomLeft: Radius.circular(8.0),
          bottomRight: Radius.circular(8.0),
        )));
      });
    });
  });

  group('AppSizes Tests', () {
    group('Icon Sizes', () {
      test('should have correct icon size values in ascending order', () {
        expect(AppSizes.iconXs, equals(12.0));
        expect(AppSizes.iconSm, equals(16.0));
        expect(AppSizes.iconMd, equals(20.0));
        expect(AppSizes.iconLg, equals(24.0));
        expect(AppSizes.iconXl, equals(32.0));
        expect(AppSizes.iconXxl, equals(40.0));
        expect(AppSizes.iconXxxl, equals(48.0));
        expect(AppSizes.iconHuge, equals(64.0));
        expect(AppSizes.iconMassive, equals(80.0));
        expect(AppSizes.iconEnormous, equals(96.0));

        expect(AppSizes.iconXs < AppSizes.iconSm, isTrue);
        expect(AppSizes.iconSm < AppSizes.iconMd, isTrue);
        expect(AppSizes.iconMd < AppSizes.iconLg, isTrue);
        expect(AppSizes.iconLg < AppSizes.iconXl, isTrue);
      });
    });

    group('Component Sizes', () {
      test('should have correct button height values', () {
        expect(AppSizes.buttonHeightSm, equals(36.0));
        expect(AppSizes.buttonHeight, equals(48.0));
        expect(AppSizes.buttonHeightLg, equals(56.0));
        expect(AppSizes.buttonHeightSm < AppSizes.buttonHeight, isTrue);
        expect(AppSizes.buttonHeight < AppSizes.buttonHeightLg, isTrue);
      });

      test('should have correct input height values', () {
        expect(AppSizes.inputHeightSm, equals(36.0));
        expect(AppSizes.inputHeight, equals(48.0));
        expect(AppSizes.inputHeightLg, equals(56.0));
        expect(AppSizes.inputHeightSm < AppSizes.inputHeight, isTrue);
        expect(AppSizes.inputHeight < AppSizes.inputHeightLg, isTrue);
      });

      test('should have correct avatar size values', () {
        expect(AppSizes.avatarXs, equals(24.0));
        expect(AppSizes.avatarSm, equals(32.0));
        expect(AppSizes.avatarMd, equals(40.0));
        expect(AppSizes.avatarLg, equals(48.0));
        expect(AppSizes.avatarXl, equals(64.0));
        expect(AppSizes.avatarXxl, equals(80.0));
        expect(AppSizes.avatarXxxl, equals(96.0));
      });

      test('should have correct layout dimensions', () {
        expect(AppSizes.appBarHeight, equals(56.0));
        expect(AppSizes.bottomNavHeight, equals(60.0));
        expect(AppSizes.tabBarHeight, equals(48.0));
        expect(AppSizes.sidebarWidth, equals(280.0));
        expect(AppSizes.sidebarWidthCollapsed, equals(72.0));
        expect(AppSizes.maxContentWidth, equals(1200.0));
      });
    });
  });

  group('AppElevation Tests', () {
    test('should have correct elevation values in ascending order', () {
      expect(AppElevation.none, equals(0.0));
      expect(AppElevation.xs, equals(1.0));
      expect(AppElevation.sm, equals(2.0));
      expect(AppElevation.md, equals(4.0));
      expect(AppElevation.lg, equals(6.0));
      expect(AppElevation.xl, equals(8.0));
      expect(AppElevation.xxl, equals(12.0));
      expect(AppElevation.xxxl, equals(16.0));
      expect(AppElevation.huge, equals(24.0));

      expect(AppElevation.none < AppElevation.xs, isTrue);
      expect(AppElevation.xs < AppElevation.sm, isTrue);
      expect(AppElevation.sm < AppElevation.md, isTrue);
      expect(AppElevation.md < AppElevation.lg, isTrue);
      expect(AppElevation.lg < AppElevation.xl, isTrue);
      expect(AppElevation.xl < AppElevation.xxl, isTrue);
      expect(AppElevation.xxl < AppElevation.xxxl, isTrue);
      expect(AppElevation.xxxl < AppElevation.huge, isTrue);
    });
  });

  group('AppDurations Tests', () {
    test('should have correct duration values in ascending order', () {
      expect(AppDurations.instant, equals(Duration.zero));
      expect(AppDurations.fast, equals(const Duration(milliseconds: 150)));
      expect(AppDurations.normal, equals(const Duration(milliseconds: 250)));
      expect(AppDurations.slow, equals(const Duration(milliseconds: 400)));
      expect(AppDurations.slower, equals(const Duration(milliseconds: 600)));
      expect(AppDurations.slowest, equals(const Duration(milliseconds: 1000)));

      expect(AppDurations.instant < AppDurations.fast, isTrue);
      expect(AppDurations.fast < AppDurations.normal, isTrue);
      expect(AppDurations.normal < AppDurations.slow, isTrue);
      expect(AppDurations.slow < AppDurations.slower, isTrue);
      expect(AppDurations.slower < AppDurations.slowest, isTrue);
    });
  });
}