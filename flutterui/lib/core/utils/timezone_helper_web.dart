import 'dart:js_interop';

/// JS interop for Intl.DateTimeFormat().resolvedOptions().timeZone
@JS('Intl.DateTimeFormat')
extension type _IntlDateTimeFormat._(JSObject _) implements JSObject {
  external _IntlDateTimeFormat();
  external _ResolvedOptions resolvedOptions();
}

@JS()
extension type _ResolvedOptions._(JSObject _) implements JSObject {
  external String get timeZone;
}

/// Get the user's IANA timezone (e.g. "America/Chicago") via browser JS API.
String getLocalTimezone() {
  try {
    return _IntlDateTimeFormat().resolvedOptions().timeZone;
  } catch (_) {
    return 'UTC';
  }
}
