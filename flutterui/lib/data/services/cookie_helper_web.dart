// ignore_for_file: avoid_web_libraries_in_flutter
import 'dart:html' as html;

/// Detect cookie auth by checking if bond_csrf cookie is present.
/// This survives page refreshes since the cookie persists.
bool get isWebCookieAuth => getCsrfToken() != null;

void setWebCookieAuth(bool value) {
  // No-op: cookie auth is detected from bond_csrf cookie presence.
  // The flag is derived, not stored, so it survives page refreshes.
}

String? getCsrfToken() {
  final cookies = html.document.cookie ?? '';
  for (final cookie in cookies.split(';')) {
    final parts = cookie.trim().split('=');
    if (parts.length == 2 && parts[0].trim() == 'bond_csrf') {
      return parts[1].trim();
    }
  }
  return null;
}
