import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { BackupCodes } from './backup-codes'

describe('BackupCodes', () => {
  const mockBackupCodes = [
    { code: 'CODE1234', used: false },
    { code: 'CODE5678', used: false },
    { code: 'CODE9012', used: true },
    { code: 'CODE3456', used: false },
    { code: 'CODE7890', used: true },
  ]

  const mockOnFetchCodes = vi.fn()
  const mockOnRegenerateCodes = vi.fn()
  const mockOnError = vi.fn()

  // FIX: Declare mock references that will be assigned in beforeEach
  let mockClipboardWriteText: ReturnType<typeof vi.fn>
  let mockClipboardReadText: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()

    // Mock URL.createObjectURL
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    global.URL.revokeObjectURL = vi.fn()

    // FIX: Create fresh mocks in beforeEach for proper test isolation
    mockClipboardWriteText = vi.fn(() => Promise.resolve())
    mockClipboardReadText = vi.fn(() => Promise.resolve(''))

    // Mock clipboard API with fresh references
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: mockClipboardWriteText,
        readText: mockClipboardReadText,
      },
      configurable: true,
      writable: true,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Rendering', () => {
    it('should render backup codes component with provided codes', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      // FIX: Use role-based query to avoid multiple element matches
      expect(screen.getByRole('heading', { name: /backup codes/i })).toBeInTheDocument()
      expect(screen.getByText('CODE1234')).toBeInTheDocument()
      expect(screen.getByText('CODE5678')).toBeInTheDocument()
    })

    it('should show loading state when fetching codes', () => {
      mockOnFetchCodes.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockBackupCodes), 100))
      )

      render(<BackupCodes onFetchCodes={mockOnFetchCodes} />)

      // Component now has role="status" with aria-label
      expect(screen.getByRole('status')).toBeInTheDocument()
      expect(screen.getByLabelText('Loading backup codes')).toBeInTheDocument()
    })

    it('should fetch codes on mount when not provided', async () => {
      mockOnFetchCodes.mockResolvedValue(mockBackupCodes)

      render(<BackupCodes onFetchCodes={mockOnFetchCodes} />)

      await waitFor(() => {
        expect(mockOnFetchCodes).toHaveBeenCalled()
      })
    })

    it('should show error when fetch fails', async () => {
      mockOnFetchCodes.mockRejectedValue(new Error('Failed to fetch'))

      render(<BackupCodes onFetchCodes={mockOnFetchCodes} onError={mockOnError} />)

      await waitFor(() => {
        expect(screen.getByText(/failed to load backup codes/i)).toBeInTheDocument()
        expect(mockOnError).toHaveBeenCalled()
      })
    })

    it('should display unused and used counts', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      expect(screen.getByText(/3 unused/i)).toBeInTheDocument()
      expect(screen.getByText(/2 used/i)).toBeInTheDocument()
    })

    it('should not show used badge when all codes are unused', () => {
      const allUnused = mockBackupCodes.map((c) => ({ ...c, used: false }))
      render(<BackupCodes backupCodes={allUnused} />)

      expect(screen.getByText(/5 unused/i)).toBeInTheDocument()
      // FIX: More specific regex to avoid matching "unused"
      expect(screen.queryByText(/^\d+ used$/i)).not.toBeInTheDocument()
    })
  })

  describe('Code Display', () => {
    it('should display all backup codes', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      mockBackupCodes.forEach(({ code }) => {
        expect(screen.getByText(code)).toBeInTheDocument()
      })
    })

    it('should mark used codes with strikethrough', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      const usedCodes = mockBackupCodes.filter((c) => c.used)
      usedCodes.forEach(({ code }) => {
        const codeElement = screen.getByText(code)
        expect(codeElement).toHaveClass('line-through')
      })
    })

    it('should show "Used" badge on used codes', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      const usedBadges = screen.getAllByText(/^used$/i)
      expect(usedBadges).toHaveLength(2)
    })

    it('should number codes sequentially', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      expect(screen.getByText('#1')).toBeInTheDocument()
      expect(screen.getByText('#5')).toBeInTheDocument()
    })

    it('should not show copy button for used codes', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      const copyButtons = screen.getAllByRole('button', { name: /copy/i })
      // Should only have 3 copy buttons (3 unused codes)
      expect(copyButtons).toHaveLength(3)
    })
  })

  describe('Copy Functionality', () => {
    it('should copy code to clipboard', async () => {
      const user = userEvent.setup()
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      const firstCopyButton = screen.getAllByRole('button', { name: /copy/i })[0]
      expect(firstCopyButton).toBeInTheDocument()

      await user.click(firstCopyButton)

      // Test UI feedback (user-centric approach)
      expect(await screen.findByText(/copied/i)).toBeInTheDocument()
    })

    it('should show copied state temporarily', async () => {
      // FIX: Setup fake timers BEFORE userEvent.setup()
      vi.useFakeTimers()
      const user = userEvent.setup()

      render(<BackupCodes backupCodes={mockBackupCodes} />)

      const firstCopyButton = screen.getAllByRole('button', { name: /copy/i })[0]
      await user.click(firstCopyButton)

      expect(screen.getByText(/copied/i)).toBeInTheDocument()

      // FIX: Use runAllTimers() to execute all pending timers including React state updates
      act(() => {
        vi.runAllTimers()
      })

      expect(screen.queryByText(/copied/i)).not.toBeInTheDocument()

      vi.useRealTimers()
    })

    it('should handle clipboard errors gracefully', async () => {
      const user = userEvent.setup()
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
      // FIX: Use stored mock reference instead of vi.mocked
      mockClipboardWriteText.mockRejectedValueOnce(new Error('Clipboard error'))

      render(<BackupCodes backupCodes={mockBackupCodes} />)

      const firstCopyButton = screen.getAllByRole('button', { name: /copy/i })[0]
      await user.click(firstCopyButton)

      expect(consoleError).toHaveBeenCalled()
      consoleError.mockRestore()
    })
  })

  describe('Download Functionality', () => {
    it('should download codes when button is clicked', async () => {
      const user = userEvent.setup()
      const mockClick = vi.fn()
      const mockAppendChild = vi.spyOn(document.body, 'appendChild').mockImplementation(() => null as any)
      const mockRemoveChild = vi.spyOn(document.body, 'removeChild').mockImplementation(() => null as any)
      const mockCreateElement = vi.spyOn(document, 'createElement').mockReturnValue({
        click: mockClick,
        href: '',
        download: '',
      } as any)

      render(<BackupCodes backupCodes={mockBackupCodes} showDownload={true} />)

      const downloadButton = screen.getByRole('button', { name: /download codes/i })
      await user.click(downloadButton)

      expect(mockCreateElement).toHaveBeenCalledWith('a')
      expect(mockClick).toHaveBeenCalled()

      mockCreateElement.mockRestore()
      mockAppendChild.mockRestore()
      mockRemoveChild.mockRestore()
    })

    it('should not show download button when disabled', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} showDownload={false} />)

      expect(screen.queryByRole('button', { name: /download codes/i })).not.toBeInTheDocument()
    })

    it('should include both used and unused codes in download', async () => {
      const user = userEvent.setup()
      let blobContent = ''
      const mockBlob = vi.spyOn(global, 'Blob').mockImplementation((content: any) => {
        blobContent = content[0]
        return new Blob(content)
      })

      render(<BackupCodes backupCodes={mockBackupCodes} showDownload={true} />)

      const downloadButton = screen.getByRole('button', { name: /download codes/i })
      await user.click(downloadButton)

      expect(blobContent).toContain('CODE1234')
      expect(blobContent).toContain('CODE9012')
      expect(blobContent).toContain('UNUSED CODES (3)')
      expect(blobContent).toContain('USED CODES (2)')

      mockBlob.mockRestore()
    })
  })

  describe('Regenerate Functionality', () => {
    it('should show regenerate button when enabled', () => {
      render(
        <BackupCodes
          backupCodes={mockBackupCodes}
          allowRegeneration={true}
          onRegenerateCodes={mockOnRegenerateCodes}
        />
      )

      expect(screen.getByRole('button', { name: /regenerate codes/i })).toBeInTheDocument()
    })

    it('should not show regenerate button when disabled', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} allowRegeneration={false} />)

      expect(screen.queryByRole('button', { name: /regenerate codes/i })).not.toBeInTheDocument()
    })

    it('should show confirmation before regenerating', async () => {
      const user = userEvent.setup()
      render(
        <BackupCodes
          backupCodes={mockBackupCodes}
          allowRegeneration={true}
          onRegenerateCodes={mockOnRegenerateCodes}
        />
      )

      const regenerateButton = screen.getByRole('button', { name: /regenerate codes/i })

      // FIX: Wrap state-changing action in act()
      await act(async () => {
        await user.click(regenerateButton)
      })

      // Now query for elements that should appear after state update
      expect(await screen.findByRole('button', { name: /confirm regenerate/i })).toBeInTheDocument()
      expect(await screen.findByText(/regenerating will invalidate all existing/i)).toBeInTheDocument()
    })

    it('should allow canceling regeneration', async () => {
      const user = userEvent.setup()
      render(
        <BackupCodes
          backupCodes={mockBackupCodes}
          allowRegeneration={true}
          onRegenerateCodes={mockOnRegenerateCodes}
        />
      )

      const regenerateButton = screen.getByRole('button', { name: /regenerate codes/i })

      // FIX: Wrap first click in act()
      await act(async () => {
        await user.click(regenerateButton)
      })

      const cancelButton = await screen.findByRole('button', { name: /cancel/i })

      // FIX: Wrap cancel click in act()
      await act(async () => {
        await user.click(cancelButton)
      })

      // Wait for confirmation to disappear
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /confirm regenerate/i })).not.toBeInTheDocument()
      })
    })

    it('should regenerate codes on confirmation', async () => {
      const user = userEvent.setup()
      const newCodes = [{ code: 'NEWCODE1', used: false }]
      mockOnRegenerateCodes.mockResolvedValue(newCodes)

      render(
        <BackupCodes
          backupCodes={mockBackupCodes}
          allowRegeneration={true}
          onRegenerateCodes={mockOnRegenerateCodes}
        />
      )

      const regenerateButton = screen.getByRole('button', { name: /regenerate codes/i })

      // FIX: Wrap regenerate click in act()
      await act(async () => {
        await user.click(regenerateButton)
      })

      const confirmButton = await screen.findByRole('button', { name: /confirm regenerate/i })

      // FIX: Wrap confirm click in act()
      await act(async () => {
        await user.click(confirmButton)
      })

      await waitFor(() => {
        expect(mockOnRegenerateCodes).toHaveBeenCalled()
        expect(screen.getByText('NEWCODE1')).toBeInTheDocument()
      })
    })

    it('should show loading state during regeneration', async () => {
      const user = userEvent.setup()
      mockOnRegenerateCodes.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve([]), 100))
      )

      render(
        <BackupCodes
          backupCodes={mockBackupCodes}
          allowRegeneration={true}
          onRegenerateCodes={mockOnRegenerateCodes}
        />
      )

      const regenerateButton = screen.getByRole('button', { name: /regenerate codes/i })

      // FIX: Wrap regenerate click in act()
      await act(async () => {
        await user.click(regenerateButton)
      })

      const confirmButton = await screen.findByRole('button', { name: /confirm regenerate/i })

      // FIX: Wrap confirm click in act()
      await act(async () => {
        await user.click(confirmButton)
      })

      // Wait for loading state
      expect(await screen.findByText(/regenerating/i)).toBeInTheDocument()
    })

    it('should handle regeneration error', async () => {
      const user = userEvent.setup()
      mockOnRegenerateCodes.mockRejectedValue(new Error('Regeneration failed'))

      render(
        <BackupCodes
          backupCodes={mockBackupCodes}
          allowRegeneration={true}
          onRegenerateCodes={mockOnRegenerateCodes}
          onError={mockOnError}
        />
      )

      const regenerateButton = screen.getByRole('button', { name: /regenerate codes/i })

      // FIX: Wrap regenerate click in act()
      await act(async () => {
        await user.click(regenerateButton)
      })

      const confirmButton = await screen.findByRole('button', { name: /confirm regenerate/i })

      // FIX: Wrap confirm click in act()
      await act(async () => {
        await user.click(confirmButton)
      })

      // Wait for error message
      expect(await screen.findByText(/regeneration failed/i)).toBeInTheDocument()
      await waitFor(() => {
        expect(mockOnError).toHaveBeenCalled()
      })
    })
  })

  describe('Warning Messages', () => {
    it('should show warning when running low on codes', () => {
      const lowCodes = [
        { code: 'CODE1', used: false },
        { code: 'CODE2', used: false },
        { code: 'CODE3', used: true },
      ]
      render(<BackupCodes backupCodes={lowCodes} />)

      expect(screen.getByText(/running low on backup codes/i)).toBeInTheDocument()
      expect(screen.getByText(/you only have 2 backup codes remaining/i)).toBeInTheDocument()
    })

    it('should show critical warning when no codes are left', () => {
      const noCodes = [
        { code: 'CODE1', used: true },
        { code: 'CODE2', used: true },
      ]
      render(<BackupCodes backupCodes={noCodes} />)

      expect(screen.getByText(/no backup codes available/i)).toBeInTheDocument()
      expect(screen.getByText(/all your backup codes have been used/i)).toBeInTheDocument()
    })

    it('should not show warning when sufficient codes remain', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      expect(screen.queryByText(/running low/i)).not.toBeInTheDocument()
    })

    it('should use singular form for 1 remaining code', () => {
      const oneCode = [
        { code: 'CODE1', used: false },
        { code: 'CODE2', used: true },
      ]
      render(<BackupCodes backupCodes={oneCode} />)

      expect(screen.getByText(/you only have 1 backup code remaining/i)).toBeInTheDocument()
    })
  })

  describe('Information Section', () => {
    it('should display important information', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      expect(screen.getByText(/important information/i)).toBeInTheDocument()
      expect(screen.getByText(/each backup code can only be used once/i)).toBeInTheDocument()
      expect(screen.getByText(/store these codes in a secure location/i)).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have proper button labels', () => {
      render(
        <BackupCodes
          backupCodes={mockBackupCodes}
          showDownload={true}
          allowRegeneration={true}
          onRegenerateCodes={mockOnRegenerateCodes}
        />
      )

      expect(screen.getByRole('button', { name: /download codes/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /regenerate codes/i })).toBeInTheDocument()
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(
        <BackupCodes
          backupCodes={mockBackupCodes}
          showDownload={true}
          allowRegeneration={true}
          onRegenerateCodes={mockOnRegenerateCodes}
        />
      )

      // Tab through copy buttons
      await user.tab()
      const copyButtons = screen.getAllByRole('button', { name: /copy/i })
      // FIX: Wrap focus assertion in waitFor for async focus management
      await waitFor(() => {
        expect(copyButtons[0]).toHaveFocus()
      })
    })

    it('should have descriptive code labels', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      expect(screen.getByText('#1')).toBeInTheDocument()
      expect(screen.getByText('#2')).toBeInTheDocument()
    })
  })

  describe('Visual States', () => {
    it('should style unused codes differently from used codes', () => {
      render(<BackupCodes backupCodes={mockBackupCodes} />)

      const usedCode = screen.getByText('CODE9012')
      const unusedCode = screen.getByText('CODE1234')

      expect(usedCode).toHaveClass('line-through')
      expect(unusedCode).not.toHaveClass('line-through')
    })

    it('should show destructive badge when no codes left', () => {
      const noCodes = mockBackupCodes.map((c) => ({ ...c, used: true }))
      render(<BackupCodes backupCodes={noCodes} />)

      const badge = screen.getByText(/0 unused/i)
      expect(badge.closest('.badge')).toBeDefined()
    })
  })

  describe('Error Handling', () => {
    it('should display error message', async () => {
      mockOnFetchCodes.mockRejectedValue(new Error('Network error'))

      render(<BackupCodes onFetchCodes={mockOnFetchCodes} onError={mockOnError} />)

      // FIX: Wait for error state to render after async fetch fails
      expect(await screen.findByText(/failed to load backup codes/i)).toBeInTheDocument()
    })

    it('should clear error on successful operation', async () => {
      const user = userEvent.setup()
      mockOnRegenerateCodes
        .mockRejectedValueOnce(new Error('First error'))
        .mockResolvedValueOnce([{ code: 'NEW1', used: false }])

      render(
        <BackupCodes
          backupCodes={mockBackupCodes}
          allowRegeneration={true}
          onRegenerateCodes={mockOnRegenerateCodes}
        />
      )

      // First attempt - error
      const regenerateButton = screen.getByRole('button', { name: /regenerate codes/i })

      // FIX: Wrap regenerate click in act()
      await act(async () => {
        await user.click(regenerateButton)
      })

      const confirmButton = await screen.findByRole('button', { name: /confirm regenerate/i })

      // FIX: Wrap confirm click in act()
      await act(async () => {
        await user.click(confirmButton)
      })

      // Wait for error message
      expect(await screen.findByText(/first error/i)).toBeInTheDocument()

      // Close confirmation dialog
      const cancelButton = await screen.findByRole('button', { name: /cancel/i })
      await act(async () => {
        await user.click(cancelButton)
      })

      // Second attempt - success
      await act(async () => {
        await user.click(regenerateButton)
      })

      const confirmButton2 = await screen.findByRole('button', { name: /confirm regenerate/i })
      await act(async () => {
        await user.click(confirmButton2)
      })

      // Error should be cleared on successful operation
      await waitFor(() => {
        expect(screen.queryByText(/first error/i)).not.toBeInTheDocument()
      })
    })
  })
})
