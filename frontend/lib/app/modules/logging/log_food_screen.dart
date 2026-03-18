import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../data/providers/data_provider.dart';

class LogFoodScreen extends StatefulWidget {
  final ScrollController scrollController;
  const LogFoodScreen({super.key, required this.scrollController});

  @override
  State<LogFoodScreen> createState() => _LogFoodScreenState();
}

class _LogFoodScreenState extends State<LogFoodScreen> {
  final TextEditingController _controller = TextEditingController();
  bool _isLoading = false;
  bool _showResult = false;
  List<dynamic> _parsedItems = [];

  Future<void> _logFood() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;

    setState(() => _isLoading = true);
    final provider = Provider.of<DataProvider>(context, listen: false);
    
    // Call NLP Log API
    final result = await provider.logMealNLP(text);
    
    if (mounted) {
       setState(() {
         _isLoading = false;
         if (result != null) {
            // Check if result is List (new prompt requirement) or Map (old standard)
            if (result is List) {
               _parsedItems = result;
            } else if (result is Map<String, dynamic> && result.containsKey('items')) {
               _parsedItems = result['items'] as List<dynamic>? ?? <dynamic>[];
            } else if (result is Map<String, dynamic> && result.containsKey('meals')) {
               _parsedItems = result['meals'] as List<dynamic>? ?? <dynamic>[];
            } else {
               _parsedItems = <dynamic>[result]; // Single item fallback
            }
            _showResult = true;
         } else {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Failed to analyze meal. Try again.")));
         }
       });
    }
  }

  @override
  Widget build(BuildContext context) {
    // This padding ensures content isn't hidden by the keyboard
    final bottomPadding = MediaQuery.of(context).viewInsets.bottom;

    return Container(
      color: Colors.white,
      child: SingleChildScrollView(
        controller: widget.scrollController,
        padding: EdgeInsets.fromLTRB(24, 24, 24, 24 + bottomPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  "Log Food",
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                )
              ],
            ),
            const SizedBox(height: 24),

            if (_showResult) ...[
               const Text("Detected Meal", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
               const SizedBox(height: 12),
               if (_parsedItems.isEmpty)
                  const Text("No specific items extracted, but meal was logged."),
               ..._parsedItems.map((e) => ListTile(
                   leading: const Icon(Icons.check_circle, color: Colors.green),
                   title: Text(e['mealName'] ?? e['meal'] ?? "Food", style: const TextStyle(fontWeight: FontWeight.bold)),
                   trailing: Text("×${e['quantity'] ?? 1}", style: const TextStyle(fontSize: 16)),
               )),
               const SizedBox(height: 24),
               Row(
                 mainAxisAlignment: MainAxisAlignment.spaceBetween,
                 children: [
                    OutlinedButton(
                       onPressed: () => setState(() => _showResult = false), 
                       style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 24)),
                       child: const Text("Edit Text")
                    ),
                    ElevatedButton(
                       onPressed: () => Navigator.pop(context), 
                       style: ElevatedButton.styleFrom(backgroundColor: Colors.green, padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 32)),
                       child: const Text("Confirm Log", style: TextStyle(color: Colors.white))
                    ),
                 ]
               )
            ] else ...[
              // Text Field (Page 17)
              TextField(
                controller: _controller,
                autofocus: true,
                maxLines: 5,
                decoration: InputDecoration(
                  hintText:
                  'Describe your meal, e.g., "A plate of grilled chicken with rice, small portion of boiled carrots..."',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: Colors.grey[300]!),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide:
                    const BorderSide(color: Colors.green, width: 2),
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Log Food Button
              ElevatedButton(
                onPressed: _isLoading ? null : _logFood,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: _isLoading 
                  ? const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)),
                      SizedBox(width: 12), Text("Analyzing your meal...", style: TextStyle(color: Colors.white))
                    ])
                  : const Text("Analyze Meal"),
              ),
              const SizedBox(height: 16),

              // Manual Logging Button
              OutlinedButton.icon(
                onPressed: () {
                  Navigator.of(context).pop(); // Close bottom sheet
                  Navigator.of(context).pushNamed('/manualLog'); // We need to add this route or push manually
                },
                icon: const Icon(Icons.search),
                label: const Text("Manual Food Entry"),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ]
          ],
        ),
      ),
    );
  }
}