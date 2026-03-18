import 'package:flutter/material.dart';
import 'dart:math';

class OnboardingController extends ChangeNotifier {
  String? gender;
  double height = 170.0; // cm
  int age = 25;
  String? activityLevel;
  double weight = 70.0; // kg
  String? goal;
  double targetWeight = 65.0; // kg
  double pace = 0.5; // kg/week
  List<String> restrictions = [];
  List<String> healthConditions = [];

  void updateGender(String value) {
    gender = value;
    notifyListeners();
  }

  void updateHeight(double value) {
    height = value;
    notifyListeners();
  }

  void updateAge(int value) {
    age = value;
    notifyListeners();
  }

  void updateActivityLevel(String value) {
    activityLevel = value;
    notifyListeners();
  }

  void updateWeight(double value) {
    weight = value;
    notifyListeners();
  }

  void updateGoal(String value) {
    goal = value;
    // Auto-adjust target weight based on goal
    if (value == 'Lose Weight' && targetWeight >= weight) {
      targetWeight = weight - 5;
    } else if (value == 'Gain Weight' && targetWeight <= weight) {
      targetWeight = weight + 5;
    } else if (value == 'Maintain weight') {
      targetWeight = weight;
    }
    notifyListeners();
  }

  void updateTargetWeight(double value) {
    targetWeight = value;
    notifyListeners();
  }

  void updatePace(double value) {
    pace = value;
    notifyListeners();
  }

  void toggleRestriction(String value) {
    if (restrictions.contains(value)) {
      restrictions.remove(value);
    } else {
      restrictions.add(value);
    }
    notifyListeners();
  }

  void toggleHealthCondition(String value) {
    if (healthConditions.contains(value)) {
      healthConditions.remove(value);
    } else {
      healthConditions.add(value);
    }
    notifyListeners();
  }

  double calculateBmi() {
    if (height <= 0) return 0;
    return weight / pow(height / 100, 2);
  }
}