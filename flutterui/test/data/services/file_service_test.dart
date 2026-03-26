@TestOn('browser')
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/file_service.dart';

// ---------------------------------------------------------------------------
// Manual mock for AuthService
// ---------------------------------------------------------------------------
class MockAuthService implements AuthService {
  @override
  Future<Map<String, String>> get authenticatedHeaders async {
    return {
      'Authorization': 'Bearer test-token',
      'Content-Type': 'application/json',
    };
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
FileService _createService(MockAuthService authService, http.Client client) {
  return FileService.fromAuthService(
    httpClient: client,
    authService: authService,
  );
}

void main() {
  late MockAuthService mockAuthService;

  setUp(() {
    ApiConstants.baseUrl = 'http://localhost:8000';
    mockAuthService = MockAuthService();
  });

  // -------------------------------------------------------------------------
  // downloadFile
  // -------------------------------------------------------------------------
  group('downloadFile', () {
    test('200 response triggers browser download without error', () async {
      final fileBytes = Uint8List.fromList([0x50, 0x4B, 0x03, 0x04]);
      final client = MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/files/download/file-123');
        expect(request.headers['Authorization'], 'Bearer test-token');
        return http.Response.bytes(fileBytes, 200);
      });
      final service = _createService(mockAuthService, client);

      // On browser platform, this invokes the real web_download_web.dart.
      // The blob/anchor download triggers silently in test — no error means success.
      await expectLater(
        service.downloadFile('file-123', 'report.pdf'),
        completes,
      );
    });

    test('404 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Not Found', 404);
      });
      final service = _createService(mockAuthService, client);

      expect(
        () => service.downloadFile('bad-id', 'missing.pdf'),
        throwsException,
      );
    });

    test('500 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Internal Server Error', 500);
      });
      final service = _createService(mockAuthService, client);

      expect(
        () => service.downloadFile('file-123', 'report.pdf'),
        throwsException,
      );
    });

    test('network error throws Exception', () async {
      final client = MockClient((request) async {
        throw Exception('Connection refused');
      });
      final service = _createService(mockAuthService, client);

      expect(
        () => service.downloadFile('file-123', 'report.pdf'),
        throwsException,
      );
    });
  });

  // -------------------------------------------------------------------------
  // uploadFile
  // -------------------------------------------------------------------------
  group('uploadFile', () {
    test('200 response returns FileUploadResponseModel', () async {
      final client = MockClient((request) async {
        expect(request.method, 'POST');
        return http.Response(
          json.encode({
            'provider_file_id': 'pf-123',
            'file_name': 'test.txt',
            'mime_type': 'text/plain',
            'suggested_tool': 'code_interpreter',
            'message': 'File uploaded successfully',
          }),
          200,
        );
      });
      final service = _createService(mockAuthService, client);
      final bytes = Uint8List.fromList([0x48, 0x65, 0x6C, 0x6C, 0x6F]);

      final result = await service.uploadFile('test.txt', bytes);

      expect(result.providerFileId, 'pf-123');
    });

    test('500 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Server Error', 500);
      });
      final service = _createService(mockAuthService, client);
      final bytes = Uint8List.fromList([0x48]);

      expect(
        () => service.uploadFile('test.txt', bytes),
        throwsException,
      );
    });
  });

  // -------------------------------------------------------------------------
  // deleteFile
  // -------------------------------------------------------------------------
  group('deleteFile', () {
    test('200 response completes successfully', () async {
      final client = MockClient((request) async {
        expect(request.method, 'DELETE');
        expect(request.url.path, '/files/pf-123');
        return http.Response('', 200);
      });
      final service = _createService(mockAuthService, client);

      await expectLater(service.deleteFile('pf-123'), completes);
    });

    test('204 response completes successfully', () async {
      final client = MockClient((request) async {
        return http.Response('', 204);
      });
      final service = _createService(mockAuthService, client);

      await expectLater(service.deleteFile('pf-123'), completes);
    });

    test('500 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Error', 500);
      });
      final service = _createService(mockAuthService, client);

      expect(() => service.deleteFile('pf-123'), throwsException);
    });
  });

  // -------------------------------------------------------------------------
  // getFiles
  // -------------------------------------------------------------------------
  group('getFiles', () {
    test('200 response returns list of FileInfoModel', () async {
      final client = MockClient((request) async {
        expect(request.method, 'GET');
        return http.Response(
          json.encode([
            {
              'id': 'f-1',
              'fileName': 'doc.pdf',
              'fileSize': 1024,
              'createdAt': '2024-01-01T00:00:00.000Z',
              'contentType': 'application/pdf',
            },
          ]),
          200,
        );
      });
      final service = _createService(mockAuthService, client);

      final files = await service.getFiles();

      expect(files, hasLength(1));
      expect(files[0].fileName, 'doc.pdf');
      expect(files[0].fileSize, 1024);
      expect(files[0].contentType, 'application/pdf');
    });

    test('200 with empty list returns empty list', () async {
      final client = MockClient((request) async {
        return http.Response(json.encode([]), 200);
      });
      final service = _createService(mockAuthService, client);

      final files = await service.getFiles();

      expect(files, isEmpty);
    });
  });

  // -------------------------------------------------------------------------
  // getFileInfo
  // -------------------------------------------------------------------------
  group('getFileInfo', () {
    test('200 response returns FileInfoModel', () async {
      final client = MockClient((request) async {
        expect(request.url.path, '/files/f-1');
        return http.Response(
          json.encode({
            'id': 'f-1',
            'fileName': 'readme.md',
            'fileSize': 256,
            'createdAt': '2024-06-15T12:00:00.000Z',
          }),
          200,
        );
      });
      final service = _createService(mockAuthService, client);

      final file = await service.getFileInfo('f-1');

      expect(file.id, 'f-1');
      expect(file.fileName, 'readme.md');
      expect(file.contentType, isNull);
    });

    test('404 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Not Found', 404);
      });
      final service = _createService(mockAuthService, client);

      expect(() => service.getFileInfo('bad-id'), throwsException);
    });
  });

  // -------------------------------------------------------------------------
  // getFileDetails
  // -------------------------------------------------------------------------
  group('getFileDetails', () {
    test('empty fileIds returns empty list without HTTP call', () async {
      var called = false;
      final client = MockClient((request) async {
        called = true;
        return http.Response('', 200);
      });
      final service = _createService(mockAuthService, client);

      final result = await service.getFileDetails([]);

      expect(result, isEmpty);
      expect(called, isFalse);
    });

    test('200 response returns list of FileDetailsResponseModel', () async {
      final client = MockClient((request) async {
        expect(request.url.queryParametersAll['file_ids'], ['f-1', 'f-2']);
        return http.Response(
          json.encode([
            {
              'file_id': 'f-1',
              'file_path': '/uploads/a.txt',
              'file_hash': 'abc123',
              'mime_type': 'text/plain',
              'owner_user_id': 'user-1',
            },
            {
              'file_id': 'f-2',
              'file_path': '/uploads/b.txt',
              'file_hash': 'def456',
              'mime_type': 'text/plain',
              'owner_user_id': 'user-1',
            },
          ]),
          200,
        );
      });
      final service = _createService(mockAuthService, client);

      final result = await service.getFileDetails(['f-1', 'f-2']);

      expect(result, hasLength(2));
    });
  });
}
