import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/services/file_service.dart';
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

  Future<List<FileDetailsResponseModel>> getFileDetails(List<String> fileIds) async {
    logger.i("[AgentFileService] getFileDetails called for ${fileIds.length} files");
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
          logger.e("[AgentFileService] getFileDetails timed out after 10 seconds");
          throw Exception('Request timed out while fetching file details');
        },
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final fileDetails = data.map((item) => FileDetailsResponseModel.fromJson(item)).toList();
        logger.i("[AgentFileService] Successfully retrieved ${fileDetails.length} file details");
        return fileDetails;
      } else {
        final errorMsg = 'Failed to get file details: ${response.statusCode} ${response.body}';
        logger.e("[AgentFileService] $errorMsg");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentFileService] Error in getFileDetails: ${e.toString()}");
      throw Exception('Failed to get file details: ${e.toString()}');
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

