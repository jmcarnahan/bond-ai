import 'package:logger/logger.dart';

// Configure a logger instance
final logger = Logger(
  printer: PrettyPrinter(
    methodCount: 1, // Number of method calls to be displayed
    errorMethodCount: 5, // Number of method calls if stacktrace is provided
    lineLength: 120, // Width of the output
    colors: true, // Colorful log messages
    printEmojis: true, // Print an emoji for each log message
    printTime: false, // Should each log print contain a timestamp
  ),
  output: ConsoleOutput(), // Send log messages to the console
);

// Example of a custom LogOutput for future use (e.g., sending to a remote server)
// class RemoteLogOutput extends LogOutput {
//   @override
//   void output(OutputEvent event) {
//     // Here you would send event.lines to your remote data source
//     // For example, using an HTTP client
//     for (var line in event.lines) {
//       print('Remote: $line'); // Replace with actual remote logging
//     }
//   }
// }

// To use a different output, you could reconfigure the logger:
// logger.t = Logger(
//   printer: PrettyPrinter(),
//   output: MultiOutput([ConsoleOutput(), RemoteLogOutput()]), // Example of multiple outputs
// );

// Log levels:
// logger.t("Trace log");
// logger.d("Debug log");
// logger.i("Info log");
// logger.w("Warning log");
// logger.e("Error log");
// logger.f("What a terrible failure log");
