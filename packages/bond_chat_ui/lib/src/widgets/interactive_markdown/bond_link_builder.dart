import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:markdown/markdown.dart' as md;

import 'prompt_button.dart';

class BondLinkBuilder extends MarkdownElementBuilder {
  final void Function(String prompt)? onPromptButtonTap;

  BondLinkBuilder({this.onPromptButtonTap});

  @override
  void visitElementBefore(md.Element element) {
    final href = element.attributes['href'] ?? '';
    // flutter_markdown bug (#137688): when visitElementAfterWithContext returns
    // a Widget, only the first child text widget is replaced — the rest leak as
    // orphaned styled text spans. Multi-word link text can be split into
    // multiple md.Text nodes by the parser.
    // Fix: consolidate all children into a single text node so there is exactly
    // one child widget to replace. Must keep at least one child because
    // flutter_markdown's extractTextFromElement returns null for empty children,
    // which causes the entire element to be skipped.
    if (href.startsWith('bond://') && element.children != null && element.children!.length > 1) {
      final fullText = element.textContent;
      element.children!
        ..clear()
        ..add(md.Text(fullText));
    }
  }

  @override
  Widget? visitElementAfterWithContext(
    BuildContext context,
    md.Element element,
    TextStyle? preferredStyle,
    TextStyle? parentStyle,
  ) {
    final href = element.attributes['href'] ?? '';
    final text = element.textContent;

    if (href == 'bond://prompt' || href.startsWith('bond://prompt/')) {
      return PromptButton(
        label: text,
        onPressed: () => onPromptButtonTap?.call(text),
      );
    }

    if (href.startsWith('bond://')) {
      return Text(text, style: preferredStyle);
    }

    // Regular link — fall through to default rendering via onTapLink
    return null;
  }
}
