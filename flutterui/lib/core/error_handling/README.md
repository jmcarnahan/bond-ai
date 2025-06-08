# Error Handling Guide

## Overview

This guide explains the error handling system in the Bond AI Flutter application. The system distinguishes between different types of errors and handles them appropriately.

## Error Types

### 1. **Critical Errors**
- **Description**: Errors that break the application flow (missing required data, invalid routes)
- **Action**: Navigate to home page with error message
- **Examples**: 
  - Missing agent details when opening chat
  - Invalid route parameters
  - Browser reload on pages requiring specific data

### 2. **Service Errors**
- **Description**: API or backend service failures that don't break the app
- **Action**: Show error message in snackbar, stay on current page
- **Examples**:
  - Failed to load agent list
  - Network timeout
  - 404/500 errors from API

### 3. **Authentication Errors**
- **Description**: Token expired or unauthorized access
- **Action**: Clear auth state and navigate to login page
- **Examples**:
  - 401 Unauthorized responses
  - Expired JWT token
  - Invalid authentication

## Usage

### 1. In Widgets/Screens

```dart
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';

class MyScreen extends ConsumerStatefulWidget {
  // ...
}

class _MyScreenState extends ConsumerState<MyScreen> with ErrorHandlingMixin {
  
  void loadData() async {
    // Use withErrorHandling for async operations
    await withErrorHandling(
      operation: () async {
        final data = await someService.fetchData();
        // process data
      },
      ref: ref,
      errorMessage: 'Failed to load data',
      isCritical: false,  // Set to true for critical errors
    );
  }
  
  void handleSpecificError() {
    try {
      // some operation
    } catch (e) {
      // For service errors
      handleServiceError(e, ref, customMessage: 'Custom error message');
      
      // For critical errors
      handleCriticalError(e, ref, customMessage: 'Critical error occurred');
    }
  }
}
```

### 2. In Navigation (main.dart)

Critical routing errors are already handled in the navigation logic:

```dart
if (requiredDataMissing) {
  WidgetsBinding.instance.addPostFrameCallback((_) {
    ErrorHandlerService.handleError(
      AppError.critical(
        'Unable to load page. Required information is missing.',
        details: 'Specific details about what is missing',
      ),
      ref: ref,
    );
  });
  return MaterialPageRoute(builder: (_) => homeWidget);
}
```

### 3. In Services

The HTTP client automatically checks for authentication errors:

```dart
// This happens automatically in AuthenticatedHttpClient
if (response.statusCode == 401) {
  throw Exception('401 Unauthorized: Authentication token expired or invalid');
}
```

## Error Categories

### Critical Errors (Navigate to Home)
- Missing required route arguments
- Invalid page routes
- Corrupted application state
- Browser reload on stateful pages

### Service Errors (Show Message, Stay on Page)
- API failures (404, 500, etc.)
- Network timeouts
- Failed data loads
- Validation errors

### Authentication Errors (Navigate to Login)
- 401 Unauthorized
- Token expiration
- Invalid credentials

## Best Practices

1. **Always distinguish between critical and service errors**
   - Critical = Can't continue on current page
   - Service = Can retry or show error but stay on page

2. **Provide meaningful error messages**
   - User-friendly message for display
   - Technical details in logs

3. **Use the error handling mixin**
   - Consistent error handling across all screens
   - Automatic categorization of errors

4. **Handle errors at the appropriate level**
   - Service layer: Throw meaningful exceptions
   - UI layer: Catch and handle with appropriate action

5. **Test error scenarios**
   - Browser reload
   - Token expiration
   - Network failures
   - Missing data

## Example Scenarios

### Scenario 1: Browser Reload on Chat Page
- **Error**: Missing agent details
- **Type**: Critical
- **Action**: Navigate to home, show "Unable to load chat" message

### Scenario 2: Failed to Load Agent List
- **Error**: API returned 500
- **Type**: Service
- **Action**: Show "Failed to load agents" snackbar, display retry button

### Scenario 3: Token Expired During Usage
- **Error**: 401 from any API call
- **Type**: Authentication
- **Action**: Clear auth, navigate to login, show "Session expired" message