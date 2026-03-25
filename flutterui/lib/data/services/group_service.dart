import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable;
import 'package:http/http.dart' as http;
import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/web_http_client.dart' as web_client;
import '../../core/utils/logger.dart';

@immutable
class GroupService {
  final http.Client _httpClient;
  final AuthService _authService;

  GroupService({http.Client? httpClient, required AuthService authService})
    : _httpClient = httpClient ?? web_client.createHttpClient(),
      _authService = authService;

  Future<List<Group>> getUserGroups() async {
    final headers = await _authService.authenticatedHeaders;
    final response = await _httpClient.get(
      Uri.parse('${ApiConstants.baseUrl}/groups'),
      headers: headers,
    );

    if (response.statusCode == 200) {
      final List<dynamic> jsonList = json.decode(response.body);
      return jsonList.map((json) => Group.fromJson(json)).toList();
    } else {
      logger.i('[GroupService] Failed to load groups. Status: ${response.statusCode}');
      throw Exception('Failed to load groups: ${response.statusCode}');
    }
  }

  Future<Group> createGroup({
    required String name,
    String? description,
  }) async {
    final headers = await _authService.authenticatedHeaders;
    final response = await _httpClient.post(
      Uri.parse('${ApiConstants.baseUrl}/groups'),
      headers: headers,
      body: json.encode({
        'name': name,
        'description': description,
      }),
    );

    if (response.statusCode == 201) {
      return Group.fromJson(json.decode(response.body));
    } else {
      logger.i('[GroupService] Failed to create group. Status: ${response.statusCode}');
      throw Exception('Failed to create group: ${response.statusCode}');
    }
  }

  Future<GroupWithMembers> getGroup(String groupId) async {
    final headers = await _authService.authenticatedHeaders;
    final response = await _httpClient.get(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId'),
      headers: headers,
    );

    if (response.statusCode == 200) {
      return GroupWithMembers.fromJson(json.decode(response.body));
    } else {
      logger.i('[GroupService] Failed to load group. Status: ${response.statusCode}');
      throw Exception('Failed to load group: ${response.statusCode}');
    }
  }

  Future<Group> updateGroup(
    String groupId, {
    String? name,
    String? description,
  }) async {
    final headers = await _authService.authenticatedHeaders;
    final response = await _httpClient.put(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId'),
      headers: headers,
      body: json.encode({
        if (name != null) 'name': name,
        if (description != null) 'description': description,
      }),
    );

    if (response.statusCode == 200) {
      return Group.fromJson(json.decode(response.body));
    } else {
      logger.i('[GroupService] Failed to update group. Status: ${response.statusCode}');
      throw Exception('Failed to update group: ${response.statusCode}');
    }
  }

  Future<void> deleteGroup(String groupId) async {
    final headers = await _authService.authenticatedHeaders;
    final response = await _httpClient.delete(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId'),
      headers: headers,
    );

    if (response.statusCode != 204) {
      logger.i('[GroupService] Failed to delete group. Status: ${response.statusCode}');
      throw Exception('Failed to delete group: ${response.statusCode}');
    }
  }

  Future<List<GroupMember>> getAllUsers() async {
    final headers = await _authService.authenticatedHeaders;
    final response = await _httpClient.get(
      Uri.parse('${ApiConstants.baseUrl}/groups/users'),
      headers: headers,
    );

    if (response.statusCode == 200) {
      final List<dynamic> jsonList = json.decode(response.body);
      return jsonList.map((json) => GroupMember.fromJson(json)).toList();
    } else {
      logger.i('[GroupService] Failed to load users. Status: ${response.statusCode}');
      throw Exception('Failed to load users: ${response.statusCode}');
    }
  }

  Future<void> addGroupMember(String groupId, String userId) async {
    final headers = await _authService.authenticatedHeaders;
    final response = await _httpClient.post(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId/members/$userId'),
      headers: headers,
    );

    if (response.statusCode != 201) {
      logger.i('[GroupService] Failed to add group member. Status: ${response.statusCode}');
      throw Exception('Failed to add group member: ${response.statusCode}');
    }
  }

  Future<void> removeGroupMember(String groupId, String userId) async {
    final headers = await _authService.authenticatedHeaders;
    final response = await _httpClient.delete(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId/members/$userId'),
      headers: headers,
    );

    if (response.statusCode != 204) {
      logger.i('[GroupService] Failed to remove group member. Status: ${response.statusCode}');
      throw Exception('Failed to remove group member: ${response.statusCode}');
    }
  }
}
