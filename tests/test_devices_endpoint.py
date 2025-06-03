# tests/test_devices_endpoint.py
import pytest
from fastapi import status
from utils.data_models import Device


@pytest.mark.asyncio
async def test_get_devices_empty(test_app_client, redis_client_fixture):
    """Test retrieving devices when no devices are present."""
    response = test_app_client.get("/devices")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_devices_with_data(test_app_client, online_device_fixture, offline_device_fixture):
    """Test retrieving devices when test devices are present."""
    response = test_app_client.get("/devices")
    assert response.status_code == status.HTTP_200_OK
    devices_response = response.json()

    assert len(devices_response) == 2
    devices_map = {d["id"]: d for d in devices_response}

    assert online_device_fixture["id"] in devices_map
    assert devices_map[online_device_fixture["id"]] == online_device_fixture
    assert offline_device_fixture["id"] in devices_map
    assert devices_map[offline_device_fixture["id"]] == offline_device_fixture

    for device_data in devices_response:
        Device(**device_data)


@pytest.mark.benchmark
def test_benchmark_get_all_devices(benchmark, test_app_client):
    """Benchmark for retrieving all devices."""

    def target_api_call(client):
        response = client.get("/devices")
        assert response.status_code == status.HTTP_200_OK

    benchmark(target_api_call, test_app_client)


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_get_ten_devices(benchmark, test_app_client, redis_client_fixture):
    """Benchmark retrieving 10 devices."""
    # Setup 10 devices in Redis
    device_ids = []
    for i in range(10):
        device_id = f"benchmark-device-{i}"
        device_data = {
            "id": device_id,
            "name": f"Benchmark Device {i}",
            "type": "test-device",
            "status": "online" if i % 2 == 0 else "offline",
            "online": i % 2 == 0
        }
        # Store device in Redis - with await
        await redis_client_fixture.hset(f"device:{device_id}", mapping=device_data)
        device_ids.append(device_id)

    try:
        # Use a wrapper function that handles async operations for the benchmark
        def target_api_call(client):
            response = client.get("/devices")
            assert response.status_code == status.HTTP_200_OK
            devices = response.json()
            benchmark_devices = [d for d in devices if d["id"].startswith("benchmark-device-")]
            assert len(benchmark_devices) >= 10
            return response

        # Run benchmark
        benchmark(target_api_call, test_app_client)

    finally:
        # Clean up with await
        for device_id in device_ids:
            await redis_client_fixture.delete(f"device:{device_id}")