import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/presentation/widgets/sidebar.dart';
import 'package:flutterui/presentation/screens/groups/widgets/create_group_dialog.dart';
import 'package:flutterui/presentation/screens/groups/widgets/groups_empty_state.dart';
import 'package:flutterui/presentation/screens/groups/widgets/groups_list.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';
import 'package:flutterui/core/error_handling/error_handler.dart';

class GroupsScreen extends ConsumerStatefulWidget {
  static const String routeName = '/groups';

  const GroupsScreen({super.key});

  @override
  ConsumerState<GroupsScreen> createState() => _GroupsScreenState();
}

class _GroupsScreenState extends ConsumerState<GroupsScreen> with ErrorHandlingMixin {
  void _showCreateGroupDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => const CreateGroupDialog(),
    );
  }

  @override
  Widget build(BuildContext context) {
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
        error: (error, stack) {
          // Use automatic error detection and handling
          WidgetsBinding.instance.addPostFrameCallback((_) {
            handleAutoError(error, ref, serviceErrorMessage: 'Failed to load groups');
          });

          // Check if this is an authentication error to show appropriate UI
          final appError = error is Exception ? AppError.fromException(error) : null;
          if (appError?.type == ErrorType.authentication) {
            // Show loading while redirecting to login
            return const Center(
              child: CircularProgressIndicator(),
            );
          }

          // Show a fallback UI with retry button for other errors
          return Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 40.0),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(
                    Icons.refresh,
                    size: 64,
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'Unable to Load Groups',
                    style: TextStyle(fontSize: 18),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Tap below to try again',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 20),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry'),
                    onPressed: () {
                      ref.invalidate(groupNotifierProvider);
                    },
                  ),
                ],
              ),
            ),
          );
        },
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
