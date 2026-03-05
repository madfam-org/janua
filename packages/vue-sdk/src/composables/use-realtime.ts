/**
 * Vue composable for real-time auth events via WebSocket
 *
 * Wraps the typescript-sdk WebSocket client with Vue reactivity and lifecycle management.
 */
import { ref, onUnmounted, type Ref } from 'vue';
import { WebSocket as JanuaWebSocket } from '@janua/typescript-sdk';
import type { WebSocketStatus, WebSocketMessage, WebSocketEventMap } from '@janua/typescript-sdk';
import { useJanua } from '../composables';

export interface UseRealtimeOptions {
  /** Channels to auto-subscribe on connect */
  channels?: string[];
  /** WebSocket server URL override */
  url?: string;
  /** Enable automatic reconnection (default: true) */
  reconnect?: boolean;
  /** Auto-connect on setup (default: true) */
  autoConnect?: boolean;
}

export interface UseRealtimeReturn {
  status: Ref<WebSocketStatus>;
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
  const status = ref<WebSocketStatus>('disconnected');

  const baseURL = (client as any).config?.baseURL || '';
  const wsUrl = url || baseURL.replace(/^http/, 'ws') + '/ws';

  const ws = new JanuaWebSocket({
    url: wsUrl,
    getAuthToken: () => client.getAccessToken(),
    reconnect,
  });

  ws.on('connected', () => { status.value = 'connected'; });
  ws.on('disconnected', () => { status.value = 'disconnected'; });
  ws.on('reconnecting', () => { status.value = 'reconnecting'; });
  ws.on('error', () => { status.value = 'error'; });

  if (autoConnect) {
    ws.connect().then(() => {
      for (const channel of channels) {
        ws.subscribe(channel);
      }
    }).catch(() => {
      // Connection errors handled via status ref
    });
  }

  onUnmounted(() => {
    ws.disconnect();
  });

  return {
    status,
    subscribe: (channel: string) => ws.subscribe(channel),
    unsubscribe: (channel: string) => ws.unsubscribe(channel),
    on: <K extends keyof WebSocketEventMap>(event: K, handler: (data: WebSocketEventMap[K]) => void) => ws.on(event, handler),
    off: <K extends keyof WebSocketEventMap>(event: K, handler: (data: WebSocketEventMap[K]) => void) => ws.off(event, handler),
    send: (message: WebSocketMessage) => ws.send(message),
    connect: () => ws.connect(),
    disconnect: () => ws.disconnect(),
  };
}
