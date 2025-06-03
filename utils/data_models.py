# models.py
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Dict, Any

"""Data models for device management in endpoints."""

class DeviceBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Smart Thermostat"})
    type: str = Field(..., json_schema_extra={"example": "thermostat"})
    status: str = Field(default="active", json_schema_extra={"example": "active"})


class Device(DeviceBase):
    id: str = Field(..., json_schema_extra={"example": "device-001"})
    online: bool = Field(..., json_schema_extra={"example": True})


class CommandPayload(BaseModel):
    action: str = Field(..., json_schema_extra={"example": "set_temperature"})
    parameters: Dict[str, Any] = Field(default_factory=dict, json_schema_extra={"example": {"value": 25.0}})


class CommandReceipt(BaseModel):
    message: str = Field(..., json_schema_extra={"example": "Command sent successfully and logged."})
    device_id: str = Field(..., json_schema_extra={"example": "device-001"})
    command_received: Dict[str, Any] = Field(..., json_schema_extra={"example": {
        "action": "set_brightness",
        "parameters": {"level": 80}
    }})
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),)


class CommandResponse(BaseModel):
    message: str = Field(..., json_schema_extra={"example": "Command processed."})
    device_id: str = Field(..., json_schema_extra={"example": "device-001"})
    action_performed: str = Field(..., json_schema_extra={"example": "set_temperature"})
    timestamp: datetime = Field(..., json_schema_extra={"example": datetime.now(timezone.utc)})
