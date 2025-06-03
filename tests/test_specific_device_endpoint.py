# tests/test_specific_device_endpoint.py
import pytest
from fastapi import status
from typing import Dict, Any, Optional
from utils.data_models import Device


@pytest.mark.asyncio
async def test_get_specific_device_exists(test_app_client, online_device_fixture):
    """Test retrieving a specific device that exists."""
    device_id = online_device_fixture["id"]
    response = test_app_client.get(f"/devices/{device_id}")

    assert response.status_code == status.HTTP_200_OK
    device_response = response.json()
    assert device_response == online_device_fixture
    Device(**device_response)


@pytest.mark.asyncio
async def test_get_specific_device_not_found(test_app_client, redis_client_fixture):
    """Test retrieving a device that does not exist."""
    response = test_app_client.get("/devices/non-existent-id-123")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.benchmark
def test_benchmark_get_one_device(benchmark, test_app_client, online_device_fixture):
    """Benchmark retrieving a single specific device."""
    device_id = online_device_fixture["id"]

    def target_api_call(client, dev_id):
        response = client.get(f"/devices/{dev_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == dev_id

    benchmark(target_api_call, test_app_client, device_id)


class TestGetDeviceEndpointParameterized:
    """Group of parameterized data-based tests for the GET /devices/{device_id} endpoint."""

    GET_DEVICE_ID_TEST_CASES = [
        ("test-id-001", "test-id-001", status.HTTP_200_OK, True),
        ("another-id-123", "another-id-123", status.HTTP_200_OK, True),
        ("non-existent-id-999", None, status.HTTP_404_NOT_FOUND, False),
    ]

    @pytest.mark.parametrize("query_id, setup_id, expected_code, match_data", GET_DEVICE_ID_TEST_CASES)
    @pytest.mark.asyncio
    async def test_get_device_with_various_ids(
            self, test_app_client, redis_client_fixture,
            query_id: str, setup_id: Optional[str], expected_code: int, match_data: bool
    ):
        """Test retrieving devices with various IDs."""

        expected_device_json = None
        if setup_id:
            device_payload_for_redis = {
                "name": f"Device {setup_id}",
                "type": "param_test_type",
                "status": "testing",
                "online": "true"
            }
            await redis_client_fixture.hset(f"device:{setup_id}", mapping=device_payload_for_redis)
            if match_data:
                expected_device_json = {
                    "id": setup_id,
                    "name": device_payload_for_redis["name"],
                    "type": device_payload_for_redis["type"],
                    "status": device_payload_for_redis["status"],
                    "online": True
                }

        response = test_app_client.get(f"/devices/{query_id}")
        assert response.status_code == expected_code

        response_json = response.json()
        if expected_code == status.HTTP_200_OK and match_data:
            assert response_json == expected_device_json
            Device(**response_json)
        elif expected_code == status.HTTP_404_NOT_FOUND:
            assert "detail" in response_json
            assert "not found" in response_json["detail"].lower()
