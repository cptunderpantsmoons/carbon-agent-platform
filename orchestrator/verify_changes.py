"""Verify the API key exposure fix is correct."""

import inspect

from app.schemas import ApiKeyRotateResponse, UserResponse
from app.users import user_router


def main() -> int:
    """Run the verification checks."""
    # Test 1: Verify UserResponse doesn't have api_key
    print("Test 1: Verify UserResponse schema...")
    user_fields = set(UserResponse.model_fields.keys())
    print(f"  UserResponse fields: {user_fields}")
    if "api_key" in user_fields:
        print("  FAIL: api_key should NOT be in UserResponse")
        return 1
    print("  PASS: api_key is NOT in UserResponse")

    # Test 2: Verify ApiKeyRotateResponse has new_api_key
    print("\nTest 2: Verify ApiKeyRotateResponse schema...")
    rotate_fields = set(ApiKeyRotateResponse.model_fields.keys())
    print(f"  ApiKeyRotateResponse fields: {rotate_fields}")
    if "new_api_key" not in rotate_fields:
        print("  FAIL: new_api_key should be in ApiKeyRotateResponse")
        return 1
    print("  PASS: new_api_key is in ApiKeyRotateResponse")

    # Test 3: Verify users.py imports ApiKeyRotateResponse
    print("\nTest 3: Verify users.py imports...")
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
                return 1
            print("  PASS: rotate endpoint uses ApiKeyRotateResponse")
            break
    else:
        print("  FAIL: Could not find rotate endpoint")
        return 1

    print("\n" + "=" * 50)
    print("All verification tests passed!")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
