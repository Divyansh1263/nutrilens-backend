import 'package:flutter/material.dart';
import '../../../../main.dart'; // For colors
import '../../../data/services/api_service.dart';
import 'package:provider/provider.dart';
import '../../../data/providers/data_provider.dart';

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key});

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _formKey = GlobalKey<FormState>();
  bool _obscurePassword = true;

  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.black),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header
              Text(
                "Welcome Back!",
                style: textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                "Sign in to continue your journey.",
                style: textTheme.bodyLarge?.copyWith(
                  color: Colors.grey[700],
                ),
              ),
              const SizedBox(height: 40),

              // Email Field
              TextFormField(
                controller: _emailController,
                decoration: InputDecoration(
                  labelText: "Email",
                  prefixIcon: const Icon(Icons.email_outlined),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                keyboardType: TextInputType.emailAddress,
                validator: (value) {
                  if (value == null || value.isEmpty || !value.contains('@')) {
                    return 'Please enter a valid email';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 20),

              // Password Field
              TextFormField(
                controller: _passwordController,
                obscureText: _obscurePassword,
                decoration: InputDecoration(
                  labelText: "Password",
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscurePassword
                          ? Icons.visibility_off_outlined
                          : Icons.visibility_outlined,
                    ),
                    onPressed: () {
                      setState(() {
                        _obscurePassword = !_obscurePassword;
                      });
                    },
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty || value.length < 6) {
                    return 'Password must be at least 6 characters';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // Forgot Password
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () {
                    // TODO: Handle Forgot Password
                  },
                  child: const Text(
                    "Forgot Password?",
                    style: TextStyle(color: MyApp.primaryColor),
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Sign In Button
              ElevatedButton(
                onPressed: () async {
                  if (_formKey.currentState!.validate()) {
                    // Call Login API
                    // Show Loading
                    showDialog(
                        context: context, 
                        barrierDismissible: false,
                        builder: (ctx) => const Center(child: CircularProgressIndicator())
                    );
                    
                    final response = await ApiService.loginUser(
                      _emailController.text.trim(), 
                      _passwordController.text // Use the controller for password
                    );
                    
                    if (!context.mounted) return;
                    Navigator.of(context).pop(); // Close loader

                    if (response != null && ApiService.userId != null) {
                        // Mark onboarding complete
                        await ApiService.completeOnboarding();
                        // Prime provider cache for Account/Diet greeting immediately
                        if (context.mounted) {
                          final dp = context.read<DataProvider>();
                          if (dp.userProfileModel == null) {
                            await dp.setUserProfile(response);
                          }
                        }
                        
                        if (!context.mounted) return;
                        Navigator.of(context).pushNamedAndRemoveUntil(
                          '/dashboard',
                              (Route<dynamic> route) => false,
                        );
                    } else {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                             const SnackBar(content: Text("Login failed. Check credentials."))
                          );
                        }
                    }
                  }
                },
                child: const Text("Sign In"),
              ),
              const SizedBox(height: 32),

              // "Or sign in with"
              Row(
                children: [
                  Expanded(child: Divider(color: Colors.grey[300])),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Text(
                      "Or sign in with",
                      style: TextStyle(color: Colors.grey[600]),
                    ),
                  ),
                  Expanded(child: Divider(color: Colors.grey[300])),
                ],
              ),
              const SizedBox(height: 24),

              // Social Logins (Google / Apple)
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildSocialButton(
                    'assets/images/google.png',
                    () async {
                      showDialog(
                        context: context,
                        barrierDismissible: false,
                        builder: (ctx) => const Center(
                          child: CircularProgressIndicator(),
                        ),
                      );

                      final userData = await ApiService.signInWithGoogle();

                      if (!context.mounted) return;
                      Navigator.of(context).pop(); // close loader

                      if (userData != null) {
                        await ApiService.completeOnboarding();
                        if (context.mounted) {
                          final dp = context.read<DataProvider>();
                          await dp.setUserProfile(userData);
                        }
                        final isNew =
                            userData['onboarding_completed'] == false;
                        if (!context.mounted) return;
                        Navigator.of(context).pushNamedAndRemoveUntil(
                          isNew ? '/onboarding' : '/dashboard',
                          (Route<dynamic> route) => false,
                        );
                      } else {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Google Sign-In failed or cancelled.'),
                            ),
                          );
                        }
                      }
                    },
                  ),
                ],
              ),
              const SizedBox(height: 32),

              // Sign Up Link
              TextButton(
                onPressed: () {
                  // Pop back to the auth screen
                  Navigator.of(context).pop();
                },
                child: RichText(
                  textAlign: TextAlign.center,
                  text: TextSpan(
                    style: textTheme.bodyMedium,
                    children: [
                      TextSpan(
                        text: "Don't have an account? ",
                        style: TextStyle(color: Colors.grey[600]),
                      ),
                      const TextSpan(
                        text: "Sign up",
                        style: TextStyle(

                          color: MyApp.primaryColor,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSocialButton(String iconPlaceholder, VoidCallback onPressed) {
    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        shape: const CircleBorder(),
        padding: const EdgeInsets.all(12),
        side: BorderSide(color: Colors.grey[300]!),
      ),
      child: Image.asset(
        iconPlaceholder,
        width: 28,
        height: 28,
      ),
      // In real app:
      // child: SvgPicture.asset(
      //   'assets/icons/google_logo.svg',
      //   width: 28,
      //   height: 28,
      // ),
    );
  }
}