import 'package:flutter_dotenv/flutter_dotenv.dart';

class MobileApiConfig {
  static String get baseUrl => 
      dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';
  
  static String get mobileAgentId => 
      dotenv.env['MOBILE_AGENT_ID'] ?? 'asst_BZ6WaTaNc0THp8eCSDx6leHD';
  
  static String get mobileAgentName => 
      dotenv.env['MOBILE_AGENT_NAME'] ?? 'McAfee Companion';
}