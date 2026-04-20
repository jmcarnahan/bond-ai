import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  String makeFileJson({
    String? fileId,
    String? fileName,
    int? fileSize,
    String? mimeType,
  }) {
    return json.encode({
      if (fileId != null) 'file_id': fileId,
      if (fileName != null) 'file_name': fileName,
      if (fileSize != null) 'file_size': fileSize,
      if (mimeType != null) 'mime_type': mimeType,
    });
  }

  Widget buildTestWidget({
    required String fileDataJson,
    Future<String?> Function(String fileId)? onPreviewUrl,
    Uint8List? previewImageBytes,
    VoidCallback? onOpen,
    Future<void> Function(String, String)? onDownload,
    void Function(String url)? onPreviewUrlDispose,
    double maxWidth = 400,
    double previewHeight = 200,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: FilePreviewCard(
          fileDataJson: fileDataJson,
          onPreviewUrl: onPreviewUrl,
          previewImageBytes: previewImageBytes,
          onOpen: onOpen,
          onDownload: onDownload,
          onPreviewUrlDispose: onPreviewUrlDispose,
          maxWidth: maxWidth,
          previewHeight: previewHeight,
        ),
      ),
    );
  }

  // Minimal 1x1 PNG for image tests
  final pngBytes = Uint8List.fromList([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
    0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
    0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
    0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
    0x00, 0x00, 0x02, 0x00, 0x01, 0xE2, 0x21, 0xBC,
    0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
    0x44, 0xAE, 0x42, 0x60, 0x82,
  ]);

  group('FilePreviewCard', () {
    testWidgets('renders file name in info bar', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'report.pdf',
          fileSize: 1024,
          mimeType: 'application/pdf',
        ),
      ));
      expect(find.text('report.pdf'), findsOneWidget);
    });

    testWidgets('renders formatted file size', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'data.csv',
          fileSize: 1572864,
          mimeType: 'text/csv',
        ),
      ));
      expect(find.text('1.5 MB'), findsOneWidget);
    });

    testWidgets('renders file type label badge', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'doc.pdf',
          mimeType: 'application/pdf',
        ),
      ));
      expect(find.text('PDF'), findsOneWidget);
    });

    testWidgets('handles malformed JSON gracefully', (tester) async {
      await tester.pumpWidget(buildTestWidget(fileDataJson: 'not json'));
      expect(find.text('Unknown File'), findsOneWidget);
      expect(find.text('Unknown size'), findsOneWidget);
    });

    testWidgets('shows fallback icon when no preview callbacks provided for PDF',
        (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'doc.pdf',
          mimeType: 'application/pdf',
        ),
      ));
      // Should show the PDF icon as fallback (large icon in preview + small in info bar)
      expect(find.byIcon(Icons.picture_as_pdf), findsWidgets);
    });

    testWidgets('shows loading state while preview URL resolves',
        (tester) async {
      final completer = Completer<String?>();
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'doc.pdf',
          mimeType: 'application/pdf',
        ),
        onPreviewUrl: (fileId) => completer.future,
      ));

      // Should show loading indicator while future is pending
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Complete the future and settle
      completer.complete(null);
      await tester.pumpAndSettle();
    });

    testWidgets('shows fallback icon when onPreviewUrl returns null',
        (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'doc.pdf',
          mimeType: 'application/pdf',
        ),
        onPreviewUrl: (fileId) async => null,
      ));

      await tester.pumpAndSettle();
      // Should show fallback icon (large + small)
      expect(find.byIcon(Icons.picture_as_pdf), findsWidgets);
    });

    testWidgets('shows fallback icon when onPreviewUrl throws',
        (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'doc.pdf',
          mimeType: 'application/pdf',
        ),
        onPreviewUrl: (fileId) async => throw Exception('Network error'),
      ));

      await tester.pumpAndSettle();
      // Should show fallback icon
      expect(find.byIcon(Icons.picture_as_pdf), findsWidgets);
    });

    testWidgets('renders Image.memory when previewImageBytes provided',
        (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'photo.png',
          mimeType: 'image/png',
        ),
        previewImageBytes: pngBytes,
      ));

      await tester.pumpAndSettle();
      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('calls onOpen when preview area is tapped', (tester) async {
      bool openCalled = false;
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'doc.pdf',
          mimeType: 'application/pdf',
        ),
        onOpen: () {
          openCalled = true;
        },
      ));

      await tester.tap(find.byType(InkWell).first);
      await tester.pumpAndSettle();

      expect(openCalled, isTrue);
    });

    testWidgets('calls onDownload with correct args when download button tapped',
        (tester) async {
      String? downloadedId;
      String? downloadedName;
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'report.pdf',
          fileSize: 2048,
          mimeType: 'application/pdf',
        ),
        onDownload: (id, name) async {
          downloadedId = id;
          downloadedName = name;
        },
      ));

      await tester.tap(find.byIcon(Icons.download));
      await tester.pumpAndSettle();

      expect(downloadedId, 'f1');
      expect(downloadedName, 'report.pdf');
    });

    testWidgets('shows download progress indicator during download',
        (tester) async {
      final completer = Completer<void>();
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'report.pdf',
          mimeType: 'application/pdf',
        ),
        onDownload: (id, name) => completer.future,
      ));

      await tester.tap(find.byIcon(Icons.download));
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsWidgets);

      completer.complete();
      await tester.pumpAndSettle();
    });

    testWidgets('works with all callbacks null (no crash)', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'test.txt',
          fileSize: 100,
          mimeType: 'text/plain',
        ),
      ));

      expect(find.text('test.txt'), findsOneWidget);
      expect(find.text('Text'), findsWidgets); // badge in info bar + proxy preview

      await tester.tap(find.byType(InkWell).first);
      await tester.pumpAndSettle();
    });

    testWidgets('shows download icon', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'test.txt',
        ),
      ));
      expect(find.byIcon(Icons.download), findsOneWidget);
    });

    testWidgets('shows correct icon for different file types', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'photo.jpg',
          mimeType: 'image/jpeg',
        ),
      ));
      expect(find.byIcon(Icons.image), findsWidgets);

      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f2',
          fileName: 'data.xlsx',
          mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ),
      ));
      expect(find.byIcon(Icons.table_chart), findsWidgets);
    });

    testWidgets('does not call onPreviewUrl when previewImageBytes provided',
        (tester) async {
      bool previewUrlCalled = false;

      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'photo.png',
          mimeType: 'image/png',
        ),
        previewImageBytes: pngBytes,
        onPreviewUrl: (fileId) async {
          previewUrlCalled = true;
          return 'https://example.com/preview';
        },
      ));

      await tester.pumpAndSettle();
      expect(previewUrlCalled, isFalse);
    });

    testWidgets('does not call onPreviewUrl when fileId is null',
        (tester) async {
      bool previewUrlCalled = false;
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(fileName: 'test.txt'),
        onPreviewUrl: (fileId) async {
          previewUrlCalled = true;
          return 'https://example.com/preview';
        },
      ));

      await tester.pumpAndSettle();
      expect(previewUrlCalled, isFalse);
    });

    testWidgets('shows success snackbar after download', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'report.pdf',
          mimeType: 'application/pdf',
        ),
        onDownload: (id, name) async {},
      ));

      await tester.tap(find.byIcon(Icons.download));
      await tester.pumpAndSettle();

      expect(find.text('Downloaded: report.pdf'), findsOneWidget);
    });

    testWidgets('shows error snackbar when download fails', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'report.pdf',
          mimeType: 'application/pdf',
        ),
        onDownload: (id, name) async {
          throw Exception('Server error');
        },
      ));

      await tester.tap(find.byIcon(Icons.download));
      await tester.pumpAndSettle();

      expect(find.textContaining('Download failed'), findsOneWidget);
    });

    testWidgets('respects custom maxWidth and previewHeight', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'test.txt',
          mimeType: 'text/plain',
        ),
        maxWidth: 300,
        previewHeight: 150,
      ));

      final container = tester.widget<Container>(
        find.byType(Container).first,
      );
      final constraints = container.constraints;
      expect(constraints?.maxWidth, 300);
    });

    // --- Proxy preview tests ---

    testWidgets('shows proxy preview with icon and type label for CSV files',
        (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'data.csv',
          fileSize: 2048,
          mimeType: 'text/csv',
        ),
      ));

      // Proxy preview should show the type label in the preview area
      // (one in proxy preview, one in info bar)
      expect(find.text('CSV'), findsNWidgets(2));
      // Should show the spreadsheet icon (proxy preview + info bar)
      expect(find.byIcon(Icons.table_chart), findsWidgets);
    });

    testWidgets('shows proxy preview for Word documents', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'doc.docx',
          mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ),
      ));

      expect(find.text('Word'), findsNWidgets(2));
      expect(find.byIcon(Icons.article), findsWidgets);
    });

    testWidgets('shows proxy preview for Excel files', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'data.xlsx',
          mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ),
      ));

      expect(find.text('Excel'), findsNWidgets(2));
      expect(find.byIcon(Icons.table_chart), findsWidgets);
    });

    testWidgets('shows proxy preview for plain text files', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'readme.txt',
          mimeType: 'text/plain',
        ),
      ));

      expect(find.text('Text'), findsNWidgets(2));
      expect(find.byIcon(Icons.description), findsWidgets);
    });

    testWidgets('does not call onPreviewUrl for non-previewable mime types',
        (tester) async {
      bool previewUrlCalled = false;
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(
          fileId: 'f1',
          fileName: 'data.csv',
          mimeType: 'text/csv',
        ),
        onPreviewUrl: (fileId) async {
          previewUrlCalled = true;
          return 'https://example.com/preview';
        },
      ));

      await tester.pumpAndSettle();
      expect(previewUrlCalled, isFalse);
    });

    // --- didUpdateWidget test ---

    testWidgets('re-fetches preview when fileDataJson changes', (tester) async {
      final fetchedIds = <String>[];
      final completer1 = Completer<String?>();
      final completer2 = Completer<String?>();
      int callCount = 0;

      Future<String?> onPreviewUrl(String fileId) {
        fetchedIds.add(fileId);
        callCount++;
        if (callCount == 1) return completer1.future;
        return completer2.future;
      }

      // First render with file f1 (PDF — previewable)
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: FilePreviewCard(
            fileDataJson: makeFileJson(
              fileId: 'f1',
              fileName: 'report.pdf',
              mimeType: 'application/pdf',
            ),
            onPreviewUrl: onPreviewUrl,
          ),
        ),
      ));
      await tester.pump();

      expect(fetchedIds, ['f1']);
      completer1.complete('url1');
      await tester.pumpAndSettle();

      // Update with different fileDataJson (different file ID)
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: FilePreviewCard(
            fileDataJson: makeFileJson(
              fileId: 'f2',
              fileName: 'invoice.pdf',
              mimeType: 'application/pdf',
            ),
            onPreviewUrl: onPreviewUrl,
          ),
        ),
      ));
      await tester.pump();

      expect(fetchedIds, ['f1', 'f2']);
      completer2.complete('url2');
      await tester.pumpAndSettle();
    });

    // --- onPreviewUrlDispose test ---

    testWidgets('calls onPreviewUrlDispose when widget is disposed',
        (tester) async {
      String? disposedUrl;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: FilePreviewCard(
            fileDataJson: makeFileJson(
              fileId: 'f1',
              fileName: 'doc.pdf',
              mimeType: 'application/pdf',
            ),
            onPreviewUrl: (fileId) async => 'blob:http://localhost/abc123',
            onPreviewUrlDispose: (url) {
              disposedUrl = url;
            },
          ),
        ),
      ));
      await tester.pumpAndSettle();

      // Replace the widget tree to trigger dispose
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: SizedBox()),
      ));
      await tester.pumpAndSettle();

      expect(disposedUrl, 'blob:http://localhost/abc123');
    });

    testWidgets('calls onPreviewUrlDispose on fileDataJson change',
        (tester) async {
      final disposedUrls = <String>[];

      Future<String?> onPreviewUrl(String fileId) async => 'blob:$fileId';
      void onDispose(String url) => disposedUrls.add(url);

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: FilePreviewCard(
            fileDataJson: makeFileJson(
              fileId: 'f1',
              fileName: 'a.pdf',
              mimeType: 'application/pdf',
            ),
            onPreviewUrl: onPreviewUrl,
            onPreviewUrlDispose: onDispose,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      // Change the file
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: FilePreviewCard(
            fileDataJson: makeFileJson(
              fileId: 'f2',
              fileName: 'b.pdf',
              mimeType: 'application/pdf',
            ),
            onPreviewUrl: onPreviewUrl,
            onPreviewUrlDispose: onDispose,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      // Old URL should have been revoked
      expect(disposedUrls, contains('blob:f1'));
    });
  });
}
