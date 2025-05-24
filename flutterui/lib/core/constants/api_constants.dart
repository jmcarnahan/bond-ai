// It's good practice to store API related constants in one place.
// For a real app, consider using environment variables or a config file
// for sensitive data or environment-specific URLs.

class ApiConstants {
  // Replace with your actual backend URL
  // For local development, if your Flutter app is served on localhost
  // and your backend is also on localhost but a different port (e.g., 8000 for FastAPI),
  // you would use something like 'http://localhost:8000'.
  // If using an Android emulator, 'http://10.0.2.2:8000' might be needed to reach the host machine's localhost.
  // For web, 'http://localhost:8000' should work if backend is on the same machine.
  static const String baseUrl =
      'http://localhost:8000'; // TODO: Update with your actual API base URL

  // Authentication Endpoints
  static const String loginEndpoint = '/login'; // GET to initiate Google OAuth
  static const String googleCallbackEndpoint =
      '/auth/google/callback'; // GET, but we primarily care about the token from it
  static const String usersMeEndpoint =
      '/users/me'; // GET to fetch current user details

  // Agent Endpoints
  static const String agentsEndpoint = '/agents'; // GET (list), POST (create)
  // PUT /agents/{assistant_id} - for updates, construct with ID

  // Thread Endpoints
  static const String threadsEndpoint = '/threads'; // GET (list), POST (create)
  // GET /threads/{thread_id}/messages - construct with ID

  // Chat Endpoint
  static const String chatEndpoint = '/chat'; // POST

  // File Management Endpoints
  static const String filesEndpoint =
      '/files'; // POST (upload), DELETE /files/{file_id}
}
