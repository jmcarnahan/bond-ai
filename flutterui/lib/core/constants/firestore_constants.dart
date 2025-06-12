/// Constants for Firestore collections, fields, and default values
class FirestoreConstants {
  // Collection names
  static const String incomingMessagesCollection = 'incoming_messages';
  static const String processedMessagesCollection = 'processed_messages';
  
  // Common field names
  static const String userIdField = 'userId';
  static const String processedField = 'processed';
  static const String contentField = 'content';
  static const String metadataField = 'metadata';
  static const String threadIdField = 'threadId';
  static const String processedAtField = 'processedAt';
  static const String createdAtField = 'createdAt';
  static const String originalIdField = 'originalId';
  
  // Metadata field names
  static const String threadNameField = 'threadName';
  static const String agentIdField = 'agentId';
  static const String subjectField = 'subject';
  static const String durationField = 'duration';
  
  // Default values
  static const int defaultMessageDuration = 60;
  static const String defaultThreadName = 'New Conversation';
  
  // Private constructor to prevent instantiation
  FirestoreConstants._();
}