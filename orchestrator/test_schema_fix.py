"""Test the schema changes for m1-remove-api-key-exposure."""

from datetime import datetime, timezone

from app.models import UserStatus
from app.schemas import ApiKeyRotateResponse, UserResponse, UserWithApiKeyResponse


def main() -> int:
    """Run the schema verification checks."""
    # Test 1: Verify UserResponse doesn't have api_key
    print("Test 1: Verify UserResponse schema...")
    user_fields = set(UserResponse.model_fields.keys())
    print(f"  UserResponse fields: {sorted(user_fields)}")
    if "api_key" in user_fields:
        print("  FAIL: api_key should NOT be in UserResponse")
        return 1
    print("  PASS: api_key is NOT in UserResponse")

    # Test 2: Verify ApiKeyRotateResponse has new_api_key
    print("\nTest 2: Verify ApiKeyRotateResponse schema...")
    rotate_fields = set(ApiKeyRotateResponse.model_fields.keys())
    print(f"  ApiKeyRotateResponse fields: {sorted(rotate_fields)}")
    expected_fields = {"status", "new_api_key", "message"}
    if rotate_fields != expected_fields:
        print(f"  FAIL: Expected {expected_fields}, got {rotate_fields}")
        return 1
    print("  PASS: ApiKeyRotateResponse has correct fields")

    # Test 3: Verify UserWithApiKeyResponse exists for admin use cases
    print("\nTest 3: Verify UserWithApiKeyResponse schema...")
    admin_fields = set(UserWithApiKeyResponse.model_fields.keys())
    print(f"  UserWithApiKeyResponse fields: {sorted(admin_fields)}")
    if "api_key" not in admin_fields:
        print("  FAIL: api_key should be in UserWithApiKeyResponse for admin use")
        return 1
    print("  PASS: UserWithApiKeyResponse has api_key for admin use cases")

    # Test 4: Verify we can instantiate schemas
    print("\nTest 4: Verify schema instantiation...")
    user_resp = UserResponse(
        id="test-id",
        email="test@example.com",
        display_name="Test User",
        status=UserStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    user_dict = user_resp.model_dump()
    if "api_key" in user_dict:
        print("  FAIL: api_key should not appear in UserResponse output")
        return 1
    print("  PASS: UserResponse serializes correctly without api_key")

    rotate_resp = ApiKeyRotateResponse(
        status="rotated",
        new_api_key="sk-test-key",
        message="API key rotated successfully",
    )
    rotate_dict = rotate_resp.model_dump()
    if "new_api_key" not in rotate_dict:
        print("  FAIL: new_api_key should be in ApiKeyRotateResponse output")
        return 1
    print("  PASS: ApiKeyRotateResponse serializes correctly with new_api_key")

    print("\n" + "=" * 50)
    print("All schema verification tests passed!")
    print("=" * 50)
    print("\nSummary of changes:")
    print("  - UserResponse: Does NOT include api_key (safe for GET/PATCH /user/me)")
    print(
        "  - ApiKeyRotateResponse: Includes new_api_key (for POST /user/me/api-key/rotate)"
    )
    print("  - UserWithApiKeyResponse: Includes api_key (for admin user creation only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
