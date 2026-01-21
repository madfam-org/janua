"""
IoT and Edge device API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
from pydantic import BaseModel
import logging

from ...database import get_db
from app.dependencies import require_admin
from ...models import User
from ...models.iot import IoTDevice, DeviceType, DeviceStatus, AuthMethod

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/iot",
    tags=["IoT Devices"],
    responses={404: {"description": "Not found"}},
)

class IoTDeviceCreate(BaseModel):
    device_id: str
    device_name: Optional[str] = None
    device_type: DeviceType
    auth_method: AuthMethod
    capabilities: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None

@router.post("/devices")
async def register_device(
    organization_id: str,
    device: IoTDeviceCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Register new IoT device"""
    try:
        iot_device = IoTDevice(
            organization_id=organization_id,
            device_id=device.device_id,
            device_name=device.device_name,
            device_type=device.device_type,
            auth_method=device.auth_method,
            capabilities=device.capabilities or {},
            config=device.config or {}
        )
        
        db.add(iot_device)
        await db.commit()
        
        return {
            "device_id": str(iot_device.id),
            "status": iot_device.status.value,
            "message": "Device registered successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to register IoT device: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/devices")
async def list_devices(
    organization_id: str,
    status: Optional[DeviceStatus] = None,
    device_type: Optional[DeviceType] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List IoT devices"""
    try:
        query = select(IoTDevice).where(IoTDevice.organization_id == organization_id)
        
        if status:
            query = query.where(IoTDevice.status == status)
        if device_type:
            query = query.where(IoTDevice.device_type == device_type)
        
        result = await db.execute(query)
        devices = result.scalars().all()
        
        return [
            {
                "id": str(device.id),
                "device_id": device.device_id,
                "device_name": device.device_name,
                "device_type": device.device_type.value,
                "status": device.status.value,
                "is_online": device.is_online,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                "created_at": device.created_at.isoformat()
            }
            for device in devices
        ]
        
    except Exception as e:
        logger.error(f"Failed to list IoT devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))