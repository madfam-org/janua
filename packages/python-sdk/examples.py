"""
Example usage of the Plinto Python SDK

This file demonstrates various SDK features and usage patterns.
"""

import asyncio
import os
from typing import Optional

from plinto import (
    PlintoClient,
    SignUpRequest,
    SignInRequest,
    UserUpdateRequest,
    OrganizationCreateRequest,
    OrganizationInviteRequest,
    WebhookEndpointCreateRequest,
    MFAEnableRequest,
    ForgotPasswordRequest,
    OrganizationRole,
    WebhookEventType,
    UserStatus,
)


async def authentication_examples():
    """Examples of authentication operations"""
    
    # Initialize client
    async with PlintoClient(base_url="https://api.plinto.com") as client:
        
        # Sign up a new user
        try:
            signup_response = await client.auth.sign_up(SignUpRequest(
                email="user@example.com",
                password="securepassword123",
                first_name="John",
                last_name="Doe",
                username="johndoe"
            ))
            print(f"✅ User created: {signup_response.user.email}")
            print(f"🔑 Access token: {signup_response.tokens.access_token[:20]}...")
        except Exception as e:
            print(f"❌ Sign up failed: {e}")
        
        # Sign in existing user
        try:
            signin_response = await client.auth.sign_in(SignInRequest(
                email="user@example.com",
                password="securepassword123"
            ))
            print(f"✅ Signed in: {signin_response.user.email}")
            
            # Get current user
            current_user = await client.auth.get_current_user()
            print(f"👤 Current user: {current_user.first_name} {current_user.last_name}")
            
        except Exception as e:
            print(f"❌ Sign in failed: {e}")
        
        # Password reset flow
        try:
            await client.auth.forgot_password(ForgotPasswordRequest(
                email="user@example.com"
            ))
            print("📧 Password reset email sent")
        except Exception as e:
            print(f"❌ Password reset failed: {e}")
        
        # Magic link authentication
        try:
            await client.auth.send_magic_link({
                "email": "user@example.com",
                "redirect_url": "https://myapp.com/auth/callback"
            })
            print("🔗 Magic link sent")
        except Exception as e:
            print(f"❌ Magic link failed: {e}")


async def user_management_examples():
    """Examples of user management operations"""
    
    async with PlintoClient.from_environment() as client:
        # Assumes user is already authenticated
        
        try:
            # Update user profile
            updated_user = await client.users.update_current_user(UserUpdateRequest(
                first_name="Jane",
                last_name="Smith",
                bio="Software developer passionate about identity solutions",
                timezone="America/New_York"
            ))
            print(f"✅ Profile updated: {updated_user.first_name} {updated_user.last_name}")
            
            # Upload avatar
            with open("avatar.jpg", "rb") as f:
                avatar_data = f.read()
            
            avatar_result = await client.users.upload_avatar(
                file_data=avatar_data,
                filename="avatar.jpg",
                content_type="image/jpeg"
            )
            print(f"🖼️ Avatar uploaded: {avatar_result['profile_image_url']}")
            
            # List user sessions
            sessions = await client.users.list_sessions()
            print(f"📱 Active sessions: {len(sessions.sessions)}")
            
            for session in sessions.sessions:
                status = "🟢 Current" if session.is_current else "⚪ Other"
                print(f"  {status} {session.browser} on {session.os} - {session.ip_address}")
            
            # Get security alerts
            alerts = await client.users.get_security_alerts()
            if alerts['alerts']:
                print(f"⚠️ Security alerts: {len(alerts['alerts'])}")
                for alert in alerts['alerts']:
                    print(f"  {alert['type']}: {alert['message']}")
            else:
                print("✅ No security alerts")
                
        except Exception as e:
            print(f"❌ User management failed: {e}")


async def organization_examples():
    """Examples of organization management"""
    
    async with PlintoClient.from_environment() as client:
        
        try:
            # Create organization
            org = await client.organizations.create_organization(
                OrganizationCreateRequest(
                    name="Acme Corporation",
                    slug="acme-corp",
                    description="Leading provider of innovative solutions",
                    billing_email="billing@acme.com"
                )
            )
            print(f"🏢 Organization created: {org.name} ({org.slug})")
            
            # List user's organizations
            orgs = await client.organizations.list_organizations()
            print(f"📋 User belongs to {len(orgs)} organizations:")
            for org in orgs:
                role_emoji = "👑" if org.user_role == "owner" else "🔧" if org.user_role == "admin" else "👤"
                print(f"  {role_emoji} {org.name} - {org.user_role}")
            
            # Invite member
            if orgs:
                org_id = orgs[0].id
                invitation = await client.organizations.invite_member(
                    org_id,
                    OrganizationInviteRequest(
                        email="teammate@example.com",
                        role=OrganizationRole.MEMBER,
                        message="Welcome to our team!"
                    )
                )
                print(f"📨 Invitation sent to teammate@example.com")
                
                # List organization members
                members = await client.organizations.list_members(org_id)
                print(f"👥 Organization has {len(members)} members:")
                for member in members:
                    print(f"  {member.email} - {member.role}")
                    
        except Exception as e:
            print(f"❌ Organization management failed: {e}")


async def mfa_examples():
    """Examples of MFA operations"""
    
    async with PlintoClient.from_environment() as client:
        
        try:
            # Check MFA status
            mfa_status = await client.auth.get_mfa_status()
            print(f"🔐 MFA enabled: {mfa_status.enabled}")
            print(f"✅ MFA verified: {mfa_status.verified}")
            print(f"🗝️ Backup codes remaining: {mfa_status.backup_codes_remaining}")
            
            if not mfa_status.enabled:
                # Enable MFA
                mfa_setup = await client.auth.enable_mfa(MFAEnableRequest(
                    password="userpassword123"
                ))
                print("📱 MFA setup initiated")
                print(f"🔑 Secret: {mfa_setup.secret}")
                print(f"📱 QR Code: {mfa_setup.qr_code[:50]}...")
                print(f"🔐 Backup codes: {len(mfa_setup.backup_codes)} codes generated")
                
                # Verify MFA setup (user would scan QR code and enter TOTP)
                # verification_result = await client.auth.verify_mfa(MFAVerifyRequest(
                #     code="123456"  # User enters TOTP code
                # ))
                # print("✅ MFA verified and enabled")
            
            # List available passkeys
            passkeys = await client.auth.list_passkeys()
            print(f"🗝️ Registered passkeys: {len(passkeys)}")
            for passkey in passkeys:
                print(f"  {passkey.name} - Last used: {passkey.last_used_at}")
                
        except Exception as e:
            print(f"❌ MFA management failed: {e}")


async def webhook_examples():
    """Examples of webhook management"""
    
    async with PlintoClient.from_environment() as client:
        
        try:
            # Create webhook endpoint
            webhook = await client.webhooks.create_endpoint(
                WebhookEndpointCreateRequest(
                    url="https://myapp.com/webhooks/plinto",
                    events=[
                        WebhookEventType.USER_CREATED,
                        WebhookEventType.USER_SIGNED_IN,
                        WebhookEventType.ORGANIZATION_CREATED
                    ],
                    description="Main webhook endpoint for user events",
                    headers={"X-Custom-Header": "myapp-webhook"}
                )
            )
            print(f"🎣 Webhook created: {webhook.url}")
            print(f"🔑 Secret: {webhook.secret[:20]}...")
            
            # List webhooks
            webhooks = await client.webhooks.list_endpoints()
            print(f"📡 Active webhooks: {len(webhooks.endpoints)}")
            
            for webhook in webhooks.endpoints:
                status = "🟢" if webhook.is_active else "🔴"
                print(f"  {status} {webhook.url} - {len(webhook.events)} events")
            
            # Get webhook stats
            if webhooks.endpoints:
                webhook_id = webhooks.endpoints[0].id
                stats = await client.webhooks.get_endpoint_stats(webhook_id, days=30)
                print(f"📊 Webhook stats (30 days):")
                print(f"  Total deliveries: {stats['total_deliveries']}")
                print(f"  Success rate: {stats['success_rate']:.1%}")
                print(f"  Average delivery time: {stats['average_delivery_time']:.2f}s")
                
        except Exception as e:
            print(f"❌ Webhook management failed: {e}")


async def admin_examples():
    """Examples of admin operations (requires admin privileges)"""
    
    async with PlintoClient.from_environment() as client:
        
        try:
            # Get system stats
            stats = await client.admin.get_stats()
            print("📊 System Statistics:")
            print(f"  Total users: {stats.total_users}")
            print(f"  Active users: {stats.active_users}")
            print(f"  Organizations: {stats.total_organizations}")
            print(f"  Active sessions: {stats.active_sessions}")
            print(f"  MFA enabled users: {stats.mfa_enabled_users}")
            print(f"  Users last 24h: {stats.users_last_24h}")
            
            # Get system health
            health = await client.admin.get_system_health()
            print(f"🏥 System Health: {health.status}")
            print(f"  Database: {health.database}")
            print(f"  Cache: {health.cache}")
            print(f"  Email: {health.email}")
            print(f"  Environment: {health.environment}")
            
            # List all users (admin only)
            users = await client.admin.list_all_users(
                page=1,
                per_page=10,
                status=UserStatus.ACTIVE
            )
            print(f"👥 Active users (first 10): {len(users)}")
            for user in users:
                print(f"  {user.email} - {user.status} - Admin: {user.is_admin}")
                
        except Exception as e:
            print(f"❌ Admin operations failed: {e}")


def webhook_handler_example():
    """Example webhook handler for receiving Plinto events"""
    
    from flask import Flask, request, jsonify
    from plinto import validate_webhook_signature
    
    app = Flask(__name__)
    
    # Your webhook endpoint secret from Plinto dashboard
    WEBHOOK_SECRET = os.getenv("PLINTO_WEBHOOK_SECRET")
    
    @app.route("/webhooks/plinto", methods=["POST"])
    def handle_plinto_webhook():
        """Handle incoming Plinto webhook"""
        
        # Get headers
        signature = request.headers.get("X-Plinto-Signature")
        timestamp = request.headers.get("X-Plinto-Timestamp")
        
        if not signature or not WEBHOOK_SECRET:
            return jsonify({"error": "Missing signature or secret"}), 400
        
        # Get raw payload
        payload = request.get_data(as_text=True)
        
        # Validate signature
        if not validate_webhook_signature(payload, signature, WEBHOOK_SECRET, timestamp):
            return jsonify({"error": "Invalid signature"}), 401
        
        # Parse webhook data
        webhook_data = request.get_json()
        event_type = webhook_data.get("type")
        event_data = webhook_data.get("data", {})
        
        print(f"📨 Received webhook: {event_type}")
        
        # Handle different event types
        if event_type == "user.created":
            user_data = event_data.get("user", {})
            print(f"👤 New user: {user_data.get('email')}")
            # Add your user creation logic here
            
        elif event_type == "user.signed_in":
            user_data = event_data.get("user", {})
            session_data = event_data.get("session", {})
            print(f"🔑 User signed in: {user_data.get('email')} from {session_data.get('ip_address')}")
            # Add your sign-in tracking logic here
            
        elif event_type == "organization.created":
            org_data = event_data.get("organization", {})
            print(f"🏢 New organization: {org_data.get('name')}")
            # Add your organization setup logic here
            
        else:
            print(f"❓ Unknown event type: {event_type}")
        
        return jsonify({"status": "success"}), 200
    
    return app


async def main():
    """Run all examples"""
    print("🚀 Plinto Python SDK Examples\n")
    
    print("=" * 50)
    print("Authentication Examples")
    print("=" * 50)
    await authentication_examples()
    
    print("\n" + "=" * 50)
    print("User Management Examples")
    print("=" * 50)
    await user_management_examples()
    
    print("\n" + "=" * 50)
    print("Organization Examples")
    print("=" * 50)
    await organization_examples()
    
    print("\n" + "=" * 50)
    print("MFA Examples")
    print("=" * 50)
    await mfa_examples()
    
    print("\n" + "=" * 50)
    print("Webhook Examples")
    print("=" * 50)
    await webhook_examples()
    
    print("\n" + "=" * 50)
    print("Admin Examples")
    print("=" * 50)
    await admin_examples()
    
    print("\n🎉 Examples completed!")


if __name__ == "__main__":
    # Set environment variables for examples
    os.environ.setdefault("PLINTO_BASE_URL", "https://api.plinto.com")
    # os.environ.setdefault("PLINTO_API_KEY", "your-api-key-here")
    
    # Run examples
    asyncio.run(main())