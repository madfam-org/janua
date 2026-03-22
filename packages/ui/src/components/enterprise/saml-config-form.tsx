import * as React from 'react'
import { Button } from '../button'
import { Badge } from '../badge'
import { cn } from '../../lib/utils'

export interface SAMLAttributeMapping {
  email?: string
  name?: string
  first_name?: string
  last_name?: string
  phone?: string
  [key: string]: string | undefined
}

export interface SAMLConfigFormProps {
  className?: string
  organizationId: string
  onSubmit?: (config: any) => Promise<void>
  onCancel?: () => void
  onError?: (error: Error) => void
  januaClient?: any
  apiUrl?: string
}

export function SAMLConfigForm({
  className,
  organizationId,
  onSubmit,
  onCancel,
  onError,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
}: SAMLConfigFormProps) {
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [spMetadata, setSpMetadata] = React.useState<string | null>(null)
  const [isLoadingMetadata, setIsLoadingMetadata] = React.useState(false)

  // SAML configuration
  const [entityId, setEntityId] = React.useState('')
  const [acsUrl, setAcsUrl] = React.useState('')
  const [sloUrl, _setSloUrl] = React.useState('')
  const [certificate, setCertificate] = React.useState('')
  const [certificateFile, setCertificateFile] = React.useState<File | null>(null)

  // Attribute mapping
  const [emailAttr, setEmailAttr] = React.useState('email')
  const [nameAttr, setNameAttr] = React.useState('name')
  const [firstNameAttr, setFirstNameAttr] = React.useState('firstName')
  const [lastNameAttr, setLastNameAttr] = React.useState('lastName')
  const [phoneAttr, setPhoneAttr] = React.useState('phone')
  const [customMappings, setCustomMappings] = React.useState<Array<{ key: string; value: string }>>([])

  // Advanced settings
  const [signRequests, setSignRequests] = React.useState(true)
  const [wantAssertionsSigned, setWantAssertionsSigned] = React.useState(true)
  const [nameIdFormat, setNameIdFormat] = React.useState('urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress')

  // Load SP metadata on mount
  React.useEffect(() => {
    loadSPMetadata()
  }, [organizationId])

  // Load Service Provider metadata
  const loadSPMetadata = async () => {
    setIsLoadingMetadata(true)
    try {
      let metadata: string

      if (januaClient) {
        metadata = await januaClient.sso.generateSPMetadata(organizationId)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/sso/metadata/${organizationId}`, {
          credentials: 'include',
        })

        if (!res.ok) {
          throw new Error('Failed to load SP metadata')
        }

        metadata = await res.text()
      }

      setSpMetadata(metadata)

      // Extract ACS URL and Entity ID from metadata if available
      const parser = new DOMParser()
      const doc = parser.parseFromString(metadata, 'text/xml')

      const entityIdAttr = doc.querySelector('EntityDescriptor')?.getAttribute('entityID')
      if (entityIdAttr) setEntityId(entityIdAttr)

      const acsUrlAttr = doc.querySelector('AssertionConsumerService')?.getAttribute('Location')
      if (acsUrlAttr) setAcsUrl(acsUrlAttr)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load SP metadata')
      onError?.(error)
    } finally {
      setIsLoadingMetadata(false)
    }
  }

  // Download SP metadata
  const downloadMetadata = () => {
    if (!spMetadata) return

    const blob = new Blob([spMetadata], { type: 'application/xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `saml-sp-metadata-${organizationId}.xml`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Copy SP metadata to clipboard
  const copyMetadata = async () => {
    if (!spMetadata) return
    try {
      await navigator.clipboard.writeText(spMetadata)
    } catch (err) {
      console.error('Failed to copy metadata:', err)
    }
  }

  // Handle certificate file upload
  const handleCertificateUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setCertificateFile(file)

    const reader = new FileReader()
    reader.onload = (event) => {
      const content = event.target?.result as string
      setCertificate(content)
    }
    reader.readAsText(file)
  }

  // Add custom attribute mapping
  const addCustomMapping = () => {
    setCustomMappings([...customMappings, { key: '', value: '' }])
  }

  // Update custom mapping
  const updateCustomMapping = (index: number, field: 'key' | 'value', value: string) => {
    const updated = [...customMappings]
    const mapping = updated[index]
    if (mapping) {
      mapping[field] = value
    }
    setCustomMappings(updated)
  }

  // Remove custom mapping
  const removeCustomMapping = (index: number) => {
    setCustomMappings(customMappings.filter((_, i) => i !== index))
  }

  // Handle submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validation
    if (!entityId || !acsUrl) {
      setError('Entity ID and ACS URL are required')
      return
    }

    if (!certificate) {
      setError('X.509 Certificate is required for SAML configuration')
      return
    }

    setIsSubmitting(true)

    try {
      const attributeMapping: SAMLAttributeMapping = {
        email: emailAttr,
        name: nameAttr,
        first_name: firstNameAttr,
        last_name: lastNameAttr,
        phone: phoneAttr,
      }

      // Add custom mappings
      customMappings.forEach((mapping) => {
        if (mapping.key && mapping.value) {
          attributeMapping[mapping.key] = mapping.value
        }
      })

      const configData = {
        saml_entity_id: entityId,
        saml_acs_url: acsUrl,
        saml_slo_url: sloUrl || undefined,
        saml_certificate: certificate,
        attribute_mapping: attributeMapping,
        sign_requests: signRequests,
        want_assertions_signed: wantAssertionsSigned,
        name_id_format: nameIdFormat,
      }

      if (januaClient) {
        await januaClient.sso.updateConfiguration(organizationId, configData)
      } else if (onSubmit) {
        await onSubmit(configData)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/sso/configurations/${organizationId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(configData),
        })

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}))
          throw new Error(errorData.detail || 'Failed to save SAML configuration')
        }
      }

      onCancel?.()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to save SAML configuration')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      {/* Error */}
      {error && (
        <div className="p-4 border border-red-200 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Service Provider Metadata */}
      <div className="p-4 border rounded-lg space-y-4 bg-blue-50 dark:bg-blue-900/20">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-semibold">Service Provider Metadata</h4>
            <p className="text-sm text-muted-foreground">
              Provide this metadata to your identity provider
            </p>
          </div>
          <Badge variant="default">SP Configuration</Badge>
        </div>

        {isLoadingMetadata ? (
          <div className="text-center py-4 text-muted-foreground">
            Loading metadata...
          </div>
        ) : spMetadata ? (
          <>
            <div className="space-y-2">
              <div className="flex gap-2">
                <Button type="button" onClick={downloadMetadata} variant="outline" size="sm">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download Metadata
                </Button>
                <Button type="button" onClick={copyMetadata} variant="outline" size="sm">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium">Entity ID:</span>
                <div className="text-muted-foreground truncate">{entityId || 'Not available'}</div>
              </div>
              <div>
                <span className="font-medium">ACS URL:</span>
                <div className="text-muted-foreground truncate">{acsUrl || 'Not available'}</div>
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-4 text-muted-foreground">
            No metadata available
          </div>
        )}
      </div>

      {/* Identity Provider Certificate */}
      <div className="space-y-4 p-4 border rounded-lg">
        <h4 className="font-semibold">Identity Provider Certificate</h4>

        <div className="space-y-2">
          <label htmlFor="certificateFile" className="block text-sm font-medium">
            Upload Certificate File <span className="text-red-500">*</span>
          </label>
          <input
            id="certificateFile"
            type="file"
            accept=".pem,.cer,.crt"
            onChange={handleCertificateUpload}
            className="w-full px-3 py-2 border rounded-md"
          />
          {certificateFile && (
            <p className="text-xs text-green-600">
              Loaded: {certificateFile.name}
            </p>
          )}
        </div>

        <div className="text-center text-sm text-muted-foreground">OR</div>

        <div className="space-y-2">
          <label htmlFor="certificate" className="block text-sm font-medium">
            Paste Certificate <span className="text-red-500">*</span>
          </label>
          <textarea
            id="certificate"
            value={certificate}
            onChange={(e) => setCertificate(e.target.value)}
            placeholder="-----BEGIN CERTIFICATE-----&#10;MIIDXTCCAkWgAwIBAgIJAKZHx...&#10;-----END CERTIFICATE-----"
            rows={6}
            required
            className="w-full px-3 py-2 border rounded-md font-mono text-xs"
          />
          <p className="text-xs text-muted-foreground">
            X.509 certificate from your identity provider
          </p>
        </div>
      </div>

      {/* Attribute Mapping */}
      <div className="space-y-4 p-4 border rounded-lg">
        <div>
          <h4 className="font-semibold">Attribute Mapping</h4>
          <p className="text-sm text-muted-foreground">
            Map SAML attributes to user profile fields
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="emailAttr" className="block text-sm font-medium">
              Email Attribute
            </label>
            <input
              id="emailAttr"
              type="text"
              value={emailAttr}
              onChange={(e) => setEmailAttr(e.target.value)}
              placeholder="email"
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="nameAttr" className="block text-sm font-medium">
              Name Attribute
            </label>
            <input
              id="nameAttr"
              type="text"
              value={nameAttr}
              onChange={(e) => setNameAttr(e.target.value)}
              placeholder="name"
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="firstNameAttr" className="block text-sm font-medium">
              First Name Attribute
            </label>
            <input
              id="firstNameAttr"
              type="text"
              value={firstNameAttr}
              onChange={(e) => setFirstNameAttr(e.target.value)}
              placeholder="firstName"
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="lastNameAttr" className="block text-sm font-medium">
              Last Name Attribute
            </label>
            <input
              id="lastNameAttr"
              type="text"
              value={lastNameAttr}
              onChange={(e) => setLastNameAttr(e.target.value)}
              placeholder="lastName"
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="phoneAttr" className="block text-sm font-medium">
              Phone Attribute
            </label>
            <input
              id="phoneAttr"
              type="text"
              value={phoneAttr}
              onChange={(e) => setPhoneAttr(e.target.value)}
              placeholder="phone"
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
        </div>

        {/* Custom Mappings */}
        {customMappings.length > 0 && (
          <div className="space-y-2 pt-4 border-t">
            <label className="block text-sm font-medium">Custom Attributes</label>
            {customMappings.map((mapping, index) => (
              <div key={index} className="flex gap-2">
                <input
                  type="text"
                  value={mapping.key}
                  onChange={(e) => updateCustomMapping(index, 'key', e.target.value)}
                  placeholder="User field"
                  className="flex-1 px-3 py-2 border rounded-md"
                />
                <input
                  type="text"
                  value={mapping.value}
                  onChange={(e) => updateCustomMapping(index, 'value', e.target.value)}
                  placeholder="SAML attribute"
                  className="flex-1 px-3 py-2 border rounded-md"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => removeCustomMapping(index)}
                  className="text-red-600 hover:text-red-700"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </Button>
              </div>
            ))}
          </div>
        )}

        <Button type="button" variant="outline" onClick={addCustomMapping} size="sm">
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Custom Mapping
        </Button>
      </div>

      {/* Advanced Settings */}
      <div className="space-y-4 p-4 border rounded-lg">
        <h4 className="font-semibold">Advanced Settings</h4>

        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <input
              id="signRequests"
              type="checkbox"
              checked={signRequests}
              onChange={(e) => setSignRequests(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="signRequests" className="text-sm font-medium cursor-pointer">
              Sign SAML Requests
            </label>
          </div>

          <div className="flex items-center gap-2">
            <input
              id="wantAssertionsSigned"
              type="checkbox"
              checked={wantAssertionsSigned}
              onChange={(e) => setWantAssertionsSigned(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="wantAssertionsSigned" className="text-sm font-medium cursor-pointer">
              Require Signed Assertions
            </label>
          </div>

          <div className="space-y-2">
            <label htmlFor="nameIdFormat" className="block text-sm font-medium">
              NameID Format
            </label>
            <select
              id="nameIdFormat"
              value={nameIdFormat}
              onChange={(e) => setNameIdFormat(e.target.value)}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">Email Address</option>
              <option value="urn:oasis:names:tc:SAML:2.0:nameid-format:persistent">Persistent</option>
              <option value="urn:oasis:names:tc:SAML:2.0:nameid-format:transient">Transient</option>
              <option value="urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified">Unspecified</option>
            </select>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <Button type="submit" disabled={isSubmitting} className="flex-1">
          {isSubmitting ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Saving...
            </>
          ) : (
            'Save SAML Configuration'
          )}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
