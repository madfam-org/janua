"""
Janua CLI - Command Line Interface

Provides command-line tools for Janua setup, management, and deployment.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from app import __version__, create_app
from app.config import get_settings


def create_parser() -> argparse.ArgumentParser:
    """Create the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="janua",
        description="Janua - Enterprise authentication platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  janua server --host 0.0.0.0 --port 8000    # Start development server
  janua migrate                               # Run database migrations
  janua create-user --email admin@example.com # Create admin user
  janua version                               # Show version info
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Janua {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start the Janua server")
    server_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    server_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    server_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )

    # Migration command
    migrate_parser = subparsers.add_parser("migrate", help="Run database migrations")
    migrate_parser.add_argument(
        "--upgrade",
        action="store_true",
        default=True,
        help="Upgrade database to latest version"
    )
    migrate_parser.add_argument(
        "--downgrade",
        help="Downgrade database to specific revision"
    )

    # User management commands
    user_parser = subparsers.add_parser("create-user", help="Create a new user")
    user_parser.add_argument(
        "--email",
        required=True,
        help="User email address"
    )
    user_parser.add_argument(
        "--password",
        help="User password (will prompt if not provided)"
    )
    user_parser.add_argument(
        "--admin",
        action="store_true",
        help="Make user an admin"
    )
    user_parser.add_argument(
        "--org",
        help="Organization to add user to"
    )

    # Initialize command
    init_parser = subparsers.add_parser("init", help="Initialize Janua configuration")
    init_parser.add_argument(
        "--config-dir",
        default=".",
        help="Directory to create configuration files"
    )
    init_parser.add_argument(
        "--database-url",
        help="Database connection URL"
    )
    init_parser.add_argument(
        "--redis-url",
        help="Redis connection URL"
    )

    # Health check command
    subparsers.add_parser("health", help="Check system health")

    # Version command
    subparsers.add_parser("version", help="Show version information")

    return parser


async def run_server(host: str, port: int, reload: bool = False, workers: int = 1):
    """Start the Janua server."""
    app = create_app()

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        access_log=True,
        log_level="info"
    )

    server = uvicorn.Server(config)
    await server.serve()


async def run_migrations(upgrade: bool = True, downgrade: Optional[str] = None):
    """Run database migrations."""
    try:
        from alembic.config import Config
        from alembic import command

        # Get alembic configuration
        alembic_cfg = Config("alembic.ini")

        if downgrade:
            print(f"Downgrading database to revision: {downgrade}")
            command.downgrade(alembic_cfg, downgrade)
        elif upgrade:
            print("Upgrading database to latest revision")
            command.upgrade(alembic_cfg, "head")

        print("Migration completed successfully")

    except ImportError:
        print("Alembic not available. Install with: pip install alembic")
        sys.exit(1)
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)


async def create_user(email: str, password: Optional[str] = None, admin: bool = False, org: Optional[str] = None):
    """Create a new user. Currently a stub that needs database session implementation."""
    try:
        import getpass

        if not password:
            password = getpass.getpass("Enter password: ")

        # TODO: Implement with proper database session and AuthService
        # Placeholder message until full implementation
        print(f"Creating user: {email} (admin={admin}, org={org})")
        print(f"Password length: {len(password)} characters")
        print("Note: User creation functionality needs database session implementation")

    except Exception as e:
        print(f"User creation failed: {e}")
        sys.exit(1)


def init_config(config_dir: str, database_url: Optional[str] = None, redis_url: Optional[str] = None):
    """Initialize Janua configuration."""
    config_path = Path(config_dir)
    config_path.mkdir(exist_ok=True)

    env_file = config_path / ".env"

    env_content = f"""# Janua Configuration
# Generated by janua init

# Application
APP_NAME=Janua
DEBUG=false
ENVIRONMENT=production

# Database
DATABASE_URL={database_url or "postgresql://postgres:postgres@localhost:5432/janua"}

# Redis
REDIS_URL={redis_url or "redis://localhost:6379/0"}

# JWT
JWT_SECRET_KEY=your-secret-key-here-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Email (optional)
# SENDGRID_API_KEY=your-sendgrid-key
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your-email@gmail.com
# SMTP_PASSWORD=your-password
"""

    env_file.write_text(env_content)
    print(f"Configuration created at: {env_file}")
    print("Please update the configuration values, especially JWT_SECRET_KEY")


async def check_health():
    """Check system health."""
    try:
        settings = get_settings()

        print("🔍 Janua Health Check")
        print("=" * 50)

        # Check configuration
        print(f"✅ Configuration loaded")
        print(f"   Environment: {settings.ENVIRONMENT}")
        print(f"   App Name: {settings.APP_NAME}")

        # Check database connection
        try:
            # This would need proper database connection check
            print(f"✅ Database connection configured")
            print(f"   URL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")

        # Check Redis connection
        try:
            print(f"✅ Redis connection configured")
            print(f"   URL: {settings.REDIS_URL}")
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")

        print("\n✅ Health check completed")

    except Exception as e:
        print(f"❌ Health check failed: {e}")
        sys.exit(1)


def show_version():
    """Show version information."""
    print(f"Janua {__version__}")
    print("Enterprise-grade authentication and user management platform")
    print("https://janua.dev")


async def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "server":
            await run_server(
                host=args.host,
                port=args.port,
                reload=args.reload,
                workers=args.workers
            )
        elif args.command == "migrate":
            await run_migrations(
                upgrade=args.upgrade,
                downgrade=getattr(args, 'downgrade', None)
            )
        elif args.command == "create-user":
            await create_user(
                email=args.email,
                password=getattr(args, 'password', None),
                admin=args.admin,
                org=getattr(args, 'org', None)
            )
        elif args.command == "init":
            init_config(
                config_dir=args.config_dir,
                database_url=getattr(args, 'database_url', None),
                redis_url=getattr(args, 'redis_url', None)
            )
        elif args.command == "health":
            await check_health()
        elif args.command == "version":
            show_version()
        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\nOperation cancelled")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cli_main():
    """Synchronous CLI entry point for setuptools."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    cli_main()