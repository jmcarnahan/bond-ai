# Bond AI Mobile App

This is a simplified mobile-optimized version of the Bond AI Flutter app that provides a streamlined interface with only the essential features.

## Features

- **Login Screen**: OAuth2 authentication
- **Chat Screen**: Direct chat with a configured AI agent
- **Threads Screen**: View and manage conversation threads
- **Bottom Navigation**: Simple navigation between Chat and Threads

## Setup

1. **Install dependencies**:
   ```bash
   flutter pub get
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and set:
   - `API_BASE_URL`: Your Bond AI API server URL
   - `MOBILE_AGENT_ID`: The agent ID to use (e.g., `asst_BZ6WaTaNc0THp8eCSDx6leHD`)
   - `MOBILE_AGENT_NAME`: Display name for the agent

3. **Run the mobile app**:
   ```bash
   flutter run --target lib/main_mobile.dart
   ```

## VS Code Launch Configurations

The project includes VS Code launch configurations for easy debugging:
- **Flutter - Mobile App**: Debug mode
- **Flutter - Mobile App (profile mode)**: Performance profiling
- **Flutter - Mobile App (release mode)**: Production build

## Key Differences from Desktop App

- **No sidebar navigation**: Uses bottom navigation bar instead
- **No agent management**: Fixed agent ID from configuration
- **No group management**: Simplified interface
- **Mobile-optimized layout**: Better suited for smaller screens
- **Focused feature set**: Only essential chat and thread functionality

## Running on Different Platforms

### iOS Simulator
```bash
flutter run --target lib/main_mobile.dart -d ios
```

### Android Emulator
```bash
flutter run --target lib/main_mobile.dart -d android
```

### Web (Mobile Preview)
```bash
flutter run --target lib/main_mobile.dart -d chrome
```

## Environment Configuration

For production deployments, ensure you update the API_BASE_URL to point to your production server. For mobile devices, use your machine's network IP instead of localhost:

```
API_BASE_URL=http://192.168.1.100:8000  # Replace with your IP
```