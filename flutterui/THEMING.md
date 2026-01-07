# Flutter UI Theming Guide

This guide explains how to customize the appearance of the Bond AI Flutter application, including switching between themes and creating custom themes.

## Quick Start: Switching Themes

### Use Generic Bond AI Theme (Default)
```bash
# From the flutterui directory
dart tool/generate_theme.dart

# Restart the Flutter app
flutter run -d chrome --web-port=5000 --target lib/main.dart
```

### Use McAfee Theme
```bash
# From the flutterui directory
dart tool/generate_theme.dart --config theme_configs/mcafee_config.json

# Restart the Flutter app
flutter run -d chrome --web-port=5000 --target lib/main.dart
```

That's it! The app will now use your selected theme.

## Theme System Overview

The theming system consists of three main components:

1. **Theme Configurations** (`theme_configs/*.json`) - JSON files defining theme properties
2. **Base Theme** (`lib/core/theme/base_theme.dart`) - Default theme implementation
3. **Theme Generator** (`tool/generate_theme.dart`) - Script that generates the active theme
4. **Generated Theme** (`lib/core/theme/generated_theme.dart`) - Auto-generated file used by the app

### Architecture Flow
```
theme_configs/my_theme.json → generate_theme.dart → generated_theme.dart → Flutter App
                                       ↑
                                  base_theme.dart (fallback)
```

## Switching Between Themes

### Method 1: Command Line (Recommended)

Switch to generic Bond AI theme:
```bash
dart tool/generate_theme.dart
```

Switch to McAfee theme:
```bash
dart tool/generate_theme.dart --config theme_configs/mcafee_config.json
```

Switch to any custom theme:
```bash
dart tool/generate_theme.dart --config theme_configs/your_custom_theme.json
```

### Method 2: Create a Script

Create `switch_theme.sh` in the flutterui directory:
```bash
#!/bin/bash
# Usage: ./switch_theme.sh [generic|mcafee|custom_name]

THEME=$1

case $THEME in
  generic)
    echo "Switching to generic Bond AI theme..."
    dart tool/generate_theme.dart
    ;;
  mcafee)
    echo "Switching to McAfee theme..."
    dart tool/generate_theme.dart --config theme_configs/mcafee_config.json
    ;;
  *)
    echo "Switching to $THEME theme..."
    dart tool/generate_theme.dart --config theme_configs/${THEME}_config.json
    ;;
esac

echo "Theme switched! Restart your Flutter app to see changes."
```

Make it executable:
```bash
chmod +x switch_theme.sh
```

Use it:
```bash
./switch_theme.sh generic  # Switch to Bond AI theme
./switch_theme.sh mcafee   # Switch to McAfee theme
```

## Creating a Custom Theme

### Step 1: Create Theme Configuration

Create a new JSON file in `theme_configs/` directory (e.g., `my_company_config.json`):

```json
{
  "themeName": "My Company",
  "brandingMessage": "Your Custom Tagline Here",
  "logoPath": "theme_specific/my_company_logo.png",
  "logoIconPath": "theme_specific/my_company_icon.png",
  "fontFamily": "Roboto",
  "useMaterial3": true,
  "brightness": "light",
  "primaryColor": "#2196F3",
  "scaffoldBackgroundColor": "#FFFFFF",
  "extensions": {
    "customColors": {
      "brandingSurface": "#1976D2"
    }
  },
  "colorScheme": {
    "brightness": "light",
    "primary": "#2196F3",
    "onPrimary": "#FFFFFF",
    "secondary": "#FFC107",
    "onSecondary": "#000000",
    "error": "#F44336",
    "onError": "#FFFFFF",
    "background": "#FFFFFF",
    "onBackground": "#000000",
    "surface": "#F5F5F5",
    "onSurface": "#212121"
  },
  "textTheme": {
    "displayLarge": { "fontSize": 32, "fontWeight": "w600", "color": "#212121" },
    "displayMedium": { "fontSize": 28, "fontWeight": "w600", "color": "#212121" },
    "displaySmall": { "fontSize": 24, "fontWeight": "w500", "color": "#212121" },
    "headlineMedium": { "fontSize": 20, "fontWeight": "w600", "color": "#212121" },
    "headlineSmall": { "fontSize": 18, "fontWeight": "w500", "color": "#424242" },
    "bodyLarge": { "fontSize": 16, "color": "#424242" },
    "bodyMedium": { "fontSize": 14, "color": "#616161" },
    "bodySmall": { "fontSize": 12, "color": "#757575" },
    "labelLarge": { "fontSize": 14, "fontWeight": "w500", "color": "#2196F3" },
    "labelSmall": { "fontSize": 12, "color": "#9E9E9E" }
  }
}
```

### Step 2: Add Logo Assets

Place your logo files in `flutterui/assets/theme_specific/`:
- `my_company_logo.png` - Main logo (recommended: 200x50 px)
- `my_company_icon.png` - Square icon (recommended: 64x64 px)

### Step 3: Generate and Apply Theme

```bash
# Generate theme from your configuration
dart tool/generate_theme.dart --config theme_configs/my_company_config.json

# Restart the app
flutter run -d chrome --web-port=5000 --target lib/main.dart
```

## Theme Configuration Reference

### Root Properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `themeName` | string | Display name of the theme | `"My Company"` |
| `brandingMessage` | string | Tagline shown in the app | `"Your Digital Partner"` |
| `logoPath` | string | Path to logo image | `"theme_specific/logo.png"` |
| `logoIconPath` | string | Path to icon image | `"theme_specific/icon.png"` |
| `fontFamily` | string | Font family name | `"Roboto"`, `"Poppins"` |
| `useMaterial3` | boolean | Use Material Design 3 | `true` |
| `brightness` | string | Theme brightness | `"light"` or `"dark"` |
| `primaryColor` | string | Primary theme color | `"#2196F3"` |
| `scaffoldBackgroundColor` | string | Background color | `"#FFFFFF"` |

### Color Scheme Properties

All colors in hex format (6 or 8 digits with optional #):

```json
"colorScheme": {
  "brightness": "light",
  "primary": "#2196F3",       // Main brand color
  "onPrimary": "#FFFFFF",     // Text on primary color
  "secondary": "#FFC107",     // Accent color
  "onSecondary": "#000000",   // Text on secondary
  "error": "#F44336",         // Error state color
  "onError": "#FFFFFF",       // Text on error
  "background": "#FFFFFF",    // General background
  "onBackground": "#000000",  // Text on background
  "surface": "#F5F5F5",       // Card/surface color
  "onSurface": "#212121"      // Text on surface
}
```

### Text Theme Properties

Font weights: `"w100"` to `"w900"`, `"normal"`, `"bold"`

```json
"textTheme": {
  "displayLarge": { "fontSize": 32, "fontWeight": "w600", "color": "#212121" },
  "displayMedium": { "fontSize": 28, "fontWeight": "w600", "color": "#212121" },
  "displaySmall": { "fontSize": 24, "fontWeight": "w500", "color": "#212121" },
  "headlineMedium": { "fontSize": 20, "fontWeight": "w600", "color": "#212121" },
  "headlineSmall": { "fontSize": 18, "fontWeight": "w500", "color": "#424242" },
  "bodyLarge": { "fontSize": 16, "color": "#424242" },
  "bodyMedium": { "fontSize": 14, "color": "#616161" },
  "bodySmall": { "fontSize": 12, "color": "#757575" },
  "labelLarge": { "fontSize": 14, "fontWeight": "w500", "color": "#2196F3" },
  "labelSmall": { "fontSize": 12, "color": "#9E9E9E" }
}
```

### Component Themes (Optional)

You can customize individual components:

#### AppBar Theme
```json
"appBarTheme": {
  "backgroundColor": "#FFFFFF",
  "foregroundColor": "#333333",
  "elevation": 0.5,
  "centerTitle": true,
  "titleTextStyle": { "fontSize": 20, "fontWeight": "bold", "color": "#333333" }
}
```

#### Card Theme
```json
"cardTheme": {
  "color": "#FFFFFF",
  "elevation": 2.0,
  "margin": { "type": "all", "value": 12.0 },
  "shape": {
    "type": "roundedRectangle",
    "borderRadius": { "type": "circular", "radius": 8.0 }
  }
}
```

#### Button Themes
```json
"elevatedButtonTheme": {
  "style": {
    "foregroundColor": "#FFFFFF",
    "backgroundColor": "#2196F3",
    "padding": { "type": "symmetric", "horizontal": 20.0, "vertical": 12.0 },
    "shape": {
      "type": "roundedRectangle",
      "borderRadius": { "type": "circular", "radius": 6.0 }
    }
  }
}
```

#### Input Decoration Theme
```json
"inputDecorationTheme": {
  "filled": true,
  "fillColor": "#FFFFFF",
  "border": {
    "type": "outline",
    "borderSide": { "color": "#E0E0E0", "width": 1.0 },
    "borderRadius": { "type": "circular", "radius": 8.0 }
  },
  "focusedBorder": {
    "type": "outline",
    "borderSide": { "color": "#2196F3", "width": 2.0 },
    "borderRadius": { "type": "circular", "radius": 8.0 }
  }
}
```

## Asset Management

### Directory Structure
```
flutterui/
├── assets/
│   ├── bond_logo.png           # Default Bond AI logo
│   ├── bond_logo_icon.png      # Default Bond AI icon
│   └── theme_specific/         # Theme-specific assets
│       ├── mcafee_logo.png
│       ├── mcafee_shield_logo.png
│       └── your_company_logo.png
```

### Asset Guidelines
- **Logo**: Recommended 200x50 pixels, PNG format with transparency
- **Icon**: Recommended 64x64 pixels, square format
- Place all theme-specific assets in `assets/theme_specific/`
- Use descriptive names: `companyname_logo.png`

## Examples

### Example 1: Minimal Theme Configuration
```json
{
  "themeName": "Simple",
  "brandingMessage": "Keep It Simple",
  "logoPath": "bond_logo.png",
  "logoIconPath": "bond_logo_icon.png",
  "brightness": "light",
  "primaryColor": "#000000",
  "colorScheme": {
    "brightness": "light",
    "primary": "#000000",
    "onPrimary": "#FFFFFF",
    "secondary": "#666666",
    "onSecondary": "#FFFFFF",
    "error": "#FF0000",
    "onError": "#FFFFFF",
    "background": "#FFFFFF",
    "onBackground": "#000000",
    "surface": "#F0F0F0",
    "onSurface": "#000000"
  },
  "textTheme": {
    "displayLarge": { "fontSize": 32, "fontWeight": "bold" },
    "bodyLarge": { "fontSize": 16 },
    "bodyMedium": { "fontSize": 14 }
  }
}
```

### Example 2: Dark Theme Configuration
```json
{
  "themeName": "Dark Mode",
  "brandingMessage": "Working in the Dark",
  "logoPath": "theme_specific/dark_logo.png",
  "logoIconPath": "theme_specific/dark_icon.png",
  "brightness": "dark",
  "primaryColor": "#BB86FC",
  "scaffoldBackgroundColor": "#121212",
  "colorScheme": {
    "brightness": "dark",
    "primary": "#BB86FC",
    "onPrimary": "#000000",
    "secondary": "#03DAC6",
    "onSecondary": "#000000",
    "error": "#CF6679",
    "onError": "#000000",
    "background": "#121212",
    "onBackground": "#FFFFFF",
    "surface": "#1E1E1E",
    "onSurface": "#FFFFFF"
  },
  "textTheme": {
    "displayLarge": { "fontSize": 32, "fontWeight": "w600", "color": "#FFFFFF" },
    "bodyLarge": { "fontSize": 16, "color": "#E0E0E0" },
    "bodyMedium": { "fontSize": 14, "color": "#B0B0B0" }
  }
}
```

## Troubleshooting

### Theme changes not appearing
1. Make sure you've run the theme generator: `dart tool/generate_theme.dart --config theme_configs/your_theme.json`
2. Restart the Flutter application (hot reload may not pick up theme changes)
3. Clear browser cache if running on web: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)

### Assets not loading
1. Verify asset paths in your theme configuration match actual file locations
2. Check that assets are listed in `pubspec.yaml`:
   ```yaml
   flutter:
     assets:
       - assets/
       - assets/theme_specific/
   ```
3. Run `flutter clean` and `flutter pub get`

### Generation errors
1. Validate your JSON configuration (check for missing commas, quotes)
2. Ensure all required fields are present (`themeName`, `brightness`, `primaryColor`, `colorScheme`, `textTheme`)
3. Check color format: use 6 or 8 digit hex codes with optional # prefix

### Using wrong theme
1. Check `lib/core/theme/generated_theme.dart` header comment to see which config was used
2. Re-run the generator with the correct config file
3. Make sure you're in the `flutterui` directory when running commands

## Advanced Usage

### Programmatic Theme Switching

If you want to support runtime theme switching (without regeneration), you can modify the app to load multiple themes:

1. Generate multiple theme files with different output paths:
```bash
dart tool/generate_theme.dart --config theme_configs/light_theme.json --output lib/core/theme/light_theme.dart
dart tool/generate_theme.dart --config theme_configs/dark_theme.json --output lib/core/theme/dark_theme.dart
```

2. Import and use them in your app based on user preference

### CI/CD Integration

Add theme generation to your build process:

```yaml
# .github/workflows/build.yml
steps:
  - name: Generate theme
    run: |
      cd flutterui
      dart tool/generate_theme.dart --config theme_configs/${THEME_CONFIG:-mcafee_config}.json
```

### Environment-based Themes

Use environment variables to select themes:

```bash
# build_with_theme.sh
#!/bin/bash
THEME=${FLUTTER_THEME:-generic}

if [ "$THEME" = "generic" ]; then
  dart tool/generate_theme.dart
else
  dart tool/generate_theme.dart --config theme_configs/${THEME}_config.json
fi

flutter build web
```

## Support

For issues or questions about theming:
1. Check that your JSON configuration is valid
2. Review the examples in this guide
3. Look at existing theme configurations in `theme_configs/`
4. Check the base theme implementation in `lib/core/theme/base_theme.dart`
