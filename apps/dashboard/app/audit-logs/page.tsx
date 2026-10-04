import { Card, CardContent, CardHeader, CardTitle } from '@janua/ui'
import { AuditList } from '@/components/audit/audit-list'

export default function AuditLogsPage() {
  return <Card><CardHeader><CardTitle>Organization audit logs</CardTitle></CardHeader><CardContent><AuditList /></CardContent></Card>
}
