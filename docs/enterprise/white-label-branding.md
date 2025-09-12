# White-Label & Branding Guide

## Overview

Plinto provides comprehensive white-label capabilities allowing complete customization of the authentication experience to match your brand identity, including visual design, user experience flows, email communications, and domain configuration.

## Branding Configuration

### Core Brand Settings

```typescript
interface BrandConfiguration {
  // Organization Identity
  organization: {
    name: string;
    displayName: string;
    description?: string;
    website: string;
    supportEmail: string;
    supportUrl?: string;
  };
  
  // Visual Identity
  visual: {
    logo: {
      primary: AssetConfig;      // Main logo
      alternate?: AssetConfig;   // Alternative logo
      favicon: AssetConfig;      // Browser favicon
      emailHeader?: AssetConfig; // Email header logo
    };
    
    colors: ColorPalette;
    typography: TypographyConfig;
    spacing: SpacingConfig;
    
    // Dark mode support
    darkMode?: {
      enabled: boolean;
      colors: ColorPalette;
      logos?: {
        primary: AssetConfig;
        alternate?: AssetConfig;
      };
    };
  };
  
  // UI Components
  components: {
    buttons: ButtonStyles;
    forms: FormStyles;
    cards: CardStyles;
    alerts: AlertStyles;
    
    // Custom component overrides
    overrides?: ComponentOverrides;
  };
  
  // Layout Configuration
  layout: {
    type: 'centered' | 'split' | 'fullscreen' | 'custom';
    background?: BackgroundConfig;
    containerWidth?: string;
    padding?: SpacingValues;
  };
}

interface ColorPalette {
  // Primary colors
  primary: string;
  primaryLight?: string;
  primaryDark?: string;
  
  // Secondary colors
  secondary?: string;
  secondaryLight?: string;
  secondaryDark?: string;
  
  // Semantic colors
  success: string;
  warning: string;
  error: string;
  info: string;
  
  // Neutral colors
  background: string;
  surface: string;
  text: string;
  textSecondary?: string;
  border: string;
  
  // Interactive states
  hover?: string;
  focus?: string;
  disabled?: string;
}
```

### Brand Implementation

```typescript
class BrandingService {
  async applyBranding(config: BrandConfiguration): Promise<BrandedExperience> {
    // Validate configuration
    await this.validateConfig(config);
    
    // Generate CSS variables
    const cssVariables = this.generateCSSVariables(config);
    
    // Create theme package
    const theme = await this.createTheme({
      variables: cssVariables,
      components: await this.compileComponents(config.components),
      layouts: await this.compileLayouts(config.layout),
      
      // Responsive design
      breakpoints: config.breakpoints || this.defaultBreakpoints,
      
      // Accessibility
      a11y: {
        highContrast: await this.generateHighContrast(config),
        focusIndicators: config.accessibility?.focusIndicators || 'default',
        reducedMotion: config.accessibility?.reducedMotion || false
      }
    });
    
    // Deploy theme
    const deployment = await this.deployTheme(theme);
    
    return {
      themeId: deployment.id,
      previewUrl: deployment.previewUrl,
      productionUrl: deployment.productionUrl,
      
      // Asset URLs
      assets: {
        stylesheet: deployment.stylesheetUrl,
        javascript: deployment.scriptUrl,
        fonts: deployment.fontUrls
      }
    };
  }
  
  private generateCSSVariables(config: BrandConfiguration): string {
    return `
      :root {
        /* Colors */
        --color-primary: ${config.visual.colors.primary};
        --color-primary-light: ${config.visual.colors.primaryLight};
        --color-primary-dark: ${config.visual.colors.primaryDark};
        --color-secondary: ${config.visual.colors.secondary};
        
        /* Semantic colors */
        --color-success: ${config.visual.colors.success};
        --color-warning: ${config.visual.colors.warning};
        --color-error: ${config.visual.colors.error};
        --color-info: ${config.visual.colors.info};
        
        /* Neutrals */
        --color-background: ${config.visual.colors.background};
        --color-surface: ${config.visual.colors.surface};
        --color-text: ${config.visual.colors.text};
        --color-text-secondary: ${config.visual.colors.textSecondary};
        --color-border: ${config.visual.colors.border};
        
        /* Typography */
        --font-family-base: ${config.visual.typography.fontFamily};
        --font-size-base: ${config.visual.typography.fontSize};
        --line-height-base: ${config.visual.typography.lineHeight};
        
        /* Spacing */
        --spacing-xs: ${config.visual.spacing.xs};
        --spacing-sm: ${config.visual.spacing.sm};
        --spacing-md: ${config.visual.spacing.md};
        --spacing-lg: ${config.visual.spacing.lg};
        --spacing-xl: ${config.visual.spacing.xl};
        
        /* Border radius */
        --radius-sm: ${config.components.borderRadius?.sm || '4px'};
        --radius-md: ${config.components.borderRadius?.md || '8px'};
        --radius-lg: ${config.components.borderRadius?.lg || '12px'};
        
        /* Shadows */
        --shadow-sm: ${config.components.shadows?.sm || '0 1px 2px rgba(0,0,0,0.05)'};
        --shadow-md: ${config.components.shadows?.md || '0 4px 6px rgba(0,0,0,0.1)'};
        --shadow-lg: ${config.components.shadows?.lg || '0 10px 15px rgba(0,0,0,0.1)'};
      }
      
      /* Dark mode variables */
      @media (prefers-color-scheme: dark) {
        :root[data-theme="auto"] {
          --color-background: ${config.visual.darkMode?.colors.background};
          --color-surface: ${config.visual.darkMode?.colors.surface};
          --color-text: ${config.visual.darkMode?.colors.text};
          /* ... other dark mode variables */
        }
      }
      
      :root[data-theme="dark"] {
        /* Explicit dark mode */
        --color-background: ${config.visual.darkMode?.colors.background};
        /* ... */
      }
    `;
  }
}
```

## UI Component Customization

### Login/Signup Components

```tsx
// Customizable Auth Components
import { AuthUI } from '@plinto/ui';

export function CustomLoginPage({ branding }: { branding: BrandConfiguration }) {
  return (
    <AuthUI.Container theme={branding}>
      {/* Custom header */}
      <AuthUI.Header>
        <img src={branding.visual.logo.primary.url} alt={branding.organization.name} />
        {branding.visual.tagline && (
          <p className="tagline">{branding.visual.tagline}</p>
        )}
      </AuthUI.Header>
      
      {/* Login form with custom styling */}
      <AuthUI.LoginForm
        fields={{
          email: {
            label: branding.copy?.emailLabel || 'Email',
            placeholder: branding.copy?.emailPlaceholder || 'Enter your email',
            icon: branding.icons?.email
          },
          password: {
            label: branding.copy?.passwordLabel || 'Password',
            placeholder: branding.copy?.passwordPlaceholder || 'Enter your password',
            icon: branding.icons?.password
          }
        }}
        
        buttons={{
          submit: {
            text: branding.copy?.loginButton || 'Sign In',
            style: branding.components.buttons.primary
          },
          forgotPassword: {
            text: branding.copy?.forgotPassword || 'Forgot Password?',
            style: branding.components.buttons.link
          }
        }}
        
        // Social login customization
        socialProviders={
          branding.socialLogin?.providers.map(provider => ({
            ...provider,
            button: {
              text: provider.customText || `Continue with ${provider.name}`,
              icon: provider.customIcon || provider.defaultIcon,
              style: provider.customStyle || branding.components.buttons.social
            }
          }))
        }
        
        // Custom validation messages
        validation={{
          required: branding.copy?.validation?.required || 'This field is required',
          invalidEmail: branding.copy?.validation?.email || 'Please enter a valid email',
          weakPassword: branding.copy?.validation?.password || 'Password is too weak'
        }}
      />
      
      {/* Custom footer */}
      <AuthUI.Footer>
        {branding.footer?.links?.map(link => (
          <a key={link.url} href={link.url} style={branding.components.links}>
            {link.text}
          </a>
        ))}
        {branding.footer?.copyright && (
          <p className="copyright">{branding.footer.copyright}</p>
        )}
      </AuthUI.Footer>
    </AuthUI.Container>
  );
}
```

### Widget Customization

```typescript
class WidgetCustomizer {
  async customizeWidget(
    widgetType: WidgetType,
    customization: WidgetCustomization
  ): Promise<CustomWidget> {
    const baseWidget = await this.getBaseWidget(widgetType);
    
    // Apply visual customization
    const styled = await this.applyStyles(baseWidget, {
      container: customization.containerStyle,
      header: customization.headerStyle,
      body: customization.bodyStyle,
      footer: customization.footerStyle,
      
      // Component-specific styles
      inputs: customization.inputStyles,
      buttons: customization.buttonStyles,
      links: customization.linkStyles,
      
      // State styles
      states: {
        hover: customization.hoverStyles,
        focus: customization.focusStyles,
        error: customization.errorStyles,
        success: customization.successStyles
      }
    });
    
    // Apply behavioral customization
    const configured = await this.applyBehavior(styled, {
      animations: customization.animations,
      transitions: customization.transitions,
      interactions: customization.interactions,
      
      // Validation behavior
      validation: {
        inline: customization.inlineValidation,
        async: customization.asyncValidation,
        debounce: customization.validationDebounce
      }
    });
    
    // Apply content customization
    const localized = await this.applyContent(configured, {
      text: customization.text,
      labels: customization.labels,
      placeholders: customization.placeholders,
      helpText: customization.helpText,
      errorMessages: customization.errorMessages
    });
    
    return localized;
  }
  
  async generateEmbedCode(
    widget: CustomWidget,
    options: EmbedOptions
  ): Promise<EmbedCode> {
    const config = {
      widgetId: widget.id,
      apiKey: options.apiKey,
      
      // Embedding options
      container: options.containerId,
      responsive: options.responsive !== false,
      
      // Initialization
      autoInit: options.autoInit !== false,
      
      // Callbacks
      onReady: options.onReady,
      onSuccess: options.onSuccess,
      onError: options.onError
    };
    
    return {
      // Script tag
      script: `
        <script src="https://cdn.plinto.dev/widget/v2/plinto-widget.min.js"></script>
        <script>
          PlintoWidget.init(${JSON.stringify(config)});
        </script>
      `,
      
      // NPM package
      npm: `
        import { PlintoWidget } from '@plinto/widget';
        
        const widget = new PlintoWidget(${JSON.stringify(config)});
        widget.mount('#${options.containerId}');
      `,
      
      // React component
      react: `
        import { PlintoAuthWidget } from '@plinto/react-widget';
        
        export function AuthWidget() {
          return (
            <PlintoAuthWidget
              widgetId="${widget.id}"
              apiKey="${options.apiKey}"
              onSuccess={handleSuccess}
              onError={handleError}
            />
          );
        }
      `
    };
  }
}
```

## Email Template Customization

### Email Branding System

```typescript
class EmailBrandingService {
  async customizeEmailTemplates(
    branding: EmailBranding
  ): Promise<EmailTemplateSet> {
    const templates = await this.getDefaultTemplates();
    
    const customized = await Promise.all(
      Object.entries(templates).map(async ([type, template]) => {
        const custom = await this.customizeTemplate(template, {
          // Header customization
          header: {
            logo: branding.logo,
            backgroundColor: branding.colors.header,
            padding: branding.spacing.header
          },
          
          // Body customization
          body: {
            fontFamily: branding.typography.fontFamily,
            fontSize: branding.typography.fontSize,
            lineHeight: branding.typography.lineHeight,
            textColor: branding.colors.text,
            backgroundColor: branding.colors.background,
            
            // Content wrapper
            contentWidth: branding.layout.contentWidth || '600px',
            contentPadding: branding.spacing.content
          },
          
          // Button customization
          buttons: {
            backgroundColor: branding.colors.primary,
            textColor: branding.colors.buttonText,
            borderRadius: branding.borderRadius.button,
            padding: branding.spacing.button,
            fontSize: branding.typography.buttonSize,
            fontWeight: branding.typography.buttonWeight
          },
          
          // Footer customization
          footer: {
            content: branding.footer.content,
            links: branding.footer.links,
            social: branding.footer.socialLinks,
            textColor: branding.colors.footerText,
            backgroundColor: branding.colors.footerBackground,
            fontSize: branding.typography.footerSize
          }
        });
        
        return [type, custom];
      })
    );
    
    return Object.fromEntries(customized);
  }
  
  async createEmailTemplate(
    type: EmailTemplateType,
    config: EmailTemplateConfig
  ): Promise<EmailTemplate> {
    // Build MJML template
    const mjml = `
      <mjml>
        <mj-head>
          <mj-font name="${config.fontFamily}" href="${config.fontUrl}" />
          <mj-attributes>
            <mj-all font-family="${config.fontFamily}" />
            <mj-button background-color="${config.buttonColor}" />
          </mj-attributes>
          <mj-style>
            .header { background-color: ${config.headerColor}; }
            .footer { background-color: ${config.footerColor}; }
          </mj-style>
        </mj-head>
        
        <mj-body background-color="${config.backgroundColor}">
          <!-- Header -->
          <mj-section css-class="header">
            <mj-column>
              <mj-image src="${config.logo}" width="200px" />
            </mj-column>
          </mj-section>
          
          <!-- Content -->
          <mj-section>
            <mj-column>
              <mj-text font-size="${config.fontSize}" color="${config.textColor}">
                {{content}}
              </mj-text>
              
              {{#if button}}
              <mj-button href="{{button.url}}" font-size="${config.buttonFontSize}">
                {{button.text}}
              </mj-button>
              {{/if}}
            </mj-column>
          </mj-section>
          
          <!-- Footer -->
          <mj-section css-class="footer">
            <mj-column>
              <mj-text font-size="${config.footerFontSize}" color="${config.footerTextColor}">
                {{footer}}
              </mj-text>
              
              <mj-social>
                {{#each socialLinks}}
                <mj-social-element href="{{url}}" icon-color="${config.socialIconColor}">
                  {{platform}}
                </mj-social-element>
                {{/each}}
              </mj-social>
            </mj-column>
          </mj-section>
        </mj-body>
      </mjml>
    `;
    
    // Compile to HTML
    const { html } = mjml2html(mjml);
    
    // Create text version
    const text = await this.generateTextVersion(config);
    
    return {
      id: generateId(),
      type,
      name: config.name,
      subject: config.subject,
      
      // Content
      html,
      text,
      
      // Metadata
      variables: this.extractVariables(html),
      preview: await this.generatePreview(html),
      
      // Testing
      testData: config.testData
    };
  }
}
```

### Dynamic Email Content

```typescript
class DynamicEmailService {
  async sendBrandedEmail(
    recipient: User,
    template: EmailTemplate,
    data: EmailData,
    branding: EmailBranding
  ): Promise<void> {
    // Personalize content
    const personalized = await this.personalize(template, {
      user: recipient,
      data,
      
      // Dynamic branding based on user's organization
      branding: await this.getBrandingForUser(recipient)
    });
    
    // Apply localization
    const localized = await this.localize(personalized, {
      locale: recipient.locale || 'en',
      timezone: recipient.timezone,
      
      // Date/time formatting
      dateFormat: this.getDateFormat(recipient.locale),
      timeFormat: this.getTimeFormat(recipient.locale)
    });
    
    // Add tracking
    const tracked = await this.addTracking(localized, {
      campaignId: data.campaignId,
      userId: recipient.id,
      
      // UTM parameters
      utm: {
        source: 'email',
        medium: template.type,
        campaign: data.campaignId
      }
    });
    
    // Send email
    await this.emailProvider.send({
      to: recipient.email,
      from: branding.sender || 'noreply@plinto.dev',
      subject: this.renderSubject(template.subject, data),
      html: tracked.html,
      text: tracked.text,
      
      // Headers
      headers: {
        'X-Campaign-Id': data.campaignId,
        'X-Template-Id': template.id,
        'List-Unsubscribe': this.getUnsubscribeUrl(recipient)
      }
    });
  }
}
```

## Custom Domain Configuration

### Domain White-Labeling

```typescript
class DomainWhiteLabel {
  async configureDomain(config: DomainConfig): Promise<DomainSetup> {
    // Validate domain ownership
    const ownership = await this.validateOwnership(config.domain);
    if (!ownership.verified) {
      return {
        status: 'pending_verification',
        verificationMethod: ownership.method,
        verificationValue: ownership.value,
        instructions: this.getVerificationInstructions(ownership)
      };
    }
    
    // Configure subdomains
    const subdomains = await this.configureSubdomains({
      auth: `auth.${config.domain}`,      // Authentication UI
      api: `api.${config.domain}`,        // API endpoints
      admin: `admin.${config.domain}`,    // Admin portal
      cdn: `cdn.${config.domain}`,        // Static assets
      
      // Optional subdomains
      docs: config.includeDocs ? `docs.${config.domain}` : null,
      status: config.includeStatus ? `status.${config.domain}` : null
    });
    
    // SSL certificate provisioning
    const ssl = await this.provisionSSL({
      domains: Object.values(subdomains).filter(Boolean),
      type: config.sslType || 'auto', // 'auto', 'custom', 'letsencrypt'
      
      // Custom certificate
      customCert: config.customCertificate
    });
    
    // DNS configuration
    const dnsRecords = this.generateDNSRecords({
      subdomains,
      ssl,
      
      // Email configuration
      email: config.emailDomain ? {
        spf: this.generateSPF(config.emailDomain),
        dkim: await this.generateDKIM(config.emailDomain),
        dmarc: this.generateDMARC(config.emailDomain)
      } : null
    });
    
    return {
      status: 'configured',
      domains: subdomains,
      ssl: {
        status: ssl.status,
        expiresAt: ssl.expiresAt,
        autoRenew: ssl.autoRenew
      },
      dnsRecords,
      
      // Next steps
      nextSteps: [
        'Add DNS records to your domain provider',
        'Wait for DNS propagation (up to 48 hours)',
        'Verify configuration in admin portal'
      ]
    };
  }
  
  private generateDNSRecords(config: DNSConfig): DNSRecord[] {
    const records: DNSRecord[] = [];
    
    // A/CNAME records for subdomains
    Object.entries(config.subdomains).forEach(([type, subdomain]) => {
      if (subdomain) {
        records.push({
          type: 'CNAME',
          name: subdomain.replace(`.${config.domain}`, ''),
          value: `${type}.whitelabel.plinto.dev`,
          ttl: 3600
        });
      }
    });
    
    // SSL validation records
    if (config.ssl.validationRecords) {
      records.push(...config.ssl.validationRecords);
    }
    
    // Email authentication records
    if (config.email) {
      records.push(
        {
          type: 'TXT',
          name: '@',
          value: config.email.spf,
          ttl: 3600
        },
        {
          type: 'TXT',
          name: `plinto._domainkey`,
          value: config.email.dkim,
          ttl: 3600
        },
        {
          type: 'TXT',
          name: '_dmarc',
          value: config.email.dmarc,
          ttl: 3600
        }
      );
    }
    
    return records;
  }
}
```

## Advanced Customization

### Custom CSS Injection

```typescript
class CustomCSSService {
  async injectCustomCSS(css: string, scope: CSSScope): Promise<void> {
    // Validate CSS
    const validation = await this.validateCSS(css);
    if (!validation.valid) {
      throw new Error(`Invalid CSS: ${validation.errors.join(', ')}`);
    }
    
    // Sanitize CSS
    const sanitized = await this.sanitizeCSS(css, {
      allowedProperties: this.getAllowedProperties(scope),
      allowedSelectors: this.getAllowedSelectors(scope),
      
      // Security restrictions
      blockJavaScript: true,
      blockExternal: true,
      blockImports: scope !== 'global'
    });
    
    // Scope CSS if needed
    const scoped = scope === 'global' ? sanitized : 
      this.scopeCSS(sanitized, `.plinto-${scope}`);
    
    // Minify for production
    const minified = await this.minifyCSS(scoped);
    
    // Deploy CSS
    await this.deployCSS({
      css: minified,
      scope,
      version: generateVersion(),
      
      // Cache configuration
      cache: {
        maxAge: 86400, // 24 hours
        immutable: true
      }
    });
  }
  
  async createThemeBuilder(): Promise<ThemeBuilder> {
    return {
      // Visual theme builder
      visual: new VisualThemeBuilder({
        colorPicker: true,
        fontSelector: true,
        spacingControls: true,
        borderControls: true,
        shadowControls: true
      }),
      
      // Component customizer
      components: new ComponentCustomizer({
        livePreview: true,
        codeExport: true,
        responsivePreview: true
      }),
      
      // Layout designer
      layout: new LayoutDesigner({
        gridSystem: true,
        flexboxControls: true,
        breakpointEditor: true
      }),
      
      // Export options
      export: {
        css: () => this.exportAsCSS(),
        sass: () => this.exportAsSASS(),
        less: () => this.exportAsLESS(),
        json: () => this.exportAsJSON(),
        figma: () => this.exportToFigma()
      }
    };
  }
}
```

### JavaScript SDK Customization

```typescript
class SDKCustomization {
  async customizeSDK(config: SDKCustomConfig): Promise<CustomSDK> {
    // Build custom SDK bundle
    const bundle = await this.buildBundle({
      // Core modules
      core: true,
      
      // Optional modules
      modules: config.modules || ['auth', 'user', 'organization'],
      
      // Custom extensions
      extensions: config.extensions,
      
      // Branding
      branding: {
        namespace: config.namespace || 'Plinto',
        
        // Method prefixes
        methodPrefix: config.methodPrefix,
        
        // Event names
        eventPrefix: config.eventPrefix
      },
      
      // Build options
      minify: config.minify !== false,
      sourceMaps: config.sourceMaps !== false,
      
      // Target environments
      targets: config.targets || ['es2020', 'es2015']
    });
    
    return {
      // CDN URLs
      cdn: {
        production: `https://cdn.plinto.dev/sdk/${bundle.version}/plinto.min.js`,
        development: `https://cdn.plinto.dev/sdk/${bundle.version}/plinto.js`
      },
      
      // NPM package
      npm: {
        name: config.npmPackage || '@plinto/sdk',
        version: bundle.version,
        
        // Installation
        install: `npm install ${config.npmPackage || '@plinto/sdk'}`
      },
      
      // Usage examples
      examples: this.generateExamples(config)
    };
  }
}
```

## Theming API

### Programmatic Theme Management

```typescript
// Theme API Client
class ThemeAPI {
  async createTheme(theme: ThemeDefinition): Promise<Theme> {
    return await this.api.post('/themes', {
      name: theme.name,
      description: theme.description,
      
      // Visual configuration
      colors: theme.colors,
      typography: theme.typography,
      spacing: theme.spacing,
      
      // Components
      components: theme.components,
      
      // Layouts
      layouts: theme.layouts,
      
      // Metadata
      tags: theme.tags,
      version: theme.version
    });
  }
  
  async applyTheme(
    themeId: string,
    target: ThemeTarget
  ): Promise<ThemeApplication> {
    return await this.api.post(`/themes/${themeId}/apply`, {
      target: {
        type: target.type, // 'organization', 'application', 'widget'
        id: target.id
      },
      
      // Application options
      options: {
        override: target.override || false,
        merge: target.merge || false,
        
        // Selective application
        components: target.components,
        
        // A/B testing
        percentage: target.percentage,
        
        // Scheduling
        schedule: target.schedule
      }
    });
  }
  
  async cloneTheme(
    sourceId: string,
    modifications: ThemeModifications
  ): Promise<Theme> {
    const source = await this.api.get(`/themes/${sourceId}`);
    
    return await this.createTheme({
      ...source,
      name: modifications.name || `${source.name} (Copy)`,
      
      // Apply modifications
      colors: { ...source.colors, ...modifications.colors },
      typography: { ...source.typography, ...modifications.typography },
      
      // Mark as derived
      parent: sourceId,
      derived: true
    });
  }
}
```

## Best Practices

### 1. Brand Consistency
- Maintain consistent visual language
- Use brand guidelines strictly
- Test across all touchpoints
- Regular brand audits

### 2. Accessibility
- WCAG 2.1 AA compliance minimum
- High contrast mode support
- Keyboard navigation
- Screen reader compatibility

### 3. Performance
- Optimize asset loading
- Use CSS variables for theming
- Lazy load custom fonts
- CDN distribution

### 4. Responsive Design
- Mobile-first approach
- Test on multiple devices
- Fluid typography
- Flexible layouts

### 5. Localization Ready
- Separate content from design
- RTL language support
- Flexible text containers
- Cultural sensitivity

## Support & Resources

- Branding Guide: https://docs.plinto.dev/branding
- Theme Gallery: https://themes.plinto.dev
- Design System: https://design.plinto.dev
- Support: design@plinto.dev