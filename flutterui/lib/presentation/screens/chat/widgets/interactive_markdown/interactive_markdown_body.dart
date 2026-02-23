import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import 'bond_link_builder.dart';

/// Pattern matching the URL portion of a bond:// markdown link.
/// Captures everything between `](bond://` and the closing `)` so we can
/// URL-encode any raw spaces the LLM may have left unencoded.
final _bondLinkUrlPattern = RegExp(r'\]\(bond://([^)]*)\)');

/// URL-encode spaces in bond:// link destinations so the markdown parser
/// doesn't truncate the URL at the first space (which causes orphaned text
/// to leak into the rendered output with link styling).
String sanitizeBondLinks(String data) {
  return data.replaceAllMapped(_bondLinkUrlPattern, (match) {
    final path = match.group(1)!;
    final encoded = path.replaceAll(' ', '%20');
    return '](bond://$encoded)';
  });
}

class InteractiveMarkdownBody extends StatelessWidget {
  final String data;
  final MarkdownStyleSheet? styleSheet;
  final void Function(String text, String? href, String? title) onTapLink;
  final void Function(String prompt)? onPromptButtonTap;

  const InteractiveMarkdownBody({
    super.key,
    required this.data,
    this.styleSheet,
    required this.onTapLink,
    this.onPromptButtonTap,
  });

  @override
  Widget build(BuildContext context) {
    return SelectionArea(
      child: MarkdownBody(
        data: sanitizeBondLinks(data),
        styleSheet: styleSheet,
        builders: {
          'a': BondLinkBuilder(
            onPromptButtonTap: onPromptButtonTap,
          ),
        },
        onTapLink: onTapLink,
      ),
    );
  }
}
