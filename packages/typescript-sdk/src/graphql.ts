/**
 * GraphQL client module for Plinto SDK
 * Provides type-safe GraphQL query, mutation, and subscription support
 */

import {
  ApolloClient,
  InMemoryCache,
  HttpLink,
  ApolloLink,
  from,
  type NormalizedCacheObject,
  type ApolloClientOptions,
  type DocumentNode,
  type OperationVariables,
  type ApolloQueryResult,
  type FetchResult,
  type Observable,
} from '@apollo/client/core'
import { GraphQLWsLink } from '@apollo/client/link/subscriptions'
import { createClient, type Client as WsClient } from 'graphql-ws'
import { logger } from './utils/logger'

export interface GraphQLConfig {
  httpUrl: string
  wsUrl?: string
  getAuthToken?: () => Promise<string | null> | string | null
  debug?: boolean
  cache?: InMemoryCache
}

export interface GraphQLQueryOptions<TVariables = OperationVariables> {
  variables?: TVariables
  fetchPolicy?: 'cache-first' | 'network-only' | 'cache-only' | 'no-cache' | 'standby'
  context?: Record<string, any>
}

export interface GraphQLMutationOptions<TVariables = OperationVariables> {
  variables?: TVariables
  context?: Record<string, any>
  optimisticResponse?: any
  update?: any
  refetchQueries?: any
}

export interface GraphQLSubscriptionOptions<TVariables = OperationVariables> {
  variables?: TVariables
  fetchPolicy?: 'cache-first' | 'network-only' | 'no-cache'
}

/**
 * GraphQL client for Plinto SDK
 */
export class GraphQL {
  private client: ApolloClient<NormalizedCacheObject>
  private wsClient?: WsClient
  private config: GraphQLConfig

  constructor(config: GraphQLConfig) {
    this.config = config

    // Create HTTP link
    const httpLink = new HttpLink({
      uri: config.httpUrl,
      fetch: fetch,
    })

    // Create auth middleware
    const authMiddleware = new ApolloLink((operation, forward) => {
      const token = config.getAuthToken ? config.getAuthToken() : null
      
      if (token instanceof Promise) {
        return token.then(t => {
          if (t) {
            operation.setContext(({ headers = {} }: any) => ({
              headers: {
                ...headers,
                authorization: `Bearer ${t}`,
              },
            }))
          }
          return forward(operation)
        })
      }
      
      if (token) {
        operation.setContext(({ headers = {} }: any) => ({
          headers: {
            ...headers,
            authorization: `Bearer ${token}`,
          },
        }))
      }
      
      return forward(operation)
    })

    // Create WebSocket link if URL provided
    let wsLink: GraphQLWsLink | undefined
    if (config.wsUrl) {
      this.wsClient = createClient({
        url: config.wsUrl,
        connectionParams: async () => {
          const token = config.getAuthToken ? await config.getAuthToken() : null
          return token ? { authorization: `Bearer ${token}` } : {}
        },
        on: {
          connected: () => {
            if (config.debug) {
              logger.info('GraphQL WebSocket connected')
            }
          },
          closed: () => {
            if (config.debug) {
              logger.info('GraphQL WebSocket closed')
            }
          },
          error: (error) => {
            logger.error('GraphQL WebSocket error:', error)
          },
        },
      })

      wsLink = new GraphQLWsLink(this.wsClient)
    }

    // Create Apollo Client with optional subscription support
    const link = wsLink
      ? from([authMiddleware, httpLink])
      : from([authMiddleware, httpLink])

    const clientOptions: ApolloClientOptions<NormalizedCacheObject> = {
      link,
      cache: config.cache || new InMemoryCache(),
      defaultOptions: {
        watchQuery: {
          fetchPolicy: 'cache-and-network',
        },
        query: {
          fetchPolicy: 'network-only',
        },
        mutate: {
          fetchPolicy: 'no-cache',
        },
      },
    }

    this.client = new ApolloClient(clientOptions)
  }

  /**
   * Execute a GraphQL query
   */
  async query<TData = any, TVariables extends OperationVariables = OperationVariables>(
    query: DocumentNode,
    options?: GraphQLQueryOptions<TVariables>
  ): Promise<ApolloQueryResult<TData>> {
    try {
      return await this.client.query<TData, TVariables>({
        query,
        variables: options?.variables,
        fetchPolicy: options?.fetchPolicy,
        context: options?.context,
      })
    } catch (error) {
      logger.error('GraphQL query error:', error)
      throw error
    }
  }

  /**
   * Execute a GraphQL mutation
   */
  async mutate<TData = any, TVariables extends OperationVariables = OperationVariables>(
    mutation: DocumentNode,
    options?: GraphQLMutationOptions<TVariables>
  ): Promise<FetchResult<TData>> {
    try {
      return await this.client.mutate<TData, TVariables>({
        mutation,
        variables: options?.variables,
        context: options?.context,
        optimisticResponse: options?.optimisticResponse,
        update: options?.update,
        refetchQueries: options?.refetchQueries,
      })
    } catch (error) {
      logger.error('GraphQL mutation error:', error)
      throw error
    }
  }

  /**
   * Subscribe to a GraphQL subscription
   */
  subscribe<TData = any, TVariables extends OperationVariables = OperationVariables>(
    subscription: DocumentNode,
    options?: GraphQLSubscriptionOptions<TVariables>
  ): Observable<FetchResult<TData>> {
    if (!this.wsClient) {
      throw new Error('WebSocket URL not configured for subscriptions')
    }

    return this.client.subscribe<TData, TVariables>({
      query: subscription,
      variables: options?.variables,
      fetchPolicy: options?.fetchPolicy,
    })
  }

  /**
   * Clear the Apollo Client cache
   */
  async clearCache(): Promise<void> {
    await this.client.clearStore()
  }

  /**
   * Reset the Apollo Client store
   */
  async resetStore(): Promise<void> {
    await this.client.resetStore()
  }

  /**
   * Get the underlying Apollo Client instance
   */
  getClient(): ApolloClient<NormalizedCacheObject> {
    return this.client
  }

  /**
   * Close WebSocket connection
   */
  async disconnect(): Promise<void> {
    if (this.wsClient) {
      await this.wsClient.dispose()
      if (this.config.debug) {
        logger.info('GraphQL WebSocket disconnected')
      }
    }
  }

  /**
   * Check if subscriptions are available
   */
  hasSubscriptionSupport(): boolean {
    return !!this.wsClient
  }
}

/**
 * Create a GraphQL client instance
 */
export function createGraphQLClient(config: GraphQLConfig): GraphQL {
  return new GraphQL(config)
}
