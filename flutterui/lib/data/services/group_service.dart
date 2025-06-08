import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/data/services/auth_service.dart';

class GroupService {
  final AuthService _authService;

  GroupService(this._authService);

  Future<List<Group>> getUserGroups() async {
    final token = await _authService.retrieveToken();
    if (token == null) {
      throw Exception('No auth token available');
    }

    final response = await http.get(
      Uri.parse('${ApiConstants.baseUrl}/groups'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode == 200) {
      final List<dynamic> jsonList = json.decode(response.body);
      return jsonList.map((json) => Group.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load groups: ${response.statusCode}');
    }
  }

  Future<Group> createGroup({
    required String name,
    String? description,
  }) async {
    final token = await _authService.retrieveToken();
    if (token == null) {
      throw Exception('No auth token available');
    }

    final response = await http.post(
      Uri.parse('${ApiConstants.baseUrl}/groups'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: json.encode({
        'name': name,
        'description': description,
      }),
    );

    if (response.statusCode == 201) {
      return Group.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to create group: ${response.statusCode}');
    }
  }

  Future<GroupWithMembers> getGroup(String groupId) async {
    final token = await _authService.retrieveToken();
    if (token == null) {
      throw Exception('No auth token available');
    }

    final response = await http.get(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode == 200) {
      return GroupWithMembers.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to load group: ${response.statusCode}');
    }
  }

  Future<Group> updateGroup(
    String groupId, {
    String? name,
    String? description,
  }) async {
    final token = await _authService.retrieveToken();
    if (token == null) {
      throw Exception('No auth token available');
    }

    final response = await http.put(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: json.encode({
        if (name != null) 'name': name,
        if (description != null) 'description': description,
      }),
    );

    if (response.statusCode == 200) {
      return Group.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to update group: ${response.statusCode}');
    }
  }

  Future<void> deleteGroup(String groupId) async {
    final token = await _authService.retrieveToken();
    if (token == null) {
      throw Exception('No auth token available');
    }

    final response = await http.delete(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode != 204) {
      throw Exception('Failed to delete group: ${response.statusCode}');
    }
  }

  Future<List<GroupMember>> getAllUsers() async {
    final token = await _authService.retrieveToken();
    if (token == null) {
      throw Exception('No auth token available');
    }

    final response = await http.get(
      Uri.parse('${ApiConstants.baseUrl}/groups/users'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode == 200) {
      final List<dynamic> jsonList = json.decode(response.body);
      return jsonList.map((json) => GroupMember.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load users: ${response.statusCode}');
    }
  }

  Future<void> addGroupMember(String groupId, String userId) async {
    final token = await _authService.retrieveToken();
    if (token == null) {
      throw Exception('No auth token available');
    }

    final response = await http.post(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId/members/$userId'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode != 201) {
      throw Exception('Failed to add group member: ${response.statusCode}');
    }
  }

  Future<void> removeGroupMember(String groupId, String userId) async {
    final token = await _authService.retrieveToken();
    if (token == null) {
      throw Exception('No auth token available');
    }

    final response = await http.delete(
      Uri.parse('${ApiConstants.baseUrl}/groups/$groupId/members/$userId'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode != 204) {
      throw Exception('Failed to remove group member: ${response.statusCode}');
    }
  }
}