'use client'

import { Loader2, FileText } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import type { DataSubjectRightType } from '../types'
import { REQUEST_TYPES } from '../constants'

interface DSRFormProps {
  selectedType: DataSubjectRightType
  reason: string
  onTypeChange: (type: DataSubjectRightType) => void
  onReasonChange: (reason: string) => void
  onSubmit: (e: React.FormEvent) => void
  submitting: boolean
}

export function DSRForm({
  selectedType,
  reason,
  onTypeChange,
  onReasonChange,
  onSubmit,
  submitting,
}: DSRFormProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Exercise Your Data Rights</CardTitle>
        <CardDescription>
          Under GDPR and privacy regulations, you have the right to control your personal data
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="font-medium">Request Type</label>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {REQUEST_TYPES.map((type) => (
                <div
                  key={type.value}
                  className={`cursor-pointer rounded-lg border p-4 transition-colors ${
                    selectedType === type.value
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  }`}
                  onClick={() => onTypeChange(type.value)}
                >
                  <label className="flex cursor-pointer items-start space-x-3">
                    <input
                      type="radio"
                      name="requestType"
                      value={type.value}
                      checked={selectedType === type.value}
                      onChange={(e) => onTypeChange(e.target.value as DataSubjectRightType)}
                      className="mt-1 size-4"
                    />
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{type.label}</span>
                        <span className="text-muted-foreground text-xs">{type.gdprArticle}</span>
                      </div>
                      <p className="text-muted-foreground mt-1 text-sm">{type.description}</p>
                    </div>
                  </label>
                </div>
              ))}
            </div>
          </div>

          {selectedType !== 'access' && (
            <div className="space-y-2">
              <label className="font-medium">Reason for Request</label>
              <textarea
                value={reason}
                onChange={(e) => onReasonChange(e.target.value)}
                placeholder="Please provide details about your request..."
                rows={4}
                className="border-input bg-background focus:border-primary focus:ring-primary w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1"
              />
            </div>
          )}

          <div className="border-primary/30 bg-primary/5 rounded-lg border p-4">
            <h4 className="text-primary text-sm font-semibold">What happens next?</h4>
            <ul className="text-primary/80 mt-2 space-y-1 text-sm">
              <li>• We&apos;ll verify your identity via email</li>
              <li>• Your request will be reviewed within 30 days (GDPR requirement)</li>
              <li>• You&apos;ll receive email updates on the status</li>
            </ul>
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <FileText className="mr-2 size-4" />
                  Submit Request
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
