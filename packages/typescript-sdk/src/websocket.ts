/**
 * WebSocket client module for Janua SDK
 * Provides real-time communication with automatic reconnection
 */

import { EventEmitter } from './utils'
import { logger } from './utils/logger'
import { NetworkError } from './errors'

export interface WebSocketConfig {
  url: string
  getAuthToken?: () => Promise<string | null> | string | null
  reconnect?: boolean
  reconnectInterval?: number
  reconnectAttempts?: number
  heartbeatInterval?: number
  debug?: boolean
  protocols?: string | string[]
}

export interface WebSocketMessage {
  type: string
  channel?: string
  data?: unknown
  event?: string
  timestamp?: number
}

export interface WebSocketEventMap {
  connected: { timestamp: number }
  disconnected: { code: number; reason: string }
  message: WebSocketMessage
  error: { error: Error }
  reconnecting: { attempt: number; maxAttempts: number }
  reconnected: { timestamp: number }
}

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'error'

/**
 * WebSocket client with automatic reconnection and heartbeat
 */
export class WebSocket extends EventEmitter<WebSocketEventMap> {
  private ws: globalThis.WebSocket | null = null
  private config: Required<WebSocketConfig>
  private status: WebSocketStatus = 'disconnected'
  private reconnectAttempt = 0
  private reconnectTimer: NodeJS.Timeout | null = null
  private heartbeatTimer: NodeJS.Timeout | null = null
  private channels = new Set<string>()
  private intentionallyClosed = false

  constructor(config: WebSocketConfig) {
    super()

    this.config = {
      url: config.url,
      getAuthToken: config.getAuthToken || (() => null),
      reconnect: config.reconnect ?? true,
      reconnectInterval: config.reconnectInterval || 5000,
      reconnectAttempts: config.reconnectAttempts || 5,
      heartbeatInterval: config.heartbeatInterval || 30000,
      debug: config.debug ?? false,
      protocols: config.protocols ?? [],
    }
  }

  /**
   * Connect to WebSocket server
   */
  async connect(): Promise<void> {
    if (this.ws && this.status === 'connected') {
      logger.warn('WebSocket already connected')
      return
    }

    this.intentionallyClosed = false
    this.setStatus('connecting')

    try {
      const token = await this.config.getAuthToken()

      // Security: Never send auth token as URL query parameter (visible in logs, referrer headers, etc.)
      // Instead, connect without token and send auth as first message after open.
      this.ws = new globalThis.WebSocket(this.config.url, this.config.protocols)

      this.ws.onopen = () => {
        // Send auth token as first message after connection established
        if (token && this.ws) {
          this.ws.send(JSON.stringify({ type: 'auth', token }))
        }
        this.handleOpen()
      }
      this.ws.onmessage = (event) => this.handleMessage(event)
      this.ws.onerror = (event) => this.handleError(event)
      this.ws.onclose = (event) => this.handleClose(event)
    } catch (error) {
      this.handleError(error as Error)
      throw error
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.intentionallyClosed = true
    this.clearTimers()

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }

    this.setStatus('disconnected')
  }

  /**
   * Send a message to the server
   */
  send(message: WebSocketMessage): void {
    if (!this.ws || this.status !== 'connected') {
      throw new NetworkError('WebSocket not connected')
    }

    const payload = JSON.stringify({
      ...message,
      timestamp: Date.now(),
    })

    this.ws.send(payload)

    if (this.config.debug) {
      logger.info('WebSocket message sent:', message)
    }
  }

  /**
   * Subscribe to a channel
   */
  subscribe(channel: string): void {
    if (this.channels.has(channel)) {
      logger.warn(`Already subscribed to channel: ${channel}`)
      return
    }

    this.channels.add(channel)
    this.send({
      type: 'subscribe',
      channel,
    })

    if (this.config.debug) {
      logger.info(`Subscribed to channel: ${channel}`)
    }
  }

  /**
   * Unsubscribe from a channel
   */
  unsubscribe(channel: string): void {
    if (!this.channels.has(channel)) {
      logger.warn(`Not subscribed to channel: ${channel}`)
      return
    }

    this.channels.delete(channel)
    this.send({
      type: 'unsubscribe',
      channel,
    })

    if (this.config.debug) {
      logger.info(`Unsubscribed from channel: ${channel}`)
    }
  }

  /**
   * Publish a message to a channel
   */
  publish(channel: string, data: unknown, event?: string): void {
    this.send({
      type: 'publish',
      channel,
      data,
      event,
    })
  }

  /**
   * Get current connection status
   */
  getStatus(): WebSocketStatus {
    return this.status
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.status === 'connected'
  }

  /**
   * Get subscribed channels
   */
  getChannels(): string[] {
    return Array.from(this.channels)
  }

  /**
   * Handle WebSocket open event
   */
  private handleOpen(): void {
    this.setStatus('connected')
    this.reconnectAttempt = 0

    this.emit('connected', { timestamp: Date.now() })

    if (this.config.debug) {
      logger.info('WebSocket connected')
    }

    // Start heartbeat
    this.startHeartbeat()

    // Resubscribe to channels after reconnection
    if (this.channels.size > 0) {
      for (const channel of this.channels) {
        this.send({
          type: 'subscribe',
          channel,
        })
      }
    }
  }

  /**
   * Handle WebSocket message event
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)

      this.emit('message', message)

      if (this.config.debug) {
        logger.info('WebSocket message received:', message)
      }

      // Handle pong response
      if (message.type === 'pong') {
        if (this.config.debug) {
          logger.info('Heartbeat pong received')
        }
      }
    } catch (error) {
      logger.error('Failed to parse WebSocket message:', error)
    }
  }

  /**
   * Handle WebSocket error event
   */
  private handleError(error: Error | Event): void {
    this.setStatus('error')

    const err = error instanceof Error ? error : new Error('WebSocket error')
    this.emit('error', { error: err })

    logger.error('WebSocket error:', err)
  }

  /**
   * Handle WebSocket close event
   */
  private handleClose(event: CloseEvent): void {
    this.setStatus('disconnected')
    this.clearTimers()

    this.emit('disconnected', {
      code: event.code,
      reason: event.reason || 'Unknown',
    })

    if (this.config.debug) {
      logger.info(`WebSocket closed: ${event.code} - ${event.reason}`)
    }

    // Attempt reconnection if not intentionally closed
    if (!this.intentionallyClosed && this.config.reconnect) {
      this.attemptReconnect()
    }
  }

  /**
   * Attempt to reconnect to the server
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempt >= this.config.reconnectAttempts) {
      logger.error('Max reconnection attempts reached')
      return
    }

    this.reconnectAttempt++
    this.setStatus('reconnecting')

    this.emit('reconnecting', {
      attempt: this.reconnectAttempt,
      maxAttempts: this.config.reconnectAttempts,
    })

    if (this.config.debug) {
      logger.info(
        `Reconnecting... (${this.reconnectAttempt}/${this.config.reconnectAttempts})`
      )
    }

    this.reconnectTimer = setTimeout(() => {
      this.connect().catch((error) => {
        logger.error('Reconnection failed:', error)
      })
    }, this.config.reconnectInterval)
  }

  /**
   * Start heartbeat to keep connection alive
   */
  private startHeartbeat(): void {
    this.clearHeartbeat()

    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.status === 'connected') {
        this.send({ type: 'ping' })

        if (this.config.debug) {
          logger.info('Heartbeat ping sent')
        }
      }
    }, this.config.heartbeatInterval)
  }

  /**
   * Clear heartbeat timer
   */
  private clearHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  /**
   * Clear all timers
   */
  private clearTimers(): void {
    this.clearHeartbeat()

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  /**
   * Set connection status
   */
  private setStatus(status: WebSocketStatus): void {
    this.status = status
  }
}

/**
 * Create a WebSocket client instance
 */
export function createWebSocketClient(config: WebSocketConfig): WebSocket {
  return new WebSocket(config)
}

/**
 * Options for WebSocketClient constructor (alternative signature)
 */
export interface WebSocketClientOptions {
  token?: string
  autoReconnect?: boolean
  heartbeatInterval?: number
  debug?: boolean
  protocols?: string | string[]
}

/**
 * WebSocketClient - Alternative API with (url, options) constructor
 *
 * This class provides a more traditional WebSocket client API where the URL
 * is passed as the first argument and options as the second. It wraps the
 * WebSocket class internally.
 */
export class WebSocketClient extends EventEmitter<WebSocketEventMap> {
  private ws: WebSocket
  private subscriptions = new Map<string, (message: unknown) => void>()

  constructor(url: string, options: WebSocketClientOptions = {}) {
    super()

    this.ws = new WebSocket({
      url,
      getAuthToken: options.token ? () => options.token! : undefined,
      reconnect: options.autoReconnect ?? true,
      heartbeatInterval: options.heartbeatInterval ?? 30000,
      debug: options.debug ?? false,
      protocols: options.protocols,
    })

    // Forward all events from the underlying WebSocket
    this.ws.on('connected', (data) => this.emit('connected', data))
    this.ws.on('disconnected', (data) => this.emit('disconnected', data))
    this.ws.on('message', (data) => {
      this.emit('message', data)
      // Route to channel subscriptions
      if (data.channel && this.subscriptions.has(data.channel)) {
        const handler = this.subscriptions.get(data.channel)
        if (handler) {
          handler(data.data)
        }
      }
    })
    this.ws.on('error', (data) => this.emit('error', data))
    this.ws.on('reconnecting', (data) => this.emit('reconnecting', data))
    this.ws.on('reconnected', (data) => this.emit('reconnected', data))
  }

  /**
   * Connect to the WebSocket server
   */
  connect(): Promise<void> {
    return this.ws.connect()
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): Promise<void> {
    this.ws.disconnect()
    return Promise.resolve()
  }

  /**
   * Subscribe to a channel with a callback
   */
  subscribe(channel: string, callback: (message: unknown) => void): Promise<void> {
    this.subscriptions.set(channel, callback)
    this.ws.subscribe(channel)
    return Promise.resolve()
  }

  /**
   * Unsubscribe from a channel
   */
  unsubscribe(channel: string): Promise<void> {
    this.subscriptions.delete(channel)
    this.ws.unsubscribe(channel)
    return Promise.resolve()
  }

  /**
   * Publish a message to a channel
   */
  publish(channel: string, data: unknown, event?: string): Promise<void> {
    this.ws.publish(channel, data, event)
    return Promise.resolve()
  }

  /**
   * Get current connection status
   */
  getStatus(): WebSocketStatus {
    return this.ws.getStatus()
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws.isConnected()
  }

  /**
   * Get subscribed channels
   */
  getChannels(): string[] {
    return this.ws.getChannels()
  }
}
