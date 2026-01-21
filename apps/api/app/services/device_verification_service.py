"""
Device Verification Service

Provides functionality for managing trusted devices and detecting new/unknown devices.
This helps prevent unauthorized access and allows users to manage their device security.
"""

import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

# Optional user_agents library for better device detection
try:
    from user_agents import parse as parse_user_agent
    HAS_USER_AGENTS = True
except ImportError:
    HAS_USER_AGENTS = False

    def parse_user_agent(ua_string: str):
        """Fallback user agent parser when user_agents library is not available."""
        class FallbackUA:
            def __init__(self, ua: str):
                self.ua = ua
                # Simple browser detection
                self.browser = type('Browser', (), {'family': 'Unknown', 'version_string': ''})()
                self.os = type('OS', (), {'family': 'Unknown', 'version_string': ''})()
                self.device = type('Device', (), {'family': 'Unknown', 'brand': None, 'model': None})()

                # Basic parsing
                if 'Chrome' in ua:
                    self.browser.family = 'Chrome'
                elif 'Firefox' in ua:
                    self.browser.family = 'Firefox'
                elif 'Safari' in ua:
                    self.browser.family = 'Safari'
                elif 'Edge' in ua:
                    self.browser.family = 'Edge'

                if 'Windows' in ua:
                    self.os.family = 'Windows'
                elif 'Mac OS' in ua or 'Macintosh' in ua:
                    self.os.family = 'Mac OS X'
                elif 'Linux' in ua:
                    self.os.family = 'Linux'
                elif 'Android' in ua:
                    self.os.family = 'Android'
                elif 'iOS' in ua or 'iPhone' in ua or 'iPad' in ua:
                    self.os.family = 'iOS'

        return FallbackUA(ua_string)

from app.models import Session, TrustedDevice

logger = structlog.get_logger(__name__)


class DeviceVerificationService:
    """Service for managing device verification and trusted devices."""

    @staticmethod
    def generate_device_fingerprint(
        user_agent: Optional[str],
        ip_address: Optional[str] = None,
        additional_data: Optional[str] = None,
    ) -> str:
        """
        Generate a unique fingerprint for a device based on available data.

        Note: This is a basic implementation. For production, consider using
        browser fingerprinting libraries on the client side for more accuracy.

        Args:
            user_agent: Browser/app user agent string
            ip_address: Client IP (optional, not recommended for fingerprint as it changes)
            additional_data: Any additional identifying data from client

        Returns:
            A hex string fingerprint
        """
        # Combine available data for fingerprinting
        # Note: We intentionally don't include IP as it changes frequently
        fingerprint_data = []

        if user_agent:
            # Parse user agent to extract stable components
            try:
                ua = parse_user_agent(user_agent)
                fingerprint_data.append(f"browser:{ua.browser.family}:{ua.browser.version_string}")
                fingerprint_data.append(f"os:{ua.os.family}:{ua.os.version_string}")
                fingerprint_data.append(f"device:{ua.device.family}")
            except Exception:
                # Fall back to raw user agent
                fingerprint_data.append(f"ua:{user_agent}")

        if additional_data:
            fingerprint_data.append(f"extra:{additional_data}")

        # Generate fingerprint hash
        fingerprint_string = "|".join(fingerprint_data)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]

    @staticmethod
    def get_friendly_device_name(user_agent: Optional[str]) -> str:
        """
        Generate a user-friendly device name from user agent.

        Args:
            user_agent: Browser/app user agent string

        Returns:
            A friendly name like "Chrome on Windows" or "Safari on iPhone"
        """
        if not user_agent:
            return "Unknown Device"

        try:
            ua = parse_user_agent(user_agent)
            browser = ua.browser.family or "Unknown Browser"
            os_name = ua.os.family or "Unknown OS"

            if ua.is_mobile:
                device = ua.device.family or "Mobile"
                return f"{browser} on {device}"
            elif ua.is_tablet:
                device = ua.device.family or "Tablet"
                return f"{browser} on {device}"
            else:
                return f"{browser} on {os_name}"
        except Exception:
            return "Unknown Device"

    @staticmethod
    async def is_device_trusted(
        db: AsyncSession,
        user_id: UUID,
        device_fingerprint: str,
    ) -> Tuple[bool, Optional[TrustedDevice]]:
        """
        Check if a device is trusted for a user.

        Args:
            db: Database session
            user_id: User ID
            device_fingerprint: Device fingerprint to check

        Returns:
            Tuple of (is_trusted, trusted_device_record)
        """
        result = await db.execute(
            select(TrustedDevice).where(
                and_(
                    TrustedDevice.user_id == user_id,
                    TrustedDevice.device_fingerprint == device_fingerprint,
                )
            )
        )
        trusted_device = result.scalar_one_or_none()

        if not trusted_device:
            return False, None

        # Check if trust has expired
        if trusted_device.trust_expires_at and trusted_device.trust_expires_at < datetime.utcnow():
            return False, trusted_device

        return True, trusted_device

    @staticmethod
    async def trust_device(
        db: AsyncSession,
        user_id: UUID,
        device_fingerprint: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        device_name: Optional[str] = None,
        trust_duration_days: Optional[int] = 30,
    ) -> TrustedDevice:
        """
        Mark a device as trusted for a user.

        Args:
            db: Database session
            user_id: User ID
            device_fingerprint: Device fingerprint
            user_agent: User agent string
            ip_address: IP address
            device_name: Custom device name (optional)
            trust_duration_days: Days to trust device (None = permanent)

        Returns:
            The TrustedDevice record
        """
        # Check if device already trusted
        result = await db.execute(
            select(TrustedDevice).where(
                and_(
                    TrustedDevice.user_id == user_id,
                    TrustedDevice.device_fingerprint == device_fingerprint,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing trust
            existing.last_used_at = datetime.utcnow()
            existing.last_ip_address = ip_address
            if trust_duration_days:
                existing.trust_expires_at = datetime.utcnow() + timedelta(days=trust_duration_days)
            else:
                existing.trust_expires_at = None
            await db.commit()
            logger.info(
                "Updated existing trusted device",
                user_id=str(user_id),
                device_fingerprint=device_fingerprint[:8] + "...",
            )
            return existing

        # Create new trusted device
        friendly_name = device_name or DeviceVerificationService.get_friendly_device_name(user_agent)
        trust_expires = datetime.utcnow() + timedelta(days=trust_duration_days) if trust_duration_days else None

        trusted_device = TrustedDevice(
            user_id=user_id,
            device_fingerprint=device_fingerprint,
            device_name=friendly_name,
            user_agent=user_agent,
            ip_address=ip_address,
            last_ip_address=ip_address,
            trust_expires_at=trust_expires,
            last_used_at=datetime.utcnow(),
        )

        db.add(trusted_device)
        await db.commit()
        await db.refresh(trusted_device)

        logger.info(
            "New device trusted",
            user_id=str(user_id),
            device_fingerprint=device_fingerprint[:8] + "...",
            device_name=friendly_name,
        )

        return trusted_device

    @staticmethod
    async def revoke_device_trust(
        db: AsyncSession,
        user_id: UUID,
        device_id: UUID,
    ) -> bool:
        """
        Revoke trust for a specific device.

        Args:
            db: Database session
            user_id: User ID
            device_id: TrustedDevice ID to revoke

        Returns:
            True if device was revoked, False if not found
        """
        result = await db.execute(
            select(TrustedDevice).where(
                and_(
                    TrustedDevice.id == device_id,
                    TrustedDevice.user_id == user_id,
                )
            )
        )
        device = result.scalar_one_or_none()

        if not device:
            return False

        await db.delete(device)
        await db.commit()

        logger.info(
            "Device trust revoked",
            user_id=str(user_id),
            device_id=str(device_id),
            device_name=device.device_name,
        )

        return True

    @staticmethod
    async def revoke_all_devices(
        db: AsyncSession,
        user_id: UUID,
        except_device_fingerprint: Optional[str] = None,
    ) -> int:
        """
        Revoke trust for all devices of a user.

        Args:
            db: Database session
            user_id: User ID
            except_device_fingerprint: Optional fingerprint to keep (current device)

        Returns:
            Number of devices revoked
        """
        query = delete(TrustedDevice).where(TrustedDevice.user_id == user_id)

        if except_device_fingerprint:
            query = query.where(TrustedDevice.device_fingerprint != except_device_fingerprint)

        result = await db.execute(query)
        await db.commit()

        revoked_count = result.rowcount
        logger.info(
            "All device trust revoked",
            user_id=str(user_id),
            revoked_count=revoked_count,
            kept_current=bool(except_device_fingerprint),
        )

        return revoked_count

    @staticmethod
    async def list_trusted_devices(
        db: AsyncSession,
        user_id: UUID,
    ) -> List[TrustedDevice]:
        """
        Get all trusted devices for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of TrustedDevice records
        """
        result = await db.execute(
            select(TrustedDevice)
            .where(TrustedDevice.user_id == user_id)
            .order_by(TrustedDevice.last_used_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_active_sessions(
        db: AsyncSession,
        user_id: UUID,
    ) -> List[Session]:
        """
        Get all active sessions for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of active Session records
        """
        result = await db.execute(
            select(Session)
            .where(
                and_(
                    Session.user_id == user_id,
                    Session.is_active == True,
                    Session.expires_at > datetime.utcnow(),
                )
            )
            .order_by(Session.last_activity.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_session_device_info(
        db: AsyncSession,
        session_id: UUID,
        device_fingerprint: str,
        is_trusted: bool = False,
    ) -> None:
        """
        Update a session with device fingerprint information.

        Args:
            db: Database session
            session_id: Session ID
            device_fingerprint: Device fingerprint
            is_trusted: Whether this is a trusted device
        """
        await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(
                device_fingerprint=device_fingerprint,
                is_trusted_device=is_trusted,
            )
        )
        await db.commit()

    @staticmethod
    async def is_new_device_for_user(
        db: AsyncSession,
        user_id: UUID,
        device_fingerprint: str,
    ) -> bool:
        """
        Check if this is a new/unknown device for the user.

        Args:
            db: Database session
            user_id: User ID
            device_fingerprint: Device fingerprint

        Returns:
            True if device has never been seen before for this user
        """
        # Check trusted devices
        result = await db.execute(
            select(TrustedDevice).where(
                and_(
                    TrustedDevice.user_id == user_id,
                    TrustedDevice.device_fingerprint == device_fingerprint,
                )
            )
        )
        if result.scalar_one_or_none():
            return False

        # Check previous sessions
        result = await db.execute(
            select(Session).where(
                and_(
                    Session.user_id == user_id,
                    Session.device_fingerprint == device_fingerprint,
                )
            ).limit(1)
        )
        if result.scalar_one_or_none():
            return False

        return True
