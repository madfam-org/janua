# IoT & Edge Device Authentication Guide

## Overview

Janua provides specialized authentication and identity management for IoT devices, edge computing environments, and resource-constrained systems. Our IoT platform supports device attestation, offline authentication, certificate-based identity, and lightweight protocols optimized for embedded systems.

## Device Identity Management

### Device Registration & Provisioning

```typescript
// Device Identity Model
interface DeviceIdentity {
  // Unique identifiers
  deviceId: string;              // Unique device identifier
  serialNumber?: string;         // Hardware serial number
  manufacturerId?: string;       // Manufacturer ID
  modelId?: string;             // Device model identifier
  
  // Security credentials
  credentials: {
    type: 'certificate' | 'key' | 'token' | 'tpm';
    
    // X.509 certificate
    certificate?: {
      subject: string;
      issuer: string;
      serialNumber: string;
      publicKey: string;
      validFrom: Date;
      validTo: Date;
      fingerprint: string;
    };
    
    // Symmetric key
    symmetricKey?: {
      keyId: string;
      algorithm: 'AES-128' | 'AES-256';
      encryptedKey: string;
    };
    
    // TPM attestation
    tpm?: {
      ekPublic: string;      // Endorsement key
      akPublic: string;      // Attestation key
      pcrs: PCRValues;       // Platform Configuration Registers
    };
  };
  
  // Device metadata
  metadata: {
    firmwareVersion: string;
    hardwareVersion: string;
    capabilities: string[];
    location?: GeoLocation;
    groupId?: string;
    tags?: string[];
  };
  
  // Lifecycle
  lifecycle: {
    status: 'provisioning' | 'active' | 'suspended' | 'decommissioned';
    provisionedAt?: Date;
    lastSeen?: Date;
    lastAuthenticated?: Date;
    nextKeyRotation?: Date;
  };
  
  // Security posture
  security: {
    trustLevel: number;        // 0-100
    compromised: boolean;
    quarantined: boolean;
    attestationStatus?: AttestationStatus;
  };
}

// Device Provisioning Service
class DeviceProvisioningService {
  async provisionDevice(request: ProvisioningRequest): Promise<ProvisionedDevice> {
    // Step 1: Validate device claim
    const claim = await this.validateClaim(request.claim);
    
    // Step 2: Generate device credentials
    const credentials = await this.generateCredentials({
      type: request.credentialType || 'certificate',
      strength: request.securityLevel || 'high',
      
      // Certificate generation for X.509
      certificate: request.credentialType === 'certificate' ? {
        subject: `CN=${request.deviceId},O=${request.organizationId}`,
        validityDays: 365,
        keySize: 2048,
        signatureAlgorithm: 'RSA-SHA256'
      } : undefined,
      
      // Symmetric key for constrained devices
      symmetricKey: request.credentialType === 'key' ? {
        algorithm: 'AES-256',
        keyDerivation: 'PBKDF2'
      } : undefined
    });
    
    // Step 3: Register device identity
    const device = await this.registerDevice({
      deviceId: request.deviceId,
      organizationId: request.organizationId,
      credentials,
      
      metadata: {
        ...request.metadata,
        provisioningMethod: request.method,
        provisioningProtocol: request.protocol
      }
    });
    
    // Step 4: Configure device policies
    await this.configureDevicePolicies(device.deviceId, {
      authenticationPolicy: request.authPolicy || 'standard',
      accessPolicy: request.accessPolicy || 'default',
      updatePolicy: request.updatePolicy || 'auto'
    });
    
    // Step 5: Generate provisioning response
    return {
      device,
      credentials: await this.packageCredentials(credentials, request.format),
      
      // Configuration for device
      configuration: {
        endpoints: {
          auth: this.getAuthEndpoint(request.region),
          data: this.getDataEndpoint(request.region),
          update: this.getUpdateEndpoint(request.region)
        },
        
        // Protocol configuration
        protocols: {
          mqtt: request.protocols?.includes('mqtt') ? {
            broker: this.getMQTTBroker(request.region),
            port: 8883,
            clientId: device.deviceId,
            topics: this.getDeviceTopics(device.deviceId)
          } : undefined,
          
          coap: request.protocols?.includes('coap') ? {
            server: this.getCOAPServer(request.region),
            port: 5684,
            dtls: true
          } : undefined,
          
          https: {
            endpoint: this.getHTTPSEndpoint(request.region),
            port: 443
          }
        }
      }
    };
  }
  
  async bulkProvision(
    devices: DeviceSpec[],
    options: BulkProvisioningOptions
  ): Promise<BulkProvisioningResult> {
    // Process devices in parallel batches
    const batchSize = options.batchSize || 100;
    const batches = this.createBatches(devices, batchSize);
    
    const results = await Promise.all(
      batches.map(batch => this.provisionBatch(batch, options))
    );
    
    return {
      total: devices.length,
      successful: results.reduce((sum, r) => sum + r.successful, 0),
      failed: results.reduce((sum, r) => sum + r.failed, 0),
      
      // Manifest for deployment
      manifest: await this.generateManifest(results, options.format)
    };
  }
}
```

## Lightweight Authentication Protocols

### MQTT Authentication

```typescript
class MQTTAuthHandler {
  async authenticateDevice(
    clientId: string,
    username: string,
    password: Buffer,
    clientCertificate?: Certificate
  ): Promise<AuthResult> {
    // Certificate-based authentication (preferred)
    if (clientCertificate) {
      return await this.authenticateCertificate(clientCertificate, clientId);
    }
    
    // Username/password authentication
    if (username && password) {
      return await this.authenticateCredentials(username, password, clientId);
    }
    
    // Token-based authentication
    if (username.startsWith('token:')) {
      const token = username.substring(6);
      return await this.authenticateToken(token, clientId);
    }
    
    throw new Error('No valid authentication method provided');
  }
  
  private async authenticateCertificate(
    certificate: Certificate,
    clientId: string
  ): Promise<AuthResult> {
    // Validate certificate
    const validation = await this.validateCertificate(certificate);
    
    if (!validation.valid) {
      return {
        authenticated: false,
        reason: validation.reason
      };
    }
    
    // Extract device ID from certificate
    const deviceId = this.extractDeviceId(certificate);
    
    // Verify device ID matches client ID
    if (deviceId !== clientId) {
      return {
        authenticated: false,
        reason: 'Client ID mismatch'
      };
    }
    
    // Check device status
    const device = await this.devices.get(deviceId);
    
    if (device.lifecycle.status !== 'active') {
      return {
        authenticated: false,
        reason: `Device ${device.lifecycle.status}`
      };
    }
    
    // Update last seen
    await this.devices.updateLastSeen(deviceId);
    
    return {
      authenticated: true,
      deviceId,
      
      // ACL for MQTT topics
      acl: {
        publish: this.getPublishTopics(device),
        subscribe: this.getSubscribeTopics(device)
      }
    };
  }
  
  async generateMQTTCredentials(
    deviceId: string,
    options: MQTTCredentialOptions
  ): Promise<MQTTCredentials> {
    if (options.type === 'certificate') {
      // Generate client certificate
      const cert = await this.generateClientCertificate(deviceId);
      
      return {
        type: 'certificate',
        clientId: deviceId,
        certificate: cert.certificate,
        privateKey: cert.privateKey,
        caCertificate: this.getCACertificate()
      };
    } else {
      // Generate username/password
      const password = await this.generateSecurePassword();
      
      return {
        type: 'password',
        clientId: deviceId,
        username: `device/${deviceId}`,
        password: password
      };
    }
  }
}
```

### CoAP/DTLS Authentication

```typescript
class CoAPAuthHandler {
  async authenticateDTLS(
    pskIdentity: string,
    psk: Buffer
  ): Promise<DTLSAuthResult> {
    // Lookup device by PSK identity
    const device = await this.devices.findByPSKIdentity(pskIdentity);
    
    if (!device) {
      return {
        authenticated: false,
        reason: 'Unknown PSK identity'
      };
    }
    
    // Verify PSK
    const valid = await this.verifyPSK(device.deviceId, psk);
    
    if (!valid) {
      return {
        authenticated: false,
        reason: 'Invalid PSK'
      };
    }
    
    // Check device status
    if (device.lifecycle.status !== 'active') {
      return {
        authenticated: false,
        reason: `Device ${device.lifecycle.status}`
      };
    }
    
    return {
      authenticated: true,
      deviceId: device.deviceId,
      
      // CoAP resource permissions
      permissions: await this.getCoAPPermissions(device)
    };
  }
  
  async generatePSK(deviceId: string): Promise<PSKCredentials> {
    // Generate unique PSK identity
    const identity = `${deviceId}@${this.tenantId}`;
    
    // Generate cryptographically secure PSK
    const psk = crypto.randomBytes(32);
    
    // Store PSK (encrypted)
    await this.storePSK(deviceId, {
      identity,
      psk: await this.encryptPSK(psk),
      createdAt: new Date(),
      expiresAt: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000)
    });
    
    return {
      identity,
      psk: psk.toString('hex'),
      
      // CoAP configuration
      config: {
        server: this.getCOAPServer(),
        port: 5684,
        dtls: {
          version: '1.2',
          cipherSuites: ['TLS_PSK_WITH_AES_128_CCM_8']
        }
      }
    };
  }
}
```

### Lightweight Token Authentication

```typescript
class LightweightTokenService {
  async generateDeviceToken(
    deviceId: string,
    options: TokenOptions
  ): Promise<DeviceToken> {
    // Create compact JWT for constrained devices
    const payload = {
      sub: deviceId,
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor((Date.now() + options.ttl) / 1000),
      
      // Minimal claims for size optimization
      scp: options.scopes?.join(' '),
      tid: this.tenantId.substring(0, 8) // Shortened tenant ID
    };
    
    // Use compact encoding
    const token = await this.signCompactToken(payload, {
      algorithm: options.algorithm || 'ES256', // ECDSA for smaller signatures
      compress: options.compress !== false
    });
    
    return {
      token,
      expiresIn: options.ttl,
      
      // Refresh configuration
      refresh: options.refreshable ? {
        endpoint: '/auth/device/refresh',
        method: 'POST',
        beforeExpiry: 300 // Refresh 5 minutes before expiry
      } : undefined
    };
  }
  
  async validateDeviceToken(token: string): Promise<TokenValidation> {
    try {
      // Decode and verify
      const decoded = await this.verifyCompactToken(token);
      
      // Check device status
      const device = await this.devices.get(decoded.sub);
      
      if (!device || device.lifecycle.status !== 'active') {
        return {
          valid: false,
          reason: 'Device not active'
        };
      }
      
      // Check token expiration
      if (decoded.exp < Math.floor(Date.now() / 1000)) {
        return {
          valid: false,
          reason: 'Token expired'
        };
      }
      
      return {
        valid: true,
        deviceId: decoded.sub,
        scopes: decoded.scp?.split(' ') || []
      };
    } catch (error) {
      return {
        valid: false,
        reason: error.message
      };
    }
  }
}
```

## Offline Authentication

### Offline Token System

```typescript
class OfflineAuthenticationService {
  async generateOfflineTokenChain(
    deviceId: string,
    count: number
  ): Promise<OfflineTokenChain> {
    const tokens: OfflineToken[] = [];
    
    for (let i = 0; i < count; i++) {
      const token = await this.generateOfflineToken(deviceId, {
        sequence: i,
        validFrom: new Date(Date.now() + i * 24 * 60 * 60 * 1000),
        validFor: 24 * 60 * 60 * 1000, // 24 hours each
        
        // Chain tokens together
        previousHash: i > 0 ? this.hashToken(tokens[i - 1]) : undefined
      });
      
      tokens.push(token);
    }
    
    return {
      deviceId,
      tokens,
      
      // Sync configuration
      sync: {
        endpoint: '/auth/device/sync',
        interval: 24 * 60 * 60 * 1000, // Daily sync
        strategy: 'opportunistic' // Sync when connection available
      }
    };
  }
  
  async validateOfflineToken(
    token: string,
    context: OfflineContext
  ): Promise<OfflineValidation> {
    // Parse token
    const parsed = this.parseOfflineToken(token);
    
    // Verify signature using cached public key
    const valid = await this.verifyOfflineSignature(
      parsed,
      context.cachedPublicKey
    );
    
    if (!valid) {
      return {
        valid: false,
        reason: 'Invalid signature'
      };
    }
    
    // Check time validity (allowing for clock drift)
    const now = Date.now();
    const drift = context.maxClockDrift || 300000; // 5 minutes
    
    if (parsed.validFrom - drift > now || parsed.validTo + drift < now) {
      return {
        valid: false,
        reason: 'Token not valid at current time'
      };
    }
    
    // Check if token has been used (replay protection)
    if (await this.isTokenUsed(parsed.tokenId, context)) {
      return {
        valid: false,
        reason: 'Token already used'
      };
    }
    
    // Mark token as used
    await this.markTokenUsed(parsed.tokenId, context);
    
    return {
      valid: true,
      deviceId: parsed.deviceId,
      permissions: parsed.permissions,
      
      // Next token hint
      nextToken: parsed.nextTokenHint
    };
  }
  
  async syncOfflineState(
    deviceId: string,
    state: OfflineState
  ): Promise<SyncResult> {
    // Validate device
    const device = await this.devices.get(deviceId);
    
    // Process used tokens
    const usedTokens = state.usedTokens || [];
    await this.processUsedTokens(deviceId, usedTokens);
    
    // Generate new tokens if needed
    const remainingTokens = state.remainingTokens || 0;
    let newTokens: OfflineToken[] = [];
    
    if (remainingTokens < 10) {
      newTokens = await this.generateOfflineTokenChain(
        deviceId,
        30 - remainingTokens
      ).then(chain => chain.tokens);
    }
    
    // Update cached keys
    const keys = await this.getLatestKeys();
    
    return {
      newTokens,
      
      // Updated security material
      security: {
        publicKeys: keys.public,
        rootCertificate: keys.rootCert,
        
        // CRL for offline certificate validation
        crl: await this.getCRL(),
        crlNextUpdate: await this.getCRLNextUpdate()
      },
      
      // Device configuration updates
      config: await this.getDeviceConfig(deviceId),
      
      // Firmware update if available
      firmware: await this.checkFirmwareUpdate(device)
    };
  }
}
```

## Device Attestation

### TPM-Based Attestation

```typescript
class TPMAttestationService {
  async performAttestation(
    device: DeviceIdentity,
    challenge: Buffer
  ): Promise<AttestationResult> {
    // Step 1: Request attestation from device
    const attestation = await this.requestAttestation(device.deviceId, {
      challenge,
      pcrs: [0, 1, 2, 3, 4, 5, 6, 7], // Boot measurements
      
      // Quote type
      quoteType: 'TPM2_Quote',
      
      // Signature scheme
      signatureScheme: 'RSASSA'
    });
    
    // Step 2: Verify attestation
    const verification = await this.verifyAttestation(attestation, {
      // Verify signature
      verifySignature: true,
      
      // Verify PCR values
      expectedPCRs: await this.getExpectedPCRs(device),
      
      // Verify certificate chain
      verifyCertChain: true,
      
      // Check against known good values
      referenceValues: await this.getReferenceValues(device.metadata.modelId)
    });
    
    // Step 3: Update device trust level
    if (verification.valid) {
      await this.updateTrustLevel(device.deviceId, {
        trustLevel: verification.trustScore,
        attestationStatus: 'verified',
        lastAttestation: new Date()
      });
    } else {
      await this.handleAttestationFailure(device.deviceId, verification);
    }
    
    return {
      valid: verification.valid,
      trustLevel: verification.trustScore,
      
      // Detailed results
      details: {
        pcrMatch: verification.pcrMatch,
        signatureValid: verification.signatureValid,
        certificateValid: verification.certificateValid,
        
        // Security recommendations
        recommendations: verification.recommendations
      }
    };
  }
  
  async continuousAttestation(
    deviceId: string,
    options: ContinuousAttestationOptions
  ): Promise<void> {
    // Set up periodic attestation
    const interval = options.interval || 3600000; // 1 hour default
    
    const attestationJob = async () => {
      try {
        const device = await this.devices.get(deviceId);
        const challenge = crypto.randomBytes(32);
        
        const result = await this.performAttestation(device, challenge);
        
        if (!result.valid) {
          // Handle attestation failure
          await this.handleAttestationFailure(deviceId, result);
          
          // Notify security team
          await this.notifySecurityTeam({
            deviceId,
            event: 'attestation_failure',
            details: result.details
          });
        }
        
        // Log attestation event
        await this.audit.log({
          eventType: 'DEVICE_ATTESTATION',
          deviceId,
          result: result.valid ? 'success' : 'failure',
          trustLevel: result.trustLevel
        });
      } catch (error) {
        console.error(`Attestation failed for device ${deviceId}:`, error);
      }
    };
    
    // Schedule periodic attestation
    setInterval(attestationJob, interval);
    
    // Perform initial attestation
    await attestationJob();
  }
}
```

## Constrained Device Support

### Resource-Optimized Authentication

```typescript
class ConstrainedDeviceAuth {
  async authenticateConstrained(
    request: ConstrainedAuthRequest
  ): Promise<ConstrainedAuthResponse> {
    // Use lightweight protocol based on device capabilities
    const protocol = this.selectProtocol(request.capabilities);
    
    switch (protocol) {
      case 'coap-psk':
        return await this.authenticateCoAPPSK(request);
        
      case 'mqtt-sas':
        return await this.authenticateMQTTSAS(request);
        
      case 'http-basic':
        return await this.authenticateHTTPBasic(request);
        
      case 'custom-binary':
        return await this.authenticateCustomBinary(request);
    }
  }
  
  private async authenticateCustomBinary(
    request: ConstrainedAuthRequest
  ): Promise<ConstrainedAuthResponse> {
    // Parse binary authentication packet
    const packet = this.parseBinaryPacket(request.data);
    
    // Minimal packet structure (20 bytes)
    // [Device ID: 8 bytes][Timestamp: 4 bytes][Signature: 8 bytes]
    
    const deviceId = packet.slice(0, 8);
    const timestamp = packet.readUInt32BE(8);
    const signature = packet.slice(12, 20);
    
    // Verify timestamp (prevent replay)
    const now = Math.floor(Date.now() / 1000);
    if (Math.abs(now - timestamp) > 300) { // 5 minute window
      return {
        authenticated: false,
        code: 0x01 // Time sync error
      };
    }
    
    // Verify signature using pre-shared key
    const device = await this.getDeviceByShortId(deviceId);
    const expected = this.computeSignature(deviceId, timestamp, device.psk);
    
    if (!signature.equals(expected)) {
      return {
        authenticated: false,
        code: 0x02 // Signature error
      };
    }
    
    // Generate minimal response (12 bytes)
    // [Session: 4 bytes][Expires: 4 bytes][Permissions: 4 bytes]
    const response = Buffer.alloc(12);
    const sessionId = crypto.randomBytes(4);
    response.writeUInt32BE(sessionId.readUInt32BE(0), 0);
    response.writeUInt32BE(now + 3600, 4); // 1 hour expiry
    response.writeUInt32BE(device.permissions, 8);
    
    return {
      authenticated: true,
      data: response
    };
  }
  
  async optimizeForMCU(config: MCUConfig): Promise<MCUAuthConfig> {
    return {
      // Minimal TLS configuration
      tls: config.tlsCapable ? {
        version: 'TLS_1.2',
        cipherSuite: 'TLS_ECDHE_ECDSA_WITH_AES_128_CCM_8', // Optimized for MCU
        certificate: 'compressed', // Use certificate compression
        sessionResumption: true
      } : undefined,
      
      // Binary protocol for non-TLS
      binary: !config.tlsCapable ? {
        packetSize: 64, // Small packet size
        authMethod: 'hmac-sha256-truncated',
        compression: true
      } : undefined,
      
      // Memory requirements
      memory: {
        heap: config.tlsCapable ? 16384 : 4096, // 16KB or 4KB
        stack: config.tlsCapable ? 8192 : 2048   // 8KB or 2KB
      },
      
      // Code size
      codeSize: {
        authLibrary: config.tlsCapable ? 32768 : 8192, // 32KB or 8KB
        cryptoLibrary: config.tlsCapable ? 16384 : 4096 // 16KB or 4KB
      }
    };
  }
}
```

## Edge Gateway Integration

### Edge Authentication Gateway

```typescript
class EdgeGatewayService {
  async deployEdgeGateway(config: EdgeGatewayConfig): Promise<EdgeGateway> {
    // Deploy authentication gateway at edge
    const gateway = await this.createGateway({
      location: config.location,
      capacity: config.capacity,
      
      // Local authentication cache
      cache: {
        size: config.cacheSize || 10000,
        ttl: config.cacheTTL || 3600,
        
        // Cached items
        items: ['tokens', 'certificates', 'policies']
      },
      
      // Offline capabilities
      offline: {
        enabled: true,
        maxOfflineDuration: 7 * 24 * 60 * 60 * 1000, // 7 days
        syncInterval: 60 * 60 * 1000 // 1 hour
      },
      
      // Protocol support
      protocols: {
        mqtt: { port: 8883, tls: true },
        coap: { port: 5684, dtls: true },
        https: { port: 443 },
        
        // Custom protocols
        custom: config.customProtocols
      }
    });
    
    // Configure device routing
    await this.configureRouting(gateway, {
      // Route devices to nearest gateway
      strategy: 'geo-nearest',
      
      // Failover configuration
      failover: {
        enabled: true,
        backup: config.backupGateways
      }
    });
    
    return gateway;
  }
  
  async handleEdgeAuthentication(
    request: EdgeAuthRequest,
    gateway: EdgeGateway
  ): Promise<EdgeAuthResponse> {
    // Try local cache first
    const cached = await gateway.cache.get(request.deviceId);
    
    if (cached && !this.isExpired(cached)) {
      return {
        authenticated: true,
        source: 'cache',
        latency: 1 // 1ms from cache
      };
    }
    
    // Authenticate with edge gateway
    try {
      const result = await gateway.authenticate(request);
      
      // Cache successful authentication
      if (result.authenticated) {
        await gateway.cache.set(request.deviceId, result, {
          ttl: this.calculateTTL(result)
        });
      }
      
      return {
        ...result,
        source: 'edge',
        latency: 10 // 10ms from edge
      };
    } catch (error) {
      // Fallback to cloud if edge fails
      if (gateway.config.cloudFallback) {
        const cloudResult = await this.authenticateCloud(request);
        
        return {
          ...cloudResult,
          source: 'cloud',
          latency: 100 // 100ms from cloud
        };
      }
      
      throw error;
    }
  }
}
```

## Firmware & OTA Updates

### Secure Firmware Updates

```typescript
class FirmwareUpdateService {
  async createFirmwareUpdate(
    firmware: FirmwarePackage
  ): Promise<FirmwareRelease> {
    // Sign firmware
    const signature = await this.signFirmware(firmware.binary, {
      algorithm: 'RSA-SHA256',
      key: this.signingKey
    });
    
    // Create manifest
    const manifest = {
      version: firmware.version,
      size: firmware.binary.length,
      checksum: this.calculateChecksum(firmware.binary),
      signature,
      
      // Compatibility
      compatibility: {
        minHardwareVersion: firmware.minHardware,
        maxHardwareVersion: firmware.maxHardware,
        requiredFeatures: firmware.requiredFeatures
      },
      
      // Rollback information
      rollback: {
        allowed: firmware.rollbackAllowed,
        previousVersion: firmware.previousVersion
      },
      
      // Deployment configuration
      deployment: {
        strategy: firmware.deploymentStrategy || 'phased',
        phases: firmware.phases || [
          { percentage: 1, duration: 24 },   // 1% for 24 hours
          { percentage: 10, duration: 48 },  // 10% for 48 hours
          { percentage: 50, duration: 72 },  // 50% for 72 hours
          { percentage: 100, duration: 0 }   // 100%
        ]
      }
    };
    
    // Store firmware
    const release = await this.storeFirmware({
      binary: firmware.binary,
      manifest,
      
      // CDN distribution
      cdn: {
        regions: firmware.regions || ['global'],
        compression: true,
        encryption: true
      }
    });
    
    return release;
  }
  
  async updateDevice(
    deviceId: string,
    targetVersion: string
  ): Promise<UpdateResult> {
    const device = await this.devices.get(deviceId);
    
    // Check compatibility
    const compatible = await this.checkCompatibility(device, targetVersion);
    if (!compatible) {
      return {
        success: false,
        reason: 'Incompatible firmware version'
      };
    }
    
    // Get firmware URL
    const firmware = await this.getFirmware(targetVersion);
    
    // Send update command
    const command = {
      type: 'FIRMWARE_UPDATE',
      version: targetVersion,
      url: firmware.downloadUrl,
      checksum: firmware.checksum,
      signature: firmware.signature,
      
      // Update window
      window: {
        start: new Date(),
        end: new Date(Date.now() + 24 * 60 * 60 * 1000)
      }
    };
    
    // Send via appropriate protocol
    const result = await this.sendCommand(device, command);
    
    // Monitor update progress
    await this.monitorUpdate(deviceId, targetVersion);
    
    return result;
  }
}
```

## Monitoring & Analytics

### Device Fleet Management

```typescript
class FleetManagementService {
  async getFleetStatus(
    organizationId: string
  ): Promise<FleetStatus> {
    const devices = await this.devices.findByOrganization(organizationId);
    
    return {
      // Overview
      total: devices.length,
      
      // Status breakdown
      byStatus: {
        active: devices.filter(d => d.lifecycle.status === 'active').length,
        suspended: devices.filter(d => d.lifecycle.status === 'suspended').length,
        provisioning: devices.filter(d => d.lifecycle.status === 'provisioning').length,
        decommissioned: devices.filter(d => d.lifecycle.status === 'decommissioned').length
      },
      
      // Health metrics
      health: {
        healthy: devices.filter(d => d.security.trustLevel > 80).length,
        degraded: devices.filter(d => d.security.trustLevel >= 50 && d.security.trustLevel <= 80).length,
        unhealthy: devices.filter(d => d.security.trustLevel < 50).length,
        compromised: devices.filter(d => d.security.compromised).length
      },
      
      // Connectivity
      connectivity: {
        online: devices.filter(d => this.isOnline(d)).length,
        offline: devices.filter(d => !this.isOnline(d)).length,
        lastSeen: {
          last1Hour: devices.filter(d => d.lifecycle.lastSeen > new Date(Date.now() - 3600000)).length,
          last24Hours: devices.filter(d => d.lifecycle.lastSeen > new Date(Date.now() - 86400000)).length,
          last7Days: devices.filter(d => d.lifecycle.lastSeen > new Date(Date.now() - 604800000)).length
        }
      },
      
      // Firmware versions
      firmwareVersions: this.groupByFirmwareVersion(devices),
      
      // Geographic distribution
      geographic: this.groupByLocation(devices),
      
      // Performance metrics
      performance: {
        avgAuthLatency: await this.calculateAvgAuthLatency(devices),
        authSuccessRate: await this.calculateAuthSuccessRate(devices),
        dataTransmissionRate: await this.calculateDataRate(devices)
      }
    };
  }
  
  async monitorDeviceHealth(
    deviceId: string
  ): Promise<DeviceHealth> {
    const metrics = await this.collectMetrics(deviceId, {
      period: 'last_24_hours',
      
      metrics: [
        'cpu_usage',
        'memory_usage',
        'disk_usage',
        'network_throughput',
        'error_rate',
        'restart_count',
        'auth_failures',
        'certificate_expiry'
      ]
    });
    
    return {
      deviceId,
      
      // Resource usage
      resources: {
        cpu: metrics.cpu_usage,
        memory: metrics.memory_usage,
        disk: metrics.disk_usage
      },
      
      // Network health
      network: {
        throughput: metrics.network_throughput,
        latency: metrics.network_latency,
        packetLoss: metrics.packet_loss
      },
      
      // Security health
      security: {
        authFailures: metrics.auth_failures,
        certificateExpiry: metrics.certificate_expiry,
        lastAttestation: metrics.last_attestation,
        trustLevel: metrics.trust_level
      },
      
      // Operational health
      operational: {
        uptime: metrics.uptime,
        restartCount: metrics.restart_count,
        errorRate: metrics.error_rate,
        lastError: metrics.last_error
      },
      
      // Recommendations
      recommendations: this.generateHealthRecommendations(metrics)
    };
  }
}
```

## Best Practices

### 1. Security First
- Use hardware-backed credentials when possible
- Implement attestation for critical devices
- Regular key rotation
- Secure boot validation

### 2. Scalability
- Edge gateway deployment
- Efficient caching strategies
- Protocol optimization
- Batch provisioning

### 3. Reliability
- Offline authentication support
- Multiple authentication methods
- Failover mechanisms
- Graceful degradation

### 4. Monitoring
- Real-time device health tracking
- Anomaly detection
- Predictive maintenance
- Security incident response

### 5. Lifecycle Management
- Automated provisioning
- Secure decommissioning
- Firmware update management
- Certificate lifecycle

## Support & Resources

- IoT Documentation: https://docs.janua.dev/iot
- Device SDKs: https://github.com/madfam-io/device-sdks
- Edge Gateway: https://github.com/madfam-io/edge-gateway
- Support: iot@janua.dev