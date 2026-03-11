import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/scheduled_job_provider.dart';
import 'package:flutterui/core/utils/navigation_helpers.dart';
import '../../widgets/app_drawer.dart';
import 'widgets/scheduled_jobs_empty_state.dart';
import 'widgets/scheduled_job_list_item.dart';
import 'create_scheduled_job_screen.dart';

class ScheduledJobsScreen extends ConsumerStatefulWidget {
  static const String routeName = '/scheduled-jobs';

  const ScheduledJobsScreen({super.key});

  @override
  ConsumerState<ScheduledJobsScreen> createState() => _ScheduledJobsScreenState();
}

class _ScheduledJobsScreenState extends ConsumerState<ScheduledJobsScreen>
    with WidgetsBindingObserver {
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    Future.microtask(() {
      ref.read(scheduledJobsNotifierProvider.notifier).loadJobs();
    });
    // Auto-refresh every 30s so scheduled job status stays current
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) {
        ref.read(scheduledJobsNotifierProvider.notifier).loadJobs();
      }
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Refresh when app/tab regains focus
    if (state == AppLifecycleState.resumed && mounted) {
      ref.read(scheduledJobsNotifierProvider.notifier).loadJobs();
    }
  }

  void _navigateToCreate() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => const CreateScheduledJobScreen(),
      ),
    ).then((_) {
      // Refresh jobs list when returning from create screen
      if (mounted) {
        ref.read(scheduledJobsNotifierProvider.notifier).loadJobs();
      }
    });
  }

  void _navigateToEdit(String jobId) {
    final state = ref.read(scheduledJobsNotifierProvider);
    final existingJob = state.jobs.where((j) => j.id == jobId).firstOrNull;
    if (existingJob == null) return;

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => CreateScheduledJobScreen(existingJob: existingJob),
      ),
    ).then((_) {
      // Refresh jobs list when returning from edit screen
      if (mounted) {
        ref.read(scheduledJobsNotifierProvider.notifier).loadJobs();
      }
    });
  }

  Future<void> _confirmDelete(String jobId, String jobName) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Scheduled Job'),
        content: Text('Are you sure you want to delete "$jobName"? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text('Delete', style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      final success = await ref.read(scheduledJobsNotifierProvider.notifier).deleteJob(jobId);
      if (mounted && success) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Deleted "$jobName"')),
        );
      }
    }
  }

  void _navigateToThread(String threadId) {
    navigateToThread(ref, context, threadId);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(scheduledJobsNotifierProvider);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      drawer: const AppDrawer(),
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(kToolbarHeight + 8),
        child: Container(
          decoration: BoxDecoration(
            color: colorScheme.surface,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.1),
                blurRadius: 4,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: AppBar(
            title: Text(
              'Scheduled Jobs',
              style: TextStyle(
                color: colorScheme.onSurface,
                fontSize: 18,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.5,
              ),
            ),
            centerTitle: true,
            backgroundColor: Colors.transparent,
            elevation: 0,
            leading: Builder(
              builder: (context) => IconButton(
                icon: Icon(Icons.menu, color: colorScheme.onSurface),
                onPressed: () => Scaffold.of(context).openDrawer(),
              ),
            ),
            actions: [
              IconButton(
                icon: Icon(Icons.add, color: colorScheme.onSurface),
                onPressed: _navigateToCreate,
                tooltip: 'Create scheduled job',
              ),
              const SizedBox(width: 8),
            ],
          ),
        ),
      ),
      body: state.isLoading
          ? const Center(child: CircularProgressIndicator())
          : state.error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        'Error loading jobs',
                        style: theme.textTheme.bodyLarge?.copyWith(color: colorScheme.error),
                      ),
                      const SizedBox(height: 8),
                      Text(state.error!, style: theme.textTheme.bodySmall),
                      const SizedBox(height: 16),
                      FilledButton(
                        onPressed: () => ref.read(scheduledJobsNotifierProvider.notifier).loadJobs(),
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : state.jobs.isEmpty
                  ? ScheduledJobsEmptyState(onCreateJob: _navigateToCreate)
                  : RefreshIndicator(
                      onRefresh: () => ref.read(scheduledJobsNotifierProvider.notifier).loadJobs(),
                      child: ListView.separated(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        itemCount: state.jobs.length,
                        separatorBuilder: (_, __) => Divider(
                          height: 1,
                          indent: 40,
                          color: colorScheme.outlineVariant.withValues(alpha: 0.5),
                        ),
                        itemBuilder: (context, index) {
                          final job = state.jobs[index];
                          return Dismissible(
                            key: Key(job.id),
                            direction: DismissDirection.endToStart,
                            background: Container(
                              alignment: Alignment.centerRight,
                              padding: const EdgeInsets.only(right: 20),
                              color: colorScheme.error,
                              child: const Icon(Icons.delete, color: Colors.white),
                            ),
                            confirmDismiss: (_) async {
                              await _confirmDelete(job.id, job.name);
                              return false; // We handle deletion ourselves
                            },
                            child: ScheduledJobListItem(
                              job: job,
                              onTap: () {
                                Navigator.pushNamed(
                                  context,
                                  '/scheduled-jobs/${job.id}/runs',
                                  arguments: job,
                                ).then((_) {
                                  if (mounted) {
                                    ref.read(scheduledJobsNotifierProvider.notifier).loadJobs();
                                  }
                                });
                              },
                              onEdit: () => _navigateToEdit(job.id),
                              onToggle: () async {
                                final messenger = ScaffoldMessenger.of(context);
                                final success = await ref.read(scheduledJobsNotifierProvider.notifier)
                                    .toggleJob(job.id, !job.isEnabled);
                                if (!success && mounted) {
                                  messenger.showSnackBar(
                                    const SnackBar(content: Text('Failed to toggle job. Please try again.')),
                                  );
                                }
                              },
                              onViewThread: job.lastThreadId != null
                                  ? () => _navigateToThread(job.lastThreadId!)
                                  : null,
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
