import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/presentation/widgets/sidebar.dart';
import 'package:flutterui/presentation/screens/groups/widgets/create_group_dialog.dart';
import 'package:flutterui/presentation/screens/groups/widgets/groups_empty_state.dart';
import 'package:flutterui/presentation/screens/groups/widgets/groups_error_state.dart';
import 'package:flutterui/presentation/screens/groups/widgets/groups_list.dart';

class GroupsScreen extends ConsumerWidget {
  static const String routeName = '/groups';
  
  const GroupsScreen({super.key});

  void _showCreateGroupDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => const CreateGroupDialog(),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final groupsAsync = ref.watch(groupNotifierProvider);
    final authState = ref.watch(authNotifierProvider);
    
    User? currentUser;
    if (authState is Authenticated) {
      currentUser = authState.user;
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Groups'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => _showCreateGroupDialog(context),
            tooltip: 'Create Group',
          ),
        ],
      ),
      drawer: const AppSidebar(),
      body: groupsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) => GroupsErrorState(
          error: error.toString(),
          onRetry: () => ref.refresh(groupNotifierProvider),
        ),
        data: (groups) {
          if (groups.isEmpty) {
            return GroupsEmptyState(
              onCreateGroup: () => _showCreateGroupDialog(context),
            );
          }

          return GroupsList(
            groups: groups,
            currentUser: currentUser,
          );
        },
      ),
    );
  }
}