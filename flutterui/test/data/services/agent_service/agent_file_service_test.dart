import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:flutterui/data/services/agent_service/agent_file_service.dart';
import 'package:flutterui/data/services/agent_service/agent_http_client.dart';

class MockAgentHttpClient implements AgentHttpClient {
  final Map<String, http.Response> _responses = {};
  final List<String> _requestUrls = [];
  final List<String> _requestMethods = [];
  final List<http.MultipartRequest> _multipartRequests = [];

  void setResponse(String url, http.Response response) {
    _responses[url] = response;
  }

  List<String> get requestUrls => List.unmodifiable(_requestUrls);
  List<String> get requestMethods => List.unmodifiable(_requestMethods);
  List<http.MultipartRequest> get multipartRequests => List.unmodifiable(_multipartRequests);

  @override
  Future<http.Response> get(String url) async {
    _requestUrls.add(url);
    _requestMethods.add('GET');
    
    final response = _responses[url];
    if (response != null) {
      return response;
    }
    return http.Response('Not Found', 404);
  }

  @override
  Future<http.Response> post(String url, Map<String, dynamic> data) async {
    throw UnimplementedError('Not used in file service');
  }

  @override
  Future<http.Response> put(String url, Map<String, dynamic> data) async {
    throw UnimplementedError('Not used in file service');
  }

  @override
  Future<http.Response> delete(String url) async {
    _requestUrls.add(url);
    _requestMethods.add('DELETE');
    
    final response = _responses[url];
    if (response != null) {
      return response;
    }
    return http.Response('Not Found', 404);
  }

  @override
  Future<http.Response> sendMultipartRequest(http.MultipartRequest request) async {
    _multipartRequests.add(request);
    _requestUrls.add(request.url.toString());
    _requestMethods.add('MULTIPART');
    
    final response = _responses[request.url.toString()];
    if (response != null) {
      return response;
    }
    return http.Response('Not Found', 404);
  }

  @override
  void dispose() {}
}

void main() {
  group('AgentFileService Tests', () {
    late MockAgentHttpClient mockHttpClient;
    late AgentFileService agentFileService;

    setUp(() {
      mockHttpClient = MockAgentHttpClient();
      agentFileService = AgentFileService(httpClient: mockHttpClient);
    });

    test('constructor should create service with http client', () {
      final service = AgentFileService(httpClient: mockHttpClient);
      expect(service, isA<AgentFileService>());
    });

    group('uploadFile', () {
      test('should upload file successfully', () async {
        final fileBytes = Uint8List.fromList([1, 2, 3, 4, 5]);
        const fileName = 'test.txt';

        const responseJson = '''{
          "provider_file_id": "file-123",
          "file_name": "test.txt",
          "message": "File uploaded successfully"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(responseJson, 200),
        );

        final response = await agentFileService.uploadFile(fileName, fileBytes);

        expect(response.providerFileId, equals('file-123'));
        expect(response.fileName, equals('test.txt'));
        expect(response.message, equals('File uploaded successfully'));
        expect(mockHttpClient.requestMethods.last, equals('MULTIPART'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/files'));
        expect(mockHttpClient.multipartRequests, hasLength(1));
        
        final multipartRequest = mockHttpClient.multipartRequests.first;
        expect(multipartRequest.method, equals('POST'));
        expect(multipartRequest.files, hasLength(1));
        expect(multipartRequest.files.first.field, equals('file'));
        expect(multipartRequest.files.first.filename, equals(fileName));
      });

      test('should upload empty file', () async {
        final fileBytes = Uint8List.fromList([]);
        const fileName = 'empty.txt';

        const responseJson = '''{
          "provider_file_id": "file-empty",
          "file_name": "empty.txt",
          "message": "Empty file uploaded"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(responseJson, 200),
        );

        final response = await agentFileService.uploadFile(fileName, fileBytes);

        expect(response.providerFileId, equals('file-empty'));
        expect(response.fileName, equals('empty.txt'));
        expect(response.message, equals('Empty file uploaded'));
      });

      test('should upload large file', () async {
        final fileBytes = Uint8List.fromList(List.generate(1024 * 1024, (i) => i % 256));
        const fileName = 'large.bin';

        const responseJson = '''{
          "provider_file_id": "file-large",
          "file_name": "large.bin",
          "message": "Large file uploaded"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(responseJson, 200),
        );

        final response = await agentFileService.uploadFile(fileName, fileBytes);

        expect(response.providerFileId, equals('file-large'));
        expect(response.fileName, equals('large.bin'));
        
        final multipartRequest = mockHttpClient.multipartRequests.first;
        expect(multipartRequest.files.first.length, equals(fileBytes.length));
      });

      test('should handle various file types', () async {
        final testFiles = [
          ('document.pdf', 'application/pdf'),
          ('image.png', 'image/png'),
          ('data.csv', 'text/csv'),
          ('script.py', 'text/plain'),
          ('config.json', 'application/json'),
          ('style.css', 'text/css'),
          ('app.js', 'application/javascript'),
          ('readme.md', 'text/markdown'),
        ];

        for (final (fileName, _) in testFiles) {
          final fileBytes = Uint8List.fromList([1, 2, 3]);
          
          final responseJson = '''{
            "provider_file_id": "file-${fileName.hashCode}",
            "file_name": "$fileName",
            "message": "File uploaded successfully"
          }''';

          mockHttpClient.setResponse(
            'https://your-api-url.com/files',
            http.Response(responseJson, 200),
          );

          final response = await agentFileService.uploadFile(fileName, fileBytes);

          expect(response.fileName, equals(fileName));
          
          final multipartRequest = mockHttpClient.multipartRequests.last;
          expect(multipartRequest.files.first.filename, equals(fileName));
        }
      });

      test('should handle upload with special characters in filename', () async {
        final fileBytes = Uint8List.fromList([1, 2, 3]);
        const fileName = 'файл_с_émojis_🚀.txt';

        const responseJson = '''{
          "provider_file_id": "file-special",
          "file_name": "$fileName",
          "message": "File with special chars uploaded"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(responseJson, 200),
        );

        final response = await agentFileService.uploadFile(fileName, fileBytes);

        expect(response.fileName, equals(fileName));
        
        final multipartRequest = mockHttpClient.multipartRequests.first;
        expect(multipartRequest.files.first.filename, equals(fileName));
      });

      test('should throw exception on upload error', () async {
        final fileBytes = Uint8List.fromList([1, 2, 3]);
        const fileName = 'test.txt';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response('Bad Request', 400),
        );

        expect(
          () => agentFileService.uploadFile(fileName, fileBytes),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to upload file: 400'),
          )),
        );
      });

      test('should throw exception on invalid JSON response', () async {
        final fileBytes = Uint8List.fromList([1, 2, 3]);
        const fileName = 'test.txt';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response('invalid json', 200),
        );

        expect(
          () => agentFileService.uploadFile(fileName, fileBytes),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to upload file'),
          )),
        );
      });

      test('should throw exception on network error', () async {
        final fileBytes = Uint8List.fromList([1, 2, 3]);
        const fileName = 'test.txt';

        expect(
          () => agentFileService.uploadFile(fileName, fileBytes),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('deleteFile', () {
      test('should delete file successfully with 200 status', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response('', 200),
        );

        await agentFileService.deleteFile('file-123');

        expect(mockHttpClient.requestMethods.last, equals('DELETE'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/files/file-123'));
      });

      test('should delete file successfully with 204 status', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response('', 204),
        );

        await agentFileService.deleteFile('file-123');

        expect(mockHttpClient.requestMethods.last, equals('DELETE'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/files/file-123'));
      });

      test('should throw exception on 404 error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/nonexistent',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentFileService.deleteFile('nonexistent'),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to delete file: 404'),
          )),
        );
      });

      test('should throw exception on 403 error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/protected-file',
          http.Response('Forbidden', 403),
        );

        expect(
          () => agentFileService.deleteFile('protected-file'),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to delete file: 403'),
          )),
        );
      });

      test('should handle empty file ID', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/',
          http.Response('', 200),
        );

        await agentFileService.deleteFile('');
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/files/'));
      });

      test('should handle special characters in file ID', () async {
        const specialId = 'file-with-special-@#%';
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/$specialId',
          http.Response('', 200),
        );

        await agentFileService.deleteFile(specialId);
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/files/$specialId'));
      });

      test('should handle network error in delete', () async {
        expect(
          () => agentFileService.deleteFile('file-123'),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('getFiles', () {
      test('should return list of files', () async {
        const filesJson = '''[
          {
            "id": "file-1",
            "fileName": "document1.pdf",
            "fileSize": 1024,
            "createdAt": "2023-01-01T10:00:00Z",
            "contentType": "application/pdf"
          },
          {
            "id": "file-2",
            "fileName": "document2.txt",
            "fileSize": 512,
            "createdAt": "2023-01-02T10:00:00Z",
            "contentType": "text/plain"
          }
        ]''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(filesJson, 200),
        );

        final files = await agentFileService.getFiles();

        expect(files, hasLength(2));
        expect(files[0].id, equals('file-1'));
        expect(files[0].fileName, equals('document1.pdf'));
        expect(files[0].fileSize, equals(1024));
        expect(files[0].contentType, equals('application/pdf'));
        expect(files[1].id, equals('file-2'));
        expect(files[1].fileName, equals('document2.txt'));
        expect(files[1].fileSize, equals(512));
        expect(files[1].contentType, equals('text/plain'));
        expect(mockHttpClient.requestMethods.last, equals('GET'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/files'));
      });

      test('should handle empty file list', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response('[]', 200),
        );

        final files = await agentFileService.getFiles();

        expect(files, isEmpty);
      });

      test('should handle files without content type', () async {
        const filesJson = '''[
          {
            "id": "file-1",
            "fileName": "unknown.bin",
            "fileSize": 256,
            "createdAt": "2023-01-01T10:00:00Z"
          }
        ]''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(filesJson, 200),
        );

        final files = await agentFileService.getFiles();

        expect(files, hasLength(1));
        expect(files[0].id, equals('file-1'));
        expect(files[0].fileName, equals('unknown.bin'));
        expect(files[0].fileSize, equals(256));
        expect(files[0].contentType, isNull);
      });

      test('should throw exception on 500 error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response('Internal Server Error', 500),
        );

        expect(
          () => agentFileService.getFiles(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to get files: 500'),
          )),
        );
      });

      test('should throw exception on invalid JSON', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response('invalid json', 200),
        );

        expect(
          () => agentFileService.getFiles(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to fetch files'),
          )),
        );
      });

      test('should handle network error', () async {
        expect(
          () => agentFileService.getFiles(),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('getFileInfo', () {
      test('should return file info successfully', () async {
        const fileInfoJson = '''{
          "id": "file-123",
          "fileName": "document.pdf",
          "fileSize": 2048,
          "createdAt": "2023-01-01T10:00:00Z",
          "contentType": "application/pdf"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response(fileInfoJson, 200),
        );

        final fileInfo = await agentFileService.getFileInfo('file-123');

        expect(fileInfo.id, equals('file-123'));
        expect(fileInfo.fileName, equals('document.pdf'));
        expect(fileInfo.fileSize, equals(2048));
        expect(fileInfo.contentType, equals('application/pdf'));
        expect(fileInfo.createdAt, equals(DateTime.parse('2023-01-01T10:00:00Z')));
        expect(mockHttpClient.requestMethods.last, equals('GET'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/files/file-123'));
      });

      test('should return file info without content type', () async {
        const fileInfoJson = '''{
          "id": "file-123",
          "fileName": "unknown.bin",
          "fileSize": 1024,
          "createdAt": "2023-01-01T10:00:00Z"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response(fileInfoJson, 200),
        );

        final fileInfo = await agentFileService.getFileInfo('file-123');

        expect(fileInfo.id, equals('file-123'));
        expect(fileInfo.fileName, equals('unknown.bin'));
        expect(fileInfo.fileSize, equals(1024));
        expect(fileInfo.contentType, isNull);
      });

      test('should throw exception on 404 error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/nonexistent',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentFileService.getFileInfo('nonexistent'),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to get file info: 404'),
          )),
        );
      });

      test('should throw exception on invalid JSON', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response('invalid json', 200),
        );

        expect(
          () => agentFileService.getFileInfo('file-123'),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to fetch file info'),
          )),
        );
      });

      test('should handle empty file ID', () async {
        const fileInfoJson = '''{
          "id": "",
          "fileName": "test.txt",
          "fileSize": 100,
          "createdAt": "2023-01-01T10:00:00Z"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files/',
          http.Response(fileInfoJson, 200),
        );

        final fileInfo = await agentFileService.getFileInfo('');
        expect(fileInfo.id, equals(''));
        expect(fileInfo.fileName, equals('test.txt'));
      });

      test('should handle special characters in file ID', () async {
        const specialId = 'file-with-special-@#%';
        const fileInfoJson = '''{
          "id": "$specialId",
          "fileName": "special.txt",
          "fileSize": 100,
          "createdAt": "2023-01-01T10:00:00Z"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files/$specialId',
          http.Response(fileInfoJson, 200),
        );

        final fileInfo = await agentFileService.getFileInfo(specialId);
        expect(fileInfo.id, equals(specialId));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/files/$specialId'));
      });

      test('should handle network error', () async {
        expect(
          () => agentFileService.getFileInfo('file-123'),
          throwsA(isA<Exception>()),
        );
      });
    });

    test('should handle multiple operations in sequence', () async {
      final fileBytes = Uint8List.fromList([1, 2, 3]);
      const fileName = 'test.txt';

      const uploadResponseJson = '''{
        "provider_file_id": "file-123",
        "file_name": "test.txt",
        "message": "File uploaded successfully"
      }''';

      const filesListJson = '''[
        {
          "id": "file-123",
          "fileName": "test.txt",
          "fileSize": 3,
          "createdAt": "2023-01-01T10:00:00Z"
        }
      ]''';

      const fileInfoJson = '''{
        "id": "file-123",
        "fileName": "test.txt",
        "fileSize": 3,
        "createdAt": "2023-01-01T10:00:00Z"
      }''';

      mockHttpClient.setResponse(
        'https://your-api-url.com/files',
        http.Response(uploadResponseJson, 200),
      );
      
      mockHttpClient.setResponse(
        'https://your-api-url.com/files',
        http.Response(filesListJson, 200),
      );
      
      mockHttpClient.setResponse(
        'https://your-api-url.com/files/file-123',
        http.Response(fileInfoJson, 200),
      );

      final uploadResponse = await agentFileService.uploadFile(fileName, fileBytes);
      expect(uploadResponse.providerFileId, equals('file-123'));

      final files = await agentFileService.getFiles();
      expect(files, hasLength(1));
      expect(files[0].id, equals('file-123'));

      final fileInfo = await agentFileService.getFileInfo('file-123');
      expect(fileInfo.id, equals('file-123'));

      mockHttpClient.setResponse(
        'https://your-api-url.com/files/file-123',
        http.Response('', 200),
      );

      await agentFileService.deleteFile('file-123');

      expect(mockHttpClient.requestMethods, hasLength(4));
      expect(mockHttpClient.requestMethods[0], equals('MULTIPART'));
      expect(mockHttpClient.requestMethods[1], equals('GET'));
      expect(mockHttpClient.requestMethods[2], equals('GET'));
      expect(mockHttpClient.requestMethods[3], equals('DELETE'));
    });
  });

  group('FileInfoModel Tests', () {
    test('constructor should create file info with required fields', () {
      final createdAt = DateTime.parse('2023-01-01T10:00:00Z');
      final fileInfo = FileInfoModel(
        id: 'file-123',
        fileName: 'test.txt',
        fileSize: 1024,
        createdAt: createdAt,
        contentType: 'text/plain',
      );

      expect(fileInfo.id, equals('file-123'));
      expect(fileInfo.fileName, equals('test.txt'));
      expect(fileInfo.fileSize, equals(1024));
      expect(fileInfo.createdAt, equals(createdAt));
      expect(fileInfo.contentType, equals('text/plain'));
    });

    test('constructor should create file info without content type', () {
      final createdAt = DateTime.parse('2023-01-01T10:00:00Z');
      final fileInfo = FileInfoModel(
        id: 'file-123',
        fileName: 'test.txt',
        fileSize: 1024,
        createdAt: createdAt,
      );

      expect(fileInfo.id, equals('file-123'));
      expect(fileInfo.fileName, equals('test.txt'));
      expect(fileInfo.fileSize, equals(1024));
      expect(fileInfo.createdAt, equals(createdAt));
      expect(fileInfo.contentType, isNull);
    });

    test('fromJson should create file info from valid JSON', () {
      final json = {
        'id': 'file-123',
        'fileName': 'test.txt',
        'fileSize': 1024,
        'createdAt': '2023-01-01T10:00:00Z',
        'contentType': 'text/plain',
      };

      final fileInfo = FileInfoModel.fromJson(json);

      expect(fileInfo.id, equals('file-123'));
      expect(fileInfo.fileName, equals('test.txt'));
      expect(fileInfo.fileSize, equals(1024));
      expect(fileInfo.createdAt, equals(DateTime.parse('2023-01-01T10:00:00Z')));
      expect(fileInfo.contentType, equals('text/plain'));
    });

    test('fromJson should handle missing content type', () {
      final json = {
        'id': 'file-123',
        'fileName': 'test.txt',
        'fileSize': 1024,
        'createdAt': '2023-01-01T10:00:00Z',
      };

      final fileInfo = FileInfoModel.fromJson(json);

      expect(fileInfo.id, equals('file-123'));
      expect(fileInfo.fileName, equals('test.txt'));
      expect(fileInfo.fileSize, equals(1024));
      expect(fileInfo.createdAt, equals(DateTime.parse('2023-01-01T10:00:00Z')));
      expect(fileInfo.contentType, isNull);
    });

    test('toJson should convert file info to JSON correctly', () {
      final createdAt = DateTime.parse('2023-01-01T10:00:00Z');
      final fileInfo = FileInfoModel(
        id: 'file-123',
        fileName: 'test.txt',
        fileSize: 1024,
        createdAt: createdAt,
        contentType: 'text/plain',
      );

      final json = fileInfo.toJson();

      expect(json['id'], equals('file-123'));
      expect(json['fileName'], equals('test.txt'));
      expect(json['fileSize'], equals(1024));
      expect(json['createdAt'], equals('2023-01-01T10:00:00Z'));
      expect(json['contentType'], equals('text/plain'));
    });

    test('toJson should handle null content type', () {
      final createdAt = DateTime.parse('2023-01-01T10:00:00Z');
      final fileInfo = FileInfoModel(
        id: 'file-123',
        fileName: 'test.txt',
        fileSize: 1024,
        createdAt: createdAt,
      );

      final json = fileInfo.toJson();

      expect(json['id'], equals('file-123'));
      expect(json['fileName'], equals('test.txt'));
      expect(json['fileSize'], equals(1024));
      expect(json['createdAt'], equals('2023-01-01T10:00:00Z'));
      expect(json['contentType'], isNull);
    });

    test('should handle JSON roundtrip correctly', () {
      final originalCreatedAt = DateTime.parse('2023-01-01T10:00:00Z');
      final originalFileInfo = FileInfoModel(
        id: 'file-123',
        fileName: 'test.txt',
        fileSize: 1024,
        createdAt: originalCreatedAt,
        contentType: 'text/plain',
      );

      final json = originalFileInfo.toJson();
      final reconstructedFileInfo = FileInfoModel.fromJson(json);

      expect(reconstructedFileInfo.id, equals(originalFileInfo.id));
      expect(reconstructedFileInfo.fileName, equals(originalFileInfo.fileName));
      expect(reconstructedFileInfo.fileSize, equals(originalFileInfo.fileSize));
      expect(reconstructedFileInfo.createdAt, equals(originalFileInfo.createdAt));
      expect(reconstructedFileInfo.contentType, equals(originalFileInfo.contentType));
    });

    test('should handle various file sizes', () {
      final testSizes = [0, 1, 1024, 1048576, 1073741824];

      for (final fileSize in testSizes) {
        final fileInfo = FileInfoModel(
          id: 'file-$fileSize',
          fileName: 'file$fileSize.txt',
          fileSize: fileSize,
          createdAt: DateTime.now(),
        );

        expect(fileInfo.fileSize, equals(fileSize));

        final json = fileInfo.toJson();
        final reconstructedFileInfo = FileInfoModel.fromJson(json);
        expect(reconstructedFileInfo.fileSize, equals(fileSize));
      }
    });

    test('should handle various content types', () {
      final contentTypes = [
        'text/plain',
        'application/json',
        'image/png',
        'video/mp4',
        'audio/mpeg',
        'application/pdf',
        'application/zip',
        'text/html',
        'application/javascript',
        'text/css',
      ];

      for (final contentType in contentTypes) {
        final fileInfo = FileInfoModel(
          id: 'file-${contentType.hashCode}',
          fileName: 'test.$contentType',
          fileSize: 1024,
          createdAt: DateTime.now(),
          contentType: contentType,
        );

        expect(fileInfo.contentType, equals(contentType));

        final json = fileInfo.toJson();
        final reconstructedFileInfo = FileInfoModel.fromJson(json);
        expect(reconstructedFileInfo.contentType, equals(contentType));
      }
    });

    test('should handle special characters in fields', () {
      final createdAt = DateTime.parse('2023-01-01T10:00:00Z');
      final fileInfo = FileInfoModel(
        id: 'file-with-special-@#\$%^&*()',
        fileName: 'файл_с_émojis_🚀.txt',
        fileSize: 1024,
        createdAt: createdAt,
        contentType: 'text/plain; charset=utf-8',
      );

      final json = fileInfo.toJson();
      final reconstructedFileInfo = FileInfoModel.fromJson(json);

      expect(reconstructedFileInfo.id, equals('file-with-special-@#\$%^&*()'));
      expect(reconstructedFileInfo.fileName, equals('файл_с_émojis_🚀.txt'));
      expect(reconstructedFileInfo.contentType, equals('text/plain; charset=utf-8'));
    });
  });
}