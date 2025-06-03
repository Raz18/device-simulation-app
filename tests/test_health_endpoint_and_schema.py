import pytest
from fastapi import status

def test_health_check(test_app_client):
    """Test the health check endpoint."""
    response = test_app_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["application_status"] == 'healthy'
    assert data["redis_status"] == 'healthy'


def test_openapi_schema(test_app_client):
    """Test that the OpenAPI schema is correctly generated."""
    response = test_app_client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    schema = response.json()

    assert "openapi" in schema
    assert "info" in schema
    assert schema["info"]["title"] == "Device Simulator API"
    assert schema["info"]["version"] == "0.1.0"

    assert "paths" in schema
    expected_paths = ["/devices", "/devices/{device_id}", "/devices/{device_id}/command", "/health"]
    for path in expected_paths:
        assert path in schema["paths"]


def test_openapi_schema_is_valid(test_app_client):
    """Verify the OpenAPI schema is available and well-formed."""
    response = test_app_client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK

    schema = response.json()
    for key in schema:
        print(f"{key}: {schema[key]}")  # Print schema keys and values for debugging

    # Validate basic structure
    assert "openapi" in schema
    assert "paths" in schema
    assert "components" in schema

    # Verify schema version is valid OpenAPI 3.1.x
    assert schema["openapi"].startswith("3.1")


def test_all_endpoints_documented(test_app_client):
    """Verify all application endpoints are documented in the OpenAPI schema."""
    response = test_app_client.get("/openapi.json")
    schema = response.json()

    # Define the endpoints your application should have
    expected_endpoints = {
        "/devices": ["get"],
        "/devices/{device_id}": ["get"],
        "/devices/{device_id}/command": ["post"],
        "/health": ["get"]
    }

    # Check each expected endpoint is in the schema
    for path, methods in expected_endpoints.items():
        assert path in schema["paths"], f"Path {path} missing in OpenAPI schema"
        for method in methods:
            assert method in schema["paths"][path], f"Method {method} for path {path} missing in schema"


@pytest.mark.parametrize("endpoint,method,status_code", [
    ("/devices", "get", 200),
    ("/devices/online-dev-001", "get", 200),
    ("/devices/nonexistent-device", "get", 404),
    ("/health", "get", 200)
])
def test_endpoint_response_matches_schema(test_app_client, online_device_fixture, endpoint, method, status_code):
    """Test that endpoint responses match the schema defined in OpenAPI docs."""
    # Get the OpenAPI schema
    schema_response = test_app_client.get("/openapi.json")
    schema = schema_response.json()

    # Replace placeholder parameters in the endpoint path
    if "{device_id}" in endpoint:
        if status_code == 200:
            endpoint = endpoint.replace("online-dev-001", online_device_fixture["id"])

    # Make the request
    if method.lower() == "get":
        response = test_app_client.get(endpoint)
    else:
        pytest.skip(f"Test not implemented for method {method}")

    # Check status code matches expected
    assert response.status_code == status_code

    # For successful responses, validate against schema
    if status_code == 200:
        # Find the schema for this response
        path_schema = schema["paths"].get(endpoint.split("?")[0], {})
        if not path_schema:
            # Handle parameterized paths
            for schema_path in schema["paths"]:
                if "{" in schema_path and endpoint.startswith(schema_path.split("{")[0]):
                    path_schema = schema["paths"][schema_path]
                    break

        method_schema = path_schema.get(method.lower(), {})
        response_schema = method_schema.get("responses", {}).get("200", {})

        # If there's a schema reference, resolve and validate
        if "content" in response_schema and "application/json" in response_schema["content"]:
            content_schema = response_schema["content"]["application/json"].get("schema", {})
            if "$ref" in content_schema:
                # Resolve schema reference
                ref_path = content_schema["$ref"].replace("#/components/schemas/", "")
                component_schema = schema["components"]["schemas"].get(ref_path, {})

                # Basic validation that response matches expected structure
                response_data = response.json()

                # Check if it's an array response
                if component_schema.get("type") == "array":
                    assert isinstance(response_data, list)
                    if response_data and "items" in component_schema:
                        # Validate first item against item schema
                        item_schema = component_schema["items"]
                        if "$ref" in item_schema:
                            item_ref = item_schema["$ref"].replace("#/components/schemas/", "")
                            item_schema = schema["components"]["schemas"].get(item_ref, {})

                        # Check required properties are present
                        for prop in item_schema.get("required", []):
                            assert prop in response_data[0], f"Required property {prop} missing"
                else:
                    # Check required properties are present in object response
                    for prop in component_schema.get("required", []):
                        assert prop in response_data, f"Required property {prop} missing"



def test_command_endpoint_validates_per_schema(test_app_client, online_device_fixture):
    """Test that the command endpoint validates input according to schema."""
    schema_response = test_app_client.get("/openapi.json")
    schema = schema_response.json()

    # Get command endpoint schema
    command_path = f"/devices/{online_device_fixture['id']}/command"
    command_schema_path = "/devices/{device_id}/command"

    # Valid command according to schema
    valid_command = {"action": "test_action", "parameters": {"test": "value"}}

    # Invalid command missing required field
    invalid_command = {"parameters": {"test": "value"}}

    # Test valid command
    valid_response = test_app_client.post(command_path, json=valid_command)
    assert valid_response.status_code == 200

    # Test invalid command
    invalid_response = test_app_client.post(command_path, json=invalid_command)
    assert invalid_response.status_code == 400

    # Verify error message matches schema expectation
    error_detail = invalid_response.json().get("detail", "")
    assert "invalid command structure" in error_detail.lower()