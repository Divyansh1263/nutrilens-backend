import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../../data/services/api_service.dart';
import '../../../data/providers/data_provider.dart';

class LoggingTab extends StatefulWidget {
  const LoggingTab({super.key});

  @override
  State<LoggingTab> createState() => _LoggingTabState();
}

class _LoggingTabState extends State<LoggingTab> {
  // NLP Section
  final TextEditingController _nlpController = TextEditingController();
  bool _isAnalyzing = false;
  List<Map<String, dynamic>> _analyzedMeals = [];
  bool _showAnalyzedResults = false;

  // Manual Search Section
  final TextEditingController _searchController = TextEditingController();
  List<Map<String, dynamic>> _searchResults = [];
  Map<String, dynamic>? _selectedFood;
  double _manualQuantity = 1.0;
  bool _isSearching = false;
  String _selectedMealType = 'Lunch';

  @override
  void dispose() {
    _nlpController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  // ==================== NLP METHODS ====================

  Future<void> _analyzeMeal() async {
    final text = _nlpController.text.trim();
    if (text.isEmpty) return;

    setState(() {
      _isAnalyzing = true;
      _analyzedMeals = [];
      _showAnalyzedResults = false;
    });

    try {
      // Analyze only — does NOT log to Firestore
      // Result is List<dynamic>? — flat array of meal objects
      final result = await ApiService.analyzeMealNLP(text);

      if (result != null && result.isNotEmpty) {
        setState(() {
          _analyzedMeals = result.map((item) {
            return <String, dynamic>{
              'mealName': item['mealName'] ?? item['meal'] ?? 'Unknown',
              'quantity': (item['quantity'] ?? 1).toDouble(),
              'calories': (item['calories'] ?? 0).toDouble(),
              'protein': (item['protein'] ?? 0).toDouble(),
              'carbs': (item['carbs'] ?? 0).toDouble(),
              'fat': (item['fat'] ?? 0).toDouble(),
            };
          }).toList();
          _showAnalyzedResults = true;
        });
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not identify meals. Try being more specific.')),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    } finally {
      if (mounted) setState(() => _isAnalyzing = false);
    }
  }

  Future<void> _confirmNLPLog() async {
    // Log each analyzed meal individually via /log-meal.
    // refresh: false skips per-meal tracker refresh — one call at the end.
    final provider = Provider.of<DataProvider>(context, listen: false);
    final today = DateFormat('yyyy-MM-dd').format(DateTime.now());

    for (final meal in _analyzedMeals) {
      await provider.logMeal(
        meal['mealName'] ?? 'Unknown',
        (meal['quantity'] ?? 1.0).toDouble(),
        'Lunch', // default meal type for NLP
        'nlp',
        false, // defer refresh until after loop
      );
    }

    // Single refresh after all meals are logged.
    await provider.refreshTrackerDataForDate(today, force: true);

    setState(() {
      _analyzedMeals = [];
      _showAnalyzedResults = false;
      _nlpController.clear();
    });

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('✅ Meals logged successfully!'),
        backgroundColor: Colors.green,
      ),
    );
  }

  // ==================== MANUAL SEARCH METHODS ====================

  Future<void> _searchFood(String query) async {
    if (query.length < 2) {
      setState(() => _searchResults = []);
      return;
    }

    setState(() => _isSearching = true);

    try {
      final results = await ApiService.searchFood(query);
      if (results != null && mounted) {
        setState(() {
          _searchResults = List<Map<String, dynamic>>.from(results);
        });
      }
    } catch (e) {
      // Silence search errors
    } finally {
      if (mounted) setState(() => _isSearching = false);
    }
  }

  Future<void> _selectFood(Map<String, dynamic> food) async {
    // Fetch full details
    final details = await ApiService.getFoodDetails(food['name'] ?? '');
    if (details != null && mounted) {
      setState(() {
        _selectedFood = details;
        _manualQuantity = 1.0;
        _searchResults = [];
        _searchController.text = details['mealName'] ?? food['name'] ?? '';
      });
    }
  }

  Future<void> _logManualFood() async {
    if (_selectedFood == null) return;

    final provider = Provider.of<DataProvider>(context, listen: false);

    final result = await provider.logMeal(
      _selectedFood!['mealName'] ?? '',
      _manualQuantity,
      _selectedMealType,
      'manual',
    );

    if (!result) return;
    if (!mounted) return;

    setState(() {
      _selectedFood = null;
      _manualQuantity = 1.0;
      _searchController.clear();
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('✅ Food logged successfully!'),
        backgroundColor: Colors.green,
      ),
    );
  }

  // ==================== BUILD ====================

  @override
  Widget build(BuildContext context) {
    final bottomPadding = MediaQuery.of(context).viewInsets.bottom;

    return Scaffold(
      appBar: AppBar(
        title: const Text("Log Food"),
      ),
      body: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + bottomPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ============ SECTION 1: NLP LOGGING ============
            _buildSectionHeader("🤖 Describe Your Meal", "AI will identify foods from your description"),
            const SizedBox(height: 12),
            TextField(
              controller: _nlpController,
              maxLines: 4,
              decoration: InputDecoration(
                hintText: 'e.g., "2 roti and dal with a glass of lassi"',
                hintStyle: TextStyle(color: Colors.grey[400]),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: Colors.grey[300]!),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: Colors.green, width: 2),
                ),
                filled: true,
                fillColor: Colors.grey[50],
              ),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _isAnalyzing ? null : _analyzeMeal,
              icon: _isAnalyzing
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.auto_awesome),
              label: Text(_isAnalyzing ? "Analyzing..." : "Analyze Meal"),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),

            // Analyzed Results Cards
            if (_showAnalyzedResults && _analyzedMeals.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Text("Identified Meals:", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 8),
              ..._analyzedMeals.map((meal) => Card(
                margin: const EdgeInsets.only(bottom: 8),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                child: ListTile(
                  leading: const Icon(Icons.restaurant, color: Colors.green),
                  title: Text(
                    "${meal['mealName']} × ${(meal['quantity'] as double).toStringAsFixed(0)}",
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text(
                    "${(meal['calories'] as double).toStringAsFixed(0)} cal  •  P: ${(meal['protein'] as double).toStringAsFixed(0)}g  •  C: ${(meal['carbs'] as double).toStringAsFixed(0)}g  •  F: ${(meal['fat'] as double).toStringAsFixed(0)}g",
                    style: TextStyle(color: Colors.grey[600], fontSize: 12),
                  ),
                ),
              )),
              const SizedBox(height: 8),
              ElevatedButton(
                onPressed: _confirmNLPLog,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green[700],
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text("✅ Confirm Log"),
              ),
            ],

            // ============ DIVIDER ============
            const SizedBox(height: 32),
            Row(
              children: [
                const Expanded(child: Divider()),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text("OR", style: TextStyle(color: Colors.grey[500], fontWeight: FontWeight.w500)),
                ),
                const Expanded(child: Divider()),
              ],
            ),
            const SizedBox(height: 24),

            // ============ SECTION 2: MANUAL FOOD SEARCH ============
            _buildSectionHeader("🔍 Manual Food Entry", "Search and log food with exact quantities"),
            const SizedBox(height: 12),

            // Meal Type Selector
            Row(
              children: [
                const Text("Meal Type: ", style: TextStyle(fontWeight: FontWeight.w500)),
                const SizedBox(width: 8),
                Expanded(
                  child: SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: 'Breakfast', label: Text('B', style: TextStyle(fontSize: 12))),
                      ButtonSegment(value: 'Lunch', label: Text('L', style: TextStyle(fontSize: 12))),
                      ButtonSegment(value: 'Dinner', label: Text('D', style: TextStyle(fontSize: 12))),
                      ButtonSegment(value: 'Snack', label: Text('S', style: TextStyle(fontSize: 12))),
                    ],
                    selected: {_selectedMealType},
                    onSelectionChanged: (set) => setState(() => _selectedMealType = set.first),
                    style: ButtonStyle(
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Search Field
            TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search food (e.g., "roti", "paneer")',
                prefixIcon: const Icon(Icons.search, color: Colors.green),
                suffixIcon: _isSearching
                    ? const Padding(
                        padding: EdgeInsets.all(12),
                        child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                      )
                    : null,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: Colors.grey[300]!),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: Colors.green, width: 2),
                ),
                filled: true,
                fillColor: Colors.grey[50],
              ),
              onChanged: _searchFood,
            ),

            // Search Results
            if (_searchResults.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                constraints: const BoxConstraints(maxHeight: 200),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey[300]!),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: _searchResults.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final food = _searchResults[index];
                    return ListTile(
                      dense: true,
                      title: Text(food['name'] ?? '', style: const TextStyle(fontWeight: FontWeight.w500)),
                      trailing: Text(
                        '${food['calories'] ?? 0} cal',
                        style: TextStyle(color: Colors.grey[600]),
                      ),
                      onTap: () => _selectFood(food),
                    );
                  },
                ),
              ),
            ],

            // Selected Food Details
            if (_selectedFood != null) ...[
              const SizedBox(height: 16),
              Card(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 2,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _selectedFood!['mealName'] ?? '',
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 12),
                      // Macro Display
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceAround,
                        children: [
                          _buildMacroChip("Calories", "${((_selectedFood!['calories'] ?? 0) * _manualQuantity).toStringAsFixed(0)}", Colors.orange),
                          _buildMacroChip("Protein", "${((_selectedFood!['protein'] ?? 0) * _manualQuantity).toStringAsFixed(1)}g", Colors.red),
                          _buildMacroChip("Carbs", "${((_selectedFood!['carbs'] ?? 0) * _manualQuantity).toStringAsFixed(1)}g", Colors.blue),
                          _buildMacroChip("Fat", "${((_selectedFood!['fat'] ?? 0) * _manualQuantity).toStringAsFixed(1)}g", Colors.purple),
                        ],
                      ),
                      const SizedBox(height: 16),
                      // Quantity Selector
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Text("Quantity: ", style: TextStyle(fontWeight: FontWeight.w500)),
                          IconButton(
                            onPressed: _manualQuantity > 0.5
                                ? () => setState(() => _manualQuantity -= 0.5)
                                : null,
                            icon: const Icon(Icons.remove_circle_outline, color: Colors.green),
                          ),
                          Text(
                            _manualQuantity.toStringAsFixed(1),
                            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.green),
                          ),
                          IconButton(
                            onPressed: () => setState(() => _manualQuantity += 0.5),
                            icon: const Icon(Icons.add_circle_outline, color: Colors.green),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      // Log Button
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          onPressed: _logManualFood,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.green,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                          child: const Text("Log Food"),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String title, String subtitle) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        Text(subtitle, style: TextStyle(color: Colors.grey[600], fontSize: 13)),
      ],
    );
  }

  Widget _buildMacroChip(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontWeight: FontWeight.bold, color: color, fontSize: 16)),
        const SizedBox(height: 2),
        Text(label, style: TextStyle(color: Colors.grey[600], fontSize: 11)),
      ],
    );
  }
}
