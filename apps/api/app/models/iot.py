"""
IoT and Edge device authentication models
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from ..models import Base


class DeviceType(enum.Enum):
    IOT_SENSOR = "iot_sensor"
    IOT_ACTUATOR = "iot_actuator"
    EDGE_GATEWAY = "edge_gateway"
    SMART_DEVICE = "smart_device"
    INDUSTRIAL = "industrial"
    MEDICAL = "medical"
    AUTOMOTIVE = "automotive"
    WEARABLE = "wearable"


class DeviceStatus(enum.Enum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DECOMMISSIONED = "decommissioned"
    MAINTENANCE = "maintenance"


class AuthMethod(enum.Enum):
    CERTIFICATE = "certificate"  # X.509 certificates
    TOKEN = "token"  # JWT or API tokens
    MQTT_CREDENTIALS = "mqtt_credentials"  # MQTT username/password
    COAP_DTLS = "coap_dtls"  # CoAP with DTLS
    OAUTH2 = "oauth2"  # OAuth 2.0 for devices
    CUSTOM = "custom"


class IoTDevice(Base):
    """IoT and Edge device registry"""
    __tablename__ = 'iot_devices'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    
    # Device identification
    device_id = Column(String(255), unique=True, nullable=False, index=True)  # Unique device identifier
    device_name = Column(String(200), nullable=True)
    device_type = Column(SQLEnum(DeviceType), nullable=False)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    serial_number = Column(String(100), nullable=True)
    hardware_version = Column(String(50), nullable=True)
    firmware_version = Column(String(50), nullable=True)
    
    # Status
    status = Column(SQLEnum(DeviceStatus), default=DeviceStatus.PROVISIONING)
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    
    # Location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    location_name = Column(String(200), nullable=True)
    timezone = Column(String(50), nullable=True)
    
    # Authentication
    auth_method = Column(SQLEnum(AuthMethod), nullable=False)
    certificate_id = Column(UUID(as_uuid=True), ForeignKey('device_certificates.id'), nullable=True)
    api_key = Column(String(255), nullable=True)  # Encrypted
    secret_key = Column(Text, nullable=True)  # Encrypted
    
    # Capabilities
    capabilities = Column(JSON, default=dict)
    """
    Example capabilities:
    {
        "sensors": ["temperature", "humidity", "pressure"],
        "actuators": ["relay", "motor"],
        "protocols": ["mqtt", "coap", "http"],
        "encryption": ["aes256", "tls1.3"]
    }
    """
    
    # Configuration
    config = Column(JSON, default=dict)  # Device-specific configuration
    metadata = Column(JSON, default=dict)  # Custom metadata
    tags = Column(JSON, default=list)  # Tags for grouping
    
    # Telemetry settings
    telemetry_interval = Column(Integer, default=60)  # Seconds
    batch_size = Column(Integer, default=1)
    compression_enabled = Column(Boolean, default=False)
    
    # Security
    secure_boot = Column(Boolean, default=False)
    attestation_enabled = Column(Boolean, default=False)
    last_attestation = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    provisioned_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    decommissioned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")
    certificate = relationship("DeviceCertificate", back_populates="devices")
    telemetry_data = relationship("DeviceTelemetry", back_populates="device", cascade="all, delete-orphan")
    commands = relationship("DeviceCommand", back_populates="device", cascade="all, delete-orphan")
    shadow = relationship("DeviceShadow", back_populates="device", uselist=False, cascade="all, delete-orphan")


class DeviceCertificate(Base):
    """X.509 certificates for device authentication"""
    __tablename__ = 'device_certificates'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    
    # Certificate details
    common_name = Column(String(255), nullable=False)
    certificate = Column(Text, nullable=False)  # PEM format
    private_key = Column(Text, nullable=True)  # Encrypted private key
    certificate_chain = Column(Text, nullable=True)  # Certificate chain
    
    # Certificate info
    serial_number = Column(String(100), unique=True, nullable=False)
    fingerprint = Column(String(255), unique=True, nullable=False)
    subject = Column(JSON, nullable=False)  # Certificate subject
    issuer = Column(JSON, nullable=False)  # Certificate issuer
    
    # Validity
    not_before = Column(DateTime(timezone=True), nullable=False)
    not_after = Column(DateTime(timezone=True), nullable=False)
    is_ca = Column(Boolean, default=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String(100), nullable=True)
    
    # Usage
    key_usage = Column(JSON, default=list)  # Key usage extensions
    extended_key_usage = Column(JSON, default=list)  # Extended key usage
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")
    devices = relationship("IoTDevice", back_populates="certificate")


class DeviceTelemetry(Base):
    """Device telemetry data"""
    __tablename__ = 'device_telemetry'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey('iot_devices.id'), nullable=False)
    
    # Telemetry data
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    data = Column(JSON, nullable=False)  # Telemetry payload
    """
    Example telemetry:
    {
        "temperature": 23.5,
        "humidity": 65,
        "pressure": 1013.25,
        "battery": 85,
        "signal_strength": -45
    }
    """
    
    # Metadata
    sequence_number = Column(Integer, nullable=True)
    message_id = Column(String(100), nullable=True)
    
    # Quality
    quality = Column(String(20), nullable=True)  # good, bad, uncertain
    
    # Processing
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Storage optimization
    is_compressed = Column(Boolean, default=False)
    original_size = Column(Integer, nullable=True)  # Bytes
    
    # Timestamps
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    device = relationship("IoTDevice", back_populates="telemetry_data")


class DeviceCommand(Base):
    """Commands sent to devices"""
    __tablename__ = 'device_commands'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey('iot_devices.id'), nullable=False)
    
    # Command details
    command_type = Column(String(100), nullable=False)  # reboot, update, configure, etc.
    payload = Column(JSON, nullable=False)  # Command payload
    
    # Execution
    status = Column(String(50), default="pending")  # pending, sent, acknowledged, completed, failed
    sent_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Response
    response = Column(JSON, nullable=True)  # Device response
    error_message = Column(Text, nullable=True)
    
    # Retry logic
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Timeout
    timeout_seconds = Column(Integer, default=30)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    device = relationship("IoTDevice", back_populates="commands")


class DeviceShadow(Base):
    """Device shadow/twin for offline state management"""
    __tablename__ = 'device_shadows'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey('iot_devices.id'), nullable=False, unique=True)
    
    # Shadow state
    desired_state = Column(JSON, default=dict)  # Desired device state
    reported_state = Column(JSON, default=dict)  # Last reported state
    delta_state = Column(JSON, default=dict)  # Difference between desired and reported
    
    # Metadata
    version = Column(Integer, default=1)
    
    # Timestamps
    desired_updated_at = Column(DateTime(timezone=True), nullable=True)
    reported_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    device = relationship("IoTDevice", back_populates="shadow")


class EdgeGateway(Base):
    """Edge gateway configuration for local processing"""
    __tablename__ = 'edge_gateways'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey('iot_devices.id'), nullable=False, unique=True)
    
    # Gateway configuration
    gateway_type = Column(String(50), nullable=False)  # mqtt_broker, coap_gateway, etc.
    protocol_support = Column(JSON, default=list)  # Supported protocols
    
    # Processing capabilities
    edge_computing = Column(Boolean, default=True)
    ml_inference = Column(Boolean, default=False)
    data_aggregation = Column(Boolean, default=True)
    
    # Connected devices
    max_devices = Column(Integer, default=100)
    connected_devices = Column(Integer, default=0)
    device_list = Column(JSON, default=list)  # List of connected device IDs
    
    # Network configuration
    local_network = Column(String(50), nullable=True)  # Local network CIDR
    vpn_enabled = Column(Boolean, default=False)
    vpn_config = Column(JSON, nullable=True)  # VPN configuration
    
    # Rules and policies
    routing_rules = Column(JSON, default=list)  # Message routing rules
    filtering_rules = Column(JSON, default=list)  # Data filtering rules
    processing_rules = Column(JSON, default=list)  # Local processing rules
    
    # Performance metrics
    cpu_usage = Column(Float, nullable=True)  # Percentage
    memory_usage = Column(Float, nullable=True)  # Percentage
    disk_usage = Column(Float, nullable=True)  # Percentage
    network_throughput = Column(Float, nullable=True)  # Mbps
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    device = relationship("IoTDevice")


class DeviceGroup(Base):
    """Logical grouping of devices"""
    __tablename__ = 'device_groups'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    
    # Group details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    group_type = Column(String(50), nullable=True)  # location, function, model, etc.
    
    # Members
    device_ids = Column(JSON, default=list)  # List of device IDs
    device_count = Column(Integer, default=0)
    
    # Group configuration
    shared_config = Column(JSON, default=dict)  # Configuration applied to all devices
    
    # Policies
    update_policy = Column(JSON, nullable=True)  # OTA update policy
    security_policy = Column(JSON, nullable=True)  # Security requirements
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")