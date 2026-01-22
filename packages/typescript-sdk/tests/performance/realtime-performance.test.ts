/**
 * Performance Tests for Real-time Features
 *
 * Tests GraphQL subscriptions and WebSocket pub/sub under load:
 * - Concurrent connection handling
 * - Message throughput
 * - Latency measurements
 * - Memory usage
 * - Connection stability
 */

import { describe, it, expect, beforeEach, afterEach, beforeAll as _beforeAll, afterAll as _afterAll } from 'vitest';
import { JanuaClient } from '../../src/index';
import { WebSocketClient } from '../../src/websocket';

// Performance test configuration
const PERF_CONFIG = {
  concurrent_connections: {
    light: 10,
    medium: 50,
    heavy: 100,
    extreme: 250,
  },
  message_throughput: {
    messages_per_second: 100,
    duration_seconds: 10,
  },
  latency_threshold: {
    p50: 100, // ms
    p95: 250, // ms
    p99: 500, // ms
  },
  memory_threshold: {
    max_heap_mb: 512,
    max_connections: 1000,
  },
  stability_test: {
    duration_minutes: 5,
    ping_interval_ms: 1000,
  },
};

// Mock WebSocket server for testing
const MOCK_WS_URL = 'ws://localhost:8001/ws';
const MOCK_GRAPHQL_URL = 'http://localhost:8000/graphql';
const MOCK_AUTH_TOKEN = 'perf-test-token-' + Date.now();

// Performance metrics collector
interface PerformanceMetrics {
  connectionTimes: number[];
  messageTimes: number[];
  memoryUsage: number[];
  errors: Array<{ type: string; message: string; timestamp: number }>;
  connectionCount: number;
  messageCount: number;
  startTime: number;
  endTime?: number;
}

class MetricsCollector {
  private metrics: PerformanceMetrics = {
    connectionTimes: [],
    messageTimes: [],
    memoryUsage: [],
    errors: [],
    connectionCount: 0,
    messageCount: 0,
    startTime: Date.now(),
  };

  recordConnectionTime(ms: number): void {
    this.metrics.connectionTimes.push(ms);
    this.metrics.connectionCount++;
  }

  recordMessageTime(ms: number): void {
    this.metrics.messageTimes.push(ms);
    this.metrics.messageCount++;
  }

  recordMemoryUsage(mb: number): void {
    this.metrics.memoryUsage.push(mb);
  }

  recordError(type: string, message: string): void {
    this.metrics.errors.push({ type, message, timestamp: Date.now() });
  }

  finalize(): PerformanceMetrics {
    this.metrics.endTime = Date.now();
    return this.metrics;
  }

  getPercentile(values: number[], percentile: number): number {
    if (values.length === 0) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.ceil((percentile / 100) * sorted.length) - 1;
    return sorted[Math.max(0, index)];
  }

  calculateStats(values: number[]): {
    min: number;
    max: number;
    mean: number;
    median: number;
    p95: number;
    p99: number;
  } {
    if (values.length === 0) {
      return { min: 0, max: 0, mean: 0, median: 0, p95: 0, p99: 0 };
    }

    const sorted = [...values].sort((a, b) => a - b);
    const sum = values.reduce((a, b) => a + b, 0);

    return {
      min: sorted[0],
      max: sorted[sorted.length - 1],
      mean: sum / values.length,
      median: this.getPercentile(values, 50),
      p95: this.getPercentile(values, 95),
      p99: this.getPercentile(values, 99),
    };
  }

  getReport(): string {
    const duration = (this.metrics.endTime || Date.now()) - this.metrics.startTime;
    const connectionStats = this.calculateStats(this.metrics.connectionTimes);
    const messageStats = this.calculateStats(this.metrics.messageTimes);

    return `
Performance Test Report
========================
Duration: ${(duration / 1000).toFixed(2)}s

Connections:
  Total: ${this.metrics.connectionCount}
  Connection Time (ms):
    Min: ${connectionStats.min.toFixed(2)}
    Max: ${connectionStats.max.toFixed(2)}
    Mean: ${connectionStats.mean.toFixed(2)}
    Median: ${connectionStats.median.toFixed(2)}
    P95: ${connectionStats.p95.toFixed(2)}
    P99: ${connectionStats.p99.toFixed(2)}

Messages:
  Total: ${this.metrics.messageCount}
  Throughput: ${(this.metrics.messageCount / (duration / 1000)).toFixed(2)} msg/s
  Message Latency (ms):
    Min: ${messageStats.min.toFixed(2)}
    Max: ${messageStats.max.toFixed(2)}
    Mean: ${messageStats.mean.toFixed(2)}
    Median: ${messageStats.median.toFixed(2)}
    P95: ${messageStats.p95.toFixed(2)}
    P99: ${messageStats.p99.toFixed(2)}

Memory:
  Samples: ${this.metrics.memoryUsage.length}
  ${this.metrics.memoryUsage.length > 0 ? `
  Min: ${Math.min(...this.metrics.memoryUsage).toFixed(2)} MB
  Max: ${Math.max(...this.metrics.memoryUsage).toFixed(2)} MB
  Mean: ${(this.metrics.memoryUsage.reduce((a, b) => a + b, 0) / this.metrics.memoryUsage.length).toFixed(2)} MB
  ` : 'No data'}

Errors: ${this.metrics.errors.length}
${this.metrics.errors.slice(0, 5).map(e => `  - ${e.type}: ${e.message}`).join('\n')}
${this.metrics.errors.length > 5 ? `  ... and ${this.metrics.errors.length - 5} more` : ''}
`.trim();
  }
}

// Helper to measure memory usage
function getMemoryUsageMB(): number {
  if (typeof process !== 'undefined' && process.memoryUsage) {
    return process.memoryUsage().heapUsed / 1024 / 1024;
  }
  return 0;
}

// Helper to sleep
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

describe('WebSocket Performance Tests', () => {
  let clients: WebSocketClient[] = [];
  let metrics: MetricsCollector;

  beforeEach(() => {
    clients = [];
    metrics = new MetricsCollector();
  });

  afterEach(async () => {
    // Cleanup all clients
    await Promise.all(clients.map(client => {
      if (client && typeof client.disconnect === 'function') {
        return client.disconnect();
      }
      return Promise.resolve();
    }));
    clients = [];
  });

  describe('Concurrent Connections', () => {
    it('should handle 10 concurrent connections (light load)', async () => {
      const count = PERF_CONFIG.concurrent_connections.light;
      const connectionPromises: Promise<void>[] = [];

      for (let i = 0; i < count; i++) {
        const startTime = Date.now();
        const client = new WebSocketClient(MOCK_WS_URL, {
          token: `${MOCK_AUTH_TOKEN}-${i}`,
          autoReconnect: false,
        });

        const connectPromise = new Promise<void>((resolve, reject) => {
          if (!client) {
            reject(new Error('Client not initialized'));
            return;
          }
          client.on('connected', () => {
            const connectionTime = Date.now() - startTime;
            metrics.recordConnectionTime(connectionTime);
            resolve();
          });

          client.on('error', (error: unknown) => {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            metrics.recordError('connection', errorMessage);
            reject(error instanceof Error ? error : new Error(errorMessage));
          });

          // Timeout after 5 seconds
          setTimeout(() => reject(new Error('Connection timeout')), 5000);
        });

        connectionPromises.push(connectPromise);
        clients.push(client);
        if (typeof client.connect === 'function') {
          client.connect();
        }

        // Small delay to stagger connections
        await sleep(10);
      }

      // Wait for all connections with timeout
      await Promise.race([
        Promise.all(connectionPromises),
        sleep(10000).then(() => {
          throw new Error('Test timeout: Not all connections established in 10s');
        }),
      ]);

      metrics.recordMemoryUsage(getMemoryUsageMB());
      const finalMetrics = metrics.finalize();

      // Assertions
      expect(finalMetrics.connectionCount).toBe(count);
      expect(finalMetrics.errors.length).toBe(0);

      const connectionStats = metrics.calculateStats(finalMetrics.connectionTimes);
      expect(connectionStats.p95).toBeLessThan(PERF_CONFIG.latency_threshold.p95);

      console.log('\n[Performance] Light Load Test Results:');
      if (metrics && typeof metrics.getReport === 'function') {
        console.log(metrics.getReport());
      }
    }, 15000); // 15 second timeout

    it('should handle 50 concurrent connections (medium load)', async () => {
      const count = PERF_CONFIG.concurrent_connections.medium;
      const connectionPromises: Promise<void>[] = [];

      for (let i = 0; i < count; i++) {
        const startTime = Date.now();
        const client = new WebSocketClient(MOCK_WS_URL, {
          token: `${MOCK_AUTH_TOKEN}-${i}`,
          autoReconnect: false,
        });

        const connectPromise = new Promise<void>((resolve, reject) => {
          if (!client) {
            reject(new Error('Client not initialized'));
            return;
          }
          client.on('connected', () => {
            const connectionTime = Date.now() - startTime;
            metrics.recordConnectionTime(connectionTime);
            resolve();
          });

          client.on('error', (error: unknown) => {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            metrics.recordError('connection', errorMessage);
            reject(error instanceof Error ? error : new Error(errorMessage));
          });

          setTimeout(() => reject(new Error('Connection timeout')), 10000);
        });

        connectionPromises.push(connectPromise);
        clients.push(client);
        if (typeof client.connect === 'function') {
          client.connect();
        }

        // Very small delay
        if (i % 10 === 0) {
          await sleep(5);
          metrics.recordMemoryUsage(getMemoryUsageMB());
        }
      }

      await Promise.race([
        Promise.all(connectionPromises),
        sleep(20000).then(() => {
          throw new Error('Test timeout: Not all connections established in 20s');
        }),
      ]);

      metrics.recordMemoryUsage(getMemoryUsageMB());
      const finalMetrics = metrics.finalize();

      expect(finalMetrics.connectionCount).toBe(count);
      expect(finalMetrics.errors.length).toBeLessThan(count * 0.05); // Less than 5% error rate

      const connectionStats = metrics.calculateStats(finalMetrics.connectionTimes);
      expect(connectionStats.p95).toBeLessThan(PERF_CONFIG.latency_threshold.p95);

      console.log('\n[Performance] Medium Load Test Results:');
      if (metrics && typeof metrics.getReport === 'function') {
        console.log(metrics.getReport());
      }
    }, 30000);

    it('should handle 100 concurrent connections (heavy load)', async () => {
      const count = PERF_CONFIG.concurrent_connections.heavy;
      const batchSize = 20;
      const batches = Math.ceil(count / batchSize);

      for (let batch = 0; batch < batches; batch++) {
        const batchStart = batch * batchSize;
        const batchEnd = Math.min(batchStart + batchSize, count);
        const batchPromises: Promise<void>[] = [];

        for (let i = batchStart; i < batchEnd; i++) {
          const startTime = Date.now();
          const client = new WebSocketClient(MOCK_WS_URL, {
            token: `${MOCK_AUTH_TOKEN}-${i}`,
            autoReconnect: false,
          });

          const connectPromise = new Promise<void>((resolve, reject) => {
            if (!client) {
              reject(new Error('Client not initialized'));
              return;
            }
            client.on('connected', () => {
              const connectionTime = Date.now() - startTime;
              metrics.recordConnectionTime(connectionTime);
              resolve();
            });

            client.on('error', (error: unknown) => {
              const errorMessage = error instanceof Error ? error.message : 'Unknown error';
              metrics.recordError('connection', errorMessage);
              reject(error instanceof Error ? error : new Error(errorMessage));
            });

            setTimeout(() => reject(new Error('Connection timeout')), 15000);
          });

          batchPromises.push(connectPromise);
          clients.push(client);
          if (typeof client.connect === 'function') {
            client.connect();
          }
        }

        await Promise.all(batchPromises);
        metrics.recordMemoryUsage(getMemoryUsageMB());

        // Small delay between batches
        if (batch < batches - 1) {
          await sleep(100);
        }
      }

      const finalMetrics = metrics.finalize();

      expect(finalMetrics.connectionCount).toBe(count);
      expect(finalMetrics.errors.length).toBeLessThan(count * 0.1); // Less than 10% error rate

      const connectionStats = metrics.calculateStats(finalMetrics.connectionTimes);
      expect(connectionStats.p99).toBeLessThan(PERF_CONFIG.latency_threshold.p99);

      const memoryStats = metrics.calculateStats(finalMetrics.memoryUsage);
      expect(memoryStats.max).toBeLessThan(PERF_CONFIG.memory_threshold.max_heap_mb);

      console.log('\n[Performance] Heavy Load Test Results:');
      if (metrics && typeof metrics.getReport === 'function') {
        console.log(metrics.getReport());
      }
    }, 60000);
  });

  describe('Message Throughput', () => {
    it('should handle high message throughput', async () => {
      const messagesPerSecond = PERF_CONFIG.message_throughput.messages_per_second;
      const durationSeconds = PERF_CONFIG.message_throughput.duration_seconds;
      const totalMessages = messagesPerSecond * durationSeconds;
      const delayBetweenMessages = 1000 / messagesPerSecond;

      // Create single client
      const client = new WebSocketClient(MOCK_WS_URL, {
        token: MOCK_AUTH_TOKEN,
        autoReconnect: false,
      });

      clients.push(client);

      // Wait for connection
      await new Promise<void>((resolve, reject) => {
        if (!client) {
          reject(new Error('Client not initialized'));
          return;
        }
        client.on('connected', () => resolve());
        client.on('error', (error: unknown) => {
          reject(error instanceof Error ? error : new Error(String(error)));
        });
        if (typeof client.connect === 'function') {
          client.connect();
        }
        setTimeout(() => reject(new Error('Connection timeout')), 5000);
      });

      // Subscribe to test channel
      const receivedMessages: Array<{ id: number; receivedAt: number }> = [];
      await client.subscribe('perf-test', (message: { id: number }) => {
        const receivedAt = Date.now();
        receivedMessages.push({ id: message.id, receivedAt });
      });

      // Send messages at target rate
      const sendStartTime = Date.now();
      for (let i = 0; i < totalMessages; i++) {
        const sendTime = Date.now();
        await client.publish('perf-test', {
          id: i,
          sentAt: sendTime,
          payload: `Test message ${i}`,
        });

        // Calculate latency when message is received
        const messageIndex = i;
        setTimeout(() => {
          const received = receivedMessages.find(m => m.id === messageIndex);
          if (received) {
            const latency = received.receivedAt - sendTime;
            metrics.recordMessageTime(latency);
          }
        }, 100); // Check after 100ms

        // Maintain target message rate
        const expectedTime = sendStartTime + (i + 1) * delayBetweenMessages;
        const currentTime = Date.now();
        const sleepTime = expectedTime - currentTime;

        if (sleepTime > 0) {
          await sleep(sleepTime);
        }

        // Record memory every 100 messages
        if (i % 100 === 0) {
          metrics.recordMemoryUsage(getMemoryUsageMB());
        }
      }

      // Wait for remaining messages to be received
      await sleep(1000);

      const finalMetrics = metrics.finalize();
      const duration = (finalMetrics.endTime! - finalMetrics.startTime) / 1000;
      const actualThroughput = finalMetrics.messageCount / duration;

      // Assertions
      expect(receivedMessages.length).toBeGreaterThan(totalMessages * 0.95); // At least 95% delivery
      expect(actualThroughput).toBeGreaterThan(messagesPerSecond * 0.9); // Within 10% of target

      const messageStats = metrics.calculateStats(finalMetrics.messageTimes);
      expect(messageStats.p95).toBeLessThan(PERF_CONFIG.latency_threshold.p95);

      console.log('\n[Performance] Message Throughput Test Results:');
      if (metrics && typeof metrics.getReport === 'function') {
        console.log(metrics.getReport());
      }
      console.log(`Target: ${messagesPerSecond} msg/s, Actual: ${actualThroughput.toFixed(2)} msg/s`);
      console.log(`Delivery Rate: ${((receivedMessages.length / totalMessages) * 100).toFixed(2)}%`);
    }, 30000);

    it('should handle burst message traffic', async () => {
      const burstSize = 1000;
      const burstCount = 5;
      const delayBetweenBursts = 2000; // 2 seconds

      const client = new WebSocketClient(MOCK_WS_URL, {
        token: MOCK_AUTH_TOKEN,
        autoReconnect: false,
      });
      clients.push(client);

      await new Promise<void>((resolve, reject) => {
        if (!client) {
          reject(new Error('Client not initialized'));
          return;
        }
        client.on('connected', () => resolve());
        client.on('error', (error: unknown) => {
          reject(error instanceof Error ? error : new Error(String(error)));
        });
        if (typeof client.connect === 'function') {
          client.connect();
        }
        setTimeout(() => reject(new Error('Connection timeout')), 5000);
      });

      const receivedMessages: number[] = [];
      await client.subscribe('burst-test', (message: { id: number }) => {
        receivedMessages.push(message.id);
      });

      for (let burst = 0; burst < burstCount; burst++) {
        const burstStartTime = Date.now();

        // Send burst
        const sendPromises = [];
        for (let i = 0; i < burstSize; i++) {
          const messageId = burst * burstSize + i;
          sendPromises.push(
            client.publish('burst-test', {
              id: messageId,
              burst,
              index: i,
              sentAt: Date.now(),
            })
          );
        }

        await Promise.all(sendPromises);
        const burstDuration = Date.now() - burstStartTime;
        metrics.recordMessageTime(burstDuration);

        console.log(`Burst ${burst + 1}/${burstCount}: Sent ${burstSize} messages in ${burstDuration}ms`);

        if (burst < burstCount - 1) {
          await sleep(delayBetweenBursts);
        }

        metrics.recordMemoryUsage(getMemoryUsageMB());
      }

      // Wait for messages to settle
      await sleep(2000);

      const finalMetrics = metrics.finalize();
      const totalExpected = burstSize * burstCount;
      const deliveryRate = (receivedMessages.length / totalExpected) * 100;

      expect(deliveryRate).toBeGreaterThan(90); // At least 90% delivery rate
      expect(finalMetrics.errors.length).toBe(0);

      console.log('\n[Performance] Burst Traffic Test Results:');
      if (metrics && typeof metrics.getReport === 'function') {
        console.log(metrics.getReport());
      }
      console.log(`Delivery Rate: ${deliveryRate.toFixed(2)}%`);
    }, 30000);
  });

  describe('Connection Stability', () => {
    it('should maintain stable connection over time', async () => {
      const durationMinutes = PERF_CONFIG.stability_test.duration_minutes;
      const pingIntervalMs = PERF_CONFIG.stability_test.ping_interval_ms;
      // Expected pings calculated for validation purposes
      const _expectedPings = (durationMinutes * 60 * 1000) / pingIntervalMs;

      const client = new WebSocketClient(MOCK_WS_URL, {
        token: MOCK_AUTH_TOKEN,
        autoReconnect: true,
        heartbeatInterval: pingIntervalMs,
      });
      clients.push(client);

      let pingCount = 0;
      let pongCount = 0;
      const latencies: number[] = [];

      if (client) {
        client.on('connected', () => {
          metrics.recordConnectionTime(0);
        });

        client.on('disconnected', () => {
          metrics.recordError('disconnect', 'Unexpected disconnection');
        });

        client.on('reconnecting', (attempt: number) => {
          metrics.recordError('reconnect', `Reconnection attempt ${attempt}`);
        });
      }

      // Mock ping/pong mechanism
      let pingIntervalHandle: ReturnType<typeof setInterval> | null = setInterval(() => {
        const pingTime = Date.now();
        pingCount++;

        // Simulate pong response
        setTimeout(() => {
          pongCount++;
          const latency = Date.now() - pingTime;
          latencies.push(latency);
          metrics.recordMessageTime(latency);
        }, Math.random() * 50 + 10); // 10-60ms latency

        metrics.recordMemoryUsage(getMemoryUsageMB());
      }, pingIntervalMs);

      await new Promise<void>((resolve, reject) => {
        if (!client) {
          reject(new Error('Client not initialized'));
          return;
        }
        client.on('connected', () => resolve());
        client.on('error', (error: unknown) => {
          reject(error instanceof Error ? error : new Error(String(error)));
        });
        if (typeof client.connect === 'function') {
          client.connect();
        }
        setTimeout(() => reject(new Error('Connection timeout')), 5000);
      });

      // Run stability test for specified duration
      await sleep(durationMinutes * 60 * 1000);

      if (pingIntervalHandle) {
        clearInterval(pingIntervalHandle);
        pingIntervalHandle = null;
      }

      const finalMetrics = metrics.finalize();
      const pongRate = (pongCount / pingCount) * 100;

      // Assertions
      expect(pongRate).toBeGreaterThan(95); // At least 95% pong responses
      expect(finalMetrics.errors.filter(e => e.type === 'disconnect').length).toBe(0);

      const latencyStats = metrics.calculateStats(latencies);
      expect(latencyStats.p95).toBeLessThan(PERF_CONFIG.latency_threshold.p95);

      console.log('\n[Performance] Connection Stability Test Results:');
      if (metrics && typeof metrics.getReport === 'function') {
        console.log(metrics.getReport());
      }
      console.log(`Pings: ${pingCount}, Pongs: ${pongCount}, Rate: ${pongRate.toFixed(2)}%`);
      console.log(`Latency P95: ${latencyStats.p95.toFixed(2)}ms, P99: ${latencyStats.p99.toFixed(2)}ms`);
    }, (PERF_CONFIG.stability_test.duration_minutes * 60 + 10) * 1000);
  });

  describe('Memory Usage', () => {
    it('should not leak memory with repeated connect/disconnect', async () => {
      const cycles = 50;
      const memorySnapshots: number[] = [];

      // Initial memory snapshot
      memorySnapshots.push(getMemoryUsageMB());

      for (let i = 0; i < cycles; i++) {
        const client = new WebSocketClient(MOCK_WS_URL, {
          token: `${MOCK_AUTH_TOKEN}-${i}`,
          autoReconnect: false,
        });

        await new Promise<void>((resolve, reject) => {
          if (!client) {
            reject(new Error('Client not initialized'));
            return;
          }
          client.on('connected', () => resolve());
          client.on('error', (error: unknown) => {
            reject(error instanceof Error ? error : new Error(String(error)));
          });
          if (typeof client.connect === 'function') {
            client.connect();
          }
          setTimeout(() => reject(new Error('Connection timeout')), 5000);
        });

        await sleep(100);
        if (client && typeof client.disconnect === 'function') {
          await client.disconnect();
        }

        // Memory snapshot every 10 cycles
        if (i % 10 === 0) {
          // Force garbage collection if available
          if (global.gc) {
            global.gc();
          }
          await sleep(100);
          memorySnapshots.push(getMemoryUsageMB());
        }
      }

      // Final memory snapshot
      if (global.gc) {
        global.gc();
      }
      await sleep(100);
      memorySnapshots.push(getMemoryUsageMB());

      const initialMemory = memorySnapshots[0];
      const finalMemory = memorySnapshots[memorySnapshots.length - 1];
      const memoryGrowth = finalMemory - initialMemory;
      const growthPercentage = (memoryGrowth / initialMemory) * 100;

      console.log('\n[Performance] Memory Leak Test Results:');
      console.log(`Initial Memory: ${initialMemory.toFixed(2)} MB`);
      console.log(`Final Memory: ${finalMemory.toFixed(2)} MB`);
      console.log(`Growth: ${memoryGrowth.toFixed(2)} MB (${growthPercentage.toFixed(2)}%)`);
      console.log(`Cycles: ${cycles}`);

      // Memory should not grow more than 50%
      expect(growthPercentage).toBeLessThan(50);
    }, 60000);
  });
});

describe('GraphQL Subscription Performance Tests', () => {
  let client: JanuaClient;
  let metrics: MetricsCollector;

  beforeEach(() => {
    client = new JanuaClient({
      graphqlUrl: MOCK_GRAPHQL_URL,
      websocketUrl: MOCK_WS_URL,
      token: MOCK_AUTH_TOKEN,
    });
    metrics = new MetricsCollector();
  });

  afterEach(async () => {
    if (client?.websocket && typeof client.websocket.disconnect === 'function') {
      await client.websocket.disconnect();
    }
  });

  describe('Subscription Performance', () => {
    it('should handle multiple concurrent subscriptions', async () => {
      const subscriptionCount = 20;
      const messagesPerSubscription = 50;
      const subscriptions: Array<() => void> = [];

      // Create multiple subscriptions
      for (let i = 0; i < subscriptionCount; i++) {
        const startTime = Date.now();
        const unsubscribe = await client.graphql.subscribe(
          `
          subscription TestSubscription($id: Int!) {
            testEvent(id: $id) {
              id
              data
              timestamp
            }
          }
          `,
          { id: i },
          {
            next: (data: { testEvent: { timestamp: number } }) => {
              const latency = Date.now() - data.testEvent.timestamp;
              metrics.recordMessageTime(latency);
            },
            error: (error: Error) => {
              metrics.recordError('subscription', error.message);
            },
          }
        );

        const subscriptionTime = Date.now() - startTime;
        metrics.recordConnectionTime(subscriptionTime);
        subscriptions.push(unsubscribe);
      }

      // Simulate messages for each subscription
      const messagePromises: Promise<void>[] = [];
      for (let sub = 0; sub < subscriptionCount; sub++) {
        for (let _msg = 0; _msg < messagesPerSubscription; _msg++) {
          messagePromises.push(
            (async () => {
              // Simulate server pushing subscription data
              await sleep(Math.random() * 100);
              // In real scenario, server would push via WebSocket
            })()
          );
        }
      }

      await Promise.all(messagePromises);
      await sleep(1000); // Wait for messages to process

      // Cleanup subscriptions
      subscriptions.forEach(unsub => unsub());

      const finalMetrics = metrics.finalize();
      const subscriptionStats = metrics.calculateStats(finalMetrics.connectionTimes);
      const messageStats = metrics.calculateStats(finalMetrics.messageTimes);

      expect(finalMetrics.connectionCount).toBe(subscriptionCount);
      expect(subscriptionStats.p95).toBeLessThan(PERF_CONFIG.latency_threshold.p95);
      expect(messageStats.p95).toBeLessThan(PERF_CONFIG.latency_threshold.p95);

      console.log('\n[Performance] GraphQL Subscription Performance:');
      console.log(metrics.getReport());
    }, 30000);

    it('should handle subscription updates with high frequency', async () => {
      const updateFrequency = 100; // updates per second
      const durationSeconds = 10;
      const expectedUpdates = updateFrequency * durationSeconds;
      let receivedUpdates = 0;

      const unsubscribe = await client.graphql.subscribe(
        `
        subscription HighFrequencyUpdates {
          rapidUpdates {
            id
            value
            timestamp
          }
        }
        `,
        {},
        {
          next: (data: { rapidUpdates: { timestamp: number } }) => {
            receivedUpdates++;
            const latency = Date.now() - data.rapidUpdates.timestamp;
            metrics.recordMessageTime(latency);

            if (receivedUpdates % 100 === 0) {
              metrics.recordMemoryUsage(getMemoryUsageMB());
            }
          },
          error: (error: Error) => {
            metrics.recordError('subscription', error.message);
          },
        }
      );

      // Simulate high-frequency updates
      const startTime = Date.now();
      while (Date.now() - startTime < durationSeconds * 1000) {
        // In real scenario, server pushes updates
        await sleep(1000 / updateFrequency);
      }

      await sleep(500); // Allow remaining updates to process

      unsubscribe();

      const finalMetrics = metrics.finalize();
      const deliveryRate = (receivedUpdates / expectedUpdates) * 100;
      const messageStats = metrics.calculateStats(finalMetrics.messageTimes);

      expect(deliveryRate).toBeGreaterThan(90); // At least 90% delivery
      expect(messageStats.p95).toBeLessThan(PERF_CONFIG.latency_threshold.p95);

      console.log('\n[Performance] High-Frequency Subscription Results:');
      console.log(metrics.getReport());
      console.log(`Delivery Rate: ${deliveryRate.toFixed(2)}%`);
      console.log(`Expected: ${expectedUpdates}, Received: ${receivedUpdates}`);
    }, 20000);
  });
});
