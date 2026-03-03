# @janua/ui

> **Shared design system and component library** for the Janua platform

**Version:** 0.1.0 · **Stack:** React + Radix UI + Tailwind CSS · **Status:** Production Ready

## 📋 Overview

@janua/ui is the unified design system powering all Janua applications. Built on Radix UI primitives with Tailwind CSS styling, it provides accessible, customizable, and consistent components across the platform.

## 🚀 Quick Start

### Installation

```bash
# Install in your app
yarn add @janua/ui

# Peer dependencies
yarn add react react-dom tailwindcss
```

### Setup

1. **Import styles in your app:**

```tsx
// app/layout.tsx or _app.tsx
import '@janua/ui/styles.css';
```

2. **Configure Tailwind to include UI package:**

```javascript
// tailwind.config.js
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './node_modules/@janua/ui/**/*.{js,ts,jsx,tsx}',
  ],
  presets: [require('@janua/ui/tailwind.preset')],
};
```

3. **Use components:**

```tsx
import { Button, Card, Input } from '@janua/ui';

export function MyComponent() {
  return (
    <Card>
      <Card.Header>Welcome</Card.Header>
      <Card.Content>
        <Input placeholder="Enter your email" />
        <Button>Get Started</Button>
      </Card.Content>
    </Card>
  );
}
```

## 🏗️ Architecture

### Package Structure

```
packages/ui/
├── src/
│   ├── components/          # React components
│   │   ├── auth/           # Auth components (SignIn, SignUp, MFA, UserButton, SSO, etc.)
│   │   ├── enterprise/     # Enterprise components (invitations, SSO config, SAML)
│   │   ├── compliance/     # Compliance components
│   │   ├── scim/           # SCIM provisioning components
│   │   ├── rbac/           # Role-based access control components
│   │   ├── button.tsx      # Button component
│   │   ├── card.tsx        # Card component
│   │   ├── dialog.tsx      # Dialog/Modal
│   │   ├── input.tsx       # Input fields
│   │   ├── table.tsx       # Data tables
│   │   └── ...             # More components
│   ├── providers/           # Theme and Auth context providers
│   ├── tokens/              # Design token presets
│   ├── config/              # Auth config types and defaults
│   ├── themes/              # Theme system (dual-skin)
│   ├── stores/              # State management
│   ├── lib/                 # Utility functions
│   └── index.ts             # Main export
├── tailwind.preset.js       # Tailwind preset
├── tsconfig.json            # TypeScript config
└── package.json             # Package config
```

### Design Principles

1. **Accessibility First**: All components meet WCAG 2.1 AA standards
2. **Composability**: Components work together seamlessly
3. **Customization**: Flexible theming and styling
4. **Performance**: Optimized bundle size and rendering
5. **Developer Experience**: Intuitive API with TypeScript support

## 🧩 Components

### Core Components

#### Button
```tsx
import { Button } from '@janua/ui';

// Variants
<Button variant="primary">Primary</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="destructive">Delete</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="link">Link</Button>

// Sizes
<Button size="sm">Small</Button>
<Button size="md">Medium</Button>
<Button size="lg">Large</Button>

// States
<Button disabled>Disabled</Button>
<Button loading>Loading...</Button>
```

#### Input
```tsx
import { Input } from '@janua/ui';

<Input 
  type="email"
  placeholder="Enter email"
  error="Invalid email"
  icon={<MailIcon />}
/>
```

#### Card
```tsx
import { Card } from '@janua/ui';

<Card>
  <Card.Header>
    <Card.Title>Card Title</Card.Title>
    <Card.Description>Card description</Card.Description>
  </Card.Header>
  <Card.Content>
    Content goes here
  </Card.Content>
  <Card.Footer>
    <Button>Action</Button>
  </Card.Footer>
</Card>
```

#### Dialog
```tsx
import { Dialog } from '@janua/ui';

<Dialog>
  <Dialog.Trigger>
    <Button>Open Dialog</Button>
  </Dialog.Trigger>
  <Dialog.Content>
    <Dialog.Header>
      <Dialog.Title>Dialog Title</Dialog.Title>
      <Dialog.Description>Dialog description</Dialog.Description>
    </Dialog.Header>
    <Dialog.Body>
      Dialog content
    </Dialog.Body>
    <Dialog.Footer>
      <Dialog.Close>
        <Button variant="ghost">Cancel</Button>
      </Dialog.Close>
      <Button>Confirm</Button>
    </Dialog.Footer>
  </Dialog.Content>
</Dialog>
```

### Form Components

#### Form
```tsx
import { Form, FormField, FormLabel, FormError } from '@janua/ui';

<Form onSubmit={handleSubmit}>
  <FormField name="email">
    <FormLabel>Email</FormLabel>
    <Input type="email" />
    <FormError />
  </FormField>
  
  <FormField name="password">
    <FormLabel>Password</FormLabel>
    <Input type="password" />
    <FormError />
  </FormField>
  
  <Button type="submit">Submit</Button>
</Form>
```

#### Select
```tsx
import { Select } from '@janua/ui';

<Select>
  <Select.Trigger>
    <Select.Value placeholder="Select option" />
  </Select.Trigger>
  <Select.Content>
    <Select.Item value="1">Option 1</Select.Item>
    <Select.Item value="2">Option 2</Select.Item>
    <Select.Item value="3">Option 3</Select.Item>
  </Select.Content>
</Select>
```

### Data Display

#### Table
```tsx
import { Table } from '@janua/ui';

<Table>
  <Table.Header>
    <Table.Row>
      <Table.Head>Name</Table.Head>
      <Table.Head>Email</Table.Head>
      <Table.Head>Role</Table.Head>
    </Table.Row>
  </Table.Header>
  <Table.Body>
    <Table.Row>
      <Table.Cell>John Doe</Table.Cell>
      <Table.Cell>john@example.com</Table.Cell>
      <Table.Cell>Admin</Table.Cell>
    </Table.Row>
  </Table.Body>
</Table>
```

#### Badge
```tsx
import { Badge } from '@janua/ui';

<Badge variant="success">Active</Badge>
<Badge variant="warning">Pending</Badge>
<Badge variant="error">Failed</Badge>
<Badge variant="info">Info</Badge>
```

### Navigation

#### Tabs
```tsx
import { Tabs } from '@janua/ui';

<Tabs defaultValue="tab1">
  <Tabs.List>
    <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
    <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
    <Tabs.Trigger value="tab3">Tab 3</Tabs.Trigger>
  </Tabs.List>
  <Tabs.Content value="tab1">Content 1</Tabs.Content>
  <Tabs.Content value="tab2">Content 2</Tabs.Content>
  <Tabs.Content value="tab3">Content 3</Tabs.Content>
</Tabs>
```

#### Dropdown Menu
```tsx
import { DropdownMenu } from '@janua/ui';

<DropdownMenu>
  <DropdownMenu.Trigger>
    <Button>Options</Button>
  </DropdownMenu.Trigger>
  <DropdownMenu.Content>
    <DropdownMenu.Item>Edit</DropdownMenu.Item>
    <DropdownMenu.Item>Duplicate</DropdownMenu.Item>
    <DropdownMenu.Separator />
    <DropdownMenu.Item variant="destructive">Delete</DropdownMenu.Item>
  </DropdownMenu.Content>
</DropdownMenu>
```

### Feedback

#### Toast
```tsx
import { toast } from '@janua/ui';

// Success toast
toast.success('Operation completed successfully');

// Error toast
toast.error('Something went wrong');

// Info toast
toast.info('New update available');

// Custom toast
toast.custom(<CustomToastContent />);
```

#### Alert
```tsx
import { Alert } from '@janua/ui';

<Alert variant="info">
  <Alert.Icon />
  <Alert.Title>Information</Alert.Title>
  <Alert.Description>
    This is an informational alert.
  </Alert.Description>
</Alert>
```

## Authentication Components

@janua/ui provides a complete set of auth UI components with feature parity with Clerk/Auth0/WorkOS.

### SignIn

```tsx
import { SignIn } from '@janua/ui';

// Basic usage
<SignIn
  socialProviders={{ google: true, github: true }}
  signUpUrl="/sign-up"
  afterSignIn={(user) => console.log('Signed in', user)}
/>

// Advanced: SSO detection, passkey, magic link, layout variants
<SignIn
  layout="modal"
  enableSSO={true}
  enablePasskey={true}
  enableMagicLink={true}
  enableJanuaSSO={true}
  onMFARequired={(session) => navigate('/mfa')}
  headerText="Welcome back"
  forgotPasswordUrl="/reset-password"
/>
```

### SignUp

```tsx
import { SignUp } from '@janua/ui';

<SignUp
  socialProviders={{ google: true, github: true }}
  signInUrl="/sign-in"
  requireEmailVerification={true}
  showPasswordStrength={true}
  termsUrl="/terms"
  privacyUrl="/privacy"
  layout="card"
/>
```

### MFAChallenge

PIN-style 6-digit input with auto-advance, paste support, and success animation.

```tsx
import { MFAChallenge } from '@janua/ui';

<MFAChallenge
  method="totp"
  userEmail="user@example.com"
  onVerify={async (code) => await verifyMFA(code)}
  showBackupCodeOption={true}
  onUseBackupCode={() => navigate('/backup-code')}
/>
```

### UserButton

```tsx
import { UserButton } from '@janua/ui';

<UserButton
  user={{ id: '1', email: 'user@example.com', firstName: 'John', lastName: 'Doe' }}
  onSignOut={() => signOut()}
  showOrganizations={true}
  activeOrganization="Acme Corp"
/>
```

### Config-Driven Auth (JanuaAuthProvider)

Drive all auth UI from a centralized config — fetched from API or passed statically.

```tsx
import { JanuaAuthProvider, SignIn } from '@janua/ui';

// Option A: Fetch config from API at runtime
<JanuaAuthProvider configUrl="https://api.janua.dev/api/v1/auth/ui-config?client_id=abc">
  <SignIn />
</JanuaAuthProvider>

// Option B: Static config
<JanuaAuthProvider config={{
  branding: { primaryColor: '#10b981', appName: 'My App' },
  authentication: {
    emailPassword: true,
    passkeys: true,
    socialProviders: { google: true, github: true },
  },
}}>
  <SignIn />
</JanuaAuthProvider>

// Option C: No provider (backward compatible)
<SignIn socialProviders={{ google: true }} />
```

## 🎨 Theming

### JanuaThemeProvider

```tsx
import { JanuaThemeProvider } from '@janua/ui';

// Use a preset theme
<JanuaThemeProvider preset="madfam">
  <App />
</JanuaThemeProvider>

// Custom accent color
<JanuaThemeProvider accentColor="#10b981">
  <App />
</JanuaThemeProvider>

// Granular color overrides
<JanuaThemeProvider theme={{ primary: '142 71% 45%', background: '0 0% 100%' }}>
  <App />
</JanuaThemeProvider>
```

### Presets

| Preset | Description |
|--------|-------------|
| `default` | Clean professional theme (shadcn defaults) |
| `madfam` | MADFAM ecosystem brand blue |
| `solarpunk` | Solarpunk theme from dual-skin system |

### Dark Mode

```tsx
<JanuaThemeProvider darkMode="auto">
  <App />
</JanuaThemeProvider>
```

Supports `'auto'` (system preference), `'light'`, and `'dark'`.

### CSS Custom Properties

The theme system injects CSS variables via inline styles:

```css
--janua-transition-fast: 150ms ease;
--janua-transition-base: 250ms ease;
--janua-shadow-card: 0 1px 3px rgba(0,0,0,0.1);
--janua-radius-card: 0.75rem;
```

### Animations

Built-in animations with `prefers-reduced-motion` support:

- `janua-fade-in` — Opacity fade
- `janua-slide-up` — Slide up with fade
- `janua-shake` — Error shake
- `janua-shimmer` — Loading shimmer
- `janua-checkmark` — Success checkmark

## 🔧 Customization

### Component Variants

```tsx
// Using class variance authority
import { cva } from 'class-variance-authority';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md font-medium',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-white hover:bg-primary-dark',
        secondary: 'bg-secondary text-white hover:bg-secondary-dark',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4',
        lg: 'h-12 px-6 text-lg',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);
```

### Extending Components

```tsx
// Extending existing components
import { Button as BaseButton } from '@janua/ui';

export const Button = ({ gradient, ...props }) => {
  return (
    <BaseButton
      className={gradient ? 'bg-gradient-to-r from-purple-500 to-pink-500' : ''}
      {...props}
    />
  );
};
```

## ♿ Accessibility

### Built-in Features

- **Keyboard Navigation**: Full keyboard support for all interactive components
- **Screen Reader Support**: Proper ARIA labels and descriptions
- **Focus Management**: Visible focus indicators and proper focus trapping
- **Color Contrast**: WCAG AA compliant color combinations
- **Reduced Motion**: Respects user's motion preferences

### Usage Example

```tsx
// Accessible form with proper labels
<Form>
  <FormField>
    <FormLabel htmlFor="email">Email Address</FormLabel>
    <Input 
      id="email"
      type="email"
      aria-describedby="email-error"
      aria-invalid={!!errors.email}
    />
    <FormError id="email-error">{errors.email}</FormError>
  </FormField>
</Form>
```

## 📦 Bundle Size

### Component Sizes

| Component | Size (gzipped) |
|-----------|---------------|
| Button | 2.1 KB |
| Input | 1.8 KB |
| Card | 1.2 KB |
| Dialog | 3.4 KB |
| Table | 2.8 KB |
| Select | 3.1 KB |
| **Total** | ~45 KB |

### Tree Shaking

```javascript
// Only import what you need
import { Button } from '@janua/ui/button';
import { Card } from '@janua/ui/card';

// Instead of
import * from '@janua/ui'; // Imports everything
```

## 🧪 Testing

### Component Testing

```tsx
// Testing with React Testing Library
import { render, screen } from '@testing-library/react';
import { Button } from '@janua/ui';

test('renders button with text', () => {
  render(<Button>Click me</Button>);
  expect(screen.getByText('Click me')).toBeInTheDocument();
});
```

### Visual Testing

```bash
# Run Storybook for visual testing
yarn storybook

# Run visual regression tests
yarn test:visual
```

## 📚 Documentation

### Storybook

```bash
# Start Storybook
yarn storybook

# Build Storybook
yarn build:storybook
```

View interactive documentation at [http://localhost:6006](http://localhost:6006)

### Component Props

All components are fully typed with TypeScript:

```tsx
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'destructive' | 'ghost' | 'link';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  // ... more props
}
```

## 🛠️ Development

### Setup Development Environment

```bash
# Clone the repo
git clone https://github.com/madfam-org/janua.git

# Navigate to UI package
cd packages/ui

# Install dependencies
yarn install

# Start development
yarn dev
```

### Building

```bash
# Build the package
yarn build

# Type checking
yarn typecheck

# Linting
yarn lint

# Format code
yarn format
```

## 🎯 Roadmap

### Current Sprint
- [ ] Add DatePicker component
- [ ] Implement Command palette
- [ ] Add Skeleton loaders
- [ ] Create Avatar component

### Next Quarter
- [ ] Charts and data visualization
- [ ] Advanced form validation
- [ ] Drag and drop support
- [ ] Animation presets

## 🤝 Contributing

See [UI Contributing Guide](../../docs/contributing/ui.md) for component development guidelines.

## 📄 License

Part of the Janua platform. See [LICENSE](../../LICENSE) in the root directory.