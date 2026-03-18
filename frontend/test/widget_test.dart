// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:college_project/main.dart';

void main() {
  testWidgets('App boots (smoke test)', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());
    // App has timers / async startup work; don't wait forever in a unit test.
    await tester.pump(const Duration(milliseconds: 200));

    // We don't assert a specific page (splash/auth can vary),
    // just that the widget tree boots.
    expect(find.byType(MaterialApp), findsOneWidget);
    expect(find.byType(MyApp), findsOneWidget);
  });
}
