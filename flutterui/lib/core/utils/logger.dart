import 'package:logger/logger.dart';

final logger = Logger(
  printer: SimplePrinter(
    colors: true,
    printTime: false,
  ),
  output: ConsoleOutput(),
);
