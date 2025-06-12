import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import '../../core/utils/logger.dart';

class FirestoreService {
  late final FirebaseFirestore _firestore;
  
  FirestoreService() {
    // Initialize Firestore with the correct database
    final databaseId = dotenv.env['FIRESTORE_DATABASE_ID'] ?? 'mcafee-noname';
    logger.i('[FirestoreService] Initializing with database: $databaseId');
    
    _firestore = FirebaseFirestore.instanceFor(
      app: Firebase.app(),
      databaseId: databaseId,
    );
  }
  
  // Collection names
  static const String _incomingMessagesCollection = 'incoming_messages';
  static const String _processedMessagesCollection = 'processed_messages';
  
  /// Listen for new incoming messages for a user
  Stream<DocumentSnapshot?> listenForIncomingMessages({required String userId}) {
    logger.i('[FirestoreService] Setting up Firestore listener for user: $userId');
    
    return _firestore
        .collection(_incomingMessagesCollection)
        .where('userId', isEqualTo: userId)
        .where('processed', isEqualTo: false)
        .snapshots()
        .map((snapshot) {
          logger.i('[FirestoreService] Snapshot received - ${snapshot.docs.length} documents');
          if (snapshot.docs.isEmpty) {
            logger.i('[FirestoreService] No unprocessed messages found');
            return null;
          }
          // Return the first unprocessed message
          logger.i('[FirestoreService] Found unprocessed message: ${snapshot.docs.first.id}');
          return snapshot.docs.first;
        });
  }
  
  /// Process an incoming message (just mark as processed, don't create thread or send to agent)
  Future<Map<String, dynamic>> processIncomingMessage({
    required String userId,
    required DocumentSnapshot messageDoc,
  }) async {
    try {
      final data = messageDoc.data() as Map<String, dynamic>;
      final messageContent = data['content'] as String;
      final messageMetadata = Map<String, dynamic>.from(data['metadata'] ?? {});
      
      
      // Mark the message as processed
      await _markMessageAsProcessed(messageDoc.id, null);
      
      // Move to processed collection for history
      await _moveToProcessedMessages(messageDoc, null);
      
      // Return the message info for the notification
      return {
        'content': messageContent,
        'threadName': messageMetadata['threadName'] ?? 'New Conversation',
        'agentId': messageMetadata['agentId'] as String? ?? 
                    dotenv.env['MOBILE_AGENT_ID'] ?? 
                    'asst_NhwtO75WEHWaW0Oy3Wsv9y7Q',
        'subject': messageMetadata['subject'] as String?,
        'duration': messageMetadata['duration'] as int? ?? 60, // Default to 60 seconds
      };
      
    } catch (e) {
      logger.e('Error processing incoming message: $e');
      rethrow;
    }
  }
  
  /// Mark message as processed
  Future<void> _markMessageAsProcessed(String messageId, String? threadId) async {
    try {
      final updateData = <String, dynamic>{
        'processed': true,
        'processedAt': FieldValue.serverTimestamp(),
      };
      
      if (threadId != null) {
        updateData['threadId'] = threadId;
      }
      
      await _firestore
          .collection(_incomingMessagesCollection)
          .doc(messageId)
          .update(updateData);
    } catch (e) {
      logger.e('Error marking message as processed: $e');
    }
  }
  
  /// Move processed message to history collection
  Future<void> _moveToProcessedMessages(DocumentSnapshot messageDoc, String? threadId) async {
    try {
      final data = messageDoc.data() as Map<String, dynamic>;
      data['originalId'] = messageDoc.id;
      data['threadId'] = threadId;
      data['processedAt'] = FieldValue.serverTimestamp();
      
      await _firestore.collection(_processedMessagesCollection).add(data);
      await messageDoc.reference.delete();
      
    } catch (e) {
      logger.e('Error moving message to processed collection: $e');
    }
  }
  
  /// Test method to add a message to Firestore (for testing the flow)
  Future<void> addTestIncomingMessage({
    required String userId,
    required String content,
    Map<String, dynamic>? metadata,
  }) async {
    try {
      await _firestore.collection(_incomingMessagesCollection).add({
        'userId': userId,
        'content': content,
        'createdAt': FieldValue.serverTimestamp(),
        'processed': false,
        'metadata': metadata ?? {},
      });
    } catch (e) {
      logger.e('Error adding test message to Firestore: $e');
      rethrow;
    }
  }
}