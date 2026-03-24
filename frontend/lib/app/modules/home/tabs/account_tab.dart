import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../../../main.dart';

import 'package:provider/provider.dart';
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
      if (provider.dailyTarget == null) {
        provider.fetchDailyTarget();
      }
    });
  }
  
  Future<void> _refreshData() async {
    final provider = context.read<DataProvider>();
    provider.dailyTarget = null;
    await provider.fetchDailyTarget();
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
          userProfile: provider.userProfile,
          dailyTarget: provider.dailyTarget,
          isProfileLoading: provider.isProfileLoading,
        ),
        builder: (context, view, child) {
          if (view.isProfileLoading && view.userProfile == null) {
            return const Center(child: CircularProgressIndicator());
          }

          final profile = view.userProfile ?? {};
          final email = profile['email'] ?? ApiService.userId ?? "Guest";
          final displayName =
              profile['name'] ?? (email.contains('@') ? email.split('@').first : email);
          final height = profile['height'] ?? '--';
          final weight = profile['weight'] ?? '--';
          final goal = profile['goal'] ?? 'Maintain Weight';
          final activity = profile['activity_level'] ?? 'Moderate';

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
                  _buildTargetOverview(context, view.dailyTarget),
                  const SizedBox(height: 24),
                  _buildSettingsSection(context, "Body Metrics & Goal", [
                    _buildSettingsTile("Height", "$height cm"),
                    _buildSettingsTile("Weight", "$weight kg"),
                    _buildSettingsTile("Activity Level", "$activity"),
                    _buildSettingsTile("Goal", "$goal"),
                  ]),
                  const SizedBox(height: 24),
                  _buildSettingsSection(context, "Preferences", [
                    _buildSettingsTile("Edit Profile", ">", icon: Icons.person_outline),
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

  Widget _buildTargetOverview(BuildContext context, Map<String, dynamic>? target) {
    final calories = target?['calories'] ?? "2000";
    final protein = target?['protein']?.toStringAsFixed(0) ?? "100";

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
                  _buildStat("Target Cals", "$calories"),
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
    required this.userProfile,
    required this.dailyTarget,
    required this.isProfileLoading,
  });

  final Map<String, dynamic>? userProfile;
  final Map<String, dynamic>? dailyTarget;
  final bool isProfileLoading;

  @override
  bool operator ==(Object other) {
    return other is _AccountTabViewData &&
        mapEquals(other.userProfile, userProfile) &&
        mapEquals(other.dailyTarget, dailyTarget) &&
        other.isProfileLoading == isProfileLoading;
  }

  @override
  int get hashCode => Object.hash(
        userProfile,
        dailyTarget,
        isProfileLoading,
      );
}
