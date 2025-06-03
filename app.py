# app.py
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status
import redis.asyncio as redis
from redis import exceptions as redis_exceptions
from typing import List, Optional, Dict, Any
import json
from datetime import datetime, timezone
import logging
from utils.data_models import Device, CommandPayload, CommandResponse

# Import application settings and the Settings class
from config.app_config import get_app_settings, Settings
from utils.redis_helper import get_device_data_from_redis

# Initialize settings early
settings: Settings = get_app_settings()

# --- Logging Setup ---
logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__)


# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, e.g., Redis pool."""
    logger.info("Application startup sequence initiated...now from lifepspan.")
    try:
        await initialize_redis_pool()
    except Exception as e:
        # If pool initialization fails, log critical error
        logger.critical(
            f"CRITICAL: Failed to initialize Redis pool on startup: {e}. Application might not function correctly.")
        # Example: raise SystemExit("Failed to initialize critical resources.") # This would stop the app
    yield
    """Clean up resources on shutdown, e.g., close Redis pool."""
    global redis_connection_pool
    if redis_connection_pool:
        logger.info("Application shutdown sequence initiated: Closing Redis connection pool.")
        # For redis.asyncio.ConnectionPool, disconnect closes all connections in the pool.
        await redis_connection_pool.disconnect()
        logger.info("Redis connection pool disconnected.")


# --- FastAPI App ---
app = FastAPI(
    title="Device Simulator API",
    version="0.1.0",
    description="A configurable service to simulate IoT devices with Redis, featuring connection pooling, "
                "transactions, and robust error handling.",
    lifespan=lifespan)

# --- Redis Connection Pool ---
redis_connection_pool: Optional[redis.ConnectionPool] = None


async def initialize_redis_pool():
    """Initializes the Redis connection pool."""
    global redis_connection_pool
    if redis_connection_pool is None:
        redis_url = settings.get_redis_url()
        logger.info(
            f"Initializing Redis connection pool for URL: {redis_url.replace(settings.REDIS_PASSWORD, '*****') if settings.REDIS_PASSWORD else redis_url} (max_connections: {settings.REDIS_MAX_CONNECTIONS})")
        try:
            redis_connection_pool = redis.ConnectionPool.from_url(
                redis_url,
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS
            )
            # Test the connection pool by acquiring a connection and pinging
            async with redis.Redis(connection_pool=redis_connection_pool) as r_conn:
                await r_conn.ping()
            logger.info("Redis connection pool initialized and tested successfully.")
        except redis_exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Redis and initialize pool: {e}")
            redis_connection_pool = None  # Ensure pool is None if creation failed
            # This exception will be caught by the startup event handler
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during Redis pool initialization: {e}")
            redis_connection_pool = None
            raise


async def get_redis_connection() -> redis.Redis:
    """
    FastAPI dependency to get a Redis connection from the pool.
    Raises HTTPException if the pool is not available or connection fails.
    """
    if redis_connection_pool is None:
        logger.error("Redis connection pool is not initialized.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service is not available (pool not initialized)."
        )

    try:
        # Create a new client instance using the established pool.
        # The client will borrow a connection from the pool.
        r_client = redis.Redis(connection_pool=redis_connection_pool)
        # Optionally, ping to ensure connection health, though pool should manage this.

        yield r_client
    except redis_exceptions.ConnectionError as e:
        logger.error(f"Failed to get Redis connection from pool: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not connect to Redis: {e}"
        )
    finally:
        # Ensure connection is released back to the pool
        if 'r_client' in locals() and r_client:
            await r_client.aclose()


# --- API Endpoints ---
@app.get("/devices", response_model=List[Device], summary="List all simulated devices")
async def list_all_devices(r: redis.Redis = Depends(get_redis_connection)):
    """ Lists all devices stored in Redis."""
    device_ids = []
    try:
        cursor = '0'
        while cursor != 0:
            cursor, keys = await r.scan(cursor=cursor, match="device:*", count=50)
            for key in keys:
                if not key.endswith(":commands"):
                    parts = key.split(":", 1)
                    if len(parts) == 2:
                        device_ids.append(parts[1])
        unique_device_ids = sorted(list(set(device_ids)))

        devices_out = []
        for device_id_str in unique_device_ids:
            device_data = await get_device_data_from_redis(r, device_id_str)
            if device_data:
                devices_out.append(device_data)
        return devices_out
    except redis_exceptions.RedisError as e:
        logger.error(f"Redis error while listing devices: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Error communicating with data store.")
    except Exception as e:
        logger.error(f"Unexpected error in list_all_devices: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")


@app.get("/devices/{device_id}", response_model=Device, summary="Get details of a specific device")
async def get_specific_device(device_id: str, r: redis.Redis = Depends(get_redis_connection)):
    """ Retrieves details of a specific device by its ID."""
    try:
        device = await get_device_data_from_redis(r, device_id)
        if device is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device with ID '{device_id}' not found"
            )
        return device
    except HTTPException:
        # Re-raise HTTPExceptions to maintain proper status codes
        raise

    except redis_exceptions.RedisError as e:
        logger.error(f"Redis error getting device {device_id}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Error communicating with data store.")
    except Exception as e:
        logger.error(f"Unexpected error in get_specific_device for {device_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")


@app.post("/devices/{device_id}/command", response_model=CommandResponse, summary="Send a command to a device")
async def send_device_command(device_id: str, command: Dict[str, Any], r: redis.Redis = Depends(get_redis_connection)):
    """ Sends a command to a specific device and logs the command in Redis.
        The command must match the CommandPayload model structure.
    """
    try:
        parsed_command = CommandPayload(**command)
    except Exception as e:  # PydanticValidationError
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid command structure: {str(e)}"
        )

    try:
        device = await get_device_data_from_redis(r, device_id)
        if device is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device with ID '{device_id}' not found. Cannot send command."
            )
        if not device.online:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device '{device_id}' is offline. Cannot send command."
            )

        command_history_key = f"device:{device_id}:commands"
        current_time = datetime.now(timezone.utc)
        command_to_log = {
            "action": parsed_command.action,
            "parameters": parsed_command.parameters,
            "timestamp": current_time.isoformat()
        }

        # Use a pipeline for atomic LPUSH and LTRIM
        async with r.pipeline(transaction=True) as pipe:  # transaction=True enables MULTI/EXEC
            await pipe.lpush(command_history_key, json.dumps(command_to_log))
            await pipe.ltrim(command_history_key, 0, 99)  # Keep last 100 commands
            await pipe.execute()  # Execute the transaction

        return CommandResponse(
            message="Command received, processed, and logged successfully.",
            device_id=device_id,
            action_performed=parsed_command.action,
            timestamp=current_time
        )
    except redis_exceptions.RedisError as e:
        logger.error(f"Redis error sending command to device {device_id}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Error communicating with data store.")
    except HTTPException:  # Re-raise HTTPExceptions from device checks
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending command to {device_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")


# --- Health Check Endpoint ---
@app.get("/health", status_code=status.HTTP_200_OK, tags=["Management"])
async def health_check(
        r: Optional[redis.Redis] = Depends(get_redis_connection, use_cache=False)):  # use_cache=False for health checks
    """
    Provides a basic health check for the service, including for Redis connectivity.
    """
    redis_status = "unavailable"
    if r:  # Check if dependency provided a connection
        try:
            await r.ping()
            redis_status = "healthy"
        except redis_exceptions.RedisError as e:
            logger.warning(f"Health check: Redis ping failed: {e}")
            redis_status = "unhealthy"
        # Connection is automatically closed by Depends on if 'r' was successfully yielded

    return {
        "application_status": "healthy",
        "redis_status": redis_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    # Get settings once at startup
    app_settings = get_app_settings()
    # Use the configured host and port
    uvicorn.run(
        "app:app",
        host=app_settings.API_HOST,
        port=app_settings.API_PORT,
        log_level=app_settings.LOG_LEVEL.lower(),
        reload=False  # Set to True during development
    )
