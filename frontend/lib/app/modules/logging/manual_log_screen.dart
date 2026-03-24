import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../data/providers/data_provider.dart';
import '../../data/services/api_service.dart';


class ManualLogScreen extends StatefulWidget {
  const ManualLogScreen({super.key});

  @override
  State<ManualLogScreen> createState() => _ManualLogScreenState();
}

class _ManualLogScreenState extends State<ManualLogScreen> {
  final TextEditingController _searchController = TextEditingController();
  bool _isLoading = false;
  List<Map<String, dynamic>> _searchResults = [];
  Map<String, dynamic>? _selectedFood;
  double _quantity = 1.0;
  String _mealType = 'Lunch';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _searchFood(String query) async {
    if (query.trim().length < 2) {
      setState(() => _searchResults = []);
      return;
    }

    setState(() => _isLoading = true);
    try {
      final results = await ApiService.searchFood(query.trim());
      if (!mounted) return;
      setState(() {
        _searchResults = results != null ? List<Map<String, dynamic>>.from(results) : [];
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _selectFood(Map<String, dynamic> food) async {
    final details = await ApiService.getFoodDetails((food['name'] ?? '').toString());
    if (!mounted) return;
    if (details == null) return;
    setState(() {
      _selectedFood = details;
      _quantity = 1.0;
      _searchResults = [];
      _searchController.text = (details['mealName'] ?? food['name'] ?? '').toString();
    });
  }

  Future<void> _log() async {
    if (_selectedFood == null) return;
    final provider = context.read<DataProvider>();

    final ok = await provider.logMeal(
      (_selectedFood!['mealName'] ?? '').toString(),
      _quantity,
      _mealType,
      'manual',
    );
    if (!ok) return;
    if (!mounted) return;

    setState(() {
      _selectedFood = null;
      _quantity = 1.0;
      _searchController.clear();
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('✅ Food logged successfully!'), backgroundColor: Colors.green),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Manual Food Entry"),
        elevation: 1,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
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
                    selected: {_mealType},
                    onSelectionChanged: (set) => setState(() => _mealType = set.first),
                    style: const ButtonStyle(visualDensity: VisualDensity.compact),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: "Search for a food...",
                prefixIcon: const Icon(Icons.search),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.clear),
                  onPressed: () {
                    _searchController.clear();
                    setState(() {
                      _searchResults = [];
                      _selectedFood = null;
                    });
                  },
                ),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onChanged: _searchFood,
            ),
            const SizedBox(height: 12),
            if (_isLoading) const Center(child: CircularProgressIndicator()),
            if (!_isLoading && _searchResults.isNotEmpty)
              Expanded(
                child: ListView.separated(
                  itemCount: _searchResults.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final food = _searchResults[index];
                    return ListTile(
                      dense: true,
                      title: Text((food['name'] ?? '').toString()),
                      trailing: Text('${food['calories'] ?? 0} cal'),
                      onTap: () => _selectFood(food),
                    );
                  },
                ),
              )
            else
              Expanded(
                child: _selectedFood == null
                    ? const Center(child: Text("Search for a food item above."))
                    : SingleChildScrollView(
                        child: Card(
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          elevation: 2,
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  (_selectedFood!['mealName'] ?? '').toString(),
                                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                ),
                                const SizedBox(height: 12),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                                  children: [
                                    _macro("Calories", ((_selectedFood!['calories'] ?? 0) * _quantity).toStringAsFixed(0)),
                                    _macro("Protein", '${((_selectedFood!['protein'] ?? 0) * _quantity).toStringAsFixed(1)}g'),
                                    _macro("Carbs", '${((_selectedFood!['carbs'] ?? 0) * _quantity).toStringAsFixed(1)}g'),
                                    _macro("Fat", '${((_selectedFood!['fat'] ?? 0) * _quantity).toStringAsFixed(1)}g'),
                                  ],
                                ),
                                const SizedBox(height: 16),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    const Text("Quantity: ", style: TextStyle(fontWeight: FontWeight.w500)),
                                    IconButton(
                                      onPressed: _quantity > 0.5 ? () => setState(() => _quantity -= 0.5) : null,
                                      icon: const Icon(Icons.remove_circle_outline, color: Colors.green),
                                    ),
                                    Text(
                                      _quantity.toStringAsFixed(1),
                                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.green),
                                    ),
                                    IconButton(
                                      onPressed: () => setState(() => _quantity += 0.5),
                                      icon: const Icon(Icons.add_circle_outline, color: Colors.green),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 12),
                                SizedBox(
                                  width: double.infinity,
                                  child: ElevatedButton(
                                    onPressed: _log,
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
                      ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _macro(String label, String value) {
    return Column(
      children: [
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.green)),
        const SizedBox(height: 2),
        Text(label, style: const TextStyle(color: Colors.grey, fontSize: 11)),
      ],
    );
  }
}
