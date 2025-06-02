import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/api_response_models.dart';

void main() {
  group('AgentResponseModel Tests', () {
    test('constructor should create agent response with required fields', () {
      const agentResponse = AgentResponseModel(
        agentId: 'agent-123',
        name: 'Test Agent',
      );

      expect(agentResponse.agentId, equals('agent-123'));
      expect(agentResponse.name, equals('Test Agent'));
    });

    test('fromJson should create agent response from valid JSON', () {
      final json = {
        'agent_id': 'agent-123',
        'name': 'Test Agent',
      };

      final agentResponse = AgentResponseModel.fromJson(json);

      expect(agentResponse.agentId, equals('agent-123'));
      expect(agentResponse.name, equals('Test Agent'));
    });

    test('toJson should convert agent response to JSON correctly', () {
      const agentResponse = AgentResponseModel(
        agentId: 'agent-123',
        name: 'Test Agent',
      );

      final json = agentResponse.toJson();

      expect(json['agent_id'], equals('agent-123'));
      expect(json['name'], equals('Test Agent'));
    });

    test('should handle JSON roundtrip correctly', () {
      const originalAgentResponse = AgentResponseModel(
        agentId: 'agent-123',
        name: 'Test Agent',
      );

      final json = originalAgentResponse.toJson();
      final reconstructedAgentResponse = AgentResponseModel.fromJson(json);

      expect(reconstructedAgentResponse.agentId, equals(originalAgentResponse.agentId));
      expect(reconstructedAgentResponse.name, equals(originalAgentResponse.name));
    });

    test('should handle empty strings', () {
      const agentResponse = AgentResponseModel(
        agentId: '',
        name: '',
      );

      expect(agentResponse.agentId, equals(''));
      expect(agentResponse.name, equals(''));

      final json = agentResponse.toJson();
      final reconstructedAgentResponse = AgentResponseModel.fromJson(json);
      expect(reconstructedAgentResponse.agentId, equals(''));
      expect(reconstructedAgentResponse.name, equals(''));
    });

    test('should handle special characters in fields', () {
      const agentResponse = AgentResponseModel(
        agentId: 'agent-with-special-chars-@#\$%',
        name: 'Agent with émojis 🤖 and spëcial chars',
      );

      final json = agentResponse.toJson();
      final reconstructedAgentResponse = AgentResponseModel.fromJson(json);
      expect(reconstructedAgentResponse.agentId, equals('agent-with-special-chars-@#\$%'));
      expect(reconstructedAgentResponse.name, equals('Agent with émojis 🤖 and spëcial chars'));
    });

    test('should handle long strings', () {
      final longId = 'agent-${'x' * 1000}';
      final longName = 'Agent Name ${'y' * 1000}';
      
      final agentResponse = AgentResponseModel(
        agentId: longId,
        name: longName,
      );

      expect(agentResponse.agentId, equals(longId));
      expect(agentResponse.name, equals(longName));

      final json = agentResponse.toJson();
      final reconstructedAgentResponse = AgentResponseModel.fromJson(json);
      expect(reconstructedAgentResponse.agentId, equals(longId));
      expect(reconstructedAgentResponse.name, equals(longName));
    });

    test('immutable annotation should prevent modification', () {
      const agentResponse = AgentResponseModel(
        agentId: 'agent-123',
        name: 'Test Agent',
      );
      
      expect(agentResponse, isA<AgentResponseModel>());
      expect(() => agentResponse.agentId, returnsNormally);
      expect(() => agentResponse.name, returnsNormally);
    });
  });

  group('FileUploadResponseModel Tests', () {
    test('constructor should create file upload response with required fields', () {
      const fileUploadResponse = FileUploadResponseModel(
        providerFileId: 'file-123',
        fileName: 'test.txt',
        message: 'File uploaded successfully',
      );

      expect(fileUploadResponse.providerFileId, equals('file-123'));
      expect(fileUploadResponse.fileName, equals('test.txt'));
      expect(fileUploadResponse.message, equals('File uploaded successfully'));
    });

    test('fromJson should create file upload response from valid JSON', () {
      final json = {
        'provider_file_id': 'file-123',
        'file_name': 'test.txt',
        'message': 'File uploaded successfully',
      };

      final fileUploadResponse = FileUploadResponseModel.fromJson(json);

      expect(fileUploadResponse.providerFileId, equals('file-123'));
      expect(fileUploadResponse.fileName, equals('test.txt'));
      expect(fileUploadResponse.message, equals('File uploaded successfully'));
    });

    test('toJson should convert file upload response to JSON correctly', () {
      const fileUploadResponse = FileUploadResponseModel(
        providerFileId: 'file-123',
        fileName: 'test.txt',
        message: 'File uploaded successfully',
      );

      final json = fileUploadResponse.toJson();

      expect(json['provider_file_id'], equals('file-123'));
      expect(json['file_name'], equals('test.txt'));
      expect(json['message'], equals('File uploaded successfully'));
    });

    test('should handle JSON roundtrip correctly', () {
      const originalFileUploadResponse = FileUploadResponseModel(
        providerFileId: 'file-123',
        fileName: 'test.txt',
        message: 'File uploaded successfully',
      );

      final json = originalFileUploadResponse.toJson();
      final reconstructedFileUploadResponse = FileUploadResponseModel.fromJson(json);

      expect(reconstructedFileUploadResponse.providerFileId, equals(originalFileUploadResponse.providerFileId));
      expect(reconstructedFileUploadResponse.fileName, equals(originalFileUploadResponse.fileName));
      expect(reconstructedFileUploadResponse.message, equals(originalFileUploadResponse.message));
    });

    test('should handle various file types', () {
      const fileTypes = [
        'document.pdf',
        'image.png',
        'data.csv',
        'archive.zip',
        'script.py',
        'config.json',
        'readme.md',
        'style.css',
        'app.js',
        'database.sql',
      ];

      for (final fileName in fileTypes) {
        final fileUploadResponse = FileUploadResponseModel(
          providerFileId: 'file-${fileName.hashCode}',
          fileName: fileName,
          message: 'Uploaded $fileName successfully',
        );

        expect(fileUploadResponse.fileName, equals(fileName));

        final json = fileUploadResponse.toJson();
        final reconstructedFileUploadResponse = FileUploadResponseModel.fromJson(json);
        expect(reconstructedFileUploadResponse.fileName, equals(fileName));
      }
    });

    test('should handle different message types', () {
      final messages = [
        'File uploaded successfully',
        'Upload completed',
        'File processing started',
        'Error: File too large',
        'Warning: File type not supported',
        'Info: File already exists',
        '',
        'Message with émojis 📁 and spëcial chars',
        'Very long message: ${'x' * 500}',
      ];

      for (final message in messages) {
        final fileUploadResponse = FileUploadResponseModel(
          providerFileId: 'file-123',
          fileName: 'test.txt',
          message: message,
        );

        expect(fileUploadResponse.message, equals(message));

        final json = fileUploadResponse.toJson();
        final reconstructedFileUploadResponse = FileUploadResponseModel.fromJson(json);
        expect(reconstructedFileUploadResponse.message, equals(message));
      }
    });

    test('should handle empty strings', () {
      const fileUploadResponse = FileUploadResponseModel(
        providerFileId: '',
        fileName: '',
        message: '',
      );

      expect(fileUploadResponse.providerFileId, equals(''));
      expect(fileUploadResponse.fileName, equals(''));
      expect(fileUploadResponse.message, equals(''));

      final json = fileUploadResponse.toJson();
      final reconstructedFileUploadResponse = FileUploadResponseModel.fromJson(json);
      expect(reconstructedFileUploadResponse.providerFileId, equals(''));
      expect(reconstructedFileUploadResponse.fileName, equals(''));
      expect(reconstructedFileUploadResponse.message, equals(''));
    });

    test('should handle special characters and unicode', () {
      const fileUploadResponse = FileUploadResponseModel(
        providerFileId: 'file-with-special-@#\$%^&*()_+{}[]|',
        fileName: 'файл.txt', // Cyrillic filename
        message: 'Upload complete ✅ with émojis 🎉',
      );

      final json = fileUploadResponse.toJson();
      final reconstructedFileUploadResponse = FileUploadResponseModel.fromJson(json);
      expect(reconstructedFileUploadResponse.providerFileId, equals('file-with-special-@#\$%^&*()_+{}[]|'));
      expect(reconstructedFileUploadResponse.fileName, equals('файл.txt'));
      expect(reconstructedFileUploadResponse.message, equals('Upload complete ✅ with émojis 🎉'));
    });

    test('immutable annotation should prevent modification', () {
      const fileUploadResponse = FileUploadResponseModel(
        providerFileId: 'file-123',
        fileName: 'test.txt',
        message: 'File uploaded successfully',
      );
      
      expect(fileUploadResponse, isA<FileUploadResponseModel>());
      expect(() => fileUploadResponse.providerFileId, returnsNormally);
      expect(() => fileUploadResponse.fileName, returnsNormally);
      expect(() => fileUploadResponse.message, returnsNormally);
    });

    test('should handle long provider file IDs', () {
      final longId = 'provider-file-id-${'a' * 1000}';
      
      final fileUploadResponse = FileUploadResponseModel(
        providerFileId: longId,
        fileName: 'test.txt',
        message: 'File uploaded successfully',
      );

      expect(fileUploadResponse.providerFileId, equals(longId));

      final json = fileUploadResponse.toJson();
      final reconstructedFileUploadResponse = FileUploadResponseModel.fromJson(json);
      expect(reconstructedFileUploadResponse.providerFileId, equals(longId));
    });
  });
}
