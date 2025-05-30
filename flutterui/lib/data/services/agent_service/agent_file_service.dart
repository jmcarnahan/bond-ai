import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'agent_http_client.dart';
import '../../../core/utils/logger.dart';

@immutable
class AgentFileService {
  final AgentHttpClient _httpClient;

  const AgentFileService({required AgentHttpClient httpClient})
      : _httpClient = httpClient;

  Future<FileUploadResponseModel> uploadFile(String fileName, Uint8List fileBytes) async {
    logger.i("[AgentFileService] uploadFile called for: $fileName");
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
        logger.i("[AgentFileService] Successfully uploaded file: $fileName");
        return FileUploadResponseModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to upload file: ${response.statusCode} ${response.body}';
        logger.e("[AgentFileService] $errorMsg for $fileName");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentFileService] Error in uploadFile for $fileName: ${e.toString()}");
      throw Exception('Failed to upload file: ${e.toString()}');
    }
  }

  Future<void> deleteFile(String providerFileId) async {
    logger.i("[AgentFileService] deleteFile called for ID: $providerFileId");
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.filesEndpoint}/$providerFileId';
      final response = await _httpClient.delete(url);

      if (response.statusCode == 200 || response.statusCode == 204) {
        logger.i("[AgentFileService] Successfully deleted file: $providerFileId");
        return;
      } else {
        final errorMsg = 'Failed to delete file: ${response.statusCode} ${response.body}';
        logger.e("[AgentFileService] $errorMsg for $providerFileId");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentFileService] Error in deleteFile for $providerFileId: ${e.toString()}");
      throw Exception('Failed to delete file: ${e.toString()}');
    }
  }

  Future<List<FileInfoModel>> getFiles() async {
    logger.i("[AgentFileService] getFiles called");
    try {
      final url = ApiConstants.baseUrl + ApiConstants.filesEndpoint;
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<FileInfoModel> files = data
            .map((item) => FileInfoModel.fromJson(item as Map<String, dynamic>))
            .toList();
        
        logger.i("[AgentFileService] Retrieved ${files.length} files");
        return files;
      } else {
        final errorMsg = 'Failed to get files: ${response.statusCode}';
        logger.e("[AgentFileService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentFileService] Error in getFiles: ${e.toString()}");
      throw Exception('Failed to fetch files: ${e.toString()}');
    }
  }

  Future<FileInfoModel> getFileInfo(String providerFileId) async {
    logger.i("[AgentFileService] getFileInfo called for ID: $providerFileId");
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.filesEndpoint}/$providerFileId';
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        logger.i("[AgentFileService] Successfully retrieved file info: $providerFileId");
        return FileInfoModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to get file info: ${response.statusCode}';
        logger.e("[AgentFileService] $errorMsg for $providerFileId, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentFileService] Error in getFileInfo for $providerFileId: ${e.toString()}");
      throw Exception('Failed to fetch file info: ${e.toString()}');
    }
  }
}

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