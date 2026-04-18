import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  String makeFileJson({String? fileId, String? fileName, int? fileSize, String? mimeType}) {
    return json.encode({
      if (fileId != null) 'file_id': fileId,
      if (fileName != null) 'file_name': fileName,
      if (fileSize != null) 'file_size': fileSize,
      if (mimeType != null) 'mime_type': mimeType,
    });
  }

  Widget buildTestWidget({
    required String fileDataJson,
    Future<void> Function(String, String)? onDownload,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: FileCard(fileDataJson: fileDataJson, onDownload: onDownload),
      ),
    );
  }

  group('FileCard (decoupled)', () {
    testWidgets('renders file name', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(fileId: 'f1', fileName: 'report.pdf', fileSize: 1024, mimeType: 'application/pdf'),
      ));
      expect(find.text('report.pdf'), findsOneWidget);
    });

    testWidgets('renders formatted file size', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(fileId: 'f1', fileName: 'f', fileSize: 1572864),
      ));
      expect(find.text('1.5 MB'), findsOneWidget);
    });

    testWidgets('renders file type label', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(fileId: 'f1', fileName: 'f', mimeType: 'application/pdf'),
      ));
      expect(find.text('PDF'), findsOneWidget);
    });

    testWidgets('handles malformed JSON', (tester) async {
      await tester.pumpWidget(buildTestWidget(fileDataJson: 'not json'));
      expect(find.text('Unknown File'), findsOneWidget);
    });

    testWidgets('onDownload callback receives correct args', (tester) async {
      String? downloadedId;
      String? downloadedName;
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(fileId: 'f1', fileName: 'test.txt', fileSize: 100),
        onDownload: (id, name) async {
          downloadedId = id;
          downloadedName = name;
        },
      ));

      await tester.tap(find.byType(InkWell).first);
      await tester.pumpAndSettle();

      expect(downloadedId, 'f1');
      expect(downloadedName, 'test.txt');
    });

    testWidgets('works with null onDownload (no crash on tap)', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(fileId: 'f1', fileName: 'test.txt'),
      ));
      // Tap should not crash
      await tester.tap(find.byType(InkWell).first);
      await tester.pumpAndSettle();
    });

    testWidgets('shows download icon', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        fileDataJson: makeFileJson(fileId: 'f1', fileName: 'f'),
      ));
      expect(find.byIcon(Icons.download), findsOneWidget);
    });
  });
}
