import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../main.dart';
import '../../../data/providers/data_provider.dart';
import '../../../data/services/api_service.dart';

class DietTab extends StatefulWidget {
  const DietTab({super.key});

  @override
  State<DietTab> createState() => _DietTabState();
}

class _DietTabState extends State<DietTab> {
  bool _showGreeting = true;

  @override
  void initState() {
    super.initState();
    
    // Fade out greeting after 2 seconds
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() {
          _showGreeting = false;
        });
      }
    });

    // Fetch data when tab initializes
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = Provider.of<DataProvider>(context, listen: false);
      provider.fetchUserProfile();
      provider.fetchStreak();
      provider.fetchDailyTarget();
      provider.fetchMealPlan();
      provider.fetchTrackerSummary(); // Fetch summary to check logged status
    });
  }

  Future<void> _refreshData() async {
    final provider = Provider.of<DataProvider>(context, listen: false);
    // Force refresh (set loading true if needed, or just recall APIs)
    // We should probably clear data to force spinner or just await new data
    // DataProvider logic handles "if != null return", so we might need a force refresh flag or method
    // For now, I'll manually set them null or add a refresh method in provider. 
    // Actually, looking at DataProvider, it checks if data exists. I should add a clear method or just access fetch directly if I modify provider.
    // Let's just call fetch. But wait, fetch returns if data != null.
    // I will assume for "Refresh" we want to re-fetch.
    // I'll modify provider to allow force refresh later, or just hack it here by clearing first?
    // Better: let's modifying DataProvider to allow force refresh is cleaner, but I can't touch it right now in this single file edit.
    // I'll just set the variables to null locally? No, they are in provider.
    // I will implement _refreshData logic assuming I can just call methods, but realizing they might cache.
    // User wants "Refresh", so I should probably update the DataProvider too.
    // For this step, I'll implement the UI changes.
    // Re-fetching logic:
    provider.dailyTarget = null; 
    provider.mealPlan = null;
    await Future.wait([
      provider.fetchDailyTarget(),
      provider.fetchMealPlan(),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<DataProvider>(
      builder: (context, provider, child) {
        // Allow pull to refresh even if loading (though usually we wait)
        return Scaffold(
          appBar: AppBar(
            title: const Text("Your Plan"),
          ),
          body: RefreshIndicator(
            onRefresh: _refreshData,
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(), // Ensure scroll for refresh
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Today's Date
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16.0),
                      child: Text(
                        _getFormattedDate(),
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: Colors.grey[600],
                          fontWeight: FontWeight.w500
                        ),
                      ),
                    ),
                    // Welcome Message
                    _buildWelcomeMessage(provider.userProfile, provider.dailyTarget),
                    
                    // Motivation Streak
                    _buildStreakCard(provider.streakData),

                    // Animated Flash Greeting
                    AnimatedOpacity(
                      opacity: _showGreeting ? 1.0 : 0.0,
                      duration: const Duration(milliseconds: 500),
                      child: _showGreeting ? const Center(
                        child: Padding(
                          padding: EdgeInsets.all(20), 
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              CircularProgressIndicator(),
                              SizedBox(height: 16),
                              Text("Generating your personalized plan...", style: TextStyle(color: Colors.grey, fontSize: 16, fontWeight: FontWeight.w500)),
                            ],
                          )
                        )
                      ) : const SizedBox.shrink(),
                    ),
                    
                    if (provider.isLoading && provider.mealPlan == null && !_showGreeting)
                       const Center(
                         child: Padding(
                           padding: EdgeInsets.all(20), 
                           child: CircularProgressIndicator()
                         )
                       ),
                    
                    // API 2: Calculate Daily Target
                    if (provider.dailyTarget != null)
                      _buildProgressCard(provider.dailyTarget!, provider.trackerSummary),
                    
                    const SizedBox(height: 24),
                    
                    // API 3: Generated Meal Plan
                    if (provider.mealPlan != null) ...[
                      if (provider.mealPlan!['breakfast'] != null)
                        _buildMealSection(context, "Breakfast", provider.mealPlan!['breakfast']),
                      
                      if (provider.mealPlan!['lunch'] != null)
                        _buildMealSection(context, "Lunch", provider.mealPlan!['lunch']),

                      if (provider.mealPlan!['snack'] != null)
                        _buildMealSection(context, "Snack", provider.mealPlan!['snack']),
                      
                      if (provider.mealPlan!['dinner'] != null)
                        _buildMealSection(context, "Dinner", provider.mealPlan!['dinner']),
                    ] else if (!provider.isLoading)
                      const Center(child: Text("No meal plan generated yet. Pull to refresh.")),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  String _getFormattedDate() {
    final now = DateTime.now();
    final months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    final weekDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    return "${weekDays[now.weekday - 1]}, ${now.day} ${months[now.month - 1]}";
  }

  Widget _buildWelcomeMessage(Map<String, dynamic>? userProfile, Map<String, dynamic>? dailyTarget) {
    // Determine name, handle missing API gracefully
    final name = (userProfile != null && userProfile['name'] != null) ? userProfile['name'] : "User";
    final targetCal = dailyTarget?['calories'] ?? 2000;
    
    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
           Text("Good Morning $name 👋", style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
           const SizedBox(height: 4),
           Text("Your calorie target today is $targetCal kcal.", style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey[700])),
        ]
      )
    );
  }

  Widget _buildStreakCard(Map<String, dynamic>? streakData) {
    if (streakData == null) {
      // Missing API placeholder
      return _buildMotivationCard(1); 
    }
    final streak = streakData['streak'] ?? 0;
    if (streak == 0) return const SizedBox.shrink();
    return _buildMotivationCard(streak);
  }

  Widget _buildMotivationCard(int streak) {
    return Card(
      color: Colors.orange[50],
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 16.0),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: Colors.orange[200]!)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Row(
          children: [
            const Text("🔥", style: TextStyle(fontSize: 28)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text("$streak Day Healthy Streak", style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.deepOrange)),
                  Text("You have logged meals for $streak days in a row. Keep going!", style: TextStyle(fontSize: 12, color: Colors.orange[900])),
                ],
              ),
            )
          ],
        )
      )
    );
  }

  Widget _buildProgressCard(Map<String, dynamic> target, Map<String, dynamic>? tracker) {
    double targetCal = (target['calories'] ?? 1).toDouble();
    double currentCal = tracker != null ? ((tracker['consumed']?['calories']) ?? 0).toDouble() : 0.0;
    
    double targetProt = (target['protein'] ?? 1).toDouble();
    double currentProt = tracker != null ? ((tracker['consumed']?['protein']) ?? 0).toDouble() : 0.0;
    
    double targetFat = (target['fat'] ?? 1).toDouble();
    double currentFat = tracker != null ? ((tracker['consumed']?['fat']) ?? 0).toDouble() : 0.0;
    
    double targetCarb = (target['carbs'] ?? 1).toDouble();
    double currentCarb = tracker != null ? ((tracker['consumed']?['carbs']) ?? 0).toDouble() : 0.0;

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Today's Progress", style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            _buildProgressBar(context, "Calories", currentCal, targetCal, "kcal", Colors.orange),
            const SizedBox(height: 12),
            _buildProgressBar(context, "Protein", currentProt, targetProt, "g", Colors.red),
            const SizedBox(height: 12),
            _buildProgressBar(context, "Fat", currentFat, targetFat, "g", Colors.yellow[700]!),
            const SizedBox(height: 12),
            _buildProgressBar(context, "Carbs", currentCarb, targetCarb, "g", Colors.blue),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressBar(BuildContext context, String title, double current, double target, String unit, Color color) {
    double progress = target > 0 ? (current / target) : 0;
    if (progress > 1.0) progress = 1.0;
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(title, style: Theme.of(context).textTheme.bodyMedium),
            Text("${current.toInt()} / ${target.toInt()} $unit", style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 4),
        LinearProgressIndicator(
          value: progress,
          backgroundColor: Colors.grey[200],
          color: color,
          minHeight: 8,
          borderRadius: BorderRadius.circular(4),
        ),
      ],
    );
  }

  // Changed to build a SECTION (Card) for the whole meal time
  Widget _buildMealSection(BuildContext context, String mealType, dynamic mealData) {
    // Backend v2 returns an array directly for each meal:
    //   "breakfast": [{mealName, quantity, calories, ...}, ...]
    // Legacy shape also supported:
    //   "breakfast": { items: [...], mealCalories: ... }
    List<dynamic> items = [];
    num? totalCals;

    if (mealData is List) {
      items = mealData;
      totalCals = items.fold<num>(0, (sum, e) => sum + ((e is Map) ? (e['calories'] ?? 0) as num : 0));
    } else if (mealData is Map<String, dynamic>) {
      items = (mealData['items'] as List<dynamic>?) ?? [];
      totalCals = mealData['mealCalories'] as num?;
    }

    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 20),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(16.0),
            color: Colors.grey[50],
             child: Row(
               mainAxisAlignment: MainAxisAlignment.spaceBetween,
               children: [
                 Text(
                    mealType.toUpperCase(),
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Colors.grey[700],
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                      letterSpacing: 1.2
                    ),
                  ),
                  if (totalCals != null)
                    Text(
                      "${totalCals.toString()} kcal",
                       style: Theme.of(context).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.bold),
                    )
               ],
             ),
          ),
          
          // Items List
          if (items.isEmpty)
             const Padding(padding: EdgeInsets.all(16), child: Text("No items")),
             
          for (var i = 0; i < items.length; i++) ...[
             if (i > 0) const Divider(height: 1),
             _buildMealItem(context, mealType, items[i] as Map<String, dynamic>),
          ]
        ],
      ),
    );
  }

  Widget _buildMealItem(BuildContext context, String mealType, Map<String, dynamic> item) {
    final provider = Provider.of<DataProvider>(context); // Listen to changes
    final logs = provider.trackerSummary != null ? (provider.trackerSummary!['logs'] as List?) : [];
    
    // Check if this meal name exists in logs
    int loggedQty = 0;
    String? logId;
    if (logs != null) {
      for (var log in logs) {
        if (log['mealName'] == item['mealName'] && log['mealType'] == mealType) {
           final qRaw = log['quantity'] ?? 1;
           final q = (qRaw is num) ? qRaw.toInt() : int.tryParse(qRaw.toString()) ?? 1;
           loggedQty = q;
           logId = (log['logId'] ?? log['id'] ?? log['_id'])?.toString();
           break; // treat the log entry as the source of truth for qty controls
        }
      }
    }
    bool isLogged = logId != null;

    return Container(
      color: isLogged ? Colors.lightGreen.withValues(alpha: 0.1) : null,
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
           // AI Badge
           Container(
             margin: const EdgeInsets.only(bottom: 8),
             padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
             decoration: BoxDecoration(color: Colors.blue[50], borderRadius: BorderRadius.circular(4)),
             child: Text("⭐ NutriLens AI Recommendation", style: TextStyle(color: Colors.blue[800], fontSize: 10, fontWeight: FontWeight.bold)),
           ),
           Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Image placeholder
                 Container(
                   width: 50, height: 50,
                   decoration: BoxDecoration(color: Colors.green[50], borderRadius: BorderRadius.circular(8)),
                   child: const Icon(Icons.restaurant_menu, color: MyApp.primaryColor),
                 ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item['mealName'] ?? "Unknown",
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        "${item['calories']} kcal • ${item['protein']}g P • ${item['fat']}g F • ${item['carbs']}g C",
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (item['smart_explanation'] != null)
              Padding(
                padding: const EdgeInsets.only(top: 8.0, left: 62),
                child: Text("💡 ${item['smart_explanation']}", style: TextStyle(fontStyle: FontStyle.italic, color: Colors.grey[700], fontSize: 12)),
              ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                 // Replace Button
                 TextButton.icon(
                   icon: const Icon(Icons.sync, size: 16, color: Colors.grey),
                   label: const Text("Swap", style: TextStyle(color: Colors.grey)),
                   onPressed: () => _showReplaceDialog(context, item['mealName'], mealType),
                   style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
                 ),
                 const SizedBox(width: 8),
                 if (!isLogged)
                   SizedBox(
                     height: 32,
                     child: ElevatedButton(
                       onPressed: () => _logMeal(context, mealType, item),
                       style: ElevatedButton.styleFrom(
                         backgroundColor: MyApp.primaryColor,
                         foregroundColor: Colors.white,
                         elevation: 2,
                         padding: const EdgeInsets.symmetric(horizontal: 16),
                         shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                       ),
                       child: const Text("Log", style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                     ),
                   )
                 else ...[
                   // Portion controls (increase/decrease)
                   Container(
                     height: 32,
                     padding: const EdgeInsets.symmetric(horizontal: 6),
                     decoration: BoxDecoration(
                       color: Colors.green[50],
                       borderRadius: BorderRadius.circular(20),
                       border: Border.all(color: Colors.green[100]!),
                     ),
                     child: Row(
                       mainAxisSize: MainAxisSize.min,
                       children: [
                         IconButton(
                           visualDensity: VisualDensity.compact,
                           padding: EdgeInsets.zero,
                           iconSize: 18,
                           onPressed: () {
                            if (loggedQty > 1) {
                              _updateLogQuantity(context, logId, loggedQty - 1);
                             } else if (logId != null) {
                               _deleteLog(context, logId);
                             }
                           },
                           icon: const Icon(Icons.remove, color: Colors.green),
                         ),
                         Padding(
                           padding: const EdgeInsets.symmetric(horizontal: 6),
                           child: Text(
                            "×$loggedQty",
                             style: TextStyle(color: Colors.green[800], fontWeight: FontWeight.bold, fontSize: 12),
                           ),
                         ),
                         IconButton(
                           visualDensity: VisualDensity.compact,
                           padding: EdgeInsets.zero,
                           iconSize: 18,
                          onPressed: () => _updateLogQuantity(context, logId, loggedQty + 1),
                           icon: const Icon(Icons.add, color: Colors.green),
                         ),
                       ],
                     ),
                   ),
                 ],
              ],
            )
        ],
      ),
    );
  }

  void _updateLogQuantity(BuildContext context, String? logId, int newQuantity) async {
    if (logId == null) return;
    final provider = Provider.of<DataProvider>(context, listen: false);
    // Assuming DataProvider has updateLog method or we do it via raw API.
    // I will add API call for updateLog inside api_service if missing or in provider.
    // The prompt says PUT /update-log. Let's call it via api_service.
    try {
      final response = await ApiService.updateLog(logId, newQuantity);
      if (response && context.mounted) {
        provider.fetchTrackerSummary(); // refresh UI
      }
    } catch (e) {
      // Ignored error
    }
  }

  void _deleteLog(BuildContext context, String logId) async {
    final provider = Provider.of<DataProvider>(context, listen: false);
    try {
      final response = await ApiService.deleteLog(logId);
      if (response && context.mounted) {
        provider.fetchTrackerSummary();
      }
    } catch (e) {
      // Ignored error
    }
  }

  void _logMeal(BuildContext context, String mealType, Map<String, dynamic> meal) async {
    final provider = Provider.of<DataProvider>(context, listen: false);
    final data = {
      "userId": ApiService.userId,
      "date": DateTime.now().toIso8601String().split('T')[0],
      "mealName": meal['mealName'],
      "mealType": mealType,
      "quantity": (meal['quantity'] ?? 1),
      // Provide macros so local backend can log even if Firestore is rate-limited.
      "calories": meal['calories'],
      "protein": meal['protein'],
      "carbs": meal['carbs'],
      "fat": meal['fat'],
      "source": meal['source'] ?? "ai"
    };

    final success = await provider.logMeal(data);
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(success ? "Meal Logged!" : "Failed to log meal")),
      );
    }
  }

  void _showReplaceDialog(BuildContext context, String currentMeal, String mealType) async {
     final provider = Provider.of<DataProvider>(context, listen: false);
     
     // Show Loading
     showDialog(context: context, barrierDismissible: false, builder: (_) => const Center(child: CircularProgressIndicator()));
     
     final result = await provider.replaceMeal(currentMeal);
     if (!context.mounted) return;
     Navigator.pop(context); // Close loading (Progress)

     if (result != null && result['aiSuggestions'] != null) {
       final suggestions = List<Map<String, dynamic>>.from(result['aiSuggestions']);
       
       showModalBottomSheet(
         context: context, 
         builder: (ctx) => ListView.builder(
           shrinkWrap: true,
           itemCount: suggestions.length,
           itemBuilder: (_, index) {
             final item = suggestions[index];
             return ListTile(
               title: Text(item['mealName']),
               subtitle: Text("${item['calories']} kcal"),
               trailing: const Icon(Icons.add_circle, color: Colors.green),
               onTap: () {
                 Navigator.pop(ctx); // Close Sheet
                 // Update the local Plan UI (Do not log yet)
                 final newMeal = Map<String, dynamic>.from(item);
                 newMeal['source'] = "knn_swap"; // Mark source if needed for later log

                 // Find and Swap in provider.mealPlan
                 // Since provider.mealPlan is the source of truth for the UI list
                 if (provider.mealPlan != null) {
                    final key = mealType.toLowerCase();
                    final section = provider.mealPlan![key];

                    // New shape: section is a List
                    if (section is List) {
                      final idx = section.indexWhere((e) => e is Map && e['mealName'] == currentMeal);
                      if (idx != -1) {
                        section[idx] = newMeal;
                        setState(() {});
                      }
                    }

                    // Legacy shape: section is a Map with items
                    if (section is Map && section['items'] is List) {
                      final list = section['items'] as List;
                      final idx = list.indexWhere((e) => e is Map && e['mealName'] == currentMeal);
                      if (idx != -1) {
                        list[idx] = newMeal;
                        setState(() {});
                      }
                    }
                 }
               },
             );
           }
         )
       );
     } else {
       if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("No suggestions found")));
     }
  }
}

