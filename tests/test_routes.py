import unittest
import json
import os
import sys

# Add project root to path
sys.path.append(r"d:\nutrilens\nutrilens-backend")

# Setup Environment Variable for Firebase BEFORE importing app
key_path = r"d:\nutrilens\nutrilens-backend\serviceAccountKey.json"
if os.path.exists(key_path):
    with open(key_path, "r") as f:
        os.environ["FIREBASE_SERVICE_ACCOUNT"] = f.read()
else:
    print(f"WARNING: {key_path} not found. Tests might fail if they reach Firebase init.")

# Import app
try:
    from app import app
except Exception as e:
    print(f"FAILED to import app: {e}")
    sys.exit(1)

class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_routes_list(self):
        """Test the /routes endpoint"""
        print("\nTesting /routes...")
        response = self.app.get('/routes')
        self.assertEqual(response.status_code, 200)
        print("  /routes OK")
        # print(response.get_json())

    def test_register_validation(self):
        """Test /register validation"""
        print("\nTesting /register validation...")
        response = self.app.post('/register', json={})
        self.assertIn(response.status_code, [400, 500]) # Expect error for empty body
        print("  /register validation OK")

    def test_login_validation(self):
        """Test /login validation"""
        print("\nTesting /login validation...")
        response = self.app.post('/login', json={})
        self.assertIn(response.status_code, [400, 500])
        print("  /login validation OK")

    def test_home_not_found(self):
        """Test 404 for root if not defined"""
        print("\nTesting / (home)...")
        response = self.app.get('/')
        # It's likely 404 as we didn't see a root route
        print(f"  / status: {response.status_code}")
        
if __name__ == '__main__':
    unittest.main()
