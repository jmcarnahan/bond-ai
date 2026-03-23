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
  static const String scheduledJobsEndpoint = '/scheduled-jobs';
  static const String agentFoldersEndpoint = '/agent-folders';
  static const String tokenExchangeEndpoint = '/auth/token';
  static const String logoutEndpoint = '/auth/logout';
}
