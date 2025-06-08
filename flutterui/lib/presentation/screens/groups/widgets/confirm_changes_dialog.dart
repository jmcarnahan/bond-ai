import 'package:flutter/material.dart';

class ConfirmChangesDialog extends StatelessWidget {
  final int additionsCount;
  final int removalsCount;

  const ConfirmChangesDialog({
    super.key,
    required this.additionsCount,
    required this.removalsCount,
  });

  @override
  Widget build(BuildContext context) {
    final hasAdditions = additionsCount > 0;
    final hasRemovals = removalsCount > 0;

    return AlertDialog(
      title: const Text('Confirm Changes'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('You are about to make the following changes:'),
          const SizedBox(height: 16),
          if (hasAdditions)
            Row(
              children: [
                const Icon(Icons.add, color: Colors.green),
                const SizedBox(width: 8),
                Text('Add $additionsCount ${additionsCount == 1 ? 'user' : 'users'}'),
              ],
            ),
          if (hasAdditions && hasRemovals) const SizedBox(height: 8),
          if (hasRemovals)
            Row(
              children: [
                const Icon(Icons.remove, color: Colors.red),
                const SizedBox(width: 8),
                Text('Remove $removalsCount ${removalsCount == 1 ? 'user' : 'users'}'),
              ],
            ),
          const SizedBox(height: 16),
          const Text('Do you want to continue?'),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Confirm'),
        ),
      ],
    );
  }
}