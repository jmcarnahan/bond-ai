import 'package:file_picker/file_picker.dart' show PlatformFile;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class MessageAttachmentBar extends ConsumerWidget {
  final List<PlatformFile> attachments;
  final void Function(PlatformFile)? onAttachmentRemoved;

  const MessageAttachmentBar({
    super.key,
    required this.attachments,
    this.onAttachmentRemoved,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (attachments.isEmpty) {
      return const SizedBox.shrink();
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.start,
        textDirection: TextDirection.ltr,
        children: attachments.map((file) {
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4.0),
            child: Chip(
              label: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 120.0),
                child: Text(
                  file.name,
                  overflow:  TextOverflow.ellipsis,
                  softWrap: false,
                ),
              ),
              onDeleted: () {
                if (onAttachmentRemoved != null) {
                  onAttachmentRemoved!(file);
                }
              },
              deleteIcon: const Icon(Icons.close),
            ),
          );
        }).toList(),
      ),
    );
  }
}
