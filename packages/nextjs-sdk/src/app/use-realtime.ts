/**
 * Next.js client-side hook for real-time auth events via WebSocket
 *
 * Client-only — uses 'use client' directive.
 * Wraps the typescript-sdk WebSocket client with React lifecycle management.
 */
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { WebSocket as JanuaWebSocket } from '@janua/typescript-sdk';
import type { WebSocketConfig, WebSocketStatus, WebSocketMessage, WebSocketEventMap } from '@janua/typescript-sdk';
import { useJanua } from './provider';

export interface UseRealtimeOptions {
  /** Channels to auto-subscribe on connect */
  channels?: string[];
  /** WebSocket server URL override */
  url?: string;
  /** Enable automatic reconnection (default: true) */
  reconnect?: boolean;
  /** Auto-connect on mount (default: true) */
  autoConnect?: boolean;
}

export interface UseRealtimeReturn {
  status: WebSocketStatus;
  subscribe: (channel: string) => void;
  unsubscribe: (channel: string) => void;
  on: <K extends keyof WebSocketEventMap>(event: K, handler: (data: WebSocketEventMap[K]) => void) => void;
  off: <K extends keyof WebSocketEventMap>(event: K, handler: (data: WebSocketEventMap[K]) => void) => void;
  send: (message: WebSocketMessage) => void;
  connect: () => Promise<void>;
  disconnect: () => void;
}

export function useRealtime(options: UseRealtimeOptions = {}): UseRealtimeReturn {
  const { channels = [], url, reconnect = true, autoConnect = true } = options;
  const { client } = useJanua();
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const wsRef = useRef<JanuaWebSocket | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const baseURL = (client as any).config?.baseURL || '';
    const wsUrl = url || baseURL.replace(/^http/, 'ws') + '/ws';

    const ws = new JanuaWebSocket({
      url: wsUrl,
      getAuthToken: () => client.getAccessToken(),
      reconnect,
    });

    wsRef.current = ws;

    ws.on('connected', () => setStatus('connected'));
    ws.on('disconnected', () => setStatus('disconnected'));
    ws.on('reconnecting', () => setStatus('reconnecting'));
    ws.on('error', () => setStatus('error'));

    if (autoConnect) {
      ws.connect().then(() => {
        for (const channel of channels) {
          ws.subscribe(channel);
        }
      }).catch(() => {});
    }

    return () => {
      ws.disconnect();
      wsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, url, reconnect]);

  const subscribe = useCallback((channel: string) => { wsRef.current?.subscribe(channel); }, []);
  const unsubscribe = useCallback((channel: string) => { wsRef.current?.unsubscribe(channel); }, []);
  const on = useCallback(<K extends keyof WebSocketEventMap>(event: K, handler: (data: WebSocketEventMap[K]) => void) => { wsRef.current?.on(event, handler); }, []);
  const off = useCallback(<K extends keyof WebSocketEventMap>(event: K, handler: (data: WebSocketEventMap[K]) => void) => { wsRef.current?.off(event, handler); }, []);
  const send = useCallback((message: WebSocketMessage) => { wsRef.current?.send(message); }, []);
  const connect = useCallback(async () => { await wsRef.current?.connect(); }, []);
  const disconnect = useCallback(() => { wsRef.current?.disconnect(); }, []);

  return { status, subscribe, unsubscribe, on, off, send, connect, disconnect };
}
