import { useState, useEffect } from 'react'
import { usePlinto } from '../provider'
import type { Organization } from '@plinto/sdk'

export function useOrganization() {
  const { client, isAuthenticated } = usePlinto()
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) {
      setOrganizations([])
      return
    }

    const fetchOrganizations = async () => {
      setIsLoading(true)
      try {
        const result = await client.organizations.list()
        setOrganizations(result.data)
      } catch (error) {
        console.error('Failed to fetch organizations:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchOrganizations()
  }, [client, isAuthenticated])

  const createOrganization = async (data: {
    name: string
    slug: string
    description?: string
  }) => {
    const organization = await client.organizations.create(data)
    setOrganizations(prev => [...prev, organization])
    return organization
  }

  return {
    organizations,
    isLoading,
    createOrganization,
  }
}