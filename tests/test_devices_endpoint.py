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
    device_ids = []  # You collect IDs for potential explicit cleanup
    num_devices_to_create = 10

    for i in range(num_devices_to_create):
        device_id = f"benchmark-device-{i}"
        # Data to be stored in Redis hash
        # Note: 'id' is part of the key, typically not stored in the hash itself again.
        # 'online' should be stored as a string ("true"/"false") for your app's helper.
        device_data_for_redis = {
            "name": f"Benchmark Device {i}",
            "type": "test-device",
            "status": "online" if i % 2 == 0 else "offline",
            "online": "true" if i % 2 == 0 else "false"
        }
        # Store device in Redis - with await
        await redis_client_fixture.hset(f"device:{device_id}", mapping=device_data_for_redis)
        device_ids.append(device_id)  # Collect for explicit cleanup, if desired

    # The benchmark() fixture runs the target_api_call multiple times.
    # The setup above is performed once before these benchmark runs.
    # This is good because you're benchmarking the API call, not the setup.
    try:
        def target_api_call(client):
            response = client.get("/devices")
            assert response.status_code == status.HTTP_200_OK
            devices = response.json()
            assert len(devices) == num_devices_to_create
            return response

        # Run benchmark
        benchmark(target_api_call, test_app_client)
    except Exception as e:
        pytest.fail(f"Benchmark failed: {e}")
