// Stub implementation for non-web platforms.

/// Navigates to URL in same window (no-op on mobile, uses launchUrl instead).
void navigateSameWindow(String url) {
  // No-op: Mobile platforms use launchUrl with deep links
}

/// Gets the current URL's query parameters.
Map<String, String> getCurrentQueryParams() {
  return {};
}

/// Clears query parameters from URL without reload (for cleaning up after OAuth).
void clearQueryParams() {
  // No-op on mobile
}
