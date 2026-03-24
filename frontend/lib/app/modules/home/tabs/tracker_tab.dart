import 'package:flutter/foundation.dart';
import 'package:college_project/app/modules/logging/log_food_screen.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:percent_indicator/percent_indicator.dart';
import 'package:provider/provider.dart';
import '../../../data/providers/data_provider.dart';
import '../../../data/services/api_service.dart';

class TrackerTab extends StatefulWidget {
  const TrackerTab({super.key});

  @override
  State<TrackerTab> createState() => _TrackerTabState();
}

class _TrackerTabState extends State<TrackerTab> {
  DateTime _selectedDate = DateTime.now();

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
          summary: provider.getTrackerSummaryForDate(_selectedDateKey),
          rating: provider.getDailyRatingForDate(_selectedDateKey),
          isTrackerLoading: provider.isTrackerLoading,
          isDailyRatingLoading: provider.isDailyRatingLoading,
        ),
        builder: (context, view, child) {
          if (view.isTrackerLoading && view.summary == null) {
            return const Center(child: CircularProgressIndicator());
          }

          final targets = view.summary?['targets'] ??
              {
                "calories": 2000,
                "protein": 100,
                "fat": 70,
                "carbs": 250,
              };
          final consumed = view.summary?['consumed'] ??
              {
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
              };
          final logs = view.summary?['logs'] ?? [];

          return RefreshIndicator(
            onRefresh: () => provider.refreshTrackerDataForDate(_selectedDateKey),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _buildNutrientOverview(context, targets, consumed),
                  if ((consumed['calories'] ?? 0).toDouble() > 0) ...[
                    _buildDailyRatingCard(
                      context,
                      view.rating,
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
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
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
            _buildMacroIndicator(
              "Protein",
              consumed['protein']?.toDouble() ?? 0,
              targets['protein']?.toDouble() ?? 100,
              "g",
              Colors.blue,
            ),
            _buildMacroIndicator(
              "Fat",
              consumed['fat']?.toDouble() ?? 0,
              targets['fat']?.toDouble() ?? 70,
              "g",
              Colors.orange,
            ),
            _buildMacroIndicator(
              "Carbs",
              consumed['carbs']?.toDouble() ?? 0,
              targets['carbs']?.toDouble() ?? 250,
              "g",
              Colors.purple,
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildMacroIndicator(
    String title,
    double value,
    double total,
    String unit,
    Color color,
  ) {
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

  Widget _buildLoggedFoods(BuildContext context, List logs) {
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
          final logId = (log['logId'] ?? log['id'] ?? log['_id'])?.toString();
          final qRaw = log['quantity'] ?? 1;
          final quantity =
              (qRaw is num) ? qRaw.toInt() : int.tryParse(qRaw.toString()) ?? 1;
          return Dismissible(
            key: Key(logId ?? log.hashCode.toString()),
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
              if (logId == null) return false;
              if (direction == DismissDirection.startToEnd) {
                _deleteLog(context, logId);
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
                  log['mealType'] == "Breakfast"
                      ? Icons.breakfast_dining
                      : log['mealType'] == "Lunch"
                          ? Icons.lunch_dining
                          : Icons.dinner_dining,
                  color: Colors.green,
                ),
                title: Text(
                  log['mealName'] ?? "Food",
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                subtitle: Text(
                  "${log['mealType']} • ${log['calories']} kcal${quantity > 1 ? " • Logged x$quantity" : ""}",
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
                            onPressed: logId == null
                                ? null
                                : () async {
                                    if (quantity > 1) {
                                      final ok = await ApiService.updateLog(
                                        logId,
                                        quantity - 1,
                                      );
                                      if (ok && context.mounted) {
                                        Provider.of<DataProvider>(
                                          context,
                                          listen: false,
                                        ).refreshTrackerDataForDate(_selectedDateKey);
                                      }
                                    } else {
                                      _deleteLog(context, logId);
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
                            onPressed: logId == null
                                ? null
                                : () async {
                                    final ok =
                                        await ApiService.updateLog(logId, quantity + 1);
                                    if (ok && context.mounted) {
                                      Provider.of<DataProvider>(
                                        context,
                                        listen: false,
                                      ).refreshTrackerDataForDate(_selectedDateKey);
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
    Map<String, dynamic>? dailyRating,
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

    final data = dailyRating ??
        {
          "rating": 4,
          "feedback": "Great job! Your protein intake stayed close to target.",
        };

    final rating = data['rating'] as int? ?? 4;
    final feedback =
        data['message'] ?? data['feedback'] ?? "Keep tracking to see your performance!";

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

  void _showSwapDialog(BuildContext context, Map<String, dynamic> log) async {
    final provider = Provider.of<DataProvider>(context, listen: false);
    final mealName = log['mealName'];
    if (mealName == null) return;

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
                        final id =
                            (log['logId'] ?? log['id'] ?? log['_id'])?.toString();
                        _performSwap(context, id, item['mealName']);
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
    final result = await provider.swapMeal(logId, newMeal);
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
    try {
      final response = await ApiService.deleteLog(logId);
      if (response && context.mounted) {
        provider.refreshTrackerDataForDate(_selectedDateKey);
      }
    } catch (e) {
      // Ignored error
    }
  }

  void _showEditQuantityDialog(BuildContext context, Map<String, dynamic> log) {
    int currentQty = log['quantity'] ?? 1;
    final logId = log['logId'] ?? log['id'];
    showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: Text("Edit Quantity: ${log['mealName']}"),
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
                    final response = await ApiService.updateLog(logId, currentQty);
                    if (response && context.mounted) {
                      Provider.of<DataProvider>(context, listen: false)
                          .refreshTrackerDataForDate(_selectedDateKey);
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
    required this.summary,
    required this.rating,
    required this.isTrackerLoading,
    required this.isDailyRatingLoading,
  });

  final Map<String, dynamic>? summary;
  final Map<String, dynamic>? rating;
  final bool isTrackerLoading;
  final bool isDailyRatingLoading;

  @override
  bool operator ==(Object other) {
    return other is _TrackerTabViewData &&
        mapEquals(other.summary, summary) &&
        mapEquals(other.rating, rating) &&
        other.isTrackerLoading == isTrackerLoading &&
        other.isDailyRatingLoading == isDailyRatingLoading;
  }

  @override
  int get hashCode => Object.hash(
        summary,
        rating,
        isTrackerLoading,
        isDailyRatingLoading,
      );
}
