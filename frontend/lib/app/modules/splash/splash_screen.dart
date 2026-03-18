import 'dart:async';
import 'package:flutter/material.dart';
import '../../data/services/api_service.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _initApp();
  }

  Future<void> _initApp() async {
    await ApiService.init();
    await Future.delayed(const Duration(seconds: 3));

    if (!mounted) return;

    if (ApiService.userId != null && ApiService.isOnboardingComplete) {
      Navigator.of(context).pushReplacementNamed('/dashboard');
    } else if (ApiService.isOnboardingComplete) {
      Navigator.of(context).pushReplacementNamed('/signIn');
    } else {
      Navigator.of(context).pushReplacementNamed('/auth');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF222222), // Dark background from PDF
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Placeholder for your app logo (Page 1/2)
             const Icon(Icons.favorite, size: 100, color: Colors.green),
            // You would use your local asset like this:
            // Image.asset('assets/icons/app_logo.png', width: 150),
            const SizedBox(height: 20),
            const CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
            ),
          ],
        ),
      ),
    );
  }
}