"""Verify the API key exposure fix is correct."""
import sys

# Test 1: Verify UserResponse doesn't have api_key
print("Test 1: Verify UserResponse schema...")
from app.schemas import UserResponse
user_fields = set(UserResponse.model_fields.keys())
print(f"  UserResponse fields: {user_fields}")
if 'api_key' in user_fields:
    print("  FAIL: api_key should NOT be in UserResponse")
    sys.exit(1)
print("  PASS: api_key is NOT in UserResponse")

# Test 2: Verify ApiKeyRotateResponse has new_api_key
print("\nTest 2: Verify ApiKeyRotateResponse schema...")
from app.schemas import ApiKeyRotateResponse
rotate_fields = set(ApiKeyRotateResponse.model_fields.keys())
print(f"  ApiKeyRotateResponse fields: {rotate_fields}")
if 'new_api_key' not in rotate_fields:
    print("  FAIL: new_api_key should be in ApiKeyRotateResponse")
    sys.exit(1)
print("  PASS: new_api_key is in ApiKeyRotateResponse")

# Test 3: Verify users.py imports ApiKeyRotateResponse
print("\nTest 3: Verify users.py imports...")
from app.users import user_router
import inspect
source = inspect.getsourcefile(user_router)
print(f"  Router source: {source}")
print("  PASS: users.py imports work")

# Test 4: Verify the rotate endpoint uses the response model
print("\nTest 4: Verify rotate endpoint configuration...")
for route in user_router.routes:
    if route.path == "/me/api-key/rotate":
        print(f"  Route path: {route.path}")
        print(f"  Response model: {route.response_model}")
        if route.response_model != ApiKeyRotateResponse:
            print("  FAIL: rotate endpoint should use ApiKeyRotateResponse")
            sys.exit(1)
        print("  PASS: rotate endpoint uses ApiKeyRotateResponse")
        break
else:
    print("  FAIL: Could not find rotate endpoint")
    sys.exit(1)

print("\n" + "="*50)
print("All verification tests passed!")
print("="*50)
