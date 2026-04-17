import 'package:markdown/markdown.dart' as md;

/// Extracts plain text from markdown content by walking the AST.
class MarkdownTextExtractor implements md.NodeVisitor {
  final StringBuffer _buffer = StringBuffer();

  String extract(String markdownText) {
    _buffer.clear();
    final lines = markdownText.split('\n');
    final document = md.Document().parseLines(lines);
    for (final node in document) {
      node.accept(this);
    }
    return _buffer.toString().trim();
  }

  @override
  bool visitElementBefore(md.Element element) {
    if (_buffer.isNotEmpty &&
        !_buffer.toString().endsWith('\n') &&
        const ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre']
            .contains(element.tag)) {
      _buffer.write('\n');
    }
    return true;
  }

  @override
  void visitElementAfter(md.Element element) {
    if (const ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote']
        .contains(element.tag)) {
      if (!_buffer.toString().endsWith('\n')) {
        _buffer.write('\n');
      }
    }
  }

  @override
  void visitText(md.Text text) {
    _buffer.write(text.text);
  }
}
