/**
 * K6 Load Testing - Authentication Flows
 *
 * Tests authentication performance under load:
 * - User signup flow
 * - User login flow
 * - Token validation
 * - Session management
 *
 * Usage:
 *   k6 run tests/load/auth_flows.js
 *   k6 run --vus 100 --duration 30s tests/load/auth_flows.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const signupLatency = new Trend('signup_latency');
const loginLatency = new Trend('login_latency');
const tokenValidationLatency = new Trend('token_validation_latency');
const errorRate = new Rate('errors');

// Test configuration
export const options = {
  stages: [
    { duration: '30s', target: 50 },   // Ramp up to 50 users
    { duration: '1m', target: 100 },   // Ramp up to 100 users
    { duration: '2m', target: 100 },   // Stay at 100 users
    { duration: '30s', target: 200 },  // Spike to 200 users
    { duration: '1m', target: 200 },   // Stay at 200 users
    { duration: '30s', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    'http_req_duration': ['p(95)<500', 'p(99)<1000'], // 95% < 500ms, 99% < 1000ms
    'signup_latency': ['p(95)<1000'],                 // Signup 95% < 1s
    'login_latency': ['p(95)<500'],                   // Login 95% < 500ms
    'token_validation_latency': ['p(95)<100'],        // Token validation 95% < 100ms
    'errors': ['rate<0.01'],                          // Error rate < 1%
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Generate unique test user
function generateUser() {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(7);
  return {
    email: `test.${timestamp}.${random}@loadtest.com`,
    password: 'LoadTest123!@#Strong',
    name: `Load Test User ${random}`
  };
}

// Test scenario: Complete auth flow
export default function () {
  const user = generateUser();

  // 1. User Signup
  const signupStart = Date.now();
  const signupRes = http.post(
    `${BASE_URL}/api/v1/auth/signup`,
    JSON.stringify({
      email: user.email,
      password: user.password,
      name: user.name
    }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { operation: 'signup' }
    }
  );

  signupLatency.add(Date.now() - signupStart);

  const signupSuccess = check(signupRes, {
    'signup status is 201': (r) => r.status === 201,
    'signup returns access token': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.access_token !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (!signupSuccess) {
    errorRate.add(1);
    console.error(`Signup failed: ${signupRes.status} - ${signupRes.body}`);
    return;
  }

  errorRate.add(0);
  sleep(1); // Brief pause between operations

  // 2. User Login
  const loginStart = Date.now();
  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({
      email: user.email,
      password: user.password
    }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { operation: 'login' }
    }
  );

  loginLatency.add(Date.now() - loginStart);

  const loginSuccess = check(loginRes, {
    'login status is 200': (r) => r.status === 200,
    'login returns access token': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.access_token !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (!loginSuccess) {
    errorRate.add(1);
    console.error(`Login failed: ${loginRes.status} - ${loginRes.body}`);
    return;
  }

  errorRate.add(0);

  // Extract access token
  let accessToken;
  try {
    const loginBody = JSON.parse(loginRes.body);
    accessToken = loginBody.access_token;
  } catch (e) {
    errorRate.add(1);
    console.error('Failed to parse login response');
    return;
  }

  sleep(0.5); // Brief pause

  // 3. Token Validation (Authenticated Request)
  const validationStart = Date.now();
  const validationRes = http.get(
    `${BASE_URL}/api/v1/auth/me`,
    {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
      tags: { operation: 'token_validation' }
    }
  );

  tokenValidationLatency.add(Date.now() - validationStart);

  const validationSuccess = check(validationRes, {
    'token validation status is 200': (r) => r.status === 200,
    'token validation returns user data': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.email === user.email;
      } catch (e) {
        return false;
      }
    },
  });

  if (!validationSuccess) {
    errorRate.add(1);
    console.error(`Token validation failed: ${validationRes.status}`);
  } else {
    errorRate.add(0);
  }

  sleep(1); // Simulate user think time
}

// Teardown: Print summary
export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'load_test_results.json': JSON.stringify(data, null, 2),
  };
}

function textSummary(data, options) {
  const indent = options?.indent || '';
  const _enableColors = options?.enableColors || false;

  let summary = '\n';
  summary += `${indent}=== Load Test Results ===\n\n`;

  // HTTP metrics
  if (data.metrics.http_req_duration) {
    const reqDuration = data.metrics.http_req_duration.values;
    summary += `${indent}HTTP Request Duration:\n`;
    summary += `${indent}  p(50):  ${reqDuration.p50.toFixed(2)}ms\n`;
    summary += `${indent}  p(95):  ${reqDuration.p95.toFixed(2)}ms\n`;
    summary += `${indent}  p(99):  ${reqDuration.p99.toFixed(2)}ms\n`;
    summary += `${indent}  avg:    ${reqDuration.avg.toFixed(2)}ms\n\n`;
  }

  // Signup latency
  if (data.metrics.signup_latency) {
    const signup = data.metrics.signup_latency.values;
    summary += `${indent}Signup Latency:\n`;
    summary += `${indent}  p(95):  ${signup.p95.toFixed(2)}ms\n`;
    summary += `${indent}  avg:    ${signup.avg.toFixed(2)}ms\n\n`;
  }

  // Login latency
  if (data.metrics.login_latency) {
    const login = data.metrics.login_latency.values;
    summary += `${indent}Login Latency:\n`;
    summary += `${indent}  p(95):  ${login.p95.toFixed(2)}ms\n`;
    summary += `${indent}  avg:    ${login.avg.toFixed(2)}ms\n\n`;
  }

  // Token validation latency
  if (data.metrics.token_validation_latency) {
    const validation = data.metrics.token_validation_latency.values;
    summary += `${indent}Token Validation Latency:\n`;
    summary += `${indent}  p(95):  ${validation.p95.toFixed(2)}ms\n`;
    summary += `${indent}  avg:    ${validation.avg.toFixed(2)}ms\n\n`;
  }

  // Error rate
  if (data.metrics.errors) {
    const errors = data.metrics.errors.values;
    summary += `${indent}Error Rate: ${(errors.rate * 100).toFixed(2)}%\n\n`;
  }

  // Total iterations
  if (data.metrics.iterations) {
    summary += `${indent}Total Iterations: ${data.metrics.iterations.values.count}\n`;
  }

  return summary;
}
