# tests/test_command_device_endpoint.py
import pytest
import json
from fastapi import status
from typing import Dict, Any, Optional
from utils.data_models import CommandResponse
import redis.asyncio as redis_async_lib


@pytest.mark.asyncio
async def test_send_command_to_online_device(test_app_client, online_device_fixture,
                                             redis_client_fixture: redis_async_lib.Redis):
    """Test sending a command to an online device and verify command history is stored in Redis."""
    device_id = online_device_fixture["id"]
    command_payload_dict = {"action": "set_brightness", "parameters": {"level": 80}}

    response = test_app_client.post(f"/devices/{device_id}/command", json=command_payload_dict)

    assert response.status_code == status.HTTP_200_OK
    receipt_data = response.json()
    CommandResponse(**receipt_data)
    assert receipt_data["message"] == "Command received, processed, and logged successfully."
    assert receipt_data["device_id"] == device_id
    assert receipt_data["action_performed"] == command_payload_dict["action"]

    command_history_json = await redis_client_fixture.lrange(f"device:{device_id}:commands", 0, -1)
    assert len(command_history_json) == 1

    stored_command = json.loads(command_history_json[0])
    print(stored_command)  # Debug print to see the stored command structure
    assert stored_command["action"] == command_payload_dict["action"]
    assert stored_command["parameters"] == command_payload_dict["parameters"]



@pytest.mark.asyncio
async def test_send_command_to_device_after_turning_online(
        test_app_client,
        offline_device_fixture,
        redis_client_fixture: redis_async_lib.Redis
):
    """Test sending a command to a device after it has been turned online mid test."""
    device_id = offline_device_fixture["id"]

    # Verify the device is initially offline
    response = test_app_client.get(f"/devices/{device_id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["online"] == False

    # Turn the device online by updating Redis
    await redis_client_fixture.hset(f"device:{device_id}", "online", "true")

    # Verify the device is now online
    response = test_app_client.get(f"/devices/{device_id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["online"] == True

    # Send a command to the device
    command_payload = {"action": "power_on", "parameters": {"mode": "normal"}}
    response = test_app_client.post(f"/devices/{device_id}/command", json=command_payload)

    # Verify the command was accepted
    assert response.status_code == status.HTTP_200_OK
    receipt_data = response.json()
    assert receipt_data["device_id"] == device_id
    assert receipt_data["action_performed"] == command_payload["action"]

    # Verify the command was logged in Redis
    command_history_json = await redis_client_fixture.lrange(f"device:{device_id}:commands", 0, -1)
    assert len(command_history_json) == 1

    stored_command = json.loads(command_history_json[0])
    assert stored_command["action"] == command_payload["action"]
    assert stored_command["parameters"] == command_payload["parameters"]


@pytest.mark.asyncio
async def test_send_command_to_offline_device(test_app_client, offline_device_fixture):
    """Test sending a command to an offline device should return an error."""
    device_id = offline_device_fixture["id"]
    command_payload = {"action": "activate_eco_mode"}

    response = test_app_client.post(f"/devices/{device_id}/command", json=command_payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == f"Device '{device_id}' is offline. Cannot send command."


@pytest.mark.asyncio
async def test_send_command_to_non_existent_device(test_app_client, redis_client_fixture):
    """Test sending a command to a non-existent device should return a 404 error."""
    device_id = "ghost-device-404"
    command_payload = {"action": "self_destruct"}

    response = test_app_client.post(f"/devices/{device_id}/command", json=command_payload)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == f"Device with ID '{device_id}' not found. Cannot send command."


@pytest.mark.asyncio
async def test_command_with_invalid_structure(test_app_client, online_device_fixture):
    """Test sending a command with an invalid structure should return a 400 error."""
    device_id = online_device_fixture["id"]
    # Missing required action field
    invalid_command = {"parameters": {"value": 25}}
    response = test_app_client.post(f"/devices/{device_id}/command", json=invalid_command)
    assert response.status_code == 400


@pytest.mark.benchmark
def test_benchmark_send_command_to_device(benchmark, test_app_client, online_device_fixture):
    """Benchmark sending a command to an online device."""
    device_id = online_device_fixture["id"]
    command_payload = {"action": "benchmark_action", "parameters": {"value": 12345}}

    def target_api_call(client, dev_id, payload):
        response = client.post(f"/devices/{dev_id}/command", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["action_performed"] == payload["action"]

    benchmark(target_api_call, test_app_client, device_id, command_payload)


@pytest.mark.benchmark
def test_benchmark_send_command_to_online_device_with_complex_payload(benchmark, test_app_client,
                                                                      online_device_fixture):
    """Benchmark sending a complex command to an online device."""
    device_id = online_device_fixture["id"]
    complex_payload = {
        "action": "configure_settings",
        "parameters": {
            "temperature": 22.5,
            "humidity": 45,
            "mode": "auto",
            "schedule": [
                {"time": "08:00", "temp": 21.0},
                {"time": "18:00", "temp": 22.5},
                {"time": "22:00", "temp": 20.0}
            ],
            "notifications": True
        }
    }

    def target_api_call(client, dev_id, payload):
        response = client.post(f"/devices/{dev_id}/command", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["action_performed"] == payload["action"]

    benchmark(target_api_call, test_app_client, device_id, complex_payload)


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_benchmark_rapid_commands_sequence(benchmark, test_app_client, online_device_fixture,
                                                 redis_client_fixture):
    """Benchmark sending multiple commands in rapid succession to test handling of command history."""
    device_id = online_device_fixture["id"]
    command_payload = {"action": "simple_action", "parameters": {}}

    def target_api_call(client, dev_id, payload):
        # Send 20 commands in quick succession to test performance under load
        responses = []
        for i in range(20):
            modified_payload = {
                "action": f"{payload['action']}_{i}",
                "parameters": {"sequence": i}
            }
            response = client.post(f"/devices/{dev_id}/command", json=modified_payload)
            responses.append(response)

        # Verify all responses were successful
        for i, response in enumerate(responses):
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["action_performed"] == f"{payload['action']}_{i}"

    benchmark(target_api_call, test_app_client, device_id, command_payload)

    # Verify command history was properly maintained (outside of benchmark)
    command_history = await redis_client_fixture.lrange(f"device:{device_id}:commands", 0, -1)
    assert len(command_history) >= 20


class TestDeviceCommandEndpointParameterized:
    """Group of parameterized tests for data based testing for the POST /devices/{device_id}/command endpoint."""

    COMMAND_PAYLOAD_TEST_CASES = [
        ({"action": "set_thermostat", "parameters": {"temperature": 22.5}}, status.HTTP_200_OK, None),
        ({"action": "ring_alarm", "parameters": {}}, status.HTTP_200_OK, None),
        ({"action": "short_action"}, status.HTTP_200_OK, None),
        ({}, status.HTTP_400_BAD_REQUEST, "Invalid command structure"),
        ({"parameters": {"some_param": "some_value"}}, status.HTTP_400_BAD_REQUEST, "Invalid command structure"),
        ({"action": None, "parameters": {}}, status.HTTP_400_BAD_REQUEST, "Invalid command structure"),
        ({"action": "update_firmware", "parameters": "this_should_be_a_dict"}, status.HTTP_400_BAD_REQUEST,
         "Invalid command structure"),
        ({"action": 123, "parameters": {}}, status.HTTP_400_BAD_REQUEST, "Invalid command structure"),
    ]

    @pytest.mark.parametrize("payload, expected_code, detail_substring", COMMAND_PAYLOAD_TEST_CASES)
    @pytest.mark.asyncio  # Important: Mark as asyncio to use async fixtures
    async def test_send_command_with_various_payloads(
            self, test_app_client, online_device_fixture,
            payload: Dict[str, Any], expected_code: int, detail_substring: Optional[str]
    ):
        """Test sending commands with various payloads to the device command endpoint."""
        device_id = online_device_fixture["id"]

        response = test_app_client.post(f"/devices/{device_id}/command", json=payload)
        assert response.status_code == expected_code

        response_json = response.json()
        if detail_substring:
            assert "detail" in response_json, "Error response missing 'detail' field."
            assert detail_substring.lower() in response_json["detail"].lower()
        elif expected_code == status.HTTP_200_OK:
            CommandResponse(**response_json)
            assert response_json.get("action_performed") == payload.get("action")
            assert response_json.get("device_id") == device_id
