import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/group_provider.dart';
import 'package:flutterui/core/utils/logger.dart';

class EditGroupForm extends ConsumerStatefulWidget {
  final Group group;
  final VoidCallback? onChanged;

  const EditGroupForm({
    super.key,
    required this.group,
    this.onChanged,
  });

  @override
  ConsumerState<EditGroupForm> createState() => EditGroupFormState();
}

class EditGroupFormState extends ConsumerState<EditGroupForm> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;
  late final TextEditingController _descriptionController;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.group.name);
    _descriptionController = TextEditingController(text: widget.group.description ?? '');
    
    _nameController.addListener(_onTextChanged);
    _descriptionController.addListener(_onTextChanged);
  }
  
  void _onTextChanged() {
    widget.onChanged?.call();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  bool get hasChanges {
    return _nameController.text.trim() != widget.group.name ||
           _descriptionController.text.trim() != (widget.group.description ?? '');
  }

  Future<void> saveChanges() async {
    if (!_formKey.currentState!.validate() || !hasChanges) return;

    try {
      await ref.read(groupNotifierProvider.notifier).updateGroup(
        widget.group.id,
        name: _nameController.text.trim(),
        description: _descriptionController.text.trim().isEmpty 
            ? null 
            : _descriptionController.text.trim(),
      );
    } catch (error) {
      logger.e('Error updating group: $error');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error updating group: $error')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Group Details',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: 'Group Name',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter a group name';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _descriptionController,
                decoration: const InputDecoration(
                  labelText: 'Description (optional)',
                  border: OutlineInputBorder(),
                ),
                maxLines: 3,
              ),
            ],
          ),
        ),
      ),
    );
  }
}