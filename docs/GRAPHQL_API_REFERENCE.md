# GraphQL API Reference

**Endpoint**: `https://api.janua.dev/graphql`  
**WebSocket**: `wss://api.janua.dev/graphql` (for subscriptions)  
**Version**: 1.0.0-beta  
**Last Updated**: November 26, 2026

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Schema Reference](#schema-reference)
4. [Queries](#queries)
5. [Mutations](#mutations)
6. [Subscriptions](#subscriptions)
7. [Types](#types)
8. [Examples](#examples)
9. [Error Handling](#error-handling)
10. [Best Practices](#best-practices)

---

## Overview

The Janua GraphQL API provides a flexible, efficient way to query and mutate data. It supports:

- **Queries**: Read operations with precise field selection
- **Mutations**: Write operations (create, update, delete)
- **Subscriptions**: Real-time updates over WebSocket
- **Batch Operations**: Multiple operations in single request
- **Field-Level Permissions**: Fine-grained access control

### Key Features

✅ **Type-Safe**: Fully typed schema with introspection  
✅ **Real-time**: WebSocket subscriptions for live updates  
✅ **Efficient**: Request only the data you need  
✅ **Batching**: Combine multiple operations  
✅ **Pagination**: Cursor-based pagination for large datasets  

---

## Authentication

### Bearer Token Authentication

Include JWT access token in Authorization header:

```http
POST /graphql
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Example with cURL

```bash
curl -X POST https://api.janua.dev/graphql \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"query": "{ currentUser { id email name } }"}'
```

### WebSocket Authentication

For subscriptions, send authentication in connection params:

```javascript
const wsClient = createClient({
  url: 'wss://api.janua.dev/graphql',
  connectionParams: {
    authorization: `Bearer ${accessToken}`,
  },
});
```

---

## Schema Reference

### Full Schema (SDL)

```graphql
# Scalars
scalar DateTime
scalar JSON
scalar Upload

# Root Types
type Query {
  # User Queries
  currentUser: User!
  user(id: ID!): User
  users(filter: UserFilter, pagination: PaginationInput): UserConnection!
  
  # Organization Queries
  organization(id: ID!): Organization
  organizations(filter: OrgFilter, pagination: PaginationInput): OrganizationConnection!
  
  # Role Queries
  roles: [Role!]!
  role(id: ID!): Role
  permissions: [Permission!]!
  
  # Compliance Queries
  consentPurposes: [ConsentPurpose!]!
  myConsent: [ConsentRecord!]!
  dataSubjectRequests: [DataSubjectRequest!]!
  
  # SSO Queries
  ssoConfigs(organizationId: ID!): [SSOConfig!]!
  ssoConfig(id: ID!): SSOConfig
}

type Mutation {
  # User Mutations
  updateProfile(input: UpdateProfileInput!): User!
  updateEmail(email: String!): User!
  updatePassword(input: UpdatePasswordInput!): Boolean!
  deleteAccount: Boolean!
  
  # MFA Mutations
  setupMFA(method: MFAMethod!): MFASetupResponse!
  verifyMFA(code: String!): MFAVerifyResponse!
  disableMFA(password: String!): Boolean!
  
  # Organization Mutations
  createOrganization(input: CreateOrganizationInput!): Organization!
  updateOrganization(id: ID!, input: UpdateOrganizationInput!): Organization!
  deleteOrganization(id: ID!): Boolean!
  inviteUser(input: InviteUserInput!): Invitation!
  
  # Role Mutations
  createRole(input: CreateRoleInput!): Role!
  updateRole(id: ID!, input: UpdateRoleInput!): Role!
  deleteRole(id: ID!): Boolean!
  assignRole(userId: ID!, roleId: ID!): User!
  
  # Compliance Mutations
  grantConsent(purpose: String!): ConsentRecord!
  withdrawConsent(purpose: String!): Boolean!
  submitDataSubjectRequest(input: DataSubjectRequestInput!): DataSubjectRequest!
  
  # SSO Mutations
  createSSOConfig(input: CreateSSOConfigInput!): SSOConfig!
  updateSSOConfig(id: ID!, input: UpdateSSOConfigInput!): SSOConfig!
  deleteSSOConfig(id: ID!): Boolean!
}

type Subscription {
  # User Subscriptions
  userUpdated(userId: ID!): User!
  
  # Organization Subscriptions
  organizationUpdated(organizationId: ID!): Organization!
  userInvited(organizationId: ID!): Invitation!
  
  # Audit Subscriptions
  auditLogCreated(organizationId: ID!): AuditLog!
  
  # Compliance Subscriptions
  dataSubjectRequestUpdated(requestId: ID!): DataSubjectRequest!
}

# Object Types

type User {
  id: ID!
  email: String!
  name: String!
  phone: String
  emailVerified: Boolean!
  phoneVerified: Boolean!
  mfaEnabled: Boolean!
  passkeyEnabled: Boolean!
  role: Role!
  organization: Organization
  createdAt: DateTime!
  updatedAt: DateTime!
  metadata: JSON
}

type Organization {
  id: ID!
  name: String!
  slug: String!
  plan: OrganizationPlan!
  ssoEnabled: Boolean!
  scimEnabled: Boolean!
  memberCount: Int!
  members(pagination: PaginationInput): UserConnection!
  roles: [Role!]!
  settings: OrganizationSettings!
  createdAt: DateTime!
  updatedAt: DateTime!
}

type Role {
  id: ID!
  name: String!
  description: String
  permissions: [Permission!]!
  isSystem: Boolean!
  createdAt: DateTime!
}

type Permission {
  id: ID!
  name: String!
  description: String!
  category: String!
}

type ConsentPurpose {
  id: ID!
  name: String!
  description: String!
  legalBasis: LegalBasis!
  required: Boolean!
  gdprArticle: String
}

type ConsentRecord {
  id: ID!
  userId: ID!
  purpose: String!
  granted: Boolean!
  grantedAt: DateTime
  withdrawnAt: DateTime
  ipAddress: String
  userAgent: String
}

type DataSubjectRequest {
  id: ID!
  userId: ID!
  requestType: RequestType!
  status: RequestStatus!
  gdprArticle: String!
  description: String
  createdAt: DateTime!
  completedAt: DateTime
  responseDeadline: DateTime!
}

type SSOConfig {
  id: ID!
  provider: SSOProvider!
  organizationId: ID!
  enabled: Boolean!
  metadata: SSOMetadata!
  createdAt: DateTime!
  updatedAt: DateTime!
}

type MFASetupResponse {
  method: MFAMethod!
  secret: String
  qrCode: String
  backupCodes: [String!]!
}

type MFAVerifyResponse {
  success: Boolean!
  accessToken: String
}

type Invitation {
  id: ID!
  email: String!
  organizationId: ID!
  role: Role!
  invitedBy: User!
  expiresAt: DateTime!
  status: InvitationStatus!
  createdAt: DateTime!
}

type AuditLog {
  id: ID!
  userId: ID
  organizationId: ID!
  action: String!
  resource: String!
  resourceId: ID
  metadata: JSON
  ipAddress: String
  userAgent: String
  timestamp: DateTime!
}

# Enums

enum MFAMethod {
  TOTP
  SMS
  EMAIL
}

enum OrganizationPlan {
  FREE
  PRO
  ENTERPRISE
}

enum LegalBasis {
  CONSENT
  LEGITIMATE_INTEREST
  CONTRACT
  LEGAL_OBLIGATION
}

enum RequestType {
  ACCESS
  RECTIFICATION
  ERASURE
  PORTABILITY
  RESTRICTION
  OBJECTION
}

enum RequestStatus {
  PENDING
  PROCESSING
  COMPLETED
  REJECTED
}

enum SSOProvider {
  SAML
  OAUTH
  OIDC
  GOOGLE
  MICROSOFT
  OKTA
}

enum InvitationStatus {
  PENDING
  ACCEPTED
  EXPIRED
  REVOKED
}

# Input Types

input UserFilter {
  email: String
  name: String
  organizationId: ID
  role: String
}

input OrgFilter {
  name: String
  plan: OrganizationPlan
}

input PaginationInput {
  first: Int
  after: String
  last: Int
  before: String
}

input UpdateProfileInput {
  name: String
  phone: String
  metadata: JSON
}

input UpdatePasswordInput {
  currentPassword: String!
  newPassword: String!
}

input CreateOrganizationInput {
  name: String!
  slug: String
}

input UpdateOrganizationInput {
  name: String
  settings: OrganizationSettingsInput
}

input OrganizationSettingsInput {
  requireMFA: Boolean
  allowedDomains: [String!]
}

input InviteUserInput {
  email: String!
  organizationId: ID!
  roleId: ID!
}

input CreateRoleInput {
  name: String!
  description: String
  permissions: [String!]!
}

input UpdateRoleInput {
  name: String
  description: String
  permissions: [String!]
}

input DataSubjectRequestInput {
  requestType: RequestType!
  description: String
}

input CreateSSOConfigInput {
  provider: SSOProvider!
  organizationId: ID!
  metadata: SSOMetadataInput!
}

input UpdateSSOConfigInput {
  enabled: Boolean
  metadata: SSOMetadataInput
}

input SSOMetadataInput {
  entityId: String
  ssoUrl: String
  certificate: String
  domains: [String!]
}

# Connections (Relay-style pagination)

type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type UserEdge {
  node: User!
  cursor: String!
}

type OrganizationConnection {
  edges: [OrganizationEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type OrganizationEdge {
  node: Organization!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}

# Complex Types

type OrganizationSettings {
  requireMFA: Boolean!
  allowedDomains: [String!]!
}

type SSOMetadata {
  entityId: String
  ssoUrl: String
  certificate: String
  domains: [String!]!
}
```

---

## Queries

### User Queries

#### Get Current User

```graphql
query GetCurrentUser {
  currentUser {
    id
    email
    name
    emailVerified
    mfaEnabled
    role {
      id
      name
      permissions {
        id
        name
      }
    }
    organization {
      id
      name
      plan
    }
  }
}
```

**Response:**
```json
{
  "data": {
    "currentUser": {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user@example.com",
      "name": "John Doe",
      "emailVerified": true,
      "mfaEnabled": true,
      "role": {
        "id": "role_admin",
        "name": "Administrator",
        "permissions": [
          {
            "id": "users:read",
            "name": "Read Users"
          }
        ]
      },
      "organization": {
        "id": "org_123abc",
        "name": "Acme Corporation",
        "plan": "ENTERPRISE"
      }
    }
  }
}
```

#### List Users with Pagination

```graphql
query ListUsers($filter: UserFilter, $pagination: PaginationInput) {
  users(filter: $filter, pagination: $pagination) {
    edges {
      node {
        id
        email
        name
        role {
          name
        }
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    totalCount
  }
}
```

**Variables:**
```json
{
  "filter": {
    "organizationId": "org_123abc"
  },
  "pagination": {
    "first": 20
  }
}
```

### Organization Queries

#### Get Organization Details

```graphql
query GetOrganization($id: ID!) {
  organization(id: $id) {
    id
    name
    slug
    plan
    ssoEnabled
    scimEnabled
    memberCount
    settings {
      requireMFA
      allowedDomains
    }
    members(pagination: { first: 10 }) {
      edges {
        node {
          id
          email
          name
        }
      }
    }
  }
}
```

### Compliance Queries

#### Get Consent Purposes

```graphql
query GetConsentPurposes {
  consentPurposes {
    id
    name
    description
    legalBasis
    required
    gdprArticle
  }
}
```

#### Get My Consent Records

```graphql
query GetMyConsent {
  myConsent {
    id
    purpose
    granted
    grantedAt
    withdrawnAt
  }
}
```

---

## Mutations

### User Mutations

#### Update Profile

```graphql
mutation UpdateProfile($input: UpdateProfileInput!) {
  updateProfile(input: $input) {
    id
    name
    phone
    updatedAt
  }
}
```

**Variables:**
```json
{
  "input": {
    "name": "Jane Doe",
    "phone": "+1234567890"
  }
}
```

#### Update Password

```graphql
mutation UpdatePassword($input: UpdatePasswordInput!) {
  updatePassword(input: $input)
}
```

**Variables:**
```json
{
  "input": {
    "currentPassword": "OldP@ssw0rd",
    "newPassword": "NewSecureP@ssw0rd123!"
  }
}
```

### MFA Mutations

#### Setup TOTP MFA

```graphql
mutation SetupMFA($method: MFAMethod!) {
  setupMFA(method: $method) {
    method
    secret
    qrCode
    backupCodes
  }
}
```

**Variables:**
```json
{
  "method": "TOTP"
}
```

**Response:**
```json
{
  "data": {
    "setupMFA": {
      "method": "TOTP",
      "secret": "JBSWY3DPEHPK3PXP",
      "qrCode": "data:image/png;base64,iVBORw0KGgo...",
      "backupCodes": [
        "ABC123DEF456",
        "GHI789JKL012",
        "MNO345PQR678"
      ]
    }
  }
}
```

#### Verify MFA

```graphql
mutation VerifyMFA($code: String!) {
  verifyMFA(code: $code) {
    success
    accessToken
  }
}
```

### Organization Mutations

#### Create Organization

```graphql
mutation CreateOrganization($input: CreateOrganizationInput!) {
  createOrganization(input: $input) {
    id
    name
    slug
    plan
    createdAt
  }
}
```

**Variables:**
```json
{
  "input": {
    "name": "New Company Inc",
    "slug": "new-company"
  }
}
```

#### Invite User to Organization

```graphql
mutation InviteUser($input: InviteUserInput!) {
  inviteUser(input: $input) {
    id
    email
    role {
      name
    }
    expiresAt
    status
  }
}
```

**Variables:**
```json
{
  "input": {
    "email": "newuser@example.com",
    "organizationId": "org_123abc",
    "roleId": "role_editor"
  }
}
```

### RBAC Mutations

#### Create Custom Role

```graphql
mutation CreateRole($input: CreateRoleInput!) {
  createRole(input: $input) {
    id
    name
    description
    permissions {
      id
      name
    }
    isSystem
  }
}
```

**Variables:**
```json
{
  "input": {
    "name": "Content Manager",
    "description": "Manage content but not users",
    "permissions": [
      "content:read",
      "content:write",
      "content:delete"
    ]
  }
}
```

#### Assign Role to User

```graphql
mutation AssignRole($userId: ID!, $roleId: ID!) {
  assignRole(userId: $userId, roleId: $roleId) {
    id
    email
    role {
      id
      name
    }
  }
}
```

### Compliance Mutations

#### Grant Consent

```graphql
mutation GrantConsent($purpose: String!) {
  grantConsent(purpose: $purpose) {
    id
    purpose
    granted
    grantedAt
    ipAddress
  }
}
```

**Variables:**
```json
{
  "purpose": "analytics"
}
```

#### Submit Data Subject Request

```graphql
mutation SubmitDataRequest($input: DataSubjectRequestInput!) {
  submitDataSubjectRequest(input: $input) {
    id
    requestType
    status
    gdprArticle
    responseDeadline
    createdAt
  }
}
```

**Variables:**
```json
{
  "input": {
    "requestType": "ACCESS",
    "description": "Request all my personal data as per GDPR Article 15"
  }
}
```

---

## Subscriptions

### User Subscription

```graphql
subscription OnUserUpdated($userId: ID!) {
  userUpdated(userId: $userId) {
    id
    email
    name
    updatedAt
  }
}
```

**JavaScript Client:**
```javascript
import { createClient } from 'graphql-ws';

const client = createClient({
  url: 'wss://api.janua.dev/graphql',
  connectionParams: {
    authorization: `Bearer ${accessToken}`,
  },
});

const subscription = client.subscribe(
  {
    query: `
      subscription OnUserUpdated($userId: ID!) {
        userUpdated(userId: $userId) {
          id
          email
          name
          updatedAt
        }
      }
    `,
    variables: { userId: '123e4567' },
  },
  {
    next: (data) => {
      console.log('User updated:', data.userUpdated);
    },
    error: (error) => {
      console.error('Subscription error:', error);
    },
    complete: () => {
      console.log('Subscription completed');
    },
  }
);

// Later: unsubscribe
subscription();
```

### Organization Subscription

```graphql
subscription OnOrganizationUpdated($organizationId: ID!) {
  organizationUpdated(organizationId: $organizationId) {
    id
    name
    memberCount
    updatedAt
  }
}
```

### Audit Log Subscription

```graphql
subscription OnAuditLogCreated($organizationId: ID!) {
  auditLogCreated(organizationId: $organizationId) {
    id
    userId
    action
    resource
    resourceId
    timestamp
  }
}
```

---

## Error Handling

### Error Format

GraphQL errors follow standard format:

```json
{
  "errors": [
    {
      "message": "User not found",
      "locations": [{ "line": 2, "column": 3 }],
      "path": ["user"],
      "extensions": {
        "code": "NOT_FOUND",
        "status": 404
      }
    }
  ],
  "data": null
}
```

### Common Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `UNAUTHENTICATED` | Missing or invalid auth token | 401 |
| `FORBIDDEN` | Insufficient permissions | 403 |
| `NOT_FOUND` | Resource not found | 404 |
| `VALIDATION_ERROR` | Input validation failed | 400 |
| `CONFLICT` | Resource conflict (e.g., duplicate email) | 409 |
| `RATE_LIMITED` | Too many requests | 429 |
| `INTERNAL_ERROR` | Server error | 500 |

### Handling Errors in Client

```javascript
const result = await client.query({
  query: GET_USER,
  variables: { id: userId },
});

if (result.errors) {
  result.errors.forEach(error => {
    console.error(`Error: ${error.message}`);
    console.error(`Code: ${error.extensions.code}`);
  });
}
```

---

## Best Practices

### 1. Request Only Needed Fields

❌ **Bad:**
```graphql
query GetUser {
  currentUser {
    id
    email
    name
    phone
    emailVerified
    phoneVerified
    mfaEnabled
    passkeyEnabled
    createdAt
    updatedAt
    metadata
    # ... requesting everything
  }
}
```

✅ **Good:**
```graphql
query GetUser {
  currentUser {
    id
    email
    name
  }
}
```

### 2. Use Fragments for Reusable Fields

```graphql
fragment UserFields on User {
  id
  email
  name
  role {
    id
    name
  }
}

query GetCurrentUser {
  currentUser {
    ...UserFields
  }
}

query GetUsers {
  users(pagination: { first: 10 }) {
    edges {
      node {
        ...UserFields
      }
    }
  }
}
```

### 3. Implement Cursor-Based Pagination

```graphql
query GetUsers($after: String) {
  users(pagination: { first: 20, after: $after }) {
    edges {
      node {
        id
        email
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

**Client Code:**
```javascript
let hasMore = true;
let after = null;
const allUsers = [];

while (hasMore) {
  const { data } = await client.query({
    query: GET_USERS,
    variables: { after },
  });
  
  allUsers.push(...data.users.edges.map(e => e.node));
  hasMore = data.users.pageInfo.hasNextPage;
  after = data.users.pageInfo.endCursor;
}
```

### 4. Use Aliases for Multiple Queries

```graphql
query GetMultipleUsers {
  admin: user(id: "user_1") {
    id
    name
    role { name }
  }
  editor: user(id: "user_2") {
    id
    name
    role { name }
  }
}
```

### 5. Batch Mutations

```graphql
mutation UpdateMultiple($profile: UpdateProfileInput!, $password: UpdatePasswordInput!) {
  updateProfile(input: $profile) {
    id
    name
  }
  updatePassword(input: $password)
}
```

### 6. Use Variables for Dynamic Queries

❌ **Bad:**
```graphql
query {
  user(id: "123") {
    email
  }
}
```

✅ **Good:**
```graphql
query GetUser($userId: ID!) {
  user(id: $userId) {
    email
  }
}
```

### 7. Handle Loading and Error States

```javascript
const { data, loading, error } = useQuery(GET_CURRENT_USER);

if (loading) return <Spinner />;
if (error) return <Error message={error.message} />;

return <UserProfile user={data.currentUser} />;
```

### 8. Implement Optimistic Updates

```javascript
const [updateProfile] = useMutation(UPDATE_PROFILE, {
  optimisticResponse: {
    updateProfile: {
      __typename: 'User',
      id: userId,
      name: newName,
      updatedAt: new Date().toISOString(),
    },
  },
});
```

### 9. Use Subscriptions Wisely

```javascript
// Subscribe only when component is mounted
useEffect(() => {
  const subscription = client.subscribe({
    query: USER_UPDATED_SUBSCRIPTION,
    variables: { userId },
  }).subscribe({
    next: (data) => {
      // Update cache or state
    },
  });
  
  return () => subscription.unsubscribe();
}, [userId]);
```

### 10. Monitor Query Performance

```graphql
query GetUsers @cost(weight: 1000) {
  users(pagination: { first: 100 }) {
    edges {
      node {
        id
        organization {  # N+1 query potential
          members {     # Deep nesting
            edges {
              node {
                id
              }
            }
          }
        }
      }
    }
  }
}
```

**Better:**
```graphql
query GetUsers {
  users(pagination: { first: 100 }) {
    edges {
      node {
        id
        organizationId  # Just the ID
      }
    }
  }
}
```

---

## Rate Limiting

GraphQL queries are rate-limited based on query complexity:

- **Simple queries**: 1000 requests/minute
- **Complex queries**: 100 requests/minute
- **Mutations**: 60 requests/minute
- **Subscriptions**: 10 concurrent connections

Query complexity is calculated based on:
- Field count
- Nesting depth
- Connection pagination size

---

## Playground

Interactive GraphQL Playground available at:

**Development**: http://localhost:8000/graphql  
**Staging**: https://staging-api.janua.dev/graphql  
**Production**: https://api.janua.dev/graphql

Features:
- Schema exploration
- Auto-completion
- Query history
- Documentation sidebar

---

## Support

- **Documentation**: https://docs.janua.dev/graphql
- **Questions**: [GitHub Discussions](https://github.com/madfam-org/janua/discussions) (Janua has no Discord, 2026-11-26)
- **Email**: api@janua.dev

---

**Last Updated**: November 26, 2026  
**Version**: 1.0.0-beta
