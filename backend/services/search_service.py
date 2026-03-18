# services/search_service.py
from repositories.meal_repository import meal_repo

class SearchService:
    def search_food(self, query):
        if not query or len(query) < 2:
            return []
            
        all_meals = meal_repo.get_all_meals()
        results = []
        q = query.lower()
        
        for m in all_meals:
            name_val = (m.get("mealName") or m.get("name") or m.get("title") or m.get("food_name") or "")
            name = name_val.lower()
            
            keywords_list = m.get("searchKeywords") or m.get("aliases") or []
            keywords_str = " ".join(keywords_list).lower()
            
            if not keywords_str:
                keywords_str = name
            
            if q in name or q in keywords_str:
                results.append({
                    "meal_id": m.get("id"),
                    "name": name_val,
                    "calories": m.get("calories", 0)
                })
                
                if len(results) >= 10:
                    break
                
        return results
        
    def get_food_details(self, meal_name):
        return meal_repo.get_meal_by_name(meal_name)

search_service = SearchService()
