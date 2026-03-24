import 'package:college_project/app/modules/home/tabs/logging_tab.dart';
import 'package:flutter/material.dart';

import '../tabs/account_tab.dart';
import '../tabs/diet_tab.dart';
import '../tabs/tracker_tab.dart';

class MainDashboard extends StatefulWidget {
  const MainDashboard({super.key});

  @override
  State<MainDashboard> createState() => _MainDashboardState();
}

class _MainDashboardState extends State<MainDashboard> {
  int _selectedIndex = 0; // This will be 0, 1, or 3.

  late final List<Widget> _widgetOptions;

  @override
  void initState() {
    super.initState();
    // _widgetOptions only needs 3 screens.
    // We will correctly pass the callback to TrackerTab.
    _widgetOptions = <Widget>[
      const DietTab(),
      TrackerTab(),
      LoggingTab() ,// Pass callback
      const AccountTab(),
    ];
  }

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _selectedIndex,
        children: _widgetOptions,
      ),
      bottomNavigationBar: BottomNavigationBar(
        type: BottomNavigationBarType.fixed,
        items: const <BottomNavigationBarItem>[
          BottomNavigationBarItem(
            icon: Icon(Icons.local_dining_outlined), // Placeholder for Diet icon
            label: 'Diet',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.track_changes), // Placeholder for Tracker icon
            label: 'Tracker',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.add_circle_outline), // Placeholder for Logging icon
            label: 'Logging',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.person_outline), // Placeholder for Account icon
            label: 'Account',
          ),
        ],
        currentIndex: _selectedIndex,
        onTap: _onItemTapped,
        backgroundColor: Colors.white,
        elevation: 10,
        // You can control colors directly here or in main.dart's theme
        // selectedItemColor: MyApp.primaryColor,
        // unselectedItemColor: Colors.grey,
      ),
    );
  }
}
