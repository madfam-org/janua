import Link from 'next/link'

import { Card, CardContent, CardHeader, CardTitle } from '@janua/ui'

export default function UserDetailPage() {
  return <Card><CardHeader><CardTitle>Organization member details</CardTitle></CardHeader><CardContent className="space-y-3">
    <p>Choose the member’s organization to view their membership and organization role.</p>
    <Link href="/users" className="text-primary underline">Choose an organization</Link>
    <p className="text-muted-foreground text-sm">Account-wide user profiles, session controls, and security actions are managed in Janua Admin.</p>
  </CardContent></Card>
}
