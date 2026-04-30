import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:percent_indicator/percent_indicator.dart';
import 'package:provider/provider.dart';
import '../../../data/models/models.dart';
import '../../../data/providers/data_provider.dart';
import '../../logging/log_food_screen.dart';

class TrackerTab extends StatefulWidget {
  const TrackerTab({super.key});

  @override
  State<TrackerTab> createState() => _TrackerTabState();
}

class _TrackerTabState extends State<TrackerTab> {
  DateTime _selectedDate = DateTime.now();

  // Debounce guard: logIds currently awaiting an updateLog response.
  // If a user taps +/- while a request is in-flight for that entry, ignore it.
  final Set<String> _pendingUpdates = {};

  String get _selectedDateKey =>
      DateFormat('yyyy-MM-dd').format(_selectedDate);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<DataProvider>();
      provider.fetchTrackerSummary(_selectedDateKey);
      provider.fetchDailyRating(_selectedDateKey);
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.read<DataProvider>();
    final now = DateTime.now();
    final isToday = _selectedDate.year == now.year &&
        _selectedDate.month == now.month &&
        _selectedDate.day == now.day;

    return Scaffold(
      appBar: AppBar(
        title: const Text("Tracker"),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(50.0),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                IconButton(
                  onPressed: () {
                    setState(() {
                      _selectedDate = _selectedDate.subtract(const Duration(days: 1));
                    });
                    provider.fetchTrackerSummary(_selectedDateKey);
                    provider.fetchDailyRating(_selectedDateKey);
                  },
                  icon: const Icon(Icons.arrow_back_ios, size: 18),
                ),
                Text(
                  _formatDate(_selectedDate),
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.bold),
                ),
                IconButton(
                  onPressed: isToday
                      ? null
                      : () {
                          setState(() {
                            _selectedDate =
                                _selectedDate.add(const Duration(days: 1));
                          });
                          provider.fetchTrackerSummary(_selectedDateKey);
                          provider.fetchDailyRating(_selectedDateKey);
                        },
                  icon: Icon(
                    Icons.arrow_forward_ios,
                    size: 18,
                    color: isToday ? Colors.grey : Colors.black,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      body: Selector<DataProvider, _TrackerTabViewData>(
        selector: (_, provider) => _TrackerTabViewData(
          isTrackerLoading: provider.isTrackerLoading,
          isDailyRatingLoading: provider.isDailyRatingLoading,
          summaryModel: provider.getTrackerModelForDate(_selectedDateKey),
          ratingModel: provider.getDailyRatingModelForDate(_selectedDateKey),
        ),
        builder: (context, view, child) {
          if (view.isTrackerLoading && view.summaryModel == null) {
            return const Center(child: CircularProgressIndicator());
          }

          final summaryModel = view.summaryModel;

          final tCal = summaryModel?.targets.calories ?? 2000;
          final cCal = summaryModel?.consumed.calories ?? 0;
          final tProt = summaryModel?.targets.protein ?? 100;
          final cProt = summaryModel?.consumed.protein ?? 0;
          final tFat = summaryModel?.targets.fat ?? 70;
          final cFat = summaryModel?.consumed.fat ?? 0;
          final tCarbs = summaryModel?.targets.carbs ?? 250;
          final cCarbs = summaryModel?.consumed.carbs ?? 0;

          final resolvedTargets = {'calories': tCal, 'protein': tProt, 'fat': tFat, 'carbs': tCarbs};
          final resolvedConsumed = {'calories': cCal, 'protein': cProt, 'fat': cFat, 'carbs': cCarbs};

          final logs = summaryModel?.logs ?? [];

          return RefreshIndicator(
            onRefresh: () => provider.refreshTrackerDataForDate(_selectedDateKey),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _buildNutrientOverview(context, resolvedTargets, resolvedConsumed),
                  if (cCal > 0) ...[
                    _buildDailyRatingCard(
                      context,
                      view.ratingModel,
                      view.isDailyRatingLoading,
                    ),
                    const SizedBox(height: 24),
                  ] else ...[
                    Card(
                      elevation: 2,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Padding(
                        padding: EdgeInsets.all(20.0),
                        child: Column(
                          children: [
                            Icon(Icons.restaurant_menu, size: 40, color: Colors.grey),
                            SizedBox(height: 8),
                            Text(
                              "Start logging meals to see your daily performance rating!",
                              textAlign: TextAlign.center,
                              style: TextStyle(color: Colors.grey, fontSize: 14),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                  ],
                  _buildLoggedFoods(context, logs),
                  const SizedBox(height: 24),
                  _buildWaterTracker(context),
                  const SizedBox(height: 24),
                  _buildExerciseTracker(context),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    if (date.year == now.year && date.month == now.month && date.day == now.day) {
      return "Today";
    }
    final months = [
      "Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ];
    return "${date.day} ${months[date.month - 1]} ${date.year}";
  }

  Widget _buildNutrientOverview(BuildContext context, Map targets, Map consumed) {
    double tCal = (targets['calories'] ?? 2000).toDouble();
    double cCal = (consumed['calories'] ?? 0).toDouble();
    double calPercent = (cCal / tCal).clamp(0.0, 1.0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          "Nutrient Overview",
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
        ),
        const SizedBox(height: 16),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularPercentIndicator(
              radius: 60.0,
              lineWidth: 10.0,
              percent: calPercent,
              center: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    "${cCal.toInt()}",
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 24,
                    ),
                  ),
                  Text(
                    "/${tCal.toInt()}kcal",
                    style: const TextStyle(fontSize: 12),
                  ),
                ],
              ),
              progressColor: Colors.green,
              backgroundColor: Colors.green.shade100,
              circularStrokeCap: CircularStrokeCap.round,
            ),
          ],
        ),
        const SizedBox(height: 20),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            _buildMacroIndicator("Protein", consumed['protein']?.toDouble() ?? 0, targets['protein']?.toDouble() ?? 100, "g", Colors.blue),
            _buildMacroIndicator("Fat", consumed['fat']?.toDouble() ?? 0, targets['fat']?.toDouble() ?? 70, "g", Colors.orange),
            _buildMacroIndicator("Carbs", consumed['carbs']?.toDouble() ?? 0, targets['carbs']?.toDouble() ?? 250, "g", Colors.purple),
          ],
        ),
      ],
    );
  }

  Widget _buildMacroIndicator(String title, double value, double total, String unit, Color color) {
    if (total == 0) total = 1;
    double percent = (value / total).clamp(0.0, 1.0);
    return CircularPercentIndicator(
      radius: 45.0,
      lineWidth: 6.0,
      percent: percent,
      center: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            "${value.toInt()}",
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
          ),
          Text("/${total.toInt()}$unit", style: const TextStyle(fontSize: 10)),
        ],
      ),
      footer: Padding(
        padding: const EdgeInsets.only(top: 8.0),
        child: Text(
          title,
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
        ),
      ),
      progressColor: color,
      backgroundColor: color.withValues(alpha: 0.1),
      circularStrokeCap: CircularStrokeCap.round,
    );
  }

  Widget _buildLoggedFoods(BuildContext context, List<MealLog> logs) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              "Logged Foods",
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const Spacer(),
            TextButton.icon(
              onPressed: () => onLogFoodPressed(context),
              icon: const Icon(Icons.add_circle_outline),
              label: const Text("Log Food"),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (logs.isEmpty)
          const Center(
            child: Padding(
              padding: EdgeInsets.symmetric(vertical: 30),
              child: Column(
                children: [
                  Text(
                    "No foods logged today",
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                  SizedBox(height: 8),
                  Text(
                    "Start tracking your meals to see nutrition progress.",
                    style: TextStyle(color: Colors.grey),
                  ),
                ],
              ),
            ),
          ),
        ...logs.map((log) {
          final logId = log.logId ?? log.hashCode.toString();
          final quantity = log.quantity;
          return Dismissible(
            key: Key(logId),
            background: Container(
              color: Colors.red,
              alignment: Alignment.centerLeft,
              padding: const EdgeInsets.only(left: 20),
              child: const Icon(Icons.delete, color: Colors.white),
            ),
            secondaryBackground: Container(
              color: Colors.blue,
              alignment: Alignment.centerRight,
              padding: const EdgeInsets.only(right: 20),
              child: const Icon(Icons.edit, color: Colors.white),
            ),
            confirmDismiss: (direction) async {
              if (direction == DismissDirection.startToEnd) {
                if (log.logId != null) _deleteLog(context, log.logId!);
              } else if (direction == DismissDirection.endToStart) {
                _showEditQuantityDialog(context, log);
              }
              return false;
            },
            child: Card(
              elevation: 1,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: Colors.grey[200]!),
              ),
              child: ListTile(
                leading: Icon(
                  log.mealType == "Breakfast"
                      ? Icons.breakfast_dining
                      : log.mealType == "Lunch"
                          ? Icons.lunch_dining
                          : Icons.dinner_dining,
                  color: Colors.green,
                ),
                title: Text(
                  log.mealName,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      "${log.mealType ?? 'Meal'} • ${log.calories.toInt()} kcal${quantity > 1 ? " • Logged x$quantity" : ""}",
                      style: const TextStyle(fontSize: 13),
                    ),
                    if (log.servingSize != null && log.servingSize!.isNotEmpty)
                      Text(
                        "${log.servingSize}${log.servingGrams != null ? ' • ${log.servingGrams}g' : ''}",
                        style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                      ),
                  ],
                ),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.sync, color: Colors.blue),
                      onPressed: () => _showSwapDialog(context, log),
                      tooltip: "Swap Meal",
                    ),
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
                            onPressed: log.logId == null
                                ? null
                                : () async {
                                    final id = log.logId!;
                                    if (_pendingUpdates.contains(id)) return; // debounce
                                    setState(() => _pendingUpdates.add(id));
                                    try {
                                      final prov = Provider.of<DataProvider>(
                                        context,
                                        listen: false,
                                      );
                                      if (quantity > 1) {
                                        await prov.updateLog(
                                          id,
                                          quantity - 1,
                                          _selectedDateKey,
                                        );
                                      } else {
                                        _deleteLog(context, id);
                                      }
                                    } finally {
                                      if (mounted) setState(() => _pendingUpdates.remove(id));
                                    }
                                  },
                            icon: const Icon(Icons.remove, color: Colors.green),
                          ),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 6),
                            child: Text(
                              "x$quantity",
                              style: TextStyle(
                                color: Colors.green[800],
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                              ),
                            ),
                          ),
                          IconButton(
                            visualDensity: VisualDensity.compact,
                            padding: EdgeInsets.zero,
                            iconSize: 18,
                            onPressed: log.logId == null
                                ? null
                                : () async {
                                    final id = log.logId!;
                                    if (_pendingUpdates.contains(id)) return; // debounce
                                    setState(() => _pendingUpdates.add(id));
                                    try {
                                      await Provider.of<DataProvider>(
                                        context,
                                        listen: false,
                                      ).updateLog(
                                        id,
                                        quantity + 1,
                                        _selectedDateKey,
                                      );
                                    } finally {
                                      if (mounted) setState(() => _pendingUpdates.remove(id));
                                    }
                                  },
                            icon: const Icon(Icons.add, color: Colors.green),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }),
      ],
    );
  }

  Widget _buildWaterTracker(BuildContext context) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: const Padding(
        padding: EdgeInsets.all(16.0),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                Icon(Icons.water_drop, color: Colors.blue),
                Text("Water Tracking (Coming Soon)"),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildExerciseTracker(BuildContext context) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: const Padding(
        padding: EdgeInsets.all(16.0),
        child: Center(child: Text("Exercise Log (Coming Soon)")),
      ),
    );
  }

  Widget _buildDailyRatingCard(
    BuildContext context,
    DailyRating? dailyRating,
    bool isLoading,
  ) {
    if (isLoading && dailyRating == null) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    // Step 5 — model fields only; fallback defaults when model absent
    final rating = dailyRating?.stars ?? 4;
    final feedback = dailyRating?.feedback ?? "Keep tracking to see your performance!";

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "Your Weekly Performance",
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 12),
            Row(
              children: List.generate(
                5,
                (index) => Icon(
                  index < rating ? Icons.star : Icons.star_border,
                  color: Colors.amber,
                  size: 28,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(feedback, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      ),
    );
  }

  void onLogFoodPressed(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.8,
        maxChildSize: 1.0,
        minChildSize: 0.5,
        builder: (_, controller) => ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          child: LogFoodScreen(scrollController: controller),
        ),
      ),
    );
  }

  // Fix B (audit): accepts MealLog directly — no Map serialisation round-trip.
  void _showSwapDialog(BuildContext context, MealLog log) async {
    final provider = Provider.of<DataProvider>(context, listen: false);
    final mealName = log.mealName;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );

    final result = await provider.replaceMeal(mealName);
    if (!context.mounted) return;
    Navigator.pop(context);

    if (result != null && result['aiSuggestions'] != null) {
      final suggestions = List<Map<String, dynamic>>.from(result['aiSuggestions']);

      showModalBottomSheet(
        context: context,
        builder: (ctx) => Container(
          padding: const EdgeInsets.symmetric(vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                "Select a Replacement",
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 10),
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: suggestions.length,
                  itemBuilder: (_, index) {
                    final item = suggestions[index];
                    return ListTile(
                      leading: const Icon(Icons.food_bank, color: Colors.orange),
                      title: Text(item['mealName']),
                      trailing: const Icon(
                        Icons.check_circle_outline,
                        color: Colors.green,
                      ),
                      onTap: () {
                        Navigator.pop(ctx);
                        // Use .logId directly — no Map key lookup.
                        _performSwap(context, log.logId, item['mealName']);
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("No swaps found for this meal")),
      );
    }
  }

  void _performSwap(BuildContext context, String? logId, String newMeal) async {
    if (logId == null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Error: Invalid Log ID")),
        );
      }
      return;
    }

    final provider = Provider.of<DataProvider>(context, listen: false);

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );
    final result = await provider.swapMeal(logId, newMeal, _selectedDateKey);
    if (!context.mounted) return;
    Navigator.pop(context);

    if (result != null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(result['message'] ?? "Meal swapped!")),
        );
      }
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Swap failed")),
        );
      }
    }
  }

  void _deleteLog(BuildContext context, String logId) async {
    final provider = Provider.of<DataProvider>(context, listen: false);
    // Route through DataProvider — no direct ApiService calls from UI.
    await provider.deleteLog(logId, _selectedDateKey);
  }

  void _showEditQuantityDialog(BuildContext context, MealLog log) {
    // Step 5 — read from typed model fields
    double currentQty = log.quantity;
    final logId = log.logId;
    showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: Text("Edit Quantity: ${log.mealName}"),
              content: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  IconButton(
                    onPressed:
                        currentQty > 1 ? () => setState(() => currentQty--) : null,
                    icon: const Icon(Icons.remove_circle_outline),
                  ),
                  Text(
                    "$currentQty",
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  IconButton(
                    onPressed: () => setState(() => currentQty++),
                    icon: const Icon(Icons.add_circle_outline),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text("Cancel"),
                ),
                ElevatedButton(
                  onPressed: () async {
                    Navigator.pop(ctx);
                    if (logId != null && context.mounted) {
                      await Provider.of<DataProvider>(context, listen: false)
                          .updateLog(logId, currentQty, _selectedDateKey);
                    }
                  },
                  child: const Text("Save"),
                ),
              ],
            );
          },
        );
      },
    );
  }
}

class _TrackerTabViewData {
  const _TrackerTabViewData({
    required this.isTrackerLoading,
    required this.isDailyRatingLoading,
    // ── Step 5: Model-only fields ──
    this.summaryModel,
    this.ratingModel,
  });

  final bool isTrackerLoading;
  final bool isDailyRatingLoading;
  final TrackerSummary? summaryModel;
  final DailyRating? ratingModel;

  @override
  bool operator ==(Object other) {
    if (other is! _TrackerTabViewData) return false;
    if (other.isTrackerLoading != isTrackerLoading) return false;
    if (other.isDailyRatingLoading != isDailyRatingLoading) return false;
    if (other.ratingModel != ratingModel) return false;
    if (other.summaryModel?.consumed.calories != summaryModel?.consumed.calories) return false;
    // Critical fix: compare per-log quantities so +/- triggers a rebuild
    final thisLogs  = summaryModel?.logs ?? [];
    final otherLogs = other.summaryModel?.logs ?? [];
    if (thisLogs.length != otherLogs.length) return false;
    for (int i = 0; i < thisLogs.length; i++) {
      if (thisLogs[i].quantity != otherLogs[i].quantity) return false;
      if (thisLogs[i].calories != otherLogs[i].calories) return false;
    }
    return true;
  }

  @override
  int get hashCode => Object.hash(
        isTrackerLoading,
        isDailyRatingLoading,
        summaryModel?.consumed.calories,
        // Include quantity sum so hashCode changes when quantities change
        summaryModel?.logs.fold<double>(0, (s, l) => s + l.quantity),
        ratingModel,
      );
}
