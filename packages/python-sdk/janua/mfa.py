"""Multi-Factor Authentication (MFA) module for the Janua SDK."""

from typing import Optional, List, Dict, Any

from .http_client import HTTPClient
from .types import (
    MFASettings,
    MFAMethod,
    MFAChallenge,
    TOTPSetup,
    SMSSetup,
    BackupCodes,
    JanuaConfig,
)


class MFAClient:
    """Client for MFA operations."""
    
    def __init__(self, http: HTTPClient, config: JanuaConfig):
        """
        Initialize the MFA client.
        
        Args:
            http: HTTP client instance
            config: Janua configuration
        """
        self.http = http
        self.config = config
    
    def get_settings(self, user_id: Optional[str] = None) -> MFASettings:
        """
        Get MFA settings for a user.
        
        Args:
            user_id: User ID (defaults to current user)
            
        Returns:
            MFASettings object
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        if user_id:
            response = self.http.get(f'/mfa/users/{user_id}/settings')
        else:
            response = self.http.get('/mfa/settings')
        
        data = response.json()
        return MFASettings(**data)
    
    def enable(
        self,
        method: MFAMethod,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enable MFA for a user.
        
        Args:
            method: MFA method to enable
            user_id: User ID (defaults to current user)
            
        Returns:
            Setup information for the MFA method
            
        Raises:
            ValidationError: If method is invalid
            AuthorizationError: If not authorized
            JanuaError: If enable fails
        """
        payload = {'method': method.value}
        
        if user_id:
            response = self.http.post(
                f'/mfa/users/{user_id}/enable',
                json=payload
            )
        else:
            response = self.http.post('/mfa/enable', json=payload)
        
        return response.json()
    
    def disable(
        self,
        method: Optional[MFAMethod] = None,
        user_id: Optional[str] = None,
        verification_code: Optional[str] = None,
    ) -> MFASettings:
        """
        Disable MFA for a user.
        
        Args:
            method: Specific method to disable (or all if None)
            user_id: User ID (defaults to current user)
            verification_code: Current MFA code for verification
            
        Returns:
            Updated MFASettings object
            
        Raises:
            AuthenticationError: If verification fails
            AuthorizationError: If not authorized
            JanuaError: If disable fails
        """
        payload = {}
        if method:
            payload['method'] = method.value
        if verification_code:
            payload['verification_code'] = verification_code
        
        if user_id:
            response = self.http.post(
                f'/mfa/users/{user_id}/disable',
                json=payload
            )
        else:
            response = self.http.post('/mfa/disable', json=payload)
        
        data = response.json()
        return MFASettings(**data)
    
    # TOTP (Authenticator app) methods
    
    def setup_totp(self, user_id: Optional[str] = None) -> TOTPSetup:
        """
        Set up TOTP (authenticator app) for a user.
        
        Args:
            user_id: User ID (defaults to current user)
            
        Returns:
            TOTPSetup object with QR code and secret
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If setup fails
        """
        if user_id:
            response = self.http.post(f'/mfa/users/{user_id}/totp/setup')
        else:
            response = self.http.post('/mfa/totp/setup')
        
        data = response.json()
        return TOTPSetup(**data)
    
    def verify_totp(
        self,
        code: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Verify a TOTP code.
        
        Args:
            code: TOTP code from authenticator app
            user_id: User ID (defaults to current user)
            
        Returns:
            True if code is valid
            
        Raises:
            AuthenticationError: If code is invalid
            AuthorizationError: If not authorized
            JanuaError: If verification fails
        """
        payload = {'code': code}
        
        if user_id:
            response = self.http.post(
                f'/mfa/users/{user_id}/totp/verify',
                json=payload
            )
        else:
            response = self.http.post('/mfa/totp/verify', json=payload)
        
        data = response.json()
        return data.get('valid', False)
    
    def remove_totp(
        self,
        user_id: Optional[str] = None,
        verification_code: Optional[str] = None,
    ) -> MFASettings:
        """
        Remove TOTP authentication.
        
        Args:
            user_id: User ID (defaults to current user)
            verification_code: Current TOTP code for verification
            
        Returns:
            Updated MFASettings object
            
        Raises:
            AuthenticationError: If verification fails
            AuthorizationError: If not authorized
            JanuaError: If removal fails
        """
        payload = {}
        if verification_code:
            payload['verification_code'] = verification_code
        
        if user_id:
            response = self.http.delete(
                f'/mfa/users/{user_id}/totp',
                json=payload
            )
        else:
            response = self.http.delete('/mfa/totp', json=payload)
        
        data = response.json()
        return MFASettings(**data)
    
    # SMS methods
    
    def setup_sms(
        self,
        phone_number: str,
        user_id: Optional[str] = None,
    ) -> SMSSetup:
        """
        Set up SMS MFA for a user.
        
        Args:
            phone_number: Phone number for SMS
            user_id: User ID (defaults to current user)
            
        Returns:
            SMSSetup object with verification status
            
        Raises:
            ValidationError: If phone number is invalid
            AuthorizationError: If not authorized
            JanuaError: If setup fails
        """
        payload = {'phone_number': phone_number}
        
        if user_id:
            response = self.http.post(
                f'/mfa/users/{user_id}/sms/setup',
                json=payload
            )
        else:
            response = self.http.post('/mfa/sms/setup', json=payload)
        
        data = response.json()
        return SMSSetup(**data)
    
    def verify_sms(
        self,
        code: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Verify an SMS MFA code.
        
        Args:
            code: SMS verification code
            user_id: User ID (defaults to current user)
            
        Returns:
            True if code is valid
            
        Raises:
            AuthenticationError: If code is invalid
            AuthorizationError: If not authorized
            JanuaError: If verification fails
        """
        payload = {'code': code}
        
        if user_id:
            response = self.http.post(
                f'/mfa/users/{user_id}/sms/verify',
                json=payload
            )
        else:
            response = self.http.post('/mfa/sms/verify', json=payload)
        
        data = response.json()
        return data.get('valid', False)
    
    def send_sms_code(
        self,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Send a new SMS verification code.
        
        Args:
            user_id: User ID (defaults to current user)
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If sending fails
        """
        if user_id:
            self.http.post(f'/mfa/users/{user_id}/sms/send')
        else:
            self.http.post('/mfa/sms/send')
    
    def remove_sms(
        self,
        user_id: Optional[str] = None,
        verification_code: Optional[str] = None,
    ) -> MFASettings:
        """
        Remove SMS authentication.
        
        Args:
            user_id: User ID (defaults to current user)
            verification_code: Current SMS code for verification
            
        Returns:
            Updated MFASettings object
            
        Raises:
            AuthenticationError: If verification fails
            AuthorizationError: If not authorized
            JanuaError: If removal fails
        """
        payload = {}
        if verification_code:
            payload['verification_code'] = verification_code
        
        if user_id:
            response = self.http.delete(
                f'/mfa/users/{user_id}/sms',
                json=payload
            )
        else:
            response = self.http.delete('/mfa/sms', json=payload)
        
        data = response.json()
        return MFASettings(**data)
    
    # Backup codes methods
    
    def generate_backup_codes(
        self,
        count: int = 10,
        user_id: Optional[str] = None,
    ) -> BackupCodes:
        """
        Generate backup codes for MFA.
        
        Args:
            count: Number of codes to generate
            user_id: User ID (defaults to current user)
            
        Returns:
            BackupCodes object with generated codes
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If generation fails
        """
        payload = {'count': count}
        
        if user_id:
            response = self.http.post(
                f'/mfa/users/{user_id}/backup-codes/generate',
                json=payload
            )
        else:
            response = self.http.post('/mfa/backup-codes/generate', json=payload)
        
        data = response.json()
        return BackupCodes(**data)
    
    def verify_backup_code(
        self,
        code: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Verify a backup code.
        
        Args:
            code: Backup code to verify
            user_id: User ID (defaults to current user)
            
        Returns:
            True if code is valid (and consumes it)
            
        Raises:
            AuthenticationError: If code is invalid
            AuthorizationError: If not authorized
            JanuaError: If verification fails
        """
        payload = {'code': code}
        
        if user_id:
            response = self.http.post(
                f'/mfa/users/{user_id}/backup-codes/verify',
                json=payload
            )
        else:
            response = self.http.post('/mfa/backup-codes/verify', json=payload)
        
        data = response.json()
        return data.get('valid', False)
    
    def get_backup_codes(
        self,
        user_id: Optional[str] = None,
    ) -> BackupCodes:
        """
        Get remaining backup codes.
        
        Args:
            user_id: User ID (defaults to current user)
            
        Returns:
            BackupCodes object with remaining codes info
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        if user_id:
            response = self.http.get(f'/mfa/users/{user_id}/backup-codes')
        else:
            response = self.http.get('/mfa/backup-codes')
        
        data = response.json()
        return BackupCodes(**data)
    
    # Challenge/Response flow
    
    def create_challenge(
        self,
        method: MFAMethod,
        user_id: Optional[str] = None,
    ) -> MFAChallenge:
        """
        Create an MFA challenge.
        
        Args:
            method: MFA method for the challenge
            user_id: User ID (defaults to current user)
            
        Returns:
            MFAChallenge object
            
        Raises:
            ValidationError: If method is not enabled
            AuthorizationError: If not authorized
            JanuaError: If challenge creation fails
        """
        payload = {'method': method.value}
        
        if user_id:
            response = self.http.post(
                f'/mfa/users/{user_id}/challenge',
                json=payload
            )
        else:
            response = self.http.post('/mfa/challenge', json=payload)
        
        data = response.json()
        return MFAChallenge(**data)
    
    def verify_challenge(
        self,
        challenge_id: str,
        code: str,
    ) -> Dict[str, Any]:
        """
        Verify an MFA challenge response.
        
        Args:
            challenge_id: Challenge ID
            code: Verification code
            
        Returns:
            Verification result with tokens if successful
            
        Raises:
            AuthenticationError: If code is invalid
            NotFoundError: If challenge not found
            JanuaError: If verification fails
        """
        response = self.http.post(
            f'/mfa/challenge/{challenge_id}/verify',
            json={'code': code}
        )
        return response.json()
    
    def get_available_methods(
        self,
        user_id: Optional[str] = None,
    ) -> List[MFAMethod]:
        """
        Get available MFA methods for a user.
        
        Args:
            user_id: User ID (defaults to current user)
            
        Returns:
            List of available MFA methods
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        if user_id:
            response = self.http.get(f'/mfa/users/{user_id}/methods')
        else:
            response = self.http.get('/mfa/methods')
        
        data = response.json()
        return [MFAMethod(m) for m in data.get('methods', [])]
    
    def get_trusted_devices(
        self,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get trusted devices for MFA.
        
        Args:
            user_id: User ID (defaults to current user)
            
        Returns:
            List of trusted devices
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        if user_id:
            response = self.http.get(f'/mfa/users/{user_id}/trusted-devices')
        else:
            response = self.http.get('/mfa/trusted-devices')
        
        data = response.json()
        return data.get('devices', [])
    
    def trust_device(
        self,
        device_name: str,
        duration_days: int = 30,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mark a device as trusted for MFA.
        
        Args:
            device_name: Name for the trusted device
            duration_days: How long to trust the device
            user_id: User ID (defaults to current user)
            
        Returns:
            Trusted device information
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If trust fails
        """
        payload = {
            'device_name': device_name,
            'duration_days': duration_days,
        }
        
        if user_id:
            response = self.http.post(
                f'/mfa/users/{user_id}/trust-device',
                json=payload
            )
        else:
            response = self.http.post('/mfa/trust-device', json=payload)
        
        return response.json()
    
    def remove_trusted_device(
        self,
        device_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Remove a trusted device.
        
        Args:
            device_id: Device ID to remove
            user_id: User ID (defaults to current user)
            
        Raises:
            NotFoundError: If device not found
            AuthorizationError: If not authorized
            JanuaError: If removal fails
        """
        if user_id:
            self.http.delete(f'/mfa/users/{user_id}/trusted-devices/{device_id}')
        else:
            self.http.delete(f'/mfa/trusted-devices/{device_id}')