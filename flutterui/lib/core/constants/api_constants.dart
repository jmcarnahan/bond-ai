class ApiConstants {
  static const String compiledBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: '',
  );
  static String baseUrl = compiledBaseUrl;
  static const String loginEndpoint = '/login';
  static const String googleCallbackEndpoint = '/auth/google/callback';
  static const String usersMeEndpoint = '/users/me';
  static const String agentsEndpoint = '/agents';
  static const String threadsEndpoint = '/threads';
  static const String chatEndpoint = '/chat';
  static const String filesEndpoint = '/files';
}
