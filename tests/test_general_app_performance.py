import pytest
from fastapi import status


import asyncio


# high concurrency test
@pytest.mark.asyncio
async def test_high_concurrency(test_app_client, online_device_fixture):
    """Test high concurrency by sending multiple commands to the same device."""
    device_id = online_device_fixture["id"]
    command_payload = {"action": "concurrent_action", "parameters": {"value": 123}}

    async def send_request():
        response = test_app_client.post(f"/devices/{device_id}/command", json=command_payload)
        assert response.status_code == status.HTTP_200_OK

    tasks = [send_request() for _ in range(100)]  # Simulate 100 concurrent requests
    await asyncio.gather(*tasks)


# large payload test

def test_large_payload(benchmark, test_app_client, online_device_fixture):
    """Benchmark sending a large payload to a device."""
    device_id = online_device_fixture["id"]
    large_payload = {
        "action": "bulk_update",
        "parameters": {"data": [{"key": f"value_{i}"} for i in range(100)]}
    }

    def target_api_call(client, dev_id, payload):
        response = client.post(f"/devices/{dev_id}/command", json=payload)
        assert response.status_code == status.HTTP_200_OK

    benchmark(target_api_call, test_app_client, device_id, large_payload)


#database load test
@pytest.mark.asyncio
async def test_large_database_load(redis_client_fixture, test_app_client):
    """Test retrieving a large number of devices from Redis."""
    # Populate Redis with 10,000 devices
    for i in range(100):
        device_data_in_redis = {
            "name": f"Living Room Thermostat {i}",
            "type": "test_device_type",
            "status": "active",
            "online": "true"
        }
        await redis_client_fixture.hset(f"device:device_{i}", mapping=device_data_in_redis)

    response = test_app_client.get("/devices")
    assert response.status_code == status.HTTP_200_OK
    print(f"Number of devices returned: {len(response.json())}")
    # Check if we received all 100 devices
    assert len(response.json()) == 100