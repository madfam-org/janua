'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'

const PRIVACY_RIGHTS = [
  { title: 'Right to Access', description: 'Request a copy of all data we hold about you' },
  { title: 'Right to Erasure', description: 'Request deletion of your personal data' },
  { title: 'Right to Portability', description: 'Export your data in a machine-readable format' },
  { title: 'Right to Rectification', description: 'Request correction of inaccurate data' },
  { title: 'Right to Object', description: 'Object to processing of your data' },
  { title: 'Right to Restriction', description: 'Restrict processing of your data' },
]

export function PrivacyRightsInfo() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your Privacy Rights</CardTitle>
        <CardDescription>Understanding your rights under GDPR and privacy laws</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
          {PRIVACY_RIGHTS.map((right) => (
            <div key={right.title} className="flex items-start space-x-2">
              <span className="text-primary font-bold">•</span>
              <p>
                <strong>{right.title}:</strong> {right.description}
              </p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
