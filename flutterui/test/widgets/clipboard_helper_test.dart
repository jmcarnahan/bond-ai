@TestOn('browser')
library;

// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:html' as html;
import 'dart:js_interop';
import 'dart:js_interop_unsafe';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/src/widgets/clipboard_helper_web.dart'
    as clipboard;

void main() {
  group('ClipboardHelper (js_interop migration)', () {
    test('isSupported returns true on web', () {
      expect(clipboard.isSupported, isTrue);
    });

    test('JS object creation via callAsConstructor works', () {
      // This exercises the _newJSObject() pattern:
      // (globalContext['Object'] as JSFunction).callAsConstructor()
      // NOTE: Explicit JSObject type is required for DDC (dev compiler) to
      // resolve the dart:js_interop_unsafe extension methods ([], []=, etc.).
      final JSObject obj =
          (globalContext['Object'] as JSFunction).callAsConstructor();
      expect(obj, isNotNull);
      // Verify it's a real JS object by setting/getting a property
      obj['testKey'] = 'testValue'.toJS;
      final value = (obj['testKey']! as JSString).toDart;
      expect(value, 'testValue');
    });

    test('html.Blob can be cast to JSObject via dynamic', () {
      // This exercises the `(blob as dynamic) as JSObject` pattern used in
      // copyImageToClipboard to pass dart:html Blob to JS interop APIs.
      final bytes = Uint8List.fromList([1, 2, 3]);
      final blob = html.Blob([bytes], 'image/png');

      // The cast pattern used in the migrated code:
      final jsObj = (blob as dynamic) as JSObject;
      expect(jsObj, isNotNull);

      // Verify we can read properties via js_interop_unsafe
      final size = (jsObj['size']! as JSNumber).toDartDouble.toInt();
      expect(size, 3);
      final type = (jsObj['type']! as JSString).toDart;
      expect(type, 'image/png');
    });

    test('ClipboardItem constructor is accessible', () {
      // Verify ClipboardItem exists in the browser environment.
      // This exercises the globalContext['ClipboardItem'] pattern.
      final ctor = globalContext['ClipboardItem'];
      expect(ctor, isNotNull, reason: 'ClipboardItem should exist in Chrome');
    });

    test('copyImageToClipboard returns false without user gesture', () async {
      // In headless Chrome tests, clipboard.write() requires a user gesture
      // and will be rejected. The function should catch this and return false.
      final bytes = Uint8List.fromList([137, 80, 78, 71]); // PNG magic bytes
      final result = await clipboard.copyImageToClipboard(bytes);
      expect(result, isFalse);
    });

    test('readFilesFromClipboard returns empty list without permission',
        () async {
      // clipboard.read() requires permission which isn't granted in tests.
      // The function should catch the error and return empty list.
      final files = await clipboard.readFilesFromClipboard();
      expect(files, isEmpty);
    });

    test('downloadImage creates and clicks an anchor element', () {
      // Track anchor creation by checking that no error is thrown.
      // In a browser test environment, the download won't actually trigger
      // a file save dialog, but the DOM manipulation should succeed.
      final bytes = Uint8List.fromList([1, 2, 3, 4, 5]);
      expect(
        () => clipboard.downloadImage(bytes, 'test_download.png'),
        returnsNormally,
      );
    });

    test('FileReader can read from JS Blob via dynamic cast', () async {
      // This exercises the full pattern used in readFilesFromClipboard:
      // create a blob, cast it via dynamic, read it with FileReader.
      final data = Uint8List.fromList([10, 20, 30, 40, 50]);
      final blob = html.Blob([data]);

      // Simulate the pattern: get a JSObject reference, then cast back
      final jsBlob = (blob as dynamic) as JSObject;
      final dartBlob = (jsBlob as dynamic) as html.Blob;

      final reader = html.FileReader();
      reader.readAsArrayBuffer(dartBlob);
      await reader.onLoadEnd.first;

      final result = reader.result;
      expect(result, isNotNull);
      final bytes = Uint8List.fromList((result as List).cast<int>());
      expect(bytes, data);
    });

    test('callMethodVarArgs works for JS method calls', () {
      // This exercises the pattern used for ClipboardItem.getType()
      // and FileList.item() — callMethodVarArgs on JSObject.
      //
      // Test with Array.push() and Array.indexOf() as a proxy.
      // NOTE: Explicit JSObject type is required for DDC to resolve extensions.
      final JSObject jsArray =
          (globalContext['Array'] as JSFunction).callAsConstructor();
      jsArray.callMethodVarArgs('push'.toJS, ['hello'.toJS]);
      jsArray.callMethodVarArgs('push'.toJS, ['world'.toJS]);

      final length = (jsArray['length']! as JSNumber).toDartDouble.toInt();
      expect(length, 2);

      final idx = (jsArray.callMethodVarArgs<JSNumber>(
              'indexOf'.toJS, ['world'.toJS]))
          .toDartDouble
          .toInt();
      expect(idx, 1);
    });
  });
}
