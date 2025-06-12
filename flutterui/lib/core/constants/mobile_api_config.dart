import 'package:flutter_dotenv/flutter_dotenv.dart';

class MobileApiConfig {
  static String get baseUrl =>
      dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';

  static String get defaultAgentId =>
      dotenv.env['DEFAULT_AGENT_ID'] ?? 'default-agent';

  static String get defaultAgentName =>
      dotenv.env['DEFAULT_AGENT_NAME'] ?? 'My Companion';
}
