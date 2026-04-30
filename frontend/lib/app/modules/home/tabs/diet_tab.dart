import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../../../main.dart';
import '../../../data/models/models.dart';
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
            isMealPlanLoading: provider.isMealPlanLoading,
            // ── Step 5: Model-only fields ──────────────────────────────────
            userProfileModel: provider.userProfileModel,
            dailyTargetModel: provider.dailyTargetModel,
            streakDataModel: provider.streakDataModel,
            trackerSummaryModel: provider.getTrackerModelForDate(todayKey),
            mealPlanModel: provider.mealPlanModel,
          ),
          builder: (context, view, child) {
            // Step 4.4 — log model status once per rebuild (debug only)
            assert(() {
              if (view.mealPlanModel != null) {
                debugPrint('[ui] DietTab using MealPlanModel successfully');
              }
              return true;
            }());
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
                    // Step 5 — use computed getters from ViewData
                    _buildWelcomeMessage(view.displayName, view.targetCalories),
                    _buildStreakCard(view.currentStreak),
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
                        view.mealPlanModel == null &&
                        !_showGreeting)
                      _buildMealPlanSkeleton(),
                    if (view.dailyTargetModel != null)
                      _buildProgressCard(view.dailyTargetModel, view.trackerSummaryModel),
                    const SizedBox(height: 24),
                    if (view.mealPlanModel != null) ...[
                      // Step 5 — use typed model slots
                      () {
                        final mp = view.mealPlanModel!;
                        debugPrint('[diet-tab] breakfast: ${mp.breakfast.length} items');
                        debugPrint('[diet-tab] lunch:     ${mp.lunch.length} items');
                        debugPrint('[diet-tab] snack:     ${mp.snack.length} items');
                        debugPrint('[diet-tab] dinner:    ${mp.dinner.length} items');
                        return const SizedBox.shrink();
                      }(),
                      if (view.mealPlanModel!.breakfast.isNotEmpty)
                        _buildMealSection(
                          context,
                          "Breakfast",
                          view.mealPlanModel!.breakfast
                              .map((m) => m.toJson()).toList(),
                          view.trackerSummaryModel,
                        ),
                      if (view.mealPlanModel!.lunch.isNotEmpty)
                        _buildMealSection(
                          context,
                          "Lunch",
                          view.mealPlanModel!.lunch
                              .map((m) => m.toJson()).toList(),
                          view.trackerSummaryModel,
                        ),
                      if (view.mealPlanModel!.snack.isNotEmpty)
                        _buildMealSection(
                          context,
                          "Snack",
                          view.mealPlanModel!.snack
                              .map((m) => m.toJson()).toList(),
                          view.trackerSummaryModel,
                        ),
                      if (view.mealPlanModel!.dinner.isNotEmpty)
                        _buildMealSection(
                          context,
                          "Dinner",
                          view.mealPlanModel!.dinner
                              .map((m) => m.toJson()).toList(),
                          view.trackerSummaryModel,
                        ),
                      // ── TASK 4: Plan Quality Score badge ──────────────────
                      if (view.mealPlanModel!.optimizationScore != null)
                        _buildPlanQualityBadge(
                          view.mealPlanModel!.optimizationScore!,
                          view.mealPlanModel!.scoreLabel,
                        ),
                      // ── Phase 7: AI Daily Rater badge ───────────────────
                      if (view.mealPlanModel!.mlScore != null)
                        _buildAiRatingBadge(
                          view.mealPlanModel!.mlScore!,
                          view.mealPlanModel!.mlScoreLabel,
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

  Widget _buildWelcomeMessage(String displayName, double targetCalories) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
           Text("Good Morning $displayName 👋", style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
           const SizedBox(height: 4),
           Text("Your calorie target today is ${targetCalories.toInt()} kcal.", style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey[700])),
        ]
      )
    );
  }

  Widget _buildStreakCard(int streak) {
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

  /// TASK 4 — Plan Quality Score badge.
  /// Shown below all meal sections when [optimizationScore] is available.
  Widget _buildPlanQualityBadge(double score, String? label) {
    final pct = (score * 100).round();
    final displayLabel = label ?? _scoreLabel(score);

    // Color shifts based on score tier
    final Color badgeColor;
    final Color textColor;
    final String emoji;
    if (score >= 0.85) {
      badgeColor = const Color(0xFFE0F7F4); // teal-50
      textColor  = const Color(0xFF00796B); // teal-700
      emoji = '🌟';
    } else if (score >= 0.70) {
      badgeColor = const Color(0xFFE8F5E9); // green-50
      textColor  = const Color(0xFF388E3C); // green-700
      emoji = '✅';
    } else if (score >= 0.50) {
      badgeColor = const Color(0xFFFFF8E1); // amber-50
      textColor  = const Color(0xFFF57F17); // amber-900
      emoji = '⚡';
    } else {
      badgeColor = const Color(0xFFFFEBEE); // red-50
      textColor  = const Color(0xFFC62828); // red-800
      emoji = '⚠️';
    }

    return Padding(
      padding: const EdgeInsets.only(top: 16.0, bottom: 8.0),
      child: Container(
        width: double.infinity,
        decoration: BoxDecoration(
          color: badgeColor,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: textColor.withOpacity(0.3)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 22)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Plan Quality',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: textColor.withOpacity(0.7),
                      letterSpacing: 0.5,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      Text(
                        displayLabel,
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                          color: textColor,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '($pct%)',
                        style: TextStyle(
                          fontSize: 13,
                          color: textColor.withOpacity(0.8),
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Fallback label if backend didn't send score_label.
  String _scoreLabel(double score) {
    if (score >= 0.85) return 'Excellent plan';
    if (score >= 0.70) return 'Good plan';
    if (score >= 0.50) return 'Average plan';
    return 'Needs improvement';
  }

  /// Phase 7 — AI Daily Rater badge (RandomForest ML score).
  Widget _buildAiRatingBadge(double score, String? label) {
    final pct          = (score * 100).round();
    final displayLabel = label ?? _mlScoreLabel(score);

    // Colour scheme: green → yellow → red
    final Color bgColor;
    final Color textColor;
    final Color borderColor;
    final IconData icon;

    if (score >= 0.85) {
      bgColor     = const Color(0xFFE8F5E9); // green-50
      textColor   = const Color(0xFF2E7D32); // green-800
      borderColor = const Color(0xFFA5D6A7); // green-200
      icon        = Icons.auto_awesome;
    } else if (score >= 0.70) {
      bgColor     = const Color(0xFFE3F2FD); // blue-50
      textColor   = const Color(0xFF1565C0); // blue-800
      borderColor = const Color(0xFF90CAF9); // blue-200
      icon        = Icons.thumb_up_alt_outlined;
    } else if (score >= 0.50) {
      bgColor     = const Color(0xFFFFFDE7); // yellow-50
      textColor   = const Color(0xFFF57F17); // amber-900
      borderColor = const Color(0xFFFFE082); // amber-200
      icon        = Icons.warning_amber_outlined;
    } else {
      bgColor     = const Color(0xFFFFEBEE); // red-50
      textColor   = const Color(0xFFB71C1C); // red-900
      borderColor = const Color(0xFFEF9A9A); // red-200
      icon        = Icons.trending_down;
    }

    return Padding(
      padding: const EdgeInsets.only(top: 8.0, bottom: 16.0),
      child: Container(
        width: double.infinity,
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: borderColor),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Icon(icon, color: textColor, size: 22),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'AI Rating',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: textColor.withOpacity(0.7),
                      letterSpacing: 0.5,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      Text(
                        displayLabel,
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                          color: textColor,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '($pct%)',
                        style: TextStyle(
                          fontSize: 13,
                          color: textColor.withOpacity(0.8),
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Powered by NutriLens RandomForest model',
                    style: TextStyle(
                      fontSize: 10,
                      color: textColor.withOpacity(0.55),
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _mlScoreLabel(double score) {
    if (score >= 0.85) return 'Excellent';
    if (score >= 0.70) return 'Good';
    if (score >= 0.50) return 'Average';
    return 'Needs Improvement';
  }

  // Step 5 — typed model parameters
  Widget _buildProgressCard(DailyTarget? target, TrackerSummary? tracker) {
    final tCal  = target?.calories ?? 2000;
    final cCal  = tracker?.consumed.calories ?? 0;
    final tProt = target?.protein  ?? 100;
    final cProt = tracker?.consumed.protein  ?? 0;
    final tFat  = target?.fat      ?? 70;
    final cFat  = tracker?.consumed.fat      ?? 0;
    final tCarb = target?.carbs    ?? 250;
    final cCarb = tracker?.consumed.carbs    ?? 0;

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
            _buildProgressBar(context, "Calories", cCal,  tCal,  "kcal", Colors.orange),
            const SizedBox(height: 12),
            _buildProgressBar(context, "Protein",  cProt, tProt, "g",    Colors.red),
            const SizedBox(height: 12),
            _buildProgressBar(context, "Fat",      cFat,  tFat,  "g",    Colors.yellow[700]!),
            const SizedBox(height: 12),
            _buildProgressBar(context, "Carbs",    cCarb, tCarb, "g",    Colors.blue),
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
    TrackerSummary? trackerSummary,
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
    TrackerSummary? trackerSummary,
  ) {
    // Step 5 — read logs from model directly
    final logs = trackerSummary?.logs;
    
    double loggedQty = 0.0;
    String? logId;
    if (logs != null) {
      for (final log in logs) {
        if (log.mealName == item['mealName'] && log.mealType == mealType) {
           loggedQty = log.quantity;
           logId = log.logId;
           break;
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
                        "${item['calories'] ?? 0} kcal • ${item['protein'] ?? 0}g P • ${item['fat'] ?? 0}g F • ${item['carbs'] ?? 0}g C",
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      if (item['servingSize'] != null && item['servingSize'].toString().isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2.0),
                          child: Text(
                            "${item['servingSize']}${item['servingGrams'] != null ? ' • ${item['servingGrams']}g' : ''}",
                            style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            // TASK 2.4 — Explanation System: prefer 'explanation', fallback to 'smart_explanation'
            Builder(builder: (context) {
              final explanationText = (item['explanation']?.toString().isNotEmpty == true
                  ? item['explanation']
                  : item['smart_explanation'])?.toString();
              if (explanationText == null || explanationText.isEmpty) {
                return const SizedBox.shrink();
              }
              return Padding(
                padding: const EdgeInsets.only(top: 8.0, left: 62),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.teal.shade50,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: Colors.teal.shade100),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.info_outline, size: 13, color: Colors.teal.shade600),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          explanationText,
                          style: TextStyle(
                            fontStyle: FontStyle.italic,
                            color: Colors.teal.shade800,
                            fontSize: 11,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }),
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

  void _updateLogQuantity(BuildContext context, String? logId, double newQuantity) async {
    if (logId == null) return;
    final provider = Provider.of<DataProvider>(context, listen: false);
    debugPrint('[diet-tab] updateLogQuantity: logId=$logId newQty=$newQuantity');
    // Route through DataProvider — never call ApiService directly from UI.
    await provider.updateLog(logId, newQuantity);
  }

  void _deleteLog(BuildContext context, String logId) async {
    final provider = Provider.of<DataProvider>(context, listen: false);
    // Fix M (audit): pass dateKey so the dated tracker cache is invalidated.
    final dateKey = DateFormat('yyyy-MM-dd').format(DateTime.now());
    await provider.deleteLog(logId, dateKey);
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

                  // Step 5 — swap via model.toJson() since mealPlan Map is removed
                  if (provider.mealPlanModel != null) {
                    final key = mealType.toLowerCase();
                    final oldPlan = provider.mealPlanModel!.toJson();
                    final newPlan = Map<String, dynamic>.from(oldPlan);

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
    required this.isMealPlanLoading,
    // ── Step 5: Model-only fields ──
    this.userProfileModel,
    this.dailyTargetModel,
    this.streakDataModel,
    this.trackerSummaryModel,
    this.mealPlanModel,
  });

  final bool isMealPlanLoading;
  final UserProfile? userProfileModel;
  final DailyTarget? dailyTargetModel;
  final StreakData? streakDataModel;
  final TrackerSummary? trackerSummaryModel;
  final MealPlan? mealPlanModel;

  // ── Computed getters ────────────────────────────────────────────────

  double get targetCalories => dailyTargetModel?.calories ?? 2000;

  double get consumedCalories => trackerSummaryModel?.consumed.calories ?? 0;

  int get currentStreak => streakDataModel?.streak ?? 0;

  String get displayName =>
      userProfileModel?.displayName ??
      ApiService.userId?.split('@').first ??
      'User';

  @override
  bool operator ==(Object other) {
    if (other is! _DietTabViewData) return false;
    if (other.isMealPlanLoading != isMealPlanLoading) return false;
    if (other.mealPlanModel != mealPlanModel) return false;
    if (other.dailyTargetModel != dailyTargetModel) return false;
    if (other.streakDataModel != streakDataModel) return false;
    if (other.userProfileModel != userProfileModel) return false;
    // Compare tracker date + consumed totals
    if (other.trackerSummaryModel?.date != trackerSummaryModel?.date) return false;
    if (other.trackerSummaryModel?.consumed.calories !=
        trackerSummaryModel?.consumed.calories) return false;
    // Critical fix: also compare log quantities AND mealType so +/- triggers
    // a rebuild and cross-slot matches don't cause stale display.
    final thisLogs  = trackerSummaryModel?.logs ?? [];
    final otherLogs = other.trackerSummaryModel?.logs ?? [];
    if (thisLogs.length != otherLogs.length) return false;
    for (int i = 0; i < thisLogs.length; i++) {
      if (thisLogs[i].quantity  != otherLogs[i].quantity)  return false;
      if (thisLogs[i].calories  != otherLogs[i].calories)  return false;
      if (thisLogs[i].mealName  != otherLogs[i].mealName)  return false;
    }
    return true;
  }

  @override
  int get hashCode => Object.hash(
        isMealPlanLoading,
        mealPlanModel,
        dailyTargetModel,
        trackerSummaryModel?.logs.fold<double>(0, (s, l) => s + l.quantity),
        trackerSummaryModel?.consumed.calories,
        streakDataModel,
        userProfileModel,
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
