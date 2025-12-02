'use client'

import * as React from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui/components/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui/components/card'
import {
  InvitationList,
  InviteUserForm,
  InvitationAccept,
  BulkInviteUpload,
  type Invitation,
  type InvitationCreate,
  type BulkInvitationResponse,
  type InvitationAcceptResponse,
} from '@janua/ui/components/auth'
import { januaClient } from '@/lib/janua-client'

export default function InvitationsShowcasePage() {
  const [activeTab, setActiveTab] = React.useState('manage')
  const [invitationToken, setInvitationToken] = React.useState<string>('')
  const [showAcceptDemo, setShowAcceptDemo] = React.useState(false)

  // Mock organization ID (in production, get from auth context)
  const organizationId = 'demo-org-123'

  // Handler for single invitation created
  const handleInvitationCreated = (invitation: Invitation) => {
    // removed console.log
    alert(`Invitation sent to ${invitation.email}!\n\nInvitation URL:\n${invitation.invite_url}`)

    // Switch to manage tab to see the new invitation
    setActiveTab('manage')
  }

  // Handler for bulk invitations created
  const handleBulkInvitationsCreated = (result: BulkInvitationResponse) => {
    // removed console.log
    alert(
      `Bulk invitation complete!\n\n` +
      `Total: ${result.total}\n` +
      `Successful: ${result.successful}\n` +
      `Failed: ${result.failed}\n\n` +
      `Check console for detailed results.`
    )

    // Switch to manage tab to see the new invitations
    setActiveTab('manage')
  }

  // Handler for invitation accepted
  const handleInvitationAccepted = (response: InvitationAcceptResponse) => {
    // removed console.log
    alert(
      `Invitation accepted successfully!\n\n` +
      `User ID: ${response.user_id}\n` +
      `Organization: ${response.organization_id}\n` +
      `New User: ${response.is_new_user ? 'Yes' : 'No'}`
    )
  }

  // Demo invitation token generator
  const generateDemoToken = () => {
    // In production, this would come from the actual invitation URL
    const demoToken = 'demo-token-' + Math.random().toString(36).substring(7)
    setInvitationToken(demoToken)
    setShowAcceptDemo(true)
    setActiveTab('accept')
  }

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Organization Invitations</h1>
          <p className="text-muted-foreground">
            Invite users to join your organization, manage pending invitations, and track acceptance status.
          </p>
        </div>

        {/* Info Card */}
        <Card className="border-purple-200 bg-purple-50 dark:bg-purple-900/20 dark:border-purple-800">
          <CardHeader>
            <CardTitle className="text-purple-900 dark:text-purple-100">📧 Invitation System</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-purple-800 dark:text-purple-200 space-y-2">
            <p><strong>How it works:</strong></p>
            <ol className="list-decimal list-inside ml-4 space-y-1">
              <li>Send invitations to users via email with a unique secure token</li>
              <li>Users click the invitation link and accept to join your organization</li>
              <li>New users create an account, existing users join with their current account</li>
              <li>Users are automatically assigned the role specified in the invitation</li>
            </ol>
            <p><strong>Features:</strong></p>
            <ul className="list-disc list-inside ml-4 space-y-1">
              <li>Single and bulk invitation support (up to 100 users at once)</li>
              <li>Customizable roles and personal welcome messages</li>
              <li>Expiration management (1-30 days)</li>
              <li>Track status: pending, accepted, expired, revoked</li>
              <li>Resend or revoke invitations anytime</li>
            </ul>
          </CardContent>
        </Card>

        {/* Main Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="manage">
              Manage
              <span className="ml-2 text-xs text-muted-foreground">(List)</span>
            </TabsTrigger>
            <TabsTrigger value="invite">
              Invite User
              <span className="ml-2 text-xs text-muted-foreground">(Single)</span>
            </TabsTrigger>
            <TabsTrigger value="bulk">
              Bulk Upload
              <span className="ml-2 text-xs text-muted-foreground">(CSV)</span>
            </TabsTrigger>
            <TabsTrigger value="accept">
              Accept
              <span className="ml-2 text-xs text-muted-foreground">(Demo)</span>
            </TabsTrigger>
          </TabsList>

          {/* Tab 1: Manage Invitations */}
          <TabsContent value="manage" className="mt-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Invitation Management</CardTitle>
                    <CardDescription>
                      View, filter, and manage all organization invitations
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setActiveTab('bulk')}
                      className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors"
                    >
                      📤 Bulk Upload
                    </button>
                    <button
                      onClick={() => setActiveTab('invite')}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                      + Invite User
                    </button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <InvitationList
                  organizationId={organizationId}
                  januaClient={januaClient}
                  onResend={async (invitationId) => {
                    // removed console.log
                    alert(`Invitation resent!`)
                  }}
                  onRevoke={async (invitationId) => {
                    if (confirm(`Revoke invitation?`)) {
                      // removed console.log
                    }
                  }}
                />
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 2: Invite Single User */}
          <TabsContent value="invite" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Invite User to Organization</CardTitle>
                <CardDescription>
                  Send a single invitation to a user to join your organization
                </CardDescription>
              </CardHeader>
              <CardContent>
                <InviteUserForm
                  organizationId={organizationId}
                  januaClient={januaClient}
                  onSuccess={handleInvitationCreated}
                  onCancel={() => setActiveTab('manage')}
                />
              </CardContent>
            </Card>

            {/* Invitation Tips */}
            <Card className="mt-6 border-blue-200 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-800">
              <CardHeader>
                <CardTitle className="text-blue-900 dark:text-blue-100">💡 Invitation Best Practices</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-blue-800 dark:text-blue-200 space-y-2">
                <p><strong>Email Verification:</strong> Ensure the email address is correct before sending</p>
                <p><strong>Role Selection:</strong> Choose the appropriate role for the user's responsibilities</p>
                <p><strong>Personal Message:</strong> Include a welcome message to make invitations more personal</p>
                <p><strong>Expiration:</strong> Set appropriate expiration (7 days is typical, 30 days max)</p>
                <p><strong>Follow Up:</strong> Check the Manage tab to see if invitations are accepted</p>
                <p><strong>Resend Option:</strong> If user doesn't receive email, you can resend the invitation</p>
              </CardContent>
            </Card>

            {/* Role Descriptions */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle>👥 Role Descriptions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="border rounded-lg p-4 space-y-2">
                    <h3 className="font-semibold text-green-700 dark:text-green-400">👤 Member</h3>
                    <p className="text-sm text-muted-foreground">
                      Standard user with access to core features and organization resources.
                    </p>
                    <ul className="text-xs space-y-1 list-disc list-inside">
                      <li>View organization data</li>
                      <li>Use core features</li>
                      <li>Collaborate with team</li>
                    </ul>
                  </div>

                  <div className="border rounded-lg p-4 space-y-2">
                    <h3 className="font-semibold text-blue-700 dark:text-blue-400">⭐ Admin</h3>
                    <p className="text-sm text-muted-foreground">
                      Administrative access with management capabilities and user administration.
                    </p>
                    <ul className="text-xs space-y-1 list-disc list-inside">
                      <li>All Member permissions</li>
                      <li>Manage users and invitations</li>
                      <li>Configure organization settings</li>
                    </ul>
                  </div>

                  <div className="border rounded-lg p-4 space-y-2">
                    <h3 className="font-semibold text-purple-700 dark:text-purple-400">👑 Owner</h3>
                    <p className="text-sm text-muted-foreground">
                      Full control including billing, security, and organization deletion.
                    </p>
                    <ul className="text-xs space-y-1 list-disc list-inside">
                      <li>All Admin permissions</li>
                      <li>Billing and subscriptions</li>
                      <li>Security and SSO config</li>
                      <li>Delete organization</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 3: Bulk Upload */}
          <TabsContent value="bulk" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Bulk Invitation Upload</CardTitle>
                <CardDescription>
                  Upload a CSV file to invite multiple users at once (maximum 100 users)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <BulkInviteUpload
                  organizationId={organizationId}
                  januaClient={januaClient}
                  onSuccess={handleBulkInvitationsCreated}
                  maxInvitations={100}
                />
              </CardContent>
            </Card>

            {/* CSV Format Guide */}
            <Card className="mt-6 border-amber-200 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-800">
              <CardHeader>
                <CardTitle className="text-amber-900 dark:text-amber-100">📄 CSV Format Guide</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-amber-800 dark:text-amber-200 space-y-3">
                <p><strong>Required Format:</strong></p>
                <div className="bg-white dark:bg-gray-900 p-3 rounded border font-mono text-xs">
                  email,role,message<br />
                  john@example.com,member,Welcome to our team!<br />
                  jane@example.com,admin,<br />
                  bob@example.com,member,Excited to have you join us
                </div>

                <p><strong>Column Details:</strong></p>
                <ul className="list-disc list-inside ml-4 space-y-1">
                  <li><strong>email</strong> (required): Valid email address</li>
                  <li><strong>role</strong> (optional): member, admin, or owner (default: member)</li>
                  <li><strong>message</strong> (optional): Personal welcome message</li>
                </ul>

                <p><strong>Important Notes:</strong></p>
                <ul className="list-disc list-inside ml-4 space-y-1">
                  <li>Maximum 100 invitations per upload</li>
                  <li>First row must be header row (email,role,message)</li>
                  <li>Empty message field will use default organization message</li>
                  <li>Invalid emails will be shown in preview before sending</li>
                  <li>Duplicate emails will be detected and skipped</li>
                </ul>
              </CardContent>
            </Card>

            {/* Bulk Upload Tips */}
            <Card className="mt-6 border-green-200 bg-green-50 dark:bg-green-900/20 dark:border-green-800">
              <CardHeader>
                <CardTitle className="text-green-900 dark:text-green-100">✅ Bulk Upload Best Practices</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-green-800 dark:text-green-200 space-y-2">
                <p><strong>Before Upload:</strong></p>
                <ul className="list-disc list-inside ml-4 space-y-1">
                  <li>Download the template and verify format</li>
                  <li>Clean your email list and remove duplicates</li>
                  <li>Verify email addresses are valid</li>
                  <li>Keep under 100 invitations per batch</li>
                </ul>

                <p><strong>After Upload:</strong></p>
                <ul className="list-disc list-inside ml-4 space-y-1">
                  <li>Review preview table before submitting</li>
                  <li>Check results summary for failures</li>
                  <li>Retry failed invitations individually if needed</li>
                  <li>Monitor acceptance rate in Manage tab</li>
                </ul>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 4: Accept Invitation (Demo) */}
          <TabsContent value="accept" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Accept Invitation</CardTitle>
                <CardDescription>
                  Demo of the invitation acceptance flow (normally accessed via email link)
                </CardDescription>
              </CardHeader>
              <CardContent>
                {showAcceptDemo && invitationToken ? (
                  <InvitationAccept
                    token={invitationToken}
                    januaClient={januaClient}
                    onSuccess={handleInvitationAccepted}
                    onError={(error) => {
                      console.error('Invitation accept error:', error)
                      alert(`Error: ${error.message}`)
                    }}
                  />
                ) : (
                  <div className="text-center py-12 space-y-4">
                    <div className="text-muted-foreground">
                      <p className="mb-4">Click the button below to generate a demo invitation token</p>
                      <p className="text-sm">
                        In production, users access this page via the invitation URL sent to their email.
                      </p>
                    </div>
                    <button
                      onClick={generateDemoToken}
                      className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                      Generate Demo Invitation
                    </button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Acceptance Flow Info */}
            <Card className="mt-6 border-indigo-200 bg-indigo-50 dark:bg-indigo-900/20 dark:border-indigo-800">
              <CardHeader>
                <CardTitle className="text-indigo-900 dark:text-indigo-100">🔄 Acceptance Flow</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-indigo-800 dark:text-indigo-200 space-y-3">
                <p><strong>For New Users:</strong></p>
                <ol className="list-decimal list-inside ml-4 space-y-1">
                  <li>Receive invitation email with unique link</li>
                  <li>Click link and see invitation details</li>
                  <li>Choose "Create Account" option</li>
                  <li>Enter name and password</li>
                  <li>Account created and automatically joined to organization</li>
                </ol>

                <p className="mt-4"><strong>For Existing Users:</strong></p>
                <ol className="list-decimal list-inside ml-4 space-y-1">
                  <li>Receive invitation email with unique link</li>
                  <li>Click link and see invitation details</li>
                  <li>Choose "Sign In" option</li>
                  <li>Sign in with existing credentials</li>
                  <li>Automatically joined to organization with specified role</li>
                </ol>

                <p className="mt-4"><strong>Security Features:</strong></p>
                <ul className="list-disc list-inside ml-4 space-y-1">
                  <li>Secure token-based validation</li>
                  <li>Email verification to prevent unauthorized access</li>
                  <li>Expiration enforcement (cannot accept expired invitations)</li>
                  <li>Revocation support (admins can revoke before acceptance)</li>
                </ul>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Footer Info */}
        <Card className="bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-800">
          <CardContent className="pt-6">
            <div className="text-sm text-muted-foreground space-y-2">
              <p><strong>Need Help?</strong></p>
              <ul className="list-disc list-inside ml-4 space-y-1">
                <li>Check our <a href="#" className="text-blue-600 hover:underline">Invitation Management Guide</a></li>
                <li>Learn about <a href="#" className="text-blue-600 hover:underline">Organization Roles & Permissions</a></li>
                <li>View <a href="#" className="text-blue-600 hover:underline">Bulk Upload Tutorial</a></li>
                <li>Contact <a href="#" className="text-blue-600 hover:underline">Support Team</a></li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
