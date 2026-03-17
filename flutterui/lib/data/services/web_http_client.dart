import 'web_http_client_stub.dart'
    if (dart.library.html) 'web_http_client_web.dart' as impl;

import 'package:http/http.dart' as http;

http.Client createHttpClient() => impl.createHttpClient();
