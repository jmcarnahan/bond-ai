// Web-specific implementation for OAuth same-window redirect.
import 'package:universal_html/html.dart' as html;

/// Navigates to URL in the same window (replaces current page).
void navigateSameWindow(String url) {
  html.window.location.href = url;
}

/// Gets the current URL's query parameters.
Map<String, String> getCurrentQueryParams() {
  final uri = Uri.parse(html.window.location.href);
  return uri.queryParameters;
}

/// Clears query parameters from URL without reload (for cleaning up after OAuth).
void clearQueryParams() {
  final uri = Uri.parse(html.window.location.href);
  if (uri.queryParameters.isNotEmpty) {
    // Build URL without query parameters
    final cleanUrl = uri.replace(queryParameters: {}).toString();
    // Use replaceState to update URL without reload
    html.window.history.replaceState(null, '', cleanUrl);
  }
}
