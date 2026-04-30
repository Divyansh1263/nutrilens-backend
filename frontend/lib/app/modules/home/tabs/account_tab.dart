import 'package:flutter/material.dart';

import '../../../../main.dart';

import 'package:provider/provider.dart';
import '../../../data/models/models.dart';
import '../../../data/providers/data_provider.dart';
import '../../../data/services/api_service.dart';

class AccountTab extends StatefulWidget {
  const AccountTab({super.key});

  @override
  State<AccountTab> createState() => _AccountTabState();
}

class _AccountTabState extends State<AccountTab> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<DataProvider>();
      provider.fetchUserProfile();
      if (provider.dailyTargetModel == null) {
        provider.fetchDailyTarget();
      }
    });
  }
  
  Future<void> _refreshData() async {
    final provider = context.read<DataProvider>();
    // Use the provider's own method — never mutate provider fields directly
    // from the UI layer. refreshDietData() resets + refetches dailyTarget,
    // mealPlan, and tracker via DataProvider's controlled state machine.
    await provider.refreshDietData();
    await provider.fetchUserProfile(forceRefresh: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Settings"),
      ),
      body: Selector<DataProvider, _AccountTabViewData>(
        selector: (_, provider) => _AccountTabViewData(
          isProfileLoading: provider.isProfileLoading,
          // ── Step 5: Model-only fields ──
          userProfileModel: provider.userProfileModel,
          dailyTargetModel: provider.dailyTargetModel,
        ),
        builder: (context, view, child) {
          if (view.isProfileLoading && view.userProfileModel == null) {
            return const Center(child: CircularProgressIndicator());
          }

          // Step 5 — model-only reads with safe fallbacks
          final email = view.userProfileModel?.email ??
              ApiService.userId ?? "Guest";
          final displayName = view.userProfileModel?.displayName ??
              (email.contains('@') ? email.split('@').first : email);
          final height = view.userProfileModel?.height?.toString() ?? '--';
          final weight = view.userProfileModel?.weight?.toString() ?? '--';
          final goal = view.userProfileModel?.goal ?? 'Maintain Weight';
          final activity = view.userProfileModel?.activityLevel ?? 'Moderate';

          assert(() {
            if (view.userProfileModel != null) {
              debugPrint('[ui] AccountTab using UserProfileModel — name=$displayName');
            }
            return true;
          }());

          return RefreshIndicator(
            onRefresh: _refreshData,
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _buildUserInfoCard(displayName, email),
                  const SizedBox(height: 24),
                  _buildTargetOverview(context, view.dailyTargetModel),
                  const SizedBox(height: 24),
                  _buildSettingsSection(context, "Body Metrics & Goal", [
                    _buildSettingsTile("Height", "$height cm"),
                    _buildSettingsTile("Weight", "$weight kg"),
                    _buildSettingsTile("Activity Level", activity),
                    _buildSettingsTile("Goal", goal),
                  ]),
                  const SizedBox(height: 24),
                  _buildSettingsSection(context, "Preferences", [
                    _buildSettingsTile("Edit Profile", ">", icon: Icons.person_outline, onTap: () {
                      _showEditProfileDialog(context, view.userProfileModel);
                    }),
                    _buildSettingsTile("Reminders", ">", icon: Icons.notifications_none),
                    _buildSettingsTile("Support / About Us", ">", icon: Icons.info_outline),
                    _buildSettingsTile("Logout", ">", color: Colors.red, icon: Icons.logout, onTap: () async {
                      await ApiService.logout();
                      if (!context.mounted) return;
                      Navigator.of(context).pushReplacementNamed('/auth');
                    }),
                  ]),
                ],
              ),
            ),
          );
        },
      ),
    );
  }



  Widget _buildUserInfoCard(String name, String email) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Row(
          children: [
             CircleAvatar(
              radius: 30,
              backgroundColor: MyApp.primaryColor,
              child: Text(name.isNotEmpty ? name[0].toUpperCase() : "U",
                  style: const TextStyle(fontSize: 24, color: Colors.white)),
            ),
            const SizedBox(width: 16),
             Expanded(
                child: Column(
                 crossAxisAlignment: CrossAxisAlignment.start,
                 children: [
                   Text(name,
                       style:
                       const TextStyle(fontSize: 18, fontWeight: FontWeight.bold), overflow: TextOverflow.ellipsis),
                    Text(email,
                       style:
                       const TextStyle(fontSize: 14, color: Colors.grey), overflow: TextOverflow.ellipsis),
                   const SizedBox(height: 4),
                   Container(
                     padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                     decoration: BoxDecoration(
                       color: Colors.green[50],
                       borderRadius: BorderRadius.circular(4)
                     ),
                     child: const Text("Free Plan", style: TextStyle(fontSize: 12, color: Colors.green, fontWeight: FontWeight.bold))
                   ),
                 ],
                            ),
             ),
            const Spacer(),
            IconButton(
              onPressed: () {},
              icon: const Icon(Icons.settings, color: Colors.grey),
            )
          ],
        ),
      ),
    );
  }

  void _showEditProfileDialog(BuildContext context, UserProfile? profile) {
    if (profile == null) return;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return _EditProfileSheet(profile: profile);
      },
    );
  }

  Widget _buildTargetOverview(BuildContext context, DailyTarget? targetModel) {
    // Step 5 — model fields only
    final calories = targetModel?.calories.toStringAsFixed(0) ?? "2000";
    final protein = targetModel?.protein.toStringAsFixed(0) ?? "100";

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              "Target Overview",
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            TextButton(
              onPressed: () {},
              child: const Text("Info"),
            )
          ],
        ),
        const SizedBox(height: 16),
        // Placeholder for the graph
        Container(
          height: 100,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.grey[100],
            borderRadius: BorderRadius.circular(12),
          ),
           child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                  _buildStat("Target Cals", calories),
                  const VerticalDivider(),
                  _buildStat("Target Protein", "${protein}g"),
              ]
           ),
        ),
      ],
    );
  }
  
  Widget _buildStat(String label, String value) {
     return Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
           Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.green)),
           Text(label, style: const TextStyle(color: Colors.grey)),
        ],
     );
  }

  Widget _buildSettingsSection(
      BuildContext context, String title, List<Widget> tiles) {
      
    List<Widget> spacedTiles = [];
    for (int i = 0; i < tiles.length; i++) {
       spacedTiles.add(tiles[i]);
       if (i < tiles.length - 1) {
          spacedTiles.add(const Divider(height: 1, indent: 16, endIndent: 16));
       }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
            color: Colors.grey[600],
            fontWeight: FontWeight.bold,
          ),
        ),
        Card(
          margin: const EdgeInsets.symmetric(vertical: 8),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: Colors.grey[200]!),
          ),
          child: Column(
            children: spacedTiles,
          ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }

  Widget _buildSettingsTile(String title, String trailing, {Color? color, VoidCallback? onTap, IconData? icon}) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: icon != null ? Icon(icon, color: color ?? Colors.black87) : null,
      title: Text(title,
          style: TextStyle(
              fontWeight: FontWeight.w500, color: color ?? Colors.black)),
      trailing: Text(trailing,
          style: TextStyle(color: color ?? Colors.grey[600], fontSize: 14)),
      onTap: onTap ?? () {},
    );
  }
}

class _AccountTabViewData {
  const _AccountTabViewData({
    required this.isProfileLoading,
    // ── Step 5: Model-only fields ──
    this.userProfileModel,
    this.dailyTargetModel,
  });

  final bool isProfileLoading;
  final UserProfile? userProfileModel;
  final DailyTarget? dailyTargetModel;

  @override
  bool operator ==(Object other) {
    if (other is! _AccountTabViewData) return false;
    return other.isProfileLoading == isProfileLoading &&
        other.userProfileModel == userProfileModel &&
        other.dailyTargetModel == dailyTargetModel;
  }

  @override
  int get hashCode => Object.hash(
        isProfileLoading,
        userProfileModel,
        dailyTargetModel,
      );
}

class _EditProfileSheet extends StatefulWidget {
  final UserProfile profile;
  const _EditProfileSheet({required this.profile});

  @override
  State<_EditProfileSheet> createState() => _EditProfileSheetState();
}

class _EditProfileSheetState extends State<_EditProfileSheet> {
  late TextEditingController heightController;
  late TextEditingController weightController;
  String? selectedActivity;
  String? selectedGoal;
  bool isLoading = false;

  final activityLevels = ["Sedentary", "Lightly Active", "Moderately Active", "Very Active", "Super Active"];
  final goals = ["Lose Weight", "Maintain Weight", "Gain Weight"];

  @override
  void initState() {
    super.initState();
    heightController = TextEditingController(text: widget.profile.height?.toString() ?? "");
    weightController = TextEditingController(text: widget.profile.weight?.toString() ?? "");
    
    selectedActivity = widget.profile.activityLevel;
    if (selectedActivity != null && !activityLevels.contains(selectedActivity)) {
       activityLevels.add(selectedActivity!);
    }
    selectedGoal = widget.profile.goal;
    if (selectedGoal != null && !goals.contains(selectedGoal)) {
       goals.add(selectedGoal!);
    }
  }

  @override
  void dispose() {
    heightController.dispose();
    weightController.dispose();
    super.dispose();
  }

  void _save() async {
    final height = double.tryParse(heightController.text);
    final weight = double.tryParse(weightController.text);

    if (height == null || height <= 0 || weight == null || weight <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please enter valid positive numbers for height and weight.")),
      );
      return;
    }
    
    if (selectedActivity == null || selectedGoal == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please select activity level and goal.")),
      );
      return;
    }

    setState(() => isLoading = true);
    final provider = context.read<DataProvider>();
    final success = await provider.updateUserProfile({
      "height": height,
      "weight": weight,
      "activityLevel": selectedActivity,
      "goal": selectedGoal,
    });

    setState(() => isLoading = false);

    if (success) {
      if (context.mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Profile updated")),
        );
      }
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Failed to update profile")),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 24,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text("Edit Profile", style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          TextField(
            controller: heightController,
            decoration: const InputDecoration(labelText: "Height (cm)", border: OutlineInputBorder()),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: weightController,
            decoration: const InputDecoration(labelText: "Weight (kg)", border: OutlineInputBorder()),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: selectedActivity,
            decoration: const InputDecoration(labelText: "Activity Level", border: OutlineInputBorder()),
            items: activityLevels.map((act) => DropdownMenuItem(value: act, child: Text(act))).toList(),
            onChanged: (val) => setState(() => selectedActivity = val),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: selectedGoal,
            decoration: const InputDecoration(labelText: "Goal", border: OutlineInputBorder()),
            items: goals.map((g) => DropdownMenuItem(value: g, child: Text(g))).toList(),
            onChanged: (val) => setState(() => selectedGoal = val),
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: isLoading ? null : _save,
            child: isLoading 
              ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)) 
              : const Text("Save"),
          ),
        ],
      ),
    );
  }
}

