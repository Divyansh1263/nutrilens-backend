import 'package:college_project/app/modules/auth/views/singin_screen.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';


import '../../../../main.dart';

class AuthScreen extends StatelessWidget {
  const AuthScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight),
                child: IntrinsicHeight(
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        // Top "New Year, New You!" text (Page 2)
                        Text(
                          "New Year, New You! Get healthier in 2026",
                          textAlign: TextAlign.center,
                          style: textTheme.titleMedium?.copyWith(
                            color: Colors.grey[600],
                          ),
                        ),
                        const Spacer(),

                        // Hero Image (Page 2)
                        Image.asset("assets/images/logo_with_text.png"),
                        //
                        //   'https://placehold.co/200x200/4CAF50/FFFFFF?text=AI+Bot&font=poppins',
                        //   height: 200,
                        // ),
                        // You would use your local asset like this:
                        // Image.asset('assets/images/auth_hero.png', height: 200),
                        // const SizedBox(height: 8),
                        // Main Welcome Text (Page 2)
                        Text(
                          "Hey I am your Personal Nutritionist powered by AI.",
                          textAlign: TextAlign.center,
                          style: textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          "I will ask you some questions to personalize a smart diet plan for you",
                          textAlign: TextAlign.center,
                          style: textTheme.bodyLarge?.copyWith(
                            color: Colors.grey[700],
                          ),
                        ),
                        const Spacer(),
                        // Continue Button
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton(
                            onPressed: () {
                              Navigator.of(context).pushReplacementNamed('/onboarding');
                            },
                            child: const Text("Continue"),
                          ),
                        ),
                        const SizedBox(height: 20),
                        // Sign In text
                        TextButton(
                          onPressed: () {
                            Navigator.push(context, MaterialPageRoute(builder: (context)=> SignInScreen()));
                          },
                          child: RichText(
                            text: TextSpan(
                              style: textTheme.bodyMedium,
                              children: [
                                TextSpan(
                                  text: "Already have an account? ",
                                  style: TextStyle(color: Colors.grey[600]),
                                ),
                                TextSpan(
                                  text: "Sign in",
                                  style: const TextStyle(
                                    color: MyApp.primaryColor,
                                    fontWeight: FontWeight.bold,
                                  ),
                                  recognizer: TapGestureRecognizer()
                                    ..onTap = () {
                                      // Navigate to the new Sign In screen
                                      Navigator.of(context).pushNamed('/signIn');
                                    },
                                 ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}