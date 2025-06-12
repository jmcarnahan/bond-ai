import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import '../data/services/firestore_service.dart';
import '../core/utils/logger.dart';
import 'auth_provider.dart';
import 'notification_provider.dart';

/// Provider to check if Firestore is enabled based on environment variable
final isFirestoreEnabledProvider = Provider<bool>((ref) {
  final databaseId = dotenv.env['FIRESTORE_DATABASE_ID'];
  final isEnabled = databaseId != null && databaseId.isNotEmpty;
  
  if (isEnabled) {
    logger.i('[FirestoreProvider] ✅ Firestore listener ENABLED - Database: $databaseId');
  } else {
    logger.i('[FirestoreProvider] ❌ Firestore listener DISABLED - No FIRESTORE_DATABASE_ID found');
  }
  
  return isEnabled;
});

final firestoreServiceProvider = Provider<FirestoreService?>((ref) {
  final isEnabled = ref.watch(isFirestoreEnabledProvider);
  if (!isEnabled) return null;
  
  return FirestoreService();
});

/// Provider for listening to incoming Firestore messages
final incomingMessageStreamProvider = StreamProvider.autoDispose<DocumentSnapshot?>((ref) async* {
  final authState = ref.watch(authNotifierProvider);
  final firestoreService = ref.watch(firestoreServiceProvider);
  
  // Check if Firestore is enabled
  if (firestoreService == null) {
    yield null;
    return;
  }
  
  if (authState is! Authenticated) {
    yield null;
    return;
  }
  
  final userId = authState.user.userId;
  yield* firestoreService.listenForIncomingMessages(userId: userId);
});

/// State notifier for handling message processing
class MessageProcessorNotifier extends StateNotifier<bool> {
  final FirestoreService? _firestoreService;
  final Ref _ref;
  
  MessageProcessorNotifier(this._firestoreService, this._ref) : super(false);
  
  Future<void> processMessage(DocumentSnapshot messageDoc) async {
    if (state) return; // Already processing
    
    if (_firestoreService == null) {
      logger.w('Cannot process message - Firestore service not available');
      return;
    }
    
    state = true; // Set processing flag
    
    try {
      final authState = _ref.read(authNotifierProvider);
      if (authState is! Authenticated) {
        logger.e('Cannot process message - user not authenticated');
        return;
      }
      final userId = authState.user.userId;
      
      // Process the message and get info for notification
      final messageInfo = await _firestoreService.processIncomingMessage(
        userId: userId,
        messageDoc: messageDoc,
      );
      
      // Show notification with message info
      _ref.read(notificationProvider.notifier).showNotificationWithMessageInfo(
        messageInfo: messageInfo,
      );
      
    } catch (e) {
      logger.e('Error processing message: $e');
    } finally {
      state = false; // Clear processing flag
    }
  }
}

final messageProcessorProvider = StateNotifierProvider<MessageProcessorNotifier, bool>((ref) {
  final firestoreService = ref.watch(firestoreServiceProvider);
  return MessageProcessorNotifier(firestoreService, ref);
});

