import 'cookie_helper_stub.dart'
    if (dart.library.html) 'cookie_helper_web.dart' as impl;

String? getCsrfToken() => impl.getCsrfToken();
bool get isWebCookieAuth => impl.isWebCookieAuth;
void setWebCookieAuth(bool value) => impl.setWebCookieAuth(value);
