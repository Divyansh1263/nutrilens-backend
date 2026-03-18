import 'package:flutter/material.dart';
import 'package:numberpicker/numberpicker.dart';
import 'package:provider/provider.dart';

import '../../../main.dart';
import '../../data/services/api_service.dart';
import 'controllers/onboarding_controller.dart';

// Main Onboarding Screen Widget
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  @override
  void dispose() {
    _pageController.dispose();
    _nameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  // Credentials controllers
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  void _validateAndNext() {
     if (_formKey.currentState!.validate()) {
       _nextPage();
     }
  }

  void _nextPage() async {
    if (_currentPage < 10) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      // Last page - Register User
      final controller = Provider.of<OnboardingController>(context, listen: false);
      
      // Map Activity Level
      String activity = "moderately_active";
      if (controller.activityLevel != null) {
        activity = controller.activityLevel!.toLowerCase().replaceAll(' ', '_');
      }

      // Map Goal
      String dietGoal = "lose_weight";
      if (controller.goal != null) {
        dietGoal = controller.goal!.toLowerCase().replaceAll(' ', '_');
      }
      
      // Map Speed
      String speed = "medium";
      if (controller.pace < 0.4) {
        speed = "slow";
      } else if (controller.pace > 0.8) {
        speed = "fast";
      }

      // Map Restrictions
      final restrictions = {
        "is_vegetarian": controller.restrictions.contains("Vegetarian"),
        "is_vegan": controller.restrictions.contains("Vegan"),
        "is_gluten_free": controller.restrictions.contains("Gluten Free"),
        "is_nut_free": controller.restrictions.contains("Nut Free"),
      };

      // Map Health
      final health = {
        "explanations.diabetes": controller.healthConditions.contains("Diabetes"),
        "explanations.fever": controller.healthConditions.contains("Fever / Sick"),
        "explanations.weight_loss": controller.healthConditions.contains("Weight Loss Goal"),
        "explanations.muscle_gain": controller.healthConditions.contains("Muscle Gain Goal"),
      };

      final userData = {
        "email": _emailController.text.trim(), // New
        "password": _passwordController.text, // New
        "name": _nameController.text.trim().isEmpty ? "User Name" : _nameController.text.trim(), // New
        "age": controller.age,
        "gender": controller.gender?.toLowerCase() ?? "male",
        "height": controller.height,
        "weight": controller.weight,
        "target_weight": controller.targetWeight,
        "activity_level": activity,
        "dietary_goal": dietGoal,
        "weight_loss_speed": speed,
        "dietary_restrictions": restrictions,
        "health_conditions": health
      };

      final success = await ApiService.registerUser(userData);
      
      if (success) {
        await ApiService.completeOnboarding();
        if (!mounted) return;
        Navigator.of(context).pushReplacementNamed('/dashboard');
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Failed to create profile. Check connection.")),
        );
      }
    }
  }

  void _previousPage() {
    _pageController.previousPage(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      _CredentialsPage(
         formKey: _formKey,
         nameController: _nameController,
         emailController: _emailController,
         passwordController: _passwordController,
         onContinue: _validateAndNext
      ),
      _GenderPage(onContinue: _nextPage),
      _HeightPage(onContinue: _nextPage),
      _AgePage(onContinue: _nextPage),
      _ActivityPage(onContinue: _nextPage),
      _WeightPage(onContinue: _nextPage),
      _GoalPage(onContinue: _nextPage),
      _TargetWeightPage(onContinue: _nextPage),
      _PacePage(onContinue: _nextPage),
      _RestrictionsPage(onContinue: _nextPage),
      _HealthPage(onContinue: _nextPage),
      _SummaryPage(onContinue: _nextPage),
    ];

    return Scaffold(
      appBar: AppBar(
        leading: _currentPage > 0
            ? IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: _previousPage,
        )
            : null,
        title: Text('Step ${_currentPage + 1} of ${pages.length}'),
        actions: [
          if (_currentPage < pages.length - 1)
            TextButton(
              onPressed: _nextPage,
              child: const Text('Skip'),
            )
        ],
        // Progress Bar
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(4.0),
          child: LinearProgressIndicator(
            value: (_currentPage + 1) / pages.length,
            backgroundColor: Colors.grey[300],
            valueColor:
            const AlwaysStoppedAnimation<Color>(Colors.green),
          ),
        ),
      ),
      body: PageView(
        controller: _pageController,
        physics: const NeverScrollableScrollPhysics(),
        onPageChanged: (page) {
          setState(() {
            _currentPage = page;
          });
        },
        children: pages,
      ),
    );
  }
}

// --- Page 1: Gender (Page 3) ---
class _GenderPage extends StatelessWidget {
  final VoidCallback onContinue;
  const _GenderPage({required this.onContinue});

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    return _OnboardingPageWrapper(
      title: "What is your gender?",
      onContinue: onContinue,
      child: Column(
        children: [
          Expanded(
            child: Row(
              children: [
                _buildGenderCard(
                    context,
                    'Male',
                    'assets/images/male_avatar.png',
                    controller.gender == 'Male', () {
                  controller.updateGender('Male');
                }),
                const SizedBox(width: 16),
                _buildGenderCard(
                    context,
                    'Female',
                    'assets/images/female_avatar.png',
                    controller.gender == 'Female', () {
                  controller.updateGender('Female');
                }),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Text(
            "We use your gender to design the best diet plan for you.",
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildGenderCard(BuildContext context, String title, String assetPath,bool isSelected, VoidCallback onTap) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          decoration: BoxDecoration(
            color: Colors.grey[100],
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isSelected ? Colors.green : Colors.transparent,
              width: 3,
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Expanded(
                child:ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: Image.asset(
            assetPath,
            fit: BoxFit.cover,
            errorBuilder: (context, error, stackTrace) =>
            const Icon(Icons.person, size: 100),
          ),
        ),
                // child: Image.asset(assetPath, fit: BoxFit.contain),
              ),
              const SizedBox(height: 16),
              Text(title,
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }
}

// --- Page 2: Height (Page 4) ---
class _HeightPage extends StatefulWidget {
  final VoidCallback onContinue;
  const _HeightPage({required this.onContinue});

  @override
  State<_HeightPage> createState() => _HeightPageState();
}

class _HeightPageState extends State<_HeightPage> {
  final TextEditingController _textController = TextEditingController();

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    
    final String currentHeightStr = controller.height.toStringAsFixed(1);
    if (_textController.text != currentHeightStr &&
        double.tryParse(_textController.text)?.toStringAsFixed(1) != currentHeightStr) {
       _textController.text = currentHeightStr;
    }

    return _OnboardingPageWrapper(
      title: "What is your height?",
      onContinue: widget.onContinue,
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Display current value
            Text(
              "${controller.height.toStringAsFixed(1)} cm",
              style: Theme.of(context)
                  .textTheme
                  .headlineLarge
                  ?.copyWith(fontWeight: FontWeight.bold, color: Colors.green),
            ),
            const SizedBox(height: 20),
            // Scroll Wheel Picker
            NumberPicker(
              value: controller.height.toInt().clamp(120, 220),
              minValue: 120,
              maxValue: 220,
              step: 1,
              itemHeight: 50,
              axis: Axis.horizontal,
              selectedTextStyle: Theme.of(context)
                  .textTheme
                  .headlineMedium
                  ?.copyWith(fontWeight: FontWeight.bold, color: Colors.green),
              onChanged: (value) {
                double currentDecimal = controller.height - controller.height.truncateToDouble();
                controller.updateHeight(value.toDouble() + currentDecimal);
              },
            ),
            const SizedBox(height: 30),
            // Manual Numeric Input
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40.0),
              child: TextField(
                controller: _textController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                textAlign: TextAlign.center,
                decoration: const InputDecoration(
                  labelText: "Enter manually (cm)",
                  border: OutlineInputBorder(),
                ),
                onChanged: (value) {
                  double? parsed = double.tryParse(value);
                  if (parsed != null && parsed >= 120.0 && parsed <= 220.0) {
                     parsed = double.parse(parsed.toStringAsFixed(1));
                     controller.updateHeight(parsed);
                  }
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// --- Page 3: Age (Page 5) ---
class _AgePage extends StatelessWidget {
  final VoidCallback onContinue;
  const _AgePage({required this.onContinue});

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    return _OnboardingPageWrapper(
      title: "What is your age?",
      onContinue: onContinue,
      child: SingleChildScrollView(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 40.0),
            child: NumberPicker(
              value: controller.age,
              minValue: 10,
              maxValue: 100,
              step: 1,
              itemHeight: 100,
              axis: Axis.horizontal,
              selectedTextStyle: Theme.of(context)
                  .textTheme
                  .headlineMedium
                  ?.copyWith(fontWeight: FontWeight.bold, color: Colors.green),
              onChanged: (value) {
                controller.updateAge(value);
              },
            ),
          ),
        ),
      ),
    );
  }
}

// --- Page 4: Activity (Page 6) ---
class _ActivityPage extends StatelessWidget {
  final VoidCallback onContinue;
  const _ActivityPage({required this.onContinue});

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    return _OnboardingPageWrapper(
      title: "How active are you on a daily basis?",
      onContinue: onContinue,
      child: ListView(
        children: [
          _buildActivityCard(
            context,
            'Sedentary',
            'assets/images/snail.png',
            controller.activityLevel == 'Sedentary',
                () => controller.updateActivityLevel('Sedentary'),
          ),
          _buildActivityCard(
            context,
            'Lightly active',
            'assets/images/turttle.png',
            controller.activityLevel == 'Lightly active',
                () => controller.updateActivityLevel('Lightly active'),
          ),
          _buildActivityCard(
            context,
            'Moderately active',
            'assets/images/rabbit.png',
            controller.activityLevel == 'Moderately active',
                () => controller.updateActivityLevel('Moderately active'),
          ),
          _buildActivityCard(
            context,
            'Very active',
            'assets/images/cheetah.png',
            controller.activityLevel == 'Very active',
                () => controller.updateActivityLevel('Very active'),
          ),
        ],
      ),
    );
  }

  Widget _buildActivityCard(BuildContext context, String title,
      String placeholder, bool isSelected, VoidCallback onTap) {
    return Card(
      elevation: isSelected ? 4 : 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isSelected ? Colors.green : Colors.grey[300]!,
          width: 2,
        ),
      ),
      child: ListTile(
        onTap: onTap,
        leading: Image.asset(placeholder, width: 80),
        title: Text(title,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.bold)),
        // subtitle: Text("Description of activity level..."),
        trailing: isSelected
            ? const Icon(Icons.check_circle, color: Colors.green)
            : const Icon(Icons.radio_button_unchecked, color: Colors.grey),
      ),
    );
  }
}

// --- Page 5: Weight (Page 7) ---
class _WeightPage extends StatefulWidget {
  final VoidCallback onContinue;
  const _WeightPage({required this.onContinue});

  @override
  State<_WeightPage> createState() => _WeightPageState();
}

class _WeightPageState extends State<_WeightPage> {
  final TextEditingController _textController = TextEditingController();

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  Color _getBmiColor(double bmi) {
    if (bmi < 18.5) return Colors.blue;
    if (bmi < 25) return Colors.green;
    if (bmi < 30) return Colors.orange;
    return Colors.red;
  }

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    
    final String currentWeightStr = controller.weight.toStringAsFixed(1);
    if (_textController.text != currentWeightStr && 
        double.tryParse(_textController.text)?.toStringAsFixed(1) != currentWeightStr) {
       _textController.text = currentWeightStr;
    }

    final double bmi = controller.calculateBmi();
    final Color bmiColor = _getBmiColor(bmi);

    return _OnboardingPageWrapper(
      title: "What is your weight?",
      onContinue: widget.onContinue,
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Display current value
            Text(
              "${controller.weight.toStringAsFixed(1)} kg",
              style: Theme.of(context)
                  .textTheme
                  .headlineLarge
                  ?.copyWith(fontWeight: FontWeight.bold, color: Colors.green),
            ),
            const SizedBox(height: 20),
            // Scroll Wheel Picker
            NumberPicker(
              value: controller.weight.toInt().clamp(30, 200),
              minValue: 30,
              maxValue: 200,
              step: 1,
              itemHeight: 50,
              axis: Axis.horizontal,
              selectedTextStyle: Theme.of(context)
                  .textTheme
                  .headlineMedium
                  ?.copyWith(fontWeight: FontWeight.bold, color: Colors.green),
              onChanged: (value) {
                // preserve decimal
                double currentDecimal = controller.weight - controller.weight.truncateToDouble();
                controller.updateWeight(value.toDouble() + currentDecimal);
              },
            ),
            const SizedBox(height: 30),
            // 3. Manual Input
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40.0),
              child: TextField(
                controller: _textController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                textAlign: TextAlign.center,
                decoration: const InputDecoration(
                  labelText: "Enter manually (kg)",
                  border: OutlineInputBorder(),
                ),
                onChanged: (value) {
                  double? parsed = double.tryParse(value);
                  if (parsed != null && parsed >= 30.0 && parsed <= 200.0) {
                     // round to 1 decimal place
                     parsed = double.parse(parsed.toStringAsFixed(1));
                     controller.updateWeight(parsed);
                  }
                },
              ),
            ),
            const SizedBox(height: 30),
            // BMI Info
            Text(
              "Your BMI: ${bmi.toStringAsFixed(1)}",
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: bmiColor, fontWeight: FontWeight.bold
              ),
            ),
            const SizedBox(height: 10),
            Container(
              height: 12,
              width: double.infinity,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(10),
                gradient: const LinearGradient(
                  colors: [Colors.blue, Colors.green, Colors.orange, Colors.red],
                  stops: [0.0, 0.3, 0.6, 1.0],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// --- Page 6: Goal (Page 8) ---
class _GoalPage extends StatelessWidget {
  final VoidCallback onContinue;
  const _GoalPage({required this.onContinue});

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    return _OnboardingPageWrapper(
      title: "What are your main dietary goals?",
      onContinue: onContinue,
      child: ListView(
        children: [
          _buildActivityCard(
            context,
            'Lose Weight',
            'assets/images/weight_loose.png',
            controller.goal == 'Lose Weight',
                () => controller.updateGoal('Lose Weight'),
          ),
          _buildActivityCard(
            context,
            'Maintain weight',
            'assets/images/weight_maintain_weight.png',
            controller.goal == 'Maintain weight',
                () => controller.updateGoal('Maintain weight'),
          ),
          _buildActivityCard(
            context,
            'Gain Weight',
            'assets/images/weight_gain.png',
            controller.goal == 'Gain Weight',
                () => controller.updateGoal('Gain Weight'),
          ),
        ],
      ),
    );
  }

  // Reusing the activity card widget for goals
  Widget _buildActivityCard(BuildContext context, String title,
      String placeholder, bool isSelected, VoidCallback onTap) {
    return Card(
      elevation: isSelected ? 4 : 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isSelected ? Colors.green : Colors.grey[300]!,
          width: 2,
        ),
      ),
      child: ListTile(
        onTap: onTap,
        leading: Image.asset( placeholder, width: 80),
        title: Text(title,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.bold)),
        trailing: isSelected
            ? const Icon(Icons.check_circle, color: Colors.green)
            : const Icon(Icons.radio_button_unchecked, color: Colors.grey),
      ),
    );
  }
}

// --- Page 7: Target Weight (Page 9) ---
class _TargetWeightPage extends StatefulWidget {
  final VoidCallback onContinue;
  const _TargetWeightPage({required this.onContinue});

  @override
  State<_TargetWeightPage> createState() => _TargetWeightPageState();
}

class _TargetWeightPageState extends State<_TargetWeightPage> {
  final TextEditingController _textController = TextEditingController();

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    
    final String currentTargetStr = controller.targetWeight.toStringAsFixed(1);
    if (_textController.text != currentTargetStr && 
        double.tryParse(_textController.text)?.toStringAsFixed(1) != currentTargetStr) {
       _textController.text = currentTargetStr;
    }

    return _OnboardingPageWrapper(
      title: "What is your target weight?",
      onContinue: widget.onContinue,
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Display current value
            Text(
              "${controller.targetWeight.toStringAsFixed(1)} kg",
              style: Theme.of(context)
                  .textTheme
                  .headlineLarge
                  ?.copyWith(fontWeight: FontWeight.bold, color: Colors.green),
            ),
            const SizedBox(height: 20),
            // Scroll Wheel Picker
            NumberPicker(
              value: controller.targetWeight.toInt().clamp(30, 200),
              minValue: 30,
              maxValue: 200,
              step: 1,
              itemHeight: 50,
              axis: Axis.horizontal,
              selectedTextStyle: Theme.of(context)
                  .textTheme
                  .headlineMedium
                  ?.copyWith(fontWeight: FontWeight.bold, color: Colors.green),
              onChanged: (value) {
                double currentDecimal = controller.targetWeight - controller.targetWeight.truncateToDouble();
                controller.updateTargetWeight(value.toDouble() + currentDecimal);
              },
            ),
            const SizedBox(height: 30),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40.0),
              child: TextField(
                controller: _textController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                textAlign: TextAlign.center,
                decoration: const InputDecoration(
                  labelText: "Enter target manually (kg)",
                  border: OutlineInputBorder(),
                ),
                onChanged: (value) {
                  double? parsed = double.tryParse(value);
                  if (parsed != null && parsed >= 35.0 && parsed <= 200.0) {
                     parsed = double.parse(parsed.toStringAsFixed(1));
                     controller.updateTargetWeight(parsed);
                  }
                },
              ),
            ),
            const SizedBox(height: 30),
            // Message Card
            Card(
              color: Colors.blue[50],
              child: Builder(
                builder: (context) {
                  final diff = controller.weight - controller.targetWeight;
                  final absDiff = diff.abs();
                  final percent = (absDiff / controller.weight) * 100;
                  
                  String title;
                  String subtitle;
                  
                  if (controller.targetWeight < controller.weight) {
                    title = "Weight Loss Goal";
                    subtitle = "You will lose ${absDiff.toStringAsFixed(1)} kg (${percent.toStringAsFixed(1)}%)";
                  } else if (controller.targetWeight > controller.weight) {
                    title = "Weight Gain Goal";
                    subtitle = "You will gain ${absDiff.toStringAsFixed(1)} kg (${percent.toStringAsFixed(1)}%)";
                  } else {
                    title = "Maintain Weight";
                    subtitle = "You are right on target!";
                  }

                  return ListTile(
                    leading: const Icon(Icons.info, color: Colors.blue),
                    title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
                    subtitle: Text(subtitle),
                  );
                }
              ),
            )
          ],
        ),
      ),
    );
  }
}

// --- Page 8: Pace (Page 10) ---
class _PacePage extends StatelessWidget {
  final VoidCallback onContinue;
  const _PacePage({required this.onContinue});

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    return _OnboardingPageWrapper(
      title: "Choose a weight loss speed",
      onContinue: onContinue,
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const SizedBox(height: 40),
            Text(
              "${controller.pace.toStringAsFixed(1)} kg/week",
              style: Theme.of(context)
                  .textTheme
                  .headlineMedium
                  ?.copyWith(fontWeight: FontWeight.bold, color: Colors.green),
            ),
            const SizedBox(height: 20),
            Slider(
              value: controller.pace,
              min: 0.1,
              max: 1.0,
              divisions: 9,
              label: "${controller.pace.toStringAsFixed(1)} kg/week",
              onChanged: (double value) {
                controller.updatePace(value);
              },
            ),
            // Placeholder for icons
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Icon(Icons.directions_walk), // Snail
                  Icon(Icons.directions_run), // Rabbit
                  Icon(Icons.rocket_launch), // Cheetah
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// --- Page 9: Restrictions (Page 11) ---
class _RestrictionsPage extends StatelessWidget {
  final VoidCallback onContinue;
  const _RestrictionsPage({required this.onContinue});

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    final allRestrictions = [
      "Vegetarian",
      "Vegan",
      "Gluten Free",
      "Nut Free"
    ];
    return _OnboardingPageWrapper(
      title: "Do you have any dietary restrictions?",
      onContinue: onContinue,
      child: SingleChildScrollView(
        child: Wrap(
          spacing: 8.0,
          runSpacing: 4.0,
          children: allRestrictions.map((restriction) {
            final isSelected =
            controller.restrictions.contains(restriction);
            return FilterChip(
              label: Text(restriction),
              selected: isSelected,
              onSelected: (selected) {
                controller.toggleRestriction(restriction);
              },
              selectedColor: Colors.green[100],
              checkmarkColor: Colors.green,
            );
          }).toList(),
        ),
      ),
    );
  }
}

// --- Page 10: Health (Page 12) ---
class _HealthPage extends StatelessWidget {
  final VoidCallback onContinue;
  const _HealthPage({required this.onContinue});

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context);
    final allConditions = [
      "Diabetes",
      "Fever / Sick",
      "Weight Loss Goal",
      "Muscle Gain Goal"
    ];
    return _OnboardingPageWrapper(
      title: "Do you have any health conditions?",
      onContinue: onContinue,
      child: SingleChildScrollView(
        child: Wrap(
          spacing: 8.0,
          runSpacing: 4.0,
          children: allConditions.map((condition) {
            final isSelected = controller.healthConditions.contains(condition);
            return FilterChip(
              label: Text(condition),
              selected: isSelected,
              onSelected: (selected) {
                controller.toggleHealthCondition(condition);
              },
              selectedColor: Colors.green[100],
              checkmarkColor: Colors.green,
            );
          }).toList(),
        ),
      ),
    );
  }
}

// --- Page 11: Summary (Page 13) ---
class _SummaryPage extends StatelessWidget {
  final VoidCallback onContinue;
  const _SummaryPage({required this.onContinue});

  @override
  Widget build(BuildContext context) {
    final controller = Provider.of<OnboardingController>(context, listen: false);
    return _OnboardingPageWrapper(
      title: "Generating your plan...",
      onContinue: onContinue,
      continueText: "Go to Dashboard",
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.start, // Changed to start
          children: [
            const SizedBox(height: 20), // Add some space at the top
            // New Stack widget
            Stack(
              alignment: Alignment.center,
              children: [
                // The image
                Image.asset(
                  'assets/images/ai_robot.png', // As in your code
                  height: 250,
                ),
                // The circular progress indicator
                SizedBox(
                  width: 270, // Slightly larger than the image
                  height: 270,
                  child: CircularProgressIndicator(
                    valueColor:
                    const AlwaysStoppedAnimation<Color>(MyApp.primaryColor),
                    strokeWidth: 6, // Make it a bit thicker
                  ),
                ),
              ],
            ),
            const SizedBox(height: 30), // Increased space
            Text(
              "We're personalizing your smart diet plan...",
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 40),
            // Summary of inputs
            Text("Gender: ${controller.gender}"),
            Text("Age: ${controller.age}"),
            Text("Height: ${controller.height} cm"),
            Text("Weight: ${controller.weight.toStringAsFixed(1)} kg"),
            Text("Goal: ${controller.goal}"),
          ],
        ),
      ),
    );
  }
}
// --- Helper: Page Wrapper ---
class _OnboardingPageWrapper extends StatelessWidget {
  final String title;
  final Widget child;
  final VoidCallback onContinue;
  final String continueText;

  const _OnboardingPageWrapper({
    required this.title,
    required this.child,
    required this.onContinue,
    this.continueText = "Continue",
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            title,
            style: Theme.of(context)
                .textTheme
                .headlineMedium
                ?.copyWith(fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 32),
          Expanded(child: child),
          const SizedBox(height: 16),
          ElevatedButton(
              onPressed: onContinue,
            child: Text(continueText),
          ),
        ],
      ),
    );
  }
}

// --- Page 0: Credentials ---
class _CredentialsPage extends StatelessWidget {
  final GlobalKey<FormState> formKey;
  final TextEditingController nameController;
  final TextEditingController emailController;
  final TextEditingController passwordController;
  final VoidCallback onContinue;

  const _CredentialsPage({
    required this.formKey,
    required this.nameController,
    required this.emailController,
    required this.passwordController,
    required this.onContinue
  });

  @override
  Widget build(BuildContext context) {
    // Access the form key from the parent state if possible, or wrap here?
    // Parent passes validation callback, so we assume parent wraps or checking logic is there?
    // Actually, in parent I defined _formKey but didn't wrap the PageView.
    // The PageView pages are separate widgets so I should wrap the fields here in Form 
    // BUT the key is in parent. 
    // Simpler: Just pass the key or create a new form here? 
    // If I create form here, `_validateAndNext` in parent can't trigger it easily without a key passed down.
    // Let's assume for simplicity I can use a local key here but I need to block 'Next' if invalid.
    // Ah, the `onContinue` is passed. 
    // I will use a local form here and inside the button press check validation.
    // Wait, the button is in `_OnboardingPageWrapper`.
    // I should modify `_OnboardingPageWrapper` or just put the Form in the wrapper? No.
    // I will wrap this specific page content in a Form.
    // The `onContinue` is called by the wrapper button.
    // I need `_OnboardingPageWrapper` to support a "onValidate" or simply let this page
    // handle the button?
    // `OnboardingPageWrapper` has a standard button. 
    // Hack: I'll use the parent `_formKey` if I can access context? No, keys don't work that way.
    // I'll make the `onContinue` a `bool Function()`? No, it's VoidCallback.
    
    // Better Approach: Update `_OnboardingPageWrapper` to accept a `onAction` that returns bool?
    // Or just validate inputs manually in `_validateAndNext` in parent?
    // Parent has controllers. Parent can validate text content directly without Form widget if needed.
    
    return _OnboardingPageWrapper(
      title: "Let's get to know you",
      onContinue: onContinue,
      child: SingleChildScrollView(
         child: Form(
           key: formKey,
           child: Column(
             children: [
               TextFormField(
                 controller: nameController,
                 decoration: const InputDecoration(labelText: "Name (Optional)", border: OutlineInputBorder()),
               ),
               const SizedBox(height: 16),
               TextFormField(
                 controller: emailController,
                 decoration: const InputDecoration(labelText: "Email", border: OutlineInputBorder()),
                 keyboardType: TextInputType.emailAddress,
                 autovalidateMode: AutovalidateMode.onUserInteraction,
                 validator: (val) => (val==null||!val.contains('@')) ? "Enter valid email" : null,
               ),
               const SizedBox(height: 16),
               TextFormField(
                 controller: passwordController,
                 decoration: const InputDecoration(labelText: "Password (Min 6 chars)", border: OutlineInputBorder()),
                 obscureText: true,
                 validator: (val) => (val == null || val.length < 6) ? "Password must be at least 6 chars" : null,
               ),
             ],
           ),
         ),
      ),
    );
  }
}