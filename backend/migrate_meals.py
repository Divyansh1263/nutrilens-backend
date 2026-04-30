import os
import re

def migrate_meals():
    directories = [
        r"d:\NutriLens\backend",
        r"d:\NutriLens\frontend\lib"
    ]
    
    # regex to match .collection('meals') or .collection("meals")
    collection_pattern = re.compile(r'collection\(\s*[\'"]meals_v2[\'"]\s*\)')
    collection_name_pattern = re.compile(r'COLLECTION_NAME\s*=\s*[\'"]meals[\'"]')
    
    for dir_path in directories:
        if not os.path.exists(dir_path):
            continue
        for root, dirs, files in os.walk(dir_path):
            # exclude some dirs
            if 'venv' in dirs:
                dirs.remove('venv')
            if '.git' in dirs:
                dirs.remove('.git')
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
                
            for file in files:
                if file.endswith('.py') or file.endswith('.dart'):
                    # skip this script itself
                    if file == "migrate_meals.py":
                        continue
                    
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        new_content = collection_pattern.sub('collection("meals_v3")', content)
                        new_content = re.sub(r'COLLECTION_NAME\s*=\s*[\'"]meals_v2[\'"]', 'COLLECTION_NAME = "meals_v3"', new_content)
                        new_content = re.sub(r'COL_MEALS\s*=\s*[\'"]meals_v2[\'"]', 'COL_MEALS = "meals_v3"', new_content)
                        
                        if new_content != content:
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                            print(f"Updated {filepath}")
                    except Exception as e:
                        print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    migrate_meals()
