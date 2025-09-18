/**
 * WebSocket Service for Real-time Features
 * Manages WebSocket connections, rooms, and real-time event broadcasting
 */

import { EventEmitter } from 'events';
import { Server, Socket } from 'socket.io';
import { createAdapter } from '@socket.io/redis-adapter';
import * as jwt from 'jsonwebtoken';
import crypto from 'crypto';

export interface WebSocketConfig {
  cors?: {
    origin: string | string[];
    credentials: boolean;
  };
  pingTimeout?: number;
  pingInterval?: number;
  maxPayloadSize?: number;
  transports?: string[];
  path?: string;
  jwt_secret: string;
  redis_client?: any; // For scaling across multiple servers
  allowedOrigins?: string | string[];
}

export interface WebSocketClient {
  id: string;
  socket_id: string;
  user_id?: string;
  organization_id?: string;
  session_id?: string;
  ip_address: string;
  user_agent: string;
  connected_at: Date;
  last_activity: Date;
  rooms: Set<string>;
  metadata?: Record<string, any>;
}

export interface WebSocketRoom {
  name: string;
  type: 'user' | 'organization' | 'team' | 'channel' | 'presence' | 'private';
  created_at: Date;
  members: Set<string>; // socket IDs
  metadata?: Record<string, any>;
  max_members?: number;
  presence_tracking?: boolean;
}

export interface WebSocketMessage {
  id: string;
  event: string;
  data: any;
  room?: string;
  sender_id?: string;
  timestamp: Date;
  acknowledge?: boolean;
  retry_count?: number;
}

export interface PresenceData {
  user_id: string;
  status: 'online' | 'away' | 'busy' | 'offline';
  last_seen: Date;
  metadata?: Record<string, any>;
}

export interface WebSocketMetrics {
  total_connections: number;
  active_connections: number;
  authenticated_connections: number;
  rooms_count: number;
  messages_sent: number;
  messages_received: number;
  average_latency_ms: number;
  errors_count: number;
  reconnections_count: number;
}

export class WebSocketService extends EventEmitter {
  private io: Server | null = null;
  private clients: Map<string, WebSocketClient> = new Map();
  private rooms: Map<string, WebSocketRoom> = new Map();
  private presence: Map<string, PresenceData> = new Map();
  private messageQueue: Map<string, WebSocketMessage[]> = new Map();
  private metrics: WebSocketMetrics = {
    total_connections: 0,
    active_connections: 0,
    authenticated_connections: 0,
    rooms_count: 0,
    messages_sent: 0,
    messages_received: 0,
    average_latency_ms: 0,
    errors_count: 0,
    reconnections_count: 0
  };
  private latencyMeasurements: number[] = [];

  constructor(private readonly config: WebSocketConfig) {
    super();
  }

  /**
   * Initialize WebSocket server
   */
  initialize(server: any): void {
    this.io = new Server(server, {
      cors: {
        origin: this.config.allowedOrigins || '*',
        credentials: true
      },
      pingTimeout: this.config.pingTimeout || 60000,
      pingInterval: this.config.pingInterval || 25000,
      maxHttpBufferSize: this.config.maxPayloadSize || 1e7, // 10MB
      transports: (this.config.transports || ['websocket', 'polling']) as any,
      path: this.config.path || '/ws'
    });

    this.setupMiddleware();
    this.setupEventHandlers();
    this.startMetricsCollection();

    this.emit('websocket:initialized');
  }

  /**
   * Setup authentication middleware
   */
  private setupMiddleware(): void {
    if (!this.io) return;

    this.io.use(async (socket: Socket, next: any) => {
      try {
        const token = socket.handshake.auth.token || socket.handshake.headers.authorization;
        
        if (!token) {
          // Allow anonymous connections but mark them
          socket.data.authenticated = false;
          return next();
        }

        // Verify JWT token
        const decoded = jwt.verify(token.replace('Bearer ', ''), this.config.jwt_secret) as any;
        
        socket.data.user_id = decoded.user_id;
        socket.data.session_id = decoded.session_id;
        socket.data.organization_id = decoded.organization_id;
        socket.data.authenticated = true;

        next();
      } catch (error) {
        next(new Error('Authentication failed'));
      }
    });
  }

  /**
   * Setup event handlers
   */
  private setupEventHandlers(): void {
    if (!this.io) return;

    this.io.on('connection', (socket: Socket) => {
      this.handleConnection(socket);

      // Core events
      socket.on('disconnect', () => this.handleDisconnect(socket));
      socket.on('error', (error: any) => this.handleError(socket, error));
      
      // Room events
      socket.on('join:room', (data: any) => this.handleJoinRoom(socket, data));
      socket.on('leave:room', (data: any) => this.handleLeaveRoom(socket, data));
      
      // Messaging events
      socket.on('message:send', (data: any) => this.handleMessage(socket, data));
      socket.on('message:typing', (data: any) => this.handleTyping(socket, data));
      
      // Presence events
      socket.on('presence:update', (data: any) => this.handlePresenceUpdate(socket, data));
      socket.on('presence:query', (data: any) => this.handlePresenceQuery(socket, data));
      
      // Real-time subscriptions
      socket.on('subscribe', (data: any) => this.handleSubscribe(socket, data));
      socket.on('unsubscribe', (data: any) => this.handleUnsubscribe(socket, data));
      
      // Ping for latency measurement
      socket.on('ping', () => this.handlePing(socket));
      
      // Custom events
      socket.on('custom:event', (data) => this.handleCustomEvent(socket, data));
    });
  }

  /**
   * Handle new connection
   */
  private handleConnection(socket: Socket): void {
    const client: WebSocketClient = {
      id: crypto.randomUUID(),
      socket_id: socket.id,
      user_id: socket.data.user_id,
      organization_id: socket.data.organization_id,
      session_id: socket.data.session_id,
      ip_address: socket.handshake.address,
      user_agent: socket.handshake.headers['user-agent'] || '',
      connected_at: new Date(),
      last_activity: new Date(),
      rooms: new Set()
    };

    this.clients.set(socket.id, client);
    
    // Update metrics
    this.metrics.total_connections++;
    this.metrics.active_connections++;
    if (socket.data.authenticated) {
      this.metrics.authenticated_connections++;
    }

    // Auto-join user and organization rooms if authenticated
    if (client.user_id) {
      this.joinRoom(socket, `user:${client.user_id}`, 'user');
    }
    if (client.organization_id) {
      this.joinRoom(socket, `org:${client.organization_id}`, 'organization');
    }

    // Send queued messages
    this.deliverQueuedMessages(socket);

    // Emit connection event
    socket.emit('connected', {
      socket_id: socket.id,
      authenticated: socket.data.authenticated
    });

    this.emit('client:connected', client);
  }

  /**
   * Handle disconnection
   */
  private handleDisconnect(socket: Socket): void {
    const client = this.clients.get(socket.id);
    if (!client) return;

    // Leave all rooms
    for (const roomName of client.rooms) {
      this.leaveRoom(socket, roomName);
    }

    // Update presence
    if (client.user_id) {
      this.updatePresence(client.user_id, 'offline');
    }

    // Remove client
    this.clients.delete(socket.id);

    // Update metrics
    this.metrics.active_connections--;
    if (socket.data.authenticated) {
      this.metrics.authenticated_connections--;
    }

    this.emit('client:disconnected', client);
  }

  /**
   * Handle errors
   */
  private handleError(socket: Socket, error: Error): void {
    console.error('WebSocket error:', error);
    
    this.metrics.errors_count++;
    
    this.emit('client:error', {
      socket_id: socket.id,
      error: error.message
    });
  }

  /**
   * Handle join room request
   */
  private async handleJoinRoom(socket: Socket, data: any): Promise<void> {
    const { room, type = 'channel' } = data;

    // Validate permission to join room
    if (!await this.canJoinRoom(socket, room, type)) {
      socket.emit('error', { message: 'Permission denied to join room' });
      return;
    }

    this.joinRoom(socket, room, type);
    
    socket.emit('room:joined', { room });
  }

  /**
   * Handle leave room request
   */
  private handleLeaveRoom(socket: Socket, data: any): void {
    const { room } = data;
    
    this.leaveRoom(socket, room);
    
    socket.emit('room:left', { room });
  }

  /**
   * Handle message
   */
  private async handleMessage(socket: Socket, data: any): Promise<void> {
    const client = this.clients.get(socket.id);
    if (!client) return;

    const message: WebSocketMessage = {
      id: crypto.randomUUID(),
      event: data.event || 'message',
      data: data.data,
      room: data.room,
      sender_id: client.user_id,
      timestamp: new Date(),
      acknowledge: data.acknowledge
    };

    // Update metrics
    this.metrics.messages_received++;
    client.last_activity = new Date();

    // Broadcast to room or specific socket
    if (message.room) {
      this.broadcastToRoom(message.room, message.event, message.data, socket.id);
    } else if (data.to) {
      this.sendToUser(data.to, message.event, message.data);
    }

    // Acknowledge if requested
    if (message.acknowledge) {
      socket.emit('message:ack', { id: message.id });
    }

    this.emit('message:received', message);
  }

  /**
   * Handle typing indicator
   */
  private handleTyping(socket: Socket, data: any): void {
    const client = this.clients.get(socket.id);
    if (!client || !client.user_id) return;

    const { room, typing } = data;

    this.broadcastToRoom(room, 'user:typing', {
      user_id: client.user_id,
      typing
    }, socket.id);
  }

  /**
   * Handle presence update
   */
  private handlePresenceUpdate(socket: Socket, data: any): void {
    const client = this.clients.get(socket.id);
    if (!client || !client.user_id) return;

    const { status, metadata } = data;

    this.updatePresence(client.user_id, status, metadata);

    // Broadcast to user's rooms
    for (const room of client.rooms) {
      this.broadcastToRoom(room, 'presence:updated', {
        user_id: client.user_id,
        status,
        metadata
      }, socket.id);
    }
  }

  /**
   * Handle presence query
   */
  private handlePresenceQuery(socket: Socket, data: any): void {
    const { user_ids } = data;
    
    const presence: Record<string, PresenceData> = {};
    
    for (const userId of user_ids) {
      const userPresence = this.presence.get(userId);
      if (userPresence) {
        presence[userId] = userPresence;
      }
    }

    socket.emit('presence:status', presence);
  }

  /**
   * Handle subscription
   */
  private async handleSubscribe(socket: Socket, data: any): Promise<void> {
    const { channel, filters } = data;

    // Validate subscription permission
    if (!await this.canSubscribe(socket, channel)) {
      socket.emit('error', { message: 'Permission denied to subscribe' });
      return;
    }

    // Create subscription room
    const roomName = `subscription:${channel}:${socket.id}`;
    this.joinRoom(socket, roomName, 'private');

    // Setup event forwarding based on channel
    this.setupSubscriptionForwarding(socket, channel, filters);

    socket.emit('subscribed', { channel });
  }

  /**
   * Handle unsubscribe
   */
  private handleUnsubscribe(socket: Socket, data: any): void {
    const { channel } = data;
    
    const roomName = `subscription:${channel}:${socket.id}`;
    this.leaveRoom(socket, roomName);

    socket.emit('unsubscribed', { channel });
  }

  /**
   * Handle ping for latency measurement
   */
  private handlePing(socket: Socket): void {
    const start = Date.now();
    
    socket.emit('pong', { timestamp: start }, () => {
      const latency = Date.now() - start;
      this.recordLatency(latency);
      
      socket.emit('latency', { ms: latency });
    });
  }

  /**
   * Handle custom events
   */
  private async handleCustomEvent(socket: Socket, data: any): Promise<void> {
    const client = this.clients.get(socket.id);
    if (!client) return;

    // Emit for custom processing
    this.emit('custom:event', {
      client,
      event: data.event,
      data: data.data
    });
  }

  /**
   * Broadcast event to all clients
   */
  broadcast(event: string, data: any): void {
    if (!this.io) return;

    this.io.emit(event, data);
    this.metrics.messages_sent++;
  }

  /**
   * Broadcast to specific room
   */
  broadcastToRoom(room: string, event: string, data: any, exclude?: string): void {
    if (!this.io) return;

    if (exclude) {
      this.io.to(room).except(exclude).emit(event, data);
    } else {
      this.io.to(room).emit(event, data);
    }

    this.metrics.messages_sent++;
  }

  /**
   * Send to specific user
   */
  sendToUser(userId: string, event: string, data: any): void {
    const room = `user:${userId}`;
    this.broadcastToRoom(room, event, data);
  }

  /**
   * Send to specific organization
   */
  sendToOrganization(organizationId: string, event: string, data: any): void {
    const room = `org:${organizationId}`;
    this.broadcastToRoom(room, event, data);
  }

  /**
   * Send to specific socket
   */
  sendToSocket(socketId: string, event: string, data: any): void {
    if (!this.io) return;

    this.io.to(socketId).emit(event, data);
    this.metrics.messages_sent++;
  }

  /**
   * Queue message for offline delivery
   */
  queueMessage(userId: string, message: WebSocketMessage): void {
    if (!this.messageQueue.has(userId)) {
      this.messageQueue.set(userId, []);
    }

    const queue = this.messageQueue.get(userId)!;
    queue.push(message);

    // Limit queue size
    if (queue.length > 100) {
      queue.shift();
    }
  }

  /**
   * Deliver queued messages
   */
  private deliverQueuedMessages(socket: Socket): void {
    const client = this.clients.get(socket.id);
    if (!client || !client.user_id) return;

    const queue = this.messageQueue.get(client.user_id);
    if (!queue || queue.length === 0) return;

    for (const message of queue) {
      socket.emit(message.event, message.data);
    }

    this.messageQueue.delete(client.user_id);
  }

  /**
   * Join room
   */
  private joinRoom(socket: Socket, roomName: string, type: WebSocketRoom['type'] = 'channel'): void {
    const client = this.clients.get(socket.id);
    if (!client) return;

    // Create room if doesn't exist
    if (!this.rooms.has(roomName)) {
      this.rooms.set(roomName, {
        name: roomName,
        type,
        created_at: new Date(),
        members: new Set(),
        presence_tracking: type === 'presence'
      });
      this.metrics.rooms_count++;
    }

    const room = this.rooms.get(roomName)!;
    
    // Check max members
    if (room.max_members && room.members.size >= room.max_members) {
      socket.emit('error', { message: 'Room is full' });
      return;
    }

    // Join room
    socket.join(roomName);
    room.members.add(socket.id);
    client.rooms.add(roomName);

    // Notify room members
    if (room.presence_tracking && client.user_id) {
      this.broadcastToRoom(roomName, 'member:joined', {
        user_id: client.user_id,
        timestamp: new Date()
      }, socket.id);
    }
  }

  /**
   * Leave room
   */
  private leaveRoom(socket: Socket, roomName: string): void {
    const client = this.clients.get(socket.id);
    if (!client) return;

    const room = this.rooms.get(roomName);
    if (!room) return;

    // Leave room
    socket.leave(roomName);
    room.members.delete(socket.id);
    client.rooms.delete(roomName);

    // Notify room members
    if (room.presence_tracking && client.user_id) {
      this.broadcastToRoom(roomName, 'member:left', {
        user_id: client.user_id,
        timestamp: new Date()
      });
    }

    // Delete empty rooms (except user and org rooms)
    if (room.members.size === 0 && !roomName.startsWith('user:') && !roomName.startsWith('org:')) {
      this.rooms.delete(roomName);
      this.metrics.rooms_count--;
    }
  }

  /**
   * Update user presence
   */
  private updatePresence(userId: string, status: PresenceData['status'], metadata?: any): void {
    this.presence.set(userId, {
      user_id: userId,
      status,
      last_seen: new Date(),
      metadata
    });

    this.emit('presence:changed', {
      user_id: userId,
      status,
      metadata
    });
  }

  /**
   * Check if socket can join room
   */
  private async canJoinRoom(socket: Socket, room: string, type: string): Promise<boolean> {
    const client = this.clients.get(socket.id);
    if (!client) return false;

    // Public rooms are open
    if (type === 'channel') return true;

    // User rooms - only the user can join
    if (type === 'user' && room.startsWith('user:')) {
      const userId = room.split(':')[1];
      return client.user_id === userId;
    }

    // Organization rooms - must be member
    if (type === 'organization' && room.startsWith('org:')) {
      const orgId = room.split(':')[1];
      return client.organization_id === orgId;
    }

    // Private rooms need explicit permission
    if (type === 'private') {
      // Implement permission check
      return false;
    }

    return false;
  }

  /**
   * Check if socket can subscribe to channel
   */
  private async canSubscribe(socket: Socket, channel: string): Promise<boolean> {
    const client = this.clients.get(socket.id);
    if (!client || !client.user_id) return false;

    // Implement channel-specific permission checks
    return true;
  }

  /**
   * Setup subscription event forwarding
   */
  private setupSubscriptionForwarding(socket: Socket, channel: string, filters: any): void {
    // Implement event forwarding based on channel type
    // This would connect to your event system and forward relevant events
  }

  /**
   * Record latency measurement
   */
  private recordLatency(latency: number): void {
    this.latencyMeasurements.push(latency);
    
    // Keep only last 1000 measurements
    if (this.latencyMeasurements.length > 1000) {
      this.latencyMeasurements.shift();
    }

    // Update average
    const sum = this.latencyMeasurements.reduce((a, b) => a + b, 0);
    this.metrics.average_latency_ms = Math.round(sum / this.latencyMeasurements.length);
  }

  /**
   * Start metrics collection
   */
  private startMetricsCollection(): void {
    setInterval(() => {
      this.emit('metrics:update', this.getMetrics());
    }, 10000); // Every 10 seconds
  }

  /**
   * Get metrics
   */
  getMetrics(): WebSocketMetrics {
    return { ...this.metrics };
  }

  /**
   * Get connected clients
   */
  getClients(): WebSocketClient[] {
    return Array.from(this.clients.values());
  }

  /**
   * Get rooms
   */
  getRooms(): WebSocketRoom[] {
    return Array.from(this.rooms.values());
  }

  /**
   * Disconnect client
   */
  disconnectClient(socketId: string, reason: string = 'Server disconnect'): void {
    if (!this.io) return;

    const socket = this.io.sockets.sockets.get(socketId);
    if (socket) {
      socket.disconnect(true);
    }
  }

  /**
   * Shutdown service
   */
  async shutdown(): Promise<void> {
    if (!this.io) return;

    // Disconnect all clients
    this.io.disconnectSockets(true);
    
    // Close server
    this.io.close();
    
    // Clear data
    this.clients.clear();
    this.rooms.clear();
    this.presence.clear();
    this.messageQueue.clear();

    this.emit('websocket:shutdown');
  }
}

// Export factory function
export function createWebSocketService(config: WebSocketConfig): WebSocketService {
  return new WebSocketService(config);
}