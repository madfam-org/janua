import { Card, CardContent, CardHeader, CardTitle } from '@janua/ui'

export default function SystemSettingsPage() {
  return <Card><CardHeader><CardTitle>Platform administration</CardTitle></CardHeader><CardContent className="space-y-3">
    <p>Platform-wide CORS, password, session, and rate-limit settings are managed in Janua Admin.</p>
    <p className="text-muted-foreground text-sm">These controls require platform administrator access. Organization roles do not grant platform access.</p>
    <a href="https://admin.janua.dev" className="text-primary underline">Open Janua Admin</a>
  </CardContent></Card>
}
