import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/scheduled_job_model.dart';
import 'package:flutterui/providers/scheduled_job_provider.dart';
import 'package:flutterui/core/utils/navigation_helpers.dart';
import 'widgets/scheduled_job_run_item.dart';

class ScheduledJobRunsScreen extends ConsumerStatefulWidget {
  final String jobId;
  final ScheduledJob? job;

  const ScheduledJobRunsScreen({
    super.key,
    required this.jobId,
    this.job,
  });

  @override
  ConsumerState<ScheduledJobRunsScreen> createState() => _ScheduledJobRunsScreenState();
}

class _ScheduledJobRunsScreenState extends ConsumerState<ScheduledJobRunsScreen> {
  List<ScheduledJobRun>? _runs;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadRuns();
  }

  Future<void> _loadRuns() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final runs = await ref.read(scheduledJobsNotifierProvider.notifier)
          .loadJobRuns(widget.jobId);
      if (mounted) {
        setState(() {
          _runs = runs;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  void _navigateToThread(String threadId) {
    navigateToThread(ref, context, threadId);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final jobName = widget.job?.name ?? 'Job Runs';

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        title: Text(jobName),
        backgroundColor: colorScheme.surface,
        surfaceTintColor: Colors.transparent,
        iconTheme: IconThemeData(color: colorScheme.onSurface),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text('Error loading runs', style: TextStyle(color: colorScheme.error)),
                      const SizedBox(height: 8),
                      FilledButton(onPressed: _loadRuns, child: const Text('Retry')),
                    ],
                  ),
                )
              : _runs == null || _runs!.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.history, size: 48, color: colorScheme.onSurfaceVariant.withValues(alpha: 0.5)),
                          const SizedBox(height: 16),
                          Text(
                            'No runs yet',
                            style: theme.textTheme.bodyLarge?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Runs will appear here after the job executes.',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
                            ),
                          ),
                        ],
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _loadRuns,
                      child: ListView.separated(
                        itemCount: _runs!.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (context, index) {
                          final run = _runs![index];
                          return ScheduledJobRunItem(
                            run: run,
                            onTap: () => _navigateToThread(run.threadId),
                          );
                        },
                      ),
                    ),
    );
  }
}
