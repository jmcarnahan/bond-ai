import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/core/utils/error_message_utils.dart';

void main() {
  group('humanizeErrorMessage', () {
    group('Exception prefix stripping', () {
      test('strips single Exception: prefix', () {
        expect(
          humanizeErrorMessage('Exception: Something went wrong'),
          'Something went wrong',
        );
      });

      test('strips double-nested Exception: prefixes', () {
        expect(
          humanizeErrorMessage('Exception: Exception: Something went wrong'),
          'Something went wrong',
        );
      });

      test('strips triple-nested Exception: prefixes', () {
        expect(
          humanizeErrorMessage(
              'Exception: Exception: Exception: Something went wrong'),
          'Something went wrong',
        );
      });

      test('strips ClientException: prefix', () {
        expect(
          humanizeErrorMessage('ClientException: Some error'),
          'Some error',
        );
      });

      test('strips FormatException: prefix', () {
        expect(
          humanizeErrorMessage('FormatException: Bad format'),
          'Bad format',
        );
      });

      test('leaves message without prefix unchanged', () {
        expect(
          humanizeErrorMessage('Something went wrong'),
          'Something went wrong',
        );
      });
    });

    group('network error detection', () {
      test('XMLHttpRequest error maps to connection message', () {
        expect(
          humanizeErrorMessage('ClientException: XMLHttpRequest error.'),
          'Unable to connect to the server. Please check your connection and try again.',
        );
      });

      test('connection refused maps to connection message', () {
        expect(
          humanizeErrorMessage('SocketException: Connection refused'),
          'Unable to connect to the server. Please check your connection and try again.',
        );
      });

      test('connection timed out maps to connection message', () {
        expect(
          humanizeErrorMessage('Connection timed out'),
          'Unable to connect to the server. Please check your connection and try again.',
        );
      });

      test('failed to fetch maps to connection message', () {
        expect(
          humanizeErrorMessage('Failed to fetch'),
          'Unable to connect to the server. Please check your connection and try again.',
        );
      });

      test('failed host lookup maps to connection message', () {
        expect(
          humanizeErrorMessage('SocketException: Failed host lookup'),
          'Unable to connect to the server. Please check your connection and try again.',
        );
      });
    });

    group('JSON detail extraction', () {
      test('extracts detail from 409 response', () {
        expect(
          humanizeErrorMessage(
              'Failed to create agent: 409 {"detail": "Agent already exists"}'),
          'An agent with this name already exists. Please choose a different name.',
        );
      });

      test('extracts detail from 403 response', () {
        expect(
          humanizeErrorMessage(
              'Failed to update agent: 403 {"detail": "Only the agent owner can modify the system prompt (instructions)."}'),
          'Only the agent owner can modify the system prompt (instructions).',
        );
      });

      test('extracts detail from 404 response', () {
        expect(
          humanizeErrorMessage(
              'Failed to update agent: 404 {"detail": "Agent not found."}'),
          'The requested agent was not found.',
        );
      });

      test('extracts permission-related detail', () {
        expect(
          humanizeErrorMessage(
              'Failed to update agent: 403 {"detail": "You do not have permission to edit this agent."}'),
          'You do not have permission to perform this action.',
        );
      });

      test('extracts admin-only detail', () {
        expect(
          humanizeErrorMessage(
              'Failed to update agent: 403 {"detail": "Only admin users can edit the Home agent."}'),
          'Only admin users can perform this action.',
        );
      });

      test('falls back on malformed JSON', () {
        final result = humanizeErrorMessage(
            'Failed to create agent: 409 {not valid json}');
        expect(result,
            'An agent with this name already exists. Please choose a different name.');
      });
    });

    group('status code mapping without JSON', () {
      test('maps 409 to duplicate name message', () {
        expect(
          humanizeErrorMessage('Failed to create agent: 409'),
          'An agent with this name already exists. Please choose a different name.',
        );
      });

      test('maps 403 to permission message', () {
        expect(
          humanizeErrorMessage('Failed to update agent: 403'),
          'You do not have permission to perform this action.',
        );
      });

      test('maps 404 to not found message', () {
        expect(
          humanizeErrorMessage('Failed to update agent: 404'),
          'The requested agent was not found.',
        );
      });

      test('maps 500 to server error message', () {
        expect(
          humanizeErrorMessage('Failed to create agent: 500'),
          'A server error occurred. Please try again later.',
        );
      });
    });

    group('edge cases', () {
      test('empty string returns fallback message', () {
        expect(
          humanizeErrorMessage(''),
          'An unexpected error occurred. Please try again.',
        );
      });

      test('truncates very long messages to 200 chars', () {
        final longMessage = 'A' * 300;
        final result = humanizeErrorMessage(longMessage);
        expect(result.length, 203); // 200 + '...'
        expect(result.endsWith('...'), isTrue);
      });

      test('passes through already-friendly messages', () {
        expect(
          humanizeErrorMessage('Agent name cannot be empty.'),
          'Agent name cannot be empty.',
        );
      });

      test('handles combined Exception prefix + status code', () {
        expect(
          humanizeErrorMessage(
              'Exception: Failed to create agent: 409 {"detail": "Agent already exists"}'),
          'An agent with this name already exists. Please choose a different name.',
        );
      });

      test('does not false-positive on numbers containing status codes', () {
        final result = humanizeErrorMessage('Timeout after 5000ms');
        expect(result, 'Timeout after 5000ms');
      });

      test('does not false-positive on port numbers', () {
        final result = humanizeErrorMessage('Connection failed to :4090');
        expect(result, 'Connection failed to :4090');
      });

      test('prefix stripping that leaves empty string returns fallback', () {
        expect(
          humanizeErrorMessage('Exception: '),
          'An unexpected error occurred. Please try again.',
        );
      });
    });
  });
}
