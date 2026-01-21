'use client'

interface ToggleSettingProps {
  label: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}

export function ToggleSetting({ label, description, checked, onChange }: ToggleSettingProps) {
  return (
    <div className="flex items-start justify-between space-x-4 rounded-lg border p-4">
      <div className="flex-1">
        <label className="font-medium">{label}</label>
        <p className="text-muted-foreground mt-1 text-sm">{description}</p>
      </div>
      <label className="relative inline-flex cursor-pointer items-center">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="peer sr-only"
        />
        <div className="bg-muted after:border-border after:bg-background peer-checked:bg-primary peer-checked:after:border-background peer h-6 w-11 rounded-full after:absolute after:left-[2px] after:top-[2px] after:size-5 after:rounded-full after:border after:transition-all after:content-[''] peer-checked:after:translate-x-full"></div>
      </label>
    </div>
  )
}
