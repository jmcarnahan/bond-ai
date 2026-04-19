@TestOn('browser')
library;

// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:async';
import 'dart:html' as html;
import 'dart:js_interop';
import 'dart:js_interop_unsafe';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/presentation/screens/chat/widgets/web_drop_helper_web.dart'
    as drop;

/// Helper: create an empty JS object.
JSObject _newJSObject() {
  return (globalContext['Object'] as JSFunction).callAsConstructor();
}

/// Helper: create a mock FileList-like JS object containing [files].
///
/// The mock has `length` and `item(i)` matching the real FileList interface,
/// which is exactly what _readDroppedFiles accesses via js_interop_unsafe.
JSObject _mockFileList(List<JSObject> files) {
  final mock = _newJSObject();
  mock['length'] = files.length.toJS;
  for (var i = 0; i < files.length; i++) {
    mock[i.toString()] = files[i];
  }
  // item(i) { return this[i]; }
  final itemFn = (globalContext['Function'] as JSFunction)
      .callAsConstructor('return this[arguments[0]]'.toJS);
  mock['item'] = itemFn;
  return mock;
}

/// Helper: create a JS File object with given name, content, and MIME type.
JSObject _createJSFile(String name, Uint8List content, String mimeType) {
  final jsArray = <JSAny>[content.toJS].toJS;
  final options = _newJSObject();
  options['type'] = mimeType.toJS;
  return (globalContext['File'] as JSFunction)
      .callAsConstructor(jsArray, name.toJS, options);
}

void main() {
  group('WebDropHelper (js_interop migration)', () {
    tearDown(() {
      drop.disposeWebDrop();
      // Clean up global state
      globalContext['_bondDroppedFiles'] = null;
    });

    test('isWebDropSupported returns true on web', () {
      expect(drop.isWebDropSupported, isTrue);
    });

    test('initWebDrop listens for bond-drag-enter events', () async {
      var enterCount = 0;
      drop.initWebDrop(
        onFileDrop: (_) {},
        onDragEnter: () => enterCount++,
        onDragLeave: () {},
      );

      html.window.dispatchEvent(html.CustomEvent('bond-drag-enter'));
      // Event listeners are async — yield to microtask queue
      await Future<void>.delayed(Duration.zero);
      expect(enterCount, 1);
    });

    test('initWebDrop listens for bond-drag-leave events', () async {
      var leaveCount = 0;
      drop.initWebDrop(
        onFileDrop: (_) {},
        onDragEnter: () {},
        onDragLeave: () => leaveCount++,
      );

      html.window.dispatchEvent(html.CustomEvent('bond-drag-leave'));
      await Future<void>.delayed(Duration.zero);
      expect(leaveCount, 1);
    });

    test('disposeWebDrop stops listening for events', () async {
      var enterCount = 0;
      drop.initWebDrop(
        onFileDrop: (_) {},
        onDragEnter: () => enterCount++,
        onDragLeave: () {},
      );

      drop.disposeWebDrop();
      html.window.dispatchEvent(html.CustomEvent('bond-drag-enter'));
      await Future<void>.delayed(Duration.zero);
      expect(enterCount, 0);
    });

    test('drop event with no _bondDroppedFiles does not call onFileDrop',
        () async {
      var dropCount = 0;
      drop.initWebDrop(
        onFileDrop: (_) => dropCount++,
        onDragEnter: () {},
        onDragLeave: () {},
      );

      // _bondDroppedFiles is null
      globalContext['_bondDroppedFiles'] = null;
      html.window.dispatchEvent(html.CustomEvent('bond-file-drop'));
      // Give async handler time to run
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(dropCount, 0);
    });

    test('drop event reads files from _bondDroppedFiles via js_interop',
        () async {
      final completer = Completer<List<({String name, Uint8List bytes})>>();
      drop.initWebDrop(
        onFileDrop: (files) {
          if (!completer.isCompleted) completer.complete(files);
        },
        onDragEnter: () {},
        onDragLeave: () {},
      );

      // Create a JS File and mock FileList
      final content = Uint8List.fromList([72, 101, 108, 108, 111]); // "Hello"
      final jsFile = _createJSFile('test.txt', content, 'text/plain');
      globalContext['_bondDroppedFiles'] = _mockFileList([jsFile]);

      // Dispatch drop event
      html.window.dispatchEvent(html.CustomEvent('bond-file-drop'));

      // Wait for async file reading
      final files = await completer.future.timeout(
        const Duration(seconds: 5),
        onTimeout: () => throw TimeoutException('Drop handler did not fire'),
      );

      expect(files, hasLength(1));
      expect(files[0].name, 'test.txt');
      expect(files[0].bytes, content);

      // Verify _bondDroppedFiles was cleared
      expect(globalContext['_bondDroppedFiles'], isNull);
    });

    test('drop event reads multiple files', () async {
      final completer = Completer<List<({String name, Uint8List bytes})>>();
      drop.initWebDrop(
        onFileDrop: (files) {
          if (!completer.isCompleted) completer.complete(files);
        },
        onDragEnter: () {},
        onDragLeave: () {},
      );

      final content1 = Uint8List.fromList([1, 2, 3]);
      final content2 = Uint8List.fromList([4, 5, 6, 7]);
      final file1 = _createJSFile('a.png', content1, 'image/png');
      final file2 = _createJSFile('b.pdf', content2, 'application/pdf');
      globalContext['_bondDroppedFiles'] = _mockFileList([file1, file2]);

      html.window.dispatchEvent(html.CustomEvent('bond-file-drop'));

      final files = await completer.future.timeout(
        const Duration(seconds: 5),
      );

      expect(files, hasLength(2));
      expect(files[0].name, 'a.png');
      expect(files[0].bytes, content1);
      expect(files[1].name, 'b.pdf');
      expect(files[1].bytes, content2);
    });

    test('reinitializing cleans up previous subscriptions', () async {
      var firstCount = 0;
      var secondCount = 0;

      drop.initWebDrop(
        onFileDrop: (_) {},
        onDragEnter: () => firstCount++,
        onDragLeave: () {},
      );

      // Re-init with different callbacks
      drop.initWebDrop(
        onFileDrop: (_) {},
        onDragEnter: () => secondCount++,
        onDragLeave: () {},
      );

      html.window.dispatchEvent(html.CustomEvent('bond-drag-enter'));
      await Future<void>.delayed(Duration.zero);

      expect(firstCount, 0, reason: 'Old listener should be cleaned up');
      expect(secondCount, 1, reason: 'New listener should fire');
    });
  });
}
