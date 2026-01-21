'use client'

import { Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import type { PrivacyPreferences } from '../types'
import { PROFILE_VISIBILITY_OPTIONS } from '../constants'
import { ToggleSetting } from './toggle-setting'

interface PrivacySettingsSectionProps {
  preferences: PrivacyPreferences
  onPreferencesChange: (prefs: PrivacyPreferences) => void
  onSave: () => void
  saving: boolean
}

export function PrivacySettingsSection({
  preferences,
  onPreferencesChange,
  onSave,
  saving,
}: PrivacySettingsSectionProps) {
  const updatePref = <K extends keyof PrivacyPreferences>(key: K, value: PrivacyPreferences[K]) => {
    onPreferencesChange({ ...preferences, [key]: value })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Privacy Settings</CardTitle>
        <CardDescription>Control how your data is collected, used, and shared</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Data Collection */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Data Collection & Analytics</h3>
          <ToggleSetting
            label="Analytics & Performance"
            description="Allow us to collect anonymous usage data to improve the product"
            checked={preferences.analytics}
            onChange={(checked) => updatePref('analytics', checked)}
          />
          <ToggleSetting
            label="Activity Tracking"
            description="Track your activity for personalized recommendations"
            checked={preferences.activity_tracking}
            onChange={(checked) => updatePref('activity_tracking', checked)}
          />
        </div>

        {/* Marketing */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Marketing & Communications</h3>
          <ToggleSetting
            label="Marketing Emails"
            description="Receive promotional emails and product updates"
            checked={preferences.marketing}
            onChange={(checked) => updatePref('marketing', checked)}
          />
          <ToggleSetting
            label="Email Notifications"
            description="Receive important account and security notifications"
            checked={preferences.email_notifications}
            onChange={(checked) => updatePref('email_notifications', checked)}
          />
        </div>

        {/* Data Sharing */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Data Sharing</h3>
          <ToggleSetting
            label="Third-Party Sharing"
            description="Allow sharing anonymized data with trusted partners"
            checked={preferences.third_party_sharing}
            onChange={(checked) => updatePref('third_party_sharing', checked)}
          />

          <div className="space-y-2 rounded-lg border p-4">
            <label className="font-medium">Profile Visibility</label>
            <p className="text-muted-foreground text-sm">Control who can see your profile</p>
            <div className="mt-3 space-y-2">
              {PROFILE_VISIBILITY_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={`flex cursor-pointer items-start space-x-3 rounded-lg border p-3 ${
                    preferences.profile_visibility === option.value
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="profile_visibility"
                    value={option.value}
                    checked={preferences.profile_visibility === option.value}
                    onChange={(e) =>
                      updatePref('profile_visibility', e.target.value as 'public' | 'private' | 'organization')
                    }
                    className="mt-1 size-4"
                  />
                  <div>
                    <p className="font-medium">{option.label}</p>
                    <p className="text-muted-foreground text-sm">{option.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-end border-t pt-4">
          <Button onClick={onSave} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Settings'
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
