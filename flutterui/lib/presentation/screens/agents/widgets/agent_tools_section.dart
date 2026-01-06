import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'tool_file_upload_section.dart';

class AgentToolsSection extends StatelessWidget {
  final bool enableCodeInterpreter;
  final bool enableFileSearch;
  final List<UploadedFileInfo> codeInterpreterFiles;
  final List<UploadedFileInfo> fileSearchFiles;
  final bool enabled;
  final void Function(bool) onCodeInterpreterChanged;
  final void Function(bool) onFileSearchChanged;

  const AgentToolsSection({
    super.key,
    required this.enableCodeInterpreter,
    required this.enableFileSearch,
    required this.codeInterpreterFiles,
    required this.fileSearchFiles,
    required this.enabled,
    required this.onCodeInterpreterChanged,
    required this.onFileSearchChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(height: AppSpacing.xxl),
        AgentToolSwitch(
          title: 'Code Interpreter',
          value: enableCodeInterpreter,
          onChanged: enabled ? onCodeInterpreterChanged : null,
        ),
        ToolFileUploadSection(
          toolType: 'code_interpreter',
          toolName: 'Code Interpreter',
          isEnabled: enableCodeInterpreter,
          files: codeInterpreterFiles,
        ),
        AgentToolSwitch(
          title: 'File Search',
          value: enableFileSearch,
          onChanged: enabled ? onFileSearchChanged : null,
        ),
        ToolFileUploadSection(
          toolType: 'file_search',
          toolName: 'File Search',
          isEnabled: enableFileSearch,
          files: fileSearchFiles,
        ),
      ],
    );
  }
}

class AgentToolSwitch extends StatelessWidget {
  final String title;
  final bool value;
  final ValueChanged<bool>? onChanged;

  const AgentToolSwitch({
    super.key,
    required this.title,
    required this.value,
    this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: 0.0,
      margin: AppSpacing.verticalSm,
      shape: RoundedRectangleBorder(
        borderRadius: AppBorderRadius.allMd,
        side: BorderSide(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.5),
        ),
      ),
      color: theme.colorScheme.surfaceContainer,
      child: SwitchListTile(
        title: Text(
          title,
          style: theme.textTheme.titleMedium?.copyWith(
            color: onChanged == null
                ? theme.disabledColor
                : theme.colorScheme.onSurface,
          ),
        ),
        value: value,
        onChanged: onChanged,
        activeColor: theme.colorScheme.primary,
        inactiveThumbColor: theme.colorScheme.onSurface.withValues(alpha: 0.4),
        inactiveTrackColor: theme.colorScheme.onSurface.withValues(alpha: 0.2),
        contentPadding: AppSpacing.horizontalXl.add(AppSpacing.verticalLg),
      ),
    );
  }
}
