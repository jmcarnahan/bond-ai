import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import '../../core/utils/logger.dart';
import '../../core/constants/firestore_constants.dart';

class FirestoreService {
  late final FirebaseFirestore _firestore;

  FirestoreService() {
    // Initialize Firestore with the correct database
    final databaseId = dotenv.env['FIRESTORE_DATABASE_ID'];
    if (databaseId == null || databaseId.isEmpty) {
      throw Exception('FIRESTORE_DATABASE_ID environment variable not set');
    }

    logger.i('[FirestoreService] Initializing with database: $databaseId');

    _firestore = FirebaseFirestore.instanceFor(
      app: Firebase.app(),
      databaseId: databaseId,
    );
  }

  /// Listen for new incoming messages for a user
  Stream<DocumentSnapshot?> listenForIncomingMessages({
    required String userId,
  }) {
    logger.i(
      '[FirestoreService] Setting up Firestore listener for user: $userId',
    );

    return _firestore
        .collection(FirestoreConstants.incomingMessagesCollection)
        .where(FirestoreConstants.userIdField, isEqualTo: userId)
        .where(FirestoreConstants.processedField, isEqualTo: false)
        .snapshots()
        .map((snapshot) {
          // logger.i('[FirestoreService] Snapshot received - ${snapshot.docs.length} documents');
          if (snapshot.docs.isEmpty) {
            // logger.i('[FirestoreService] No unprocessed messages found');
            return null;
          }
          // Return the first unprocessed message
          logger.i(
            '[FirestoreService] Found unprocessed message: ${snapshot.docs.first.id}',
          );
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
      logger.i('[FirestoreService] Processing incoming message data: $data');
      
      final messageContent = data[FirestoreConstants.contentField] as String;
      final messageMetadata = Map<String, dynamic>.from(
        data[FirestoreConstants.metadataField] ?? {},
      );
      
      logger.i('[FirestoreService] Message metadata: $messageMetadata');
      logger.i('[FirestoreService] Looking for agentId in metadata[${FirestoreConstants.agentIdField}]');
      
      final agentId = messageMetadata[FirestoreConstants.agentIdField] as String? ??
          dotenv.env['DEFAULT_AGENT_ID'] ??
          'default_agent_id';
      
      logger.i('[FirestoreService] Agent ID resolved to: $agentId');

      // Mark the message as processed
      await _markMessageAsProcessed(messageDoc.id, null);

      // Move to processed collection for history
      await _moveToProcessedMessages(messageDoc, null);

      // Return the message info for the notification
      return {
        FirestoreConstants.contentField: messageContent,
        FirestoreConstants.threadNameField:
            messageMetadata[FirestoreConstants.threadNameField] ??
            FirestoreConstants.defaultThreadName,
        FirestoreConstants.agentIdField: agentId,
        FirestoreConstants.subjectField:
            messageMetadata[FirestoreConstants.subjectField] as String?,
        FirestoreConstants.durationField:
            messageMetadata[FirestoreConstants.durationField] as int? ??
            FirestoreConstants.defaultMessageDuration,
      };
    } catch (e) {
      logger.e('Error processing incoming message: $e');
      rethrow;
    }
  }

  /// Mark message as processed
  Future<void> _markMessageAsProcessed(
    String messageId,
    String? threadId,
  ) async {
    try {
      final updateData = <String, dynamic>{
        FirestoreConstants.processedField: true,
        FirestoreConstants.processedAtField: FieldValue.serverTimestamp(),
      };

      if (threadId != null) {
        updateData[FirestoreConstants.threadIdField] = threadId;
      }

      await _firestore
          .collection(FirestoreConstants.incomingMessagesCollection)
          .doc(messageId)
          .update(updateData);
    } catch (e) {
      logger.e('Error marking message as processed: $e');
    }
  }

  /// Move processed message to history collection
  Future<void> _moveToProcessedMessages(
    DocumentSnapshot messageDoc,
    String? threadId,
  ) async {
    try {
      final data = messageDoc.data() as Map<String, dynamic>;
      data[FirestoreConstants.originalIdField] = messageDoc.id;
      data[FirestoreConstants.threadIdField] = threadId;
      data[FirestoreConstants.processedAtField] = FieldValue.serverTimestamp();

      await _firestore
          .collection(FirestoreConstants.processedMessagesCollection)
          .add(data);
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
      await _firestore
          .collection(FirestoreConstants.incomingMessagesCollection)
          .add({
            FirestoreConstants.userIdField: userId,
            FirestoreConstants.contentField: content,
            FirestoreConstants.createdAtField: FieldValue.serverTimestamp(),
            FirestoreConstants.processedField: false,
            FirestoreConstants.metadataField: metadata ?? {},
          });
    } catch (e) {
      logger.e('Error adding test message to Firestore: $e');
      rethrow;
    }
  }
}
