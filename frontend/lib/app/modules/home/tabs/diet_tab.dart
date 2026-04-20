import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
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
      final provider = context.read<DataProvider>();
      provider.ensureHomeTabData();
    });
  }

  Future<void> _refreshData() async {
    final provider = context.read<DataProvider>();
    await provider.refreshDietData();
  }

  @override
  Widget build(BuildContext context) {
    // Compute once per build — stable across the whole widget tree.
    final todayKey = DateFormat('yyyy-MM-dd').format(DateTime.now());

    return Scaffold(
      appBar: AppBar(
        title: const Text("Your Plan"),
      ),
      body: RefreshIndicator(
        onRefresh: _refreshData,
        child: Selector<DataProvider, _DietTabViewData>(
          selector: (_, provider) => _DietTabViewData(
            userProfile: provider.userProfile,
            dailyTarget: provider.dailyTarget,
            streakData: provider.streakData,
            trackerSummary: provider.getTrackerSummaryForDate(todayKey),
            mealPlan: provider.mealPlan,
            isMealPlanLoading: provider.isMealPlanLoading,
          ),
          builder: (context, view, child) {
            return SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16.0),
                      child: Text(
                        _getFormattedDate(),
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              color: Colors.grey[600],
                              fontWeight: FontWeight.w500,
                            ),
                      ),
                    ),
                    _buildWelcomeMessage(view.userProfile, view.dailyTarget),
                    _buildStreakCard(view.streakData),
                    AnimatedOpacity(
                      opacity: _showGreeting ? 1.0 : 0.0,
                      duration: const Duration(milliseconds: 500),
                      child: _showGreeting
                          ? const Center(
                              child: Padding(
                                padding: EdgeInsets.all(20),
                                child: Column(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    CircularProgressIndicator(),
                                    SizedBox(height: 16),
                                    Text(
                                      "Generating your personalized plan...",
                                      style: TextStyle(
                                        color: Colors.grey,
                                        fontSize: 16,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            )
                          : const SizedBox.shrink(),
                    ),
                    if (view.isMealPlanLoading &&
                        view.mealPlan == null &&
                        !_showGreeting)
                      _buildMealPlanSkeleton(),
                    if (view.dailyTarget != null)
                      _buildProgressCard(view.dailyTarget!, view.trackerSummary),
                    const SizedBox(height: 24),
                    if (view.mealPlan != null) ...[
                      // TASK 6: debug print slot sizes before rendering
                      () {
                        final mp = view.mealPlan!;
                        debugPrint('[diet-tab] breakfast: ${(mp["breakfast"] as List?)?.length ?? 0} items');
                        debugPrint('[diet-tab] lunch:     ${(mp["lunch"]     as List?)?.length ?? 0} items');
                        debugPrint('[diet-tab] snack:     ${(mp["snack"]     as List?)?.length ?? 0} items');
                        debugPrint('[diet-tab] dinner:    ${(mp["dinner"]    as List?)?.length ?? 0} items');
                        return const SizedBox.shrink();
                      }(),
                      // TASK 5: guard null AND empty list before rendering
                      if (view.mealPlan!['breakfast'] != null &&
                          !((view.mealPlan!['breakfast'] is List) &&
                            (view.mealPlan!['breakfast'] as List).isEmpty))
                        _buildMealSection(
                          context,
                          "Breakfast",
                          view.mealPlan!['breakfast'],
                          view.trackerSummary,
                        ),
                      if (view.mealPlan!['lunch'] != null &&
                          !((view.mealPlan!['lunch'] is List) &&
                            (view.mealPlan!['lunch'] as List).isEmpty))
                        _buildMealSection(
                          context,
                          "Lunch",
                          view.mealPlan!['lunch'],
                          view.trackerSummary,
                        ),
                      if (view.mealPlan!['snack'] != null &&
                          !((view.mealPlan!['snack'] is List) &&
                            (view.mealPlan!['snack'] as List).isEmpty))
                        _buildMealSection(
                          context,
                          "Snack",
                          view.mealPlan!['snack'],
                          view.trackerSummary,
                        ),
                      if (view.mealPlan!['dinner'] != null &&
                          !((view.mealPlan!['dinner'] is List) &&
                            (view.mealPlan!['dinner'] as List).isEmpty))
                        _buildMealSection(
                          context,
                          "Dinner",
                          view.mealPlan!['dinner'],
                          view.trackerSummary,
                        ),
                    ] else if (!view.isMealPlanLoading)
                      _buildFallbackMealPlan(context),
                  ],
                ),
              ),
            );
          },
        ),
      ),
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

  // ---------------------------------------------------------------------------
  // Skeleton loading: shown while isMealPlanLoading == true && mealPlan == null
  // Uses a simple animated shimmer effect with no external packages.
  // ---------------------------------------------------------------------------
  Widget _buildMealPlanSkeleton() {
    return _SkeletonLoader(
      child: Column(
        children: List.generate(4, (i) {
          // Mimic the real meal-section card structure
          return Card(
            elevation: 0,
            margin: const EdgeInsets.only(bottom: 20),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // meal header row
                Container(
                  height: 42,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(12),
                    ),
                  ),
                ),
                const SizedBox(height: 1),
                // two item rows
                ...List.generate(2, (_) => Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 14),
                  child: Row(
                    children: [
                      Container(
                        width: 50,
                        height: 50,
                        decoration: BoxDecoration(
                          color: Colors.grey[300],
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              height: 14,
                              width: double.infinity,
                              decoration: BoxDecoration(
                                color: Colors.grey[300],
                                borderRadius: BorderRadius.circular(6),
                              ),
                            ),
                            const SizedBox(height: 8),
                            Container(
                              height: 11,
                              width: 180,
                              decoration: BoxDecoration(
                                color: Colors.grey[300],
                                borderRadius: BorderRadius.circular(6),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                )),
              ],
            ),
          );
        }),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Fallback: shown when loading is done but mealPlan is still null
  // ---------------------------------------------------------------------------
  Widget _buildFallbackMealPlan(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.restaurant_menu_outlined,
                size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            Text(
              "Couldn't load your meal plan",
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.grey[700],
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              "This can happen when the server is busy.\nPull down to retry.",
              textAlign: TextAlign.center,
              style:
                  Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.grey[500],
                      ),
            ),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: () =>
                  context.read<DataProvider>().fetchMealPlan(forceRefresh: true),
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text("Retry"),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                    horizontal: 28, vertical: 12),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // Changed to build a SECTION (Card) for the whole meal time

  Widget _buildMealSection(
    BuildContext context,
    String mealType,
    dynamic mealData,
    Map<String, dynamic>? trackerSummary,
  ) {
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
             _buildMealItem(
               context,
               mealType,
               items[i] as Map<String, dynamic>,
               trackerSummary,
             ),
          ]
        ],
      ),
    );
  }

  Widget _buildMealItem(
    BuildContext context,
    String mealType,
    Map<String, dynamic> item,
    Map<String, dynamic>? trackerSummary,
  ) {
    final logs = trackerSummary != null ? (trackerSummary['logs'] as List?) : [];
    
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
                        // TASK 3: null-safe macro display
                        "${item['calories'] ?? 0} kcal • ${item['protein'] ?? 0}g P • ${item['fat'] ?? 0}g F • ${item['carbs'] ?? 0}g C",
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
        provider.refreshTrackerDataForDate(DateTime.now().toIso8601String().split('T')[0]); // refresh UI
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
        provider.refreshTrackerDataForDate(DateTime.now().toIso8601String().split('T')[0]);
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
                  final newMeal = Map<String, dynamic>.from(item);
                  newMeal['source'] = "knn_swap";

                  // Immutable update - Selector detects new map reference.
                  if (provider.mealPlan != null) {
                    final key = mealType.toLowerCase();
                    final oldPlan = provider.mealPlan!;
                    final newPlan = Map<String, dynamic>.from(oldPlan);

                    // New shape: section is a List
                    if (oldPlan[key] is List) {
                      final list = List<dynamic>.from(oldPlan[key] as List);
                      final idx = list.indexWhere((e) => e is Map && e['mealName'] == currentMeal);
                      if (idx != -1) {
                        list[idx] = newMeal;
                        newPlan[key] = list;
                        provider.setMealPlan(newPlan);
                      }
                    } else if (oldPlan[key] is Map && (oldPlan[key] as Map)['items'] is List) {
                      final inner = Map<String, dynamic>.from(oldPlan[key] as Map<String, dynamic>);
                      final list = List<dynamic>.from(inner['items'] as List);
                      final idx = list.indexWhere((e) => e is Map && e['mealName'] == currentMeal);
                      if (idx != -1) {
                        list[idx] = newMeal;
                        inner['items'] = list;
                        newPlan[key] = inner;
                        provider.setMealPlan(newPlan);
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

class _DietTabViewData {
  const _DietTabViewData({
    required this.userProfile,
    required this.dailyTarget,
    required this.streakData,
    required this.trackerSummary,
    required this.mealPlan,
    required this.isMealPlanLoading,
  });

  final Map<String, dynamic>? userProfile;
  final Map<String, dynamic>? dailyTarget;
  final Map<String, dynamic>? streakData;
  final Map<String, dynamic>? trackerSummary;
  final Map<String, dynamic>? mealPlan;
  final bool isMealPlanLoading;

  @override
  bool operator ==(Object other) {
    return other is _DietTabViewData &&
        mapEquals(other.userProfile, userProfile) &&
        mapEquals(other.dailyTarget, dailyTarget) &&
        mapEquals(other.streakData, streakData) &&
        mapEquals(other.trackerSummary, trackerSummary) &&
        mapEquals(other.mealPlan, mealPlan) &&
        other.isMealPlanLoading == isMealPlanLoading;
  }

  @override
  int get hashCode => Object.hash(
        userProfile,
        dailyTarget,
        streakData,
        trackerSummary,
        mealPlan,
        isMealPlanLoading,
      );
}

// =============================================================================
// _SkeletonLoader — wraps its child in a left-to-right shimmer animation.
// Pure Flutter, no external packages required.
// =============================================================================
class _SkeletonLoader extends StatefulWidget {
  const _SkeletonLoader({required this.child});

  final Widget child;

  @override
  State<_SkeletonLoader> createState() => _SkeletonLoaderState();
}

class _SkeletonLoaderState extends State<_SkeletonLoader>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (_, child) {
        // Sweep from -1 to +2 so the highlight fully exits both sides.
        final double shift = _controller.value * 3 - 1;
        return ShaderMask(
          shaderCallback: (bounds) => LinearGradient(
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
            colors: const [
              Color(0xFFE0E0E0),
              Color(0xFFF5F5F5),
              Color(0xFFE0E0E0),
            ],
            stops: [
              (shift - 0.3).clamp(0.0, 1.0),
              shift.clamp(0.0, 1.0),
              (shift + 0.3).clamp(0.0, 1.0),
            ],
          ).createShader(bounds),
          blendMode: BlendMode.srcATop,
          child: child,
        );
      },
      child: widget.child,
    );
  }
}
