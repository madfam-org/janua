import { GET } from './route'
import { NextResponse } from 'next/server'

// Mock Next.js server environment
jest.mock('next/server', () => ({
  NextResponse: {
    json: jest.fn((data, options) => ({
      json: () => Promise.resolve(data),
      status: options?.status || 200,
      data,
      options
    }))
  }
}))

// Type for our mocked response
type MockedResponse = {
  json: () => Promise<unknown>
  status: number
  data: {
    status: string
    timestamp: string
    service: string
    version: string
  }
  options?: unknown
}

describe('Health Route', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('should return health status', async () => {
    const response = await GET() as unknown as MockedResponse

    expect(response).toBeDefined()
    expect(response.data).toMatchObject({
      status: 'healthy',
      service: 'admin',
      version: expect.any(String)
    })
    expect(response.data.timestamp).toBeDefined()
    expect(response.status).toBe(200)
  })

  it('should include timestamp in ISO format', async () => {
    const response = await GET() as unknown as MockedResponse

    const timestamp = response.data.timestamp
    expect(timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
  })
})
