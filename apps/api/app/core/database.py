from typing import AsyncGenerator, Optional
import os
import ssl
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData, select
import structlog

# Import config with error handling
try:
    from app.config import settings
except Exception as e:
    print(f"Failed to import settings: {e}")
    raise

logger = structlog.get_logger()

# Database naming conventions
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)


def create_ssl_context() -> Optional[ssl.SSLContext]:
    """
    Create SSL context for PostgreSQL connection based on settings.
    
    Returns:
        SSL context if SSL is enabled, None if disabled.
    """
    ssl_mode = getattr(settings, 'DATABASE_SSL_MODE', 'prefer')
    
    # Disable SSL entirely
    if ssl_mode == 'disable':
        return None
    
    # For 'allow' and 'prefer', we attempt SSL but don't require verification
    if ssl_mode in ('allow', 'prefer'):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    
    # For 'require', we need SSL but don't verify certificate
    if ssl_mode == 'require':
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    
    # For 'verify-ca' and 'verify-full', we need proper certificates
    if ssl_mode in ('verify-ca', 'verify-full'):
        ctx = ssl.create_default_context()
        
        # Load CA certificate if provided
        ca_file = getattr(settings, 'DATABASE_SSL_CA_FILE', None)
        if ca_file and os.path.exists(ca_file):
            ctx.load_verify_locations(cafile=ca_file)
        
        # Load client certificate if provided (for mutual TLS)
        cert_file = getattr(settings, 'DATABASE_SSL_CERT_FILE', None)
        key_file = getattr(settings, 'DATABASE_SSL_KEY_FILE', None)
        if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
            ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
        
        # Configure verification mode
        if ssl_mode == 'verify-full':
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
        else:  # verify-ca
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_REQUIRED
        
        return ctx
    
    # Default: prefer (try SSL without verification)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# Create async engine with error handling
try:
    if not settings.DATABASE_URL:
        raise ValueError("DATABASE_URL is not configured")
    
    # Auto-fix Railway PostgreSQL URL format for SQLAlchemy async
    if settings.DATABASE_URL.startswith('postgresql://'):
        database_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
    else:
        database_url = settings.DATABASE_URL
    
    # Configure engine based on database type
    if database_url.startswith('sqlite'):
        # SQLite doesn't support connection pooling
        engine = create_async_engine(
            database_url,
            echo=settings.DEBUG,
            pool_pre_ping=True
        )
    else:
        # PostgreSQL with connection pooling and optional SSL
        ssl_context = create_ssl_context()
        ssl_mode = getattr(settings, 'DATABASE_SSL_MODE', 'prefer')
        
        # Build connect_args for asyncpg
        connect_args = {}
        if ssl_context and ssl_mode != 'disable':
            connect_args['ssl'] = ssl_context
            logger.info(
                "Database SSL enabled",
                ssl_mode=ssl_mode,
                ca_file=getattr(settings, 'DATABASE_SSL_CA_FILE', None),
            )
        else:
            logger.info("Database SSL disabled")
        
        engine = create_async_engine(
            database_url,
            echo=settings.DEBUG,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    
    # Create async session maker
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
except Exception as e:
    print(f"Failed to create database engine: {e}")
    print(f"DATABASE_URL: {getattr(settings, 'DATABASE_URL', 'NOT SET')}")
    raise


async def init_db():
    """Initialize database connection and create tables if needed"""
    try:
        async with engine.begin() as conn:
            if settings.AUTO_MIGRATE:
                await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")

        # Bootstrap admin user if ADMIN_BOOTSTRAP_PASSWORD is set
        await bootstrap_admin_user()
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def create_organization_with_membership(
    session,
    owner,
    name: str,
    slug: str,
    description: str = None,
    settings: dict = None,
    subscription_tier: str = "community",
    billing_plan: str = "free",
) -> tuple:
    """Create an organization and add the owner as an OWNER member.

    This is a reusable helper function that ensures organizations are always
    created with proper membership records. Use this instead of creating
    Organization objects directly.

    Args:
        session: Database session
        owner: User object who will own the organization
        name: Organization display name
        slug: URL-safe unique identifier
        description: Optional organization description
        settings: Optional organization settings dict
        subscription_tier: Subscription tier (community, pro, scale, enterprise)
        billing_plan: Billing plan (free, pro, enterprise)

    Returns:
        Tuple of (Organization, OrganizationMember)
    """
    from app.models import Organization, OrganizationMember

    org = Organization(
        name=name,
        slug=slug,
        owner_id=owner.id,
        description=description,
        settings=settings or {},
        subscription_tier=subscription_tier,
        billing_plan=billing_plan,
    )
    session.add(org)
    await session.flush()  # Get org.id before creating membership

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=owner.id,
        role="owner",
    )
    session.add(membership)

    return org, membership


async def bootstrap_admin_user():
    """Bootstrap the admin user and default organization if ADMIN_BOOTSTRAP_PASSWORD is set.

    This creates:
    1. Admin user with is_admin=True and email_verified=True
    2. Default organization with the admin as owner

    Both operations are idempotent - they only run if the resources don't exist.

    Environment variables:
    - ADMIN_BOOTSTRAP_PASSWORD: Required to enable bootstrap
    - ADMIN_BOOTSTRAP_EMAIL: Admin email (default: admin@janua.dev)
    - DEFAULT_ORG_SLUG: Organization slug (default: janua)
    """
    admin_password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD")
    if not admin_password:
        logger.debug("ADMIN_BOOTSTRAP_PASSWORD not set, skipping admin bootstrap")
        return

    admin_email = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@janua.dev")
    default_org_slug = os.environ.get("DEFAULT_ORG_SLUG", "janua")

    try:
        # Import here to avoid circular imports
        from app.models import User, Organization, OrganizationMember
        from passlib.context import CryptContext
        from app.core.database_manager import db_manager

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        async with db_manager.get_session() as session:
            # Check if admin already exists
            result = await session.execute(
                select(User).where(User.email == admin_email)
            )
            existing_admin = result.scalar_one_or_none()

            if existing_admin:
                admin_user = existing_admin
                logger.info("Admin user already exists", email=admin_email)
            else:
                # Create admin user
                password_hash = pwd_context.hash(admin_password)
                admin_user = User(
                    email=admin_email,
                    email_verified=True,
                    password_hash=password_hash,
                    is_admin=True,
                    is_active=True,
                    first_name="Admin",
                    last_name="User",
                )
                session.add(admin_user)
                await session.flush()  # Get admin_user.id
                logger.info("Admin user bootstrapped successfully", email=admin_email)

            # Check if default organization already exists
            result = await session.execute(
                select(Organization).where(Organization.slug == default_org_slug)
            )
            existing_org = result.scalar_one_or_none()

            if existing_org:
                # Ensure admin is a member of the org
                result = await session.execute(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id == existing_org.id,
                        OrganizationMember.user_id == admin_user.id,
                    )
                )
                existing_membership = result.scalar_one_or_none()

                if not existing_membership:
                    membership = OrganizationMember(
                        organization_id=existing_org.id,
                        user_id=admin_user.id,
                        role="owner",
                    )
                    session.add(membership)
                    logger.info("Added admin to existing organization", org=default_org_slug)
                else:
                    logger.info("Admin already member of organization", org=default_org_slug)
            else:
                # Create default organization with admin as owner (enterprise tier for MADFAM)
                _org, _membership = await create_organization_with_membership(
                    session=session,
                    owner=admin_user,
                    name="MADFAM",
                    slug=default_org_slug,
                    description="MADFAM development organization",
                    settings={"is_default": True},
                    subscription_tier="enterprise",
                    billing_plan="enterprise",
                )
                logger.info("Default organization bootstrapped", org=default_org_slug)

            await session.commit()

    except Exception as e:
        logger.error("Failed to bootstrap admin user/organization", error=str(e))
        # Don't raise - this is a non-critical bootstrap operation


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()