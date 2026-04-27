import json
import os

def extract_keywords():
    input_file = "meals_export.json"
    output_file = "meals_keywords.json"

    with open(input_file, "r", encoding="utf-8") as f:
        original_meals = json.load(f)

    filtered_data = {}

    for meal in original_meals:
        meal_name = meal.get("mealName", "")
        if not meal_name:
            continue
            
        # Normalize mealName
        meal_name = meal_name.strip().lower()
        
        # Get searchKeywords
        keywords = meal.get("searchKeywords", [])
        if not isinstance(keywords, list):
            keywords = []
            
        # Normalize keywords
        clean_keywords = []
        for kw in keywords:
            if isinstance(kw, str) and kw.strip():
                clean_keywords.append(kw.strip().lower())
                
        # Deduplicate entries: if multiple meals have same mealName, merge keywords
        if meal_name in filtered_data:
            filtered_data[meal_name].extend(clean_keywords)
        else:
            filtered_data[meal_name] = clean_keywords

    meals = []
    for meal_name, keywords in filtered_data.items():
        # Remove duplicate keywords
        unique_keywords = []
        for kw in keywords:
            if kw not in unique_keywords:
                unique_keywords.append(kw)
                
        # Expand base keyword
        if meal_name not in unique_keywords:
            unique_keywords.insert(0, meal_name)
            
        meals.append({
            "mealName": meal_name,
            "searchKeywords": unique_keywords
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(meals, f, indent=2)

    print(f"[filter] extracted {len(meals)} unique meals")

if __name__ == "__main__":
    extract_keywords()
