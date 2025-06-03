# utils/redis_helpers.py
import redis.asyncio as redis
from pydantic import ValidationError
from redis import exceptions as redis_exceptions
from typing import Optional
import logging  # Added for consistency

# Import Device model from app.py.
from utils.data_models import Device

logger = logging.getLogger(__name__)


async def get_device_data_from_redis(r: redis.Redis, device_id: str) -> Optional[Device]:
    """Fetch device data from Redis and return a Device instance."""
    device_key = f"device:{device_id}"
    try:
        raw_data = await r.hgetall(device_key)
        if not raw_data:
            return None

        raw_data["online"] = raw_data.get("online", "false").lower() == "true"
        raw_data["id"] = device_id

        device_instance = Device(**raw_data)
        return device_instance
    except redis_exceptions.ConnectionError as e:
        logger.error(f"Redis error fetching data for device {device_id} from key {device_key}: {e}")
        # Depending on policy, could re-raise a custom app exception or return None
        return None
    except ValidationError as e:
        logger.error(f"Data validation error for device {device_id} (key: {device_key}): {e}. Raw data: {raw_data}")
        raise  # Re-raise ValidationError to be handled by the endpoint, possibly as a 500 or a specific 400/422
    except Exception as e:  # Catch Pydantic validation errors or other unexpected issues
        logger.error(
            f"Error parsing data for device {device_id} (key: {device_key}): {e}. Raw data: {raw_data if 'raw_data' in locals() else 'N/A'}")
        raise RuntimeError(f"Unexpected parsing error for device {device_id}") from e
