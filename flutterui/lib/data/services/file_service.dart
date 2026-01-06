import 'dart:convert';
// ignore: avoid_web_libraries_in_flutter
import 'dart:html' show AnchorElement, Blob, Url, document;
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/services/http_client.dart';
import 'package:flutterui/data/services/auth_service.dart';
import '../../core/utils/logger.dart';

/// Service for handling file operations across the application
@immutable
class FileService {
  final AuthenticatedHttpClient _httpClient;

  const FileService({required AuthenticatedHttpClient httpClient})
      : _httpClient = httpClient;

  factory FileService.fromAuthService({
    http.Client? httpClient,
    required AuthService authService,
  }) {
    final authenticatedHttpClient = AuthenticatedHttpClient(
      httpClient: httpClient,
      authService: authService,
    );

    return FileService(httpClient: authenticatedHttpClient);
  }

  /// Upload a file and return the provider file ID and metadata
  Future<FileUploadResponseModel> uploadFile(String fileName, Uint8List fileBytes) async {
    logger.i("[FileService] uploadFile called for: $fileName");
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse(ApiConstants.baseUrl + ApiConstants.filesEndpoint),
      );

      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          fileBytes,
          filename: fileName,
          contentType: MediaType('application', 'octet-stream'),
        ),
      );

      final response = await _httpClient.sendMultipartRequest(request);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        logger.i("[FileService] Successfully uploaded file: $fileName");
        return FileUploadResponseModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to upload file: ${response.statusCode} ${response.body}';
        logger.e("[FileService] $errorMsg for $fileName");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FileService] Error in uploadFile for $fileName: ${e.toString()}");
      throw Exception('Failed to upload file: ${e.toString()}');
    }
  }

  /// Delete a file by its provider file ID
  Future<void> deleteFile(String providerFileId) async {
    logger.i("[FileService] deleteFile called for ID: $providerFileId");
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.filesEndpoint}/$providerFileId';
      final response = await _httpClient.delete(url);

      if (response.statusCode == 200 || response.statusCode == 204) {
        logger.i("[FileService] Successfully deleted file: $providerFileId");
        return;
      } else {
        final errorMsg = 'Failed to delete file: ${response.statusCode} ${response.body}';
        logger.e("[FileService] $errorMsg for $providerFileId");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FileService] Error in deleteFile for $providerFileId: ${e.toString()}");
      throw Exception('Failed to delete file: ${e.toString()}');
    }
  }

  /// Get details for multiple files by their IDs
  Future<List<FileDetailsResponseModel>> getFileDetails(List<String> fileIds) async {
    logger.i("[FileService] getFileDetails called for ${fileIds.length} files");
    try {
      if (fileIds.isEmpty) {
        return [];
      }

      // Build query parameters for the file IDs
      final queryParams = fileIds.map((id) => 'file_ids=$id').join('&');
      final uri = Uri.parse('${ApiConstants.baseUrl}${ApiConstants.filesEndpoint}/details?$queryParams');

      // Add timeout to prevent hanging
      final response = await _httpClient.get(uri.toString()).timeout(
        const Duration(seconds: 10),
        onTimeout: () {
          logger.e("[FileService] getFileDetails timed out after 10 seconds");
          throw Exception('Request timed out while fetching file details');
        },
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final fileDetails = data.map((item) => FileDetailsResponseModel.fromJson(item)).toList();
        logger.i("[FileService] Successfully retrieved ${fileDetails.length} file details");
        return fileDetails;
      } else {
        final errorMsg = 'Failed to get file details: ${response.statusCode} ${response.body}';
        logger.e("[FileService] $errorMsg");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FileService] Error in getFileDetails: ${e.toString()}");
      throw Exception('Failed to get file details: ${e.toString()}');
    }
  }

  /// Get a list of all files
  Future<List<FileInfoModel>> getFiles() async {
    logger.i("[FileService] getFiles called");
    try {
      final url = ApiConstants.baseUrl + ApiConstants.filesEndpoint;
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<FileInfoModel> files = data
            .map((item) => FileInfoModel.fromJson(item as Map<String, dynamic>))
            .toList();

        logger.i("[FileService] Retrieved ${files.length} files");
        return files;
      } else {
        final errorMsg = 'Failed to get files: ${response.statusCode}';
        logger.e("[FileService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FileService] Error in getFiles: ${e.toString()}");
      throw Exception('Failed to fetch files: ${e.toString()}');
    }
  }

  /// Get information for a single file by its provider file ID
  Future<FileInfoModel> getFileInfo(String providerFileId) async {
    logger.i("[FileService] getFileInfo called for ID: $providerFileId");
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.filesEndpoint}/$providerFileId';
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        logger.i("[FileService] Successfully retrieved file info: $providerFileId");
        return FileInfoModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to get file info: ${response.statusCode}';
        logger.e("[FileService] $errorMsg for $providerFileId, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FileService] Error in getFileInfo for $providerFileId: ${e.toString()}");
      throw Exception('Failed to fetch file info: ${e.toString()}');
    }
  }

  /// Download a file by its ID
  Future<void> downloadFile(String fileId, String fileName) async {
    logger.i("[FileService] downloadFile called for ID: $fileId, fileName: $fileName");
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.filesEndpoint}/download/$fileId';
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        logger.i("[FileService] Successfully downloaded file: $fileName");

        // For web platform, trigger download via blob
        if (kIsWeb) {
          // Create blob from response bytes and trigger download
          final blob = Blob([response.bodyBytes]);
          final blobUrl = Url.createObjectUrlFromBlob(blob);

          final anchor = AnchorElement()
            ..href = blobUrl
            ..download = fileName
            ..style.display = 'none';
          document.body?.append(anchor);
          anchor.click();
          anchor.remove();

          // Clean up the blob URL
          Url.revokeObjectUrl(blobUrl);
        } else {
          // For mobile/desktop, we would use path_provider and save to downloads
          // This would require additional implementation
          logger.w("[FileService] Mobile/desktop download not yet implemented");
          throw Exception('Download is only supported on web platform currently');
        }
      } else {
        final errorMsg = 'Failed to download file: ${response.statusCode}';
        logger.e("[FileService] $errorMsg for $fileId");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FileService] Error in downloadFile for $fileId: ${e.toString()}");
      throw Exception('Failed to download file: ${e.toString()}');
    }
  }

  void dispose() {
    _httpClient.dispose();
  }
}

/// Model for file information (moved from agent_file_service.dart)
class FileInfoModel {
  final String id;
  final String fileName;
  final int fileSize;
  final DateTime createdAt;
  final String? contentType;

  const FileInfoModel({
    required this.id,
    required this.fileName,
    required this.fileSize,
    required this.createdAt,
    this.contentType,
  });

  factory FileInfoModel.fromJson(Map<String, dynamic> json) {
    return FileInfoModel(
      id: json['id'] as String,
      fileName: json['fileName'] as String,
      fileSize: json['fileSize'] as int,
      createdAt: DateTime.parse(json['createdAt'] as String),
      contentType: json['contentType'] as String?,
    );
  }

  String get providerFileId => id;

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'fileName': fileName,
      'fileSize': fileSize,
      'createdAt': createdAt.toIso8601String(),
      'contentType': contentType,
    };
  }
}
