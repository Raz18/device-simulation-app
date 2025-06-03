# conftest.py (snippet for redis_client_fixture update)
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from fastapi.testclient import TestClient
import asyncio

from app import app  # The FastAPI app instance
from config.app_config import get_app_settings  # Import settings to use for test Redis client

settings = get_app_settings()  # Get settings for test configuration


@pytest.fixture(scope="session")
def event_loop(request):
    """Create a new event loop for the test session."""
    # ... (same as before)
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def redis_client_fixture():
    # settings from config.py for the test Redis client
    # This ensures tests run against the same DB the app would use by default
    redis_url_for_tests = settings.get_redis_url()  # Uses configured host, port, db, password

    client = redis_async.from_url(redis_url_for_tests, decode_responses=True)

    await client.ping()
    await client.flushdb()  # Clear DB before test
    yield client
    await client.flushdb()  # Clear DB after test
    await client.aclose()  # Use aclose for async client


@pytest.fixture(scope="session")
def test_app_client():
    """Create a TestClient for the FastAPI app."""
    # TestClient will use the app instance which internally uses the configured settings
    with TestClient(app) as client:
        yield client


# ... (online_device_fixture, offline_device_fixture remain the same logic) ...
@pytest_asyncio.fixture(scope="function")
async def online_device_fixture(redis_client_fixture: redis_async.Redis):
    """Fixture for an online device."""
    device_id = "online-dev-001"
    device_data_in_redis = {
        "name": "Living Room Thermostat",
        "type": "thermostat",
        "status": "active",
        "online": "true"
    }
    await redis_client_fixture.hset(f"device:{device_id}", mapping=device_data_in_redis)
    expected_api_data = {
        "id": device_id,
        "name": "Living Room Thermostat",
        "type": "thermostat",
        "status": "active",
        "online": True
    }
    yield expected_api_data


@pytest_asyncio.fixture(scope="function")
async def offline_device_fixture(redis_client_fixture: redis_async.Redis):
    """Fixture for an offline device."""
    device_id = "offline-dev-002"
    device_data_in_redis = {
        "name": "Bedroom Lamp",
        "type": "light",
        "status": "inactive",
        "online": "false"
    }
    await redis_client_fixture.hset(f"device:{device_id}", mapping=device_data_in_redis)
    expected_api_data = {
        "id": device_id,
        "name": "Bedroom Lamp",
        "type": "light",
        "status": "inactive",
        "online": False
    }
    yield expected_api_data
