from app.schemas import UserResponse, ApiKeyRotateResponse

with open("verify_output_final.txt", "w") as f:
    f.write(f"UserResponse fields: {list(UserResponse.model_fields.keys())}\n")
    f.write(
        f"ApiKeyRotateResponse fields: {list(ApiKeyRotateResponse.model_fields.keys())}\n"
    )
    f.write(f"api_key in UserResponse: {'api_key' in UserResponse.model_fields}\n")
    f.write(
        f"new_api_key in ApiKeyRotateResponse: {'new_api_key' in ApiKeyRotateResponse.model_fields}\n"
    )

print("Verification complete!")
