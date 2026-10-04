import React from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { adminAPI, type SystemHealth } from '@/lib/admin-api'
import { InfrastructureSection } from './infrastructure-section'

jest.mock('@/lib/admin-api', () => ({ adminAPI: { getHealth: jest.fn() } }))

const getHealth = jest.mocked(adminAPI.getHealth)
const healthy: SystemHealth = {
  status: 'healthy', database: 'healthy', cache: 'healthy', email: 'healthy',
  storage: 'healthy', uptime: 60, version: 'test', environment: 'test',
}

function metric(label: string) {
  return within(screen.getByText(label).closest('.rounded-lg') as HTMLElement)
}

async function renderHealth(metrics: Record<string, unknown> = {}) {
  getHealth.mockResolvedValue({ ...healthy, ...metrics })
  render(<InfrastructureSection />)
  await screen.findByText('All Systems Operational')
}

describe('InfrastructureSection telemetry truth', () => {
  beforeEach(() => jest.clearAllMocks())

  it('keeps healthy service statuses but marks omitted telemetry unavailable', async () => {
    await renderHealth()

    expect(screen.getAllByText('healthy')).toHaveLength(5)
    for (const label of ['Pool Size', 'In Use', 'Available', 'Hit Rate', 'Connected Clients',
      'Average', 'p95', 'p99', 'Throughput']) {
      expect(metric(label).getByText('Unavailable')).toBeInTheDocument()
    }
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getAllByText(/Utilization unavailable/)).toHaveLength(2)
  })

  it('renders measured values and preserves zero measurements', async () => {
    await renderHealth({
      db_pool_size: 20, db_pool_used: 0, db_pool_available: 20,
      redis_memory_used_mb: 64, redis_memory_max_mb: 256,
      redis_hit_rate: 0, redis_connected_clients: 0,
      api_avg_response_ms: 0, api_p95_response_ms: 12, api_p99_response_ms: 25,
      api_requests_per_minute: 0,
    })

    expect(metric('In Use').getByText('0')).toBeInTheDocument()
    expect(metric('Hit Rate').getByText('0.0')).toBeInTheDocument()
    expect(metric('Connected Clients').getByText('0')).toBeInTheDocument()
    expect(metric('Average').getByText('0')).toBeInTheDocument()
    expect(metric('p95').getByText('12')).toBeInTheDocument()
    expect(metric('p99').getByText('25')).toBeInTheDocument()
    expect(metric('Throughput').getByText('0')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Connection Pool' })).toHaveAttribute('aria-valuenow', '0')
    expect(screen.getByRole('progressbar', { name: 'Memory Usage' })).toHaveAttribute('aria-valuenow', '25')
    expect(screen.queryByText('Unavailable')).not.toBeInTheDocument()
  })

  it.each([undefined, null, -1, NaN, Infinity, '20'])('rejects invalid telemetry (%s)', async (value) => {
    await renderHealth({
      db_pool_size: value, db_pool_used: value, db_pool_available: value,
      redis_memory_used_mb: value, redis_memory_max_mb: value,
      redis_hit_rate: value, redis_connected_clients: value,
      api_avg_response_ms: value, api_p95_response_ms: value, api_p99_response_ms: value,
      api_requests_per_minute: value,
    })

    expect(metric('Average').getByText('Unavailable')).toBeInTheDocument()
    expect(metric('Hit Rate').getByText('Unavailable')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.queryByText(/NaN|Infinity/)).not.toBeInTheDocument()
  })

  it.each([undefined, 0])('shows measured usage without inventing utilization when capacity is %s', async (max) => {
    await renderHealth({ db_pool_used: 3, db_pool_size: max, redis_memory_used_mb: 8, redis_memory_max_mb: max })

    expect(metric('In Use').getByText('3')).toBeInTheDocument()
    expect(screen.getByText('8 MB')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getAllByText(/Utilization unavailable/)).toHaveLength(2)
  })

  it('clears previous telemetry when a later response omits it', async () => {
    await renderHealth({ api_requests_per_minute: 123, db_pool_size: 20, db_pool_used: 4 })
    expect(metric('Throughput').getByText('123')).toBeInTheDocument()

    getHealth.mockResolvedValue(healthy)
    fireEvent.click(screen.getByRole('button', { name: 'Refresh health data' }))

    await waitFor(() => expect(metric('Throughput').getByText('Unavailable')).toBeInTheDocument())
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })
})
