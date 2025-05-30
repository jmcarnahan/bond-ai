import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/providers/thread_provider.dart';

class CreateThreadDialog extends ConsumerStatefulWidget {
  const CreateThreadDialog({super.key});

  @override
  ConsumerState<CreateThreadDialog> createState() => _CreateThreadDialogState();
}

class _CreateThreadDialogState extends ConsumerState<CreateThreadDialog> {
  final TextEditingController _nameController = TextEditingController();
  bool _isCreating = false;

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _createThread() async {
    if (_isCreating) return;

    setState(() {
      _isCreating = true;
    });

    try {
      final name = _nameController.text.trim();
      await ref.read(threadsProvider.notifier).addThread(
        name: name.isNotEmpty ? name : null,
      );
      
      if (mounted) {
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to create thread: ${e.toString()}'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isCreating = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return AlertDialog(
      title: const Text('Create New Thread'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _nameController,
            enabled: !_isCreating,
            decoration: InputDecoration(
              hintText: "Optional thread name",
              border: OutlineInputBorder(
                borderRadius: AppBorderRadius.allMd,
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: AppBorderRadius.allMd,
                borderSide: BorderSide(
                  color: theme.colorScheme.primary,
                  width: 2.0,
                ),
              ),
            ),
            textCapitalization: TextCapitalization.sentences,
            maxLength: 100,
          ),
          if (_isCreating) ...[
            SizedBox(height: AppSpacing.lg),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                SizedBox(
                  height: AppSizes.iconMd,
                  width: AppSizes.iconMd,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(
                      theme.colorScheme.primary,
                    ),
                  ),
                ),
                SizedBox(width: AppSpacing.md),
                Text(
                  'Creating thread...',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: _isCreating ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _isCreating ? null : _createThread,
          child: Text(_isCreating ? 'Creating...' : 'Create'),
        ),
      ],
    );
  }
}

void showCreateThreadDialog(BuildContext context) {
  showDialog(
    context: context,
    barrierDismissible: false,
    builder: (context) => const CreateThreadDialog(),
  );
}