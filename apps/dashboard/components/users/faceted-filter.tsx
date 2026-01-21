'use client'

import { Filter } from 'lucide-react'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Checkbox } from '@janua/ui'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@janua/ui'

interface FacetedFilterProps {
  title: string
  options: { label: string; value: string }[]
  selectedValues: string[]
  onSelectionChange: (values: string[]) => void
}

export function FacetedFilter({
  title,
  options,
  selectedValues,
  onSelectionChange,
}: FacetedFilterProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 border-dashed">
          <Filter className="mr-2 size-4" />
          {title}
          {selectedValues.length > 0 && (
            <Badge variant="secondary" className="ml-2">
              {selectedValues.length}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[200px]">
        <DropdownMenuLabel>{title}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {options.map((option) => {
          const isSelected = selectedValues.includes(option.value)
          return (
            <DropdownMenuItem
              key={option.value}
              onClick={() => {
                if (isSelected) {
                  onSelectionChange(selectedValues.filter((v) => v !== option.value))
                } else {
                  onSelectionChange([...selectedValues, option.value])
                }
              }}
            >
              <Checkbox
                checked={isSelected}
                className="mr-2"
              />
              {option.label}
            </DropdownMenuItem>
          )
        })}
        {selectedValues.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => onSelectionChange([])}>
              Clear filters
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
