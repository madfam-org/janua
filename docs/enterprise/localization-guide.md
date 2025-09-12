# Localization & Internationalization Guide

## Overview

Plinto provides comprehensive localization (L10n) and internationalization (i18n) support, enabling global deployment with region-specific authentication flows, multi-language interfaces, cultural adaptations, and compliance with local regulations.

## Language Support

### Supported Languages

```typescript
interface LanguageConfiguration {
  // Core supported languages
  core: {
    'en': { name: 'English', native: 'English', rtl: false },
    'es': { name: 'Spanish', native: 'Español', rtl: false },
    'fr': { name: 'French', native: 'Français', rtl: false },
    'de': { name: 'German', native: 'Deutsch', rtl: false },
    'it': { name: 'Italian', native: 'Italiano', rtl: false },
    'pt': { name: 'Portuguese', native: 'Português', rtl: false },
    'nl': { name: 'Dutch', native: 'Nederlands', rtl: false },
    'pl': { name: 'Polish', native: 'Polski', rtl: false },
    'ru': { name: 'Russian', native: 'Русский', rtl: false },
    'uk': { name: 'Ukrainian', native: 'Українська', rtl: false },
    
    // Asian languages
    'zh-CN': { name: 'Chinese (Simplified)', native: '简体中文', rtl: false },
    'zh-TW': { name: 'Chinese (Traditional)', native: '繁體中文', rtl: false },
    'ja': { name: 'Japanese', native: '日本語', rtl: false },
    'ko': { name: 'Korean', native: '한국어', rtl: false },
    'vi': { name: 'Vietnamese', native: 'Tiếng Việt', rtl: false },
    'th': { name: 'Thai', native: 'ไทย', rtl: false },
    'id': { name: 'Indonesian', native: 'Bahasa Indonesia', rtl: false },
    
    // Middle Eastern languages
    'ar': { name: 'Arabic', native: 'العربية', rtl: true },
    'he': { name: 'Hebrew', native: 'עברית', rtl: true },
    'fa': { name: 'Persian', native: 'فارسی', rtl: true },
    'tr': { name: 'Turkish', native: 'Türkçe', rtl: false },
    
    // Indian languages
    'hi': { name: 'Hindi', native: 'हिन्दी', rtl: false },
    'bn': { name: 'Bengali', native: 'বাংলা', rtl: false },
    'ta': { name: 'Tamil', native: 'தமிழ்', rtl: false },
    
    // Nordic languages
    'sv': { name: 'Swedish', native: 'Svenska', rtl: false },
    'no': { name: 'Norwegian', native: 'Norsk', rtl: false },
    'da': { name: 'Danish', native: 'Dansk', rtl: false },
    'fi': { name: 'Finnish', native: 'Suomi', rtl: false }
  };
  
  // Locale variants
  variants: {
    'en-US': { parent: 'en', name: 'English (US)', differences: {...} },
    'en-GB': { parent: 'en', name: 'English (UK)', differences: {...} },
    'en-AU': { parent: 'en', name: 'English (Australia)', differences: {...} },
    'es-MX': { parent: 'es', name: 'Spanish (Mexico)', differences: {...} },
    'pt-BR': { parent: 'pt', name: 'Portuguese (Brazil)', differences: {...} },
    'fr-CA': { parent: 'fr', name: 'French (Canada)', differences: {...} }
  };
  
  // Fallback chains
  fallbacks: {
    'en-GB': ['en-US', 'en'],
    'es-MX': ['es-ES', 'es'],
    'pt-BR': ['pt-PT', 'pt'],
    'zh-HK': ['zh-TW', 'zh-CN', 'zh']
  };
}
```

### Translation Management

```typescript
class TranslationService {
  async loadTranslations(locale: string): Promise<Translations> {
    // Try exact locale match first
    let translations = await this.tryLoadLocale(locale);
    
    if (!translations) {
      // Try language without region
      const language = locale.split('-')[0];
      translations = await this.tryLoadLocale(language);
    }
    
    if (!translations) {
      // Use fallback chain
      const fallbacks = this.config.fallbacks[locale] || ['en'];
      for (const fallback of fallbacks) {
        translations = await this.tryLoadLocale(fallback);
        if (translations) break;
      }
    }
    
    // Merge with defaults for missing keys
    return this.mergeWithDefaults(translations);
  }
  
  async translateContent(
    content: string,
    locale: string,
    context?: TranslationContext
  ): Promise<string> {
    const translations = await this.loadTranslations(locale);
    
    // Simple key-based translation
    if (translations[content]) {
      return this.interpolate(translations[content], context);
    }
    
    // Dynamic translation using AI
    if (this.config.enableDynamicTranslation) {
      return await this.dynamicTranslate(content, locale, context);
    }
    
    // Fallback to original
    return content;
  }
  
  private interpolate(
    template: string,
    context?: TranslationContext
  ): string {
    if (!context) return template;
    
    // Replace placeholders with context values
    return template.replace(/\{\{(\w+)\}\}/g, (match, key) => {
      const value = context[key];
      
      // Format based on type
      if (typeof value === 'number') {
        return this.formatNumber(value, context.locale);
      }
      if (value instanceof Date) {
        return this.formatDate(value, context.locale);
      }
      
      return String(value || match);
    });
  }
}
```

## Regional Configuration

### Region-Specific Settings

```typescript
interface RegionalConfiguration {
  // Region definition
  region: {
    code: string;           // 'us', 'eu', 'asia', etc.
    name: string;
    countries: string[];    // ISO country codes
    defaultLocale: string;
    supportedLocales: string[];
    timezone: string;
    currency: string;
  };
  
  // Legal and compliance
  compliance: {
    dataProtection: {
      regulation: string;   // 'GDPR', 'CCPA', etc.
      consentRequired: boolean;
      ageOfConsent: number;
      dataRetention: number; // days
      rightToDelete: boolean;
    };
    
    // Authentication requirements
    authentication: {
      passwordComplexity: PasswordRules;
      mfaRequired: boolean;
      sessionTimeout: number;
      
      // Regional restrictions
      allowedAuthMethods: string[];
      blockedAuthMethods: string[];
    };
    
    // Terms and policies
    legal: {
      termsOfService: string;
      privacyPolicy: string;
      cookiePolicy: string;
      acceptanceRequired: boolean;
    };
  };
  
  // Cultural adaptations
  cultural: {
    nameFormat: 'western' | 'eastern' | 'middle_eastern';
    addressFormat: AddressFormat;
    phoneFormat: PhoneFormat;
    
    // Date and time
    dateFormat: string;     // 'MM/DD/YYYY', 'DD/MM/YYYY', etc.
    timeFormat: '12h' | '24h';
    firstDayOfWeek: 0 | 1 | 6; // Sunday, Monday, Saturday
    workingDays: number[];  // [1,2,3,4,5] for Mon-Fri
    
    // Numbers and currency
    numberFormat: {
      decimal: string;      // '.', ','
      thousand: string;     // ',', '.', ' '
      precision: number;
    };
    
    currencyFormat: {
      symbol: string;
      position: 'before' | 'after';
      decimal: string;
      thousand: string;
    };
  };
  
  // Content adaptation
  content: {
    images: {
      culturallyAppropriate: boolean;
      localizedAssets: Map<string, string>;
    };
    
    colors: {
      primary: string;      // Region-specific brand colors
      secondary: string;
      cultural: Map<string, string>; // Color meanings
    };
    
    icons: {
      localized: boolean;
      customIcons: Map<string, string>;
    };
  };
}

// Regional configuration implementation
class RegionalConfigService {
  async getRegionalConfig(
    countryCode: string
  ): Promise<RegionalConfiguration> {
    // Map country to region
    const region = this.mapCountryToRegion(countryCode);
    
    // Load region configuration
    const config = await this.loadRegionConfig(region);
    
    // Apply country-specific overrides
    const countryOverrides = await this.getCountryOverrides(countryCode);
    
    return this.mergeConfigurations(config, countryOverrides);
  }
  
  async applyRegionalSettings(
    userId: string,
    region: RegionalConfiguration
  ): Promise<void> {
    // Apply compliance settings
    await this.applyCompliance(userId, region.compliance);
    
    // Configure authentication
    await this.configureAuth(userId, region.compliance.authentication);
    
    // Set cultural preferences
    await this.setCulturalPreferences(userId, region.cultural);
    
    // Update content delivery
    await this.updateContentDelivery(userId, region.content);
  }
}
```

## Locale Detection

### Automatic Locale Detection

```typescript
class LocaleDetectionService {
  async detectLocale(request: LocaleDetectionRequest): Promise<DetectedLocale> {
    const signals: LocaleSignal[] = [];
    
    // 1. User preference (highest priority)
    if (request.user?.preferredLocale) {
      signals.push({
        source: 'user_preference',
        locale: request.user.preferredLocale,
        confidence: 1.0
      });
    }
    
    // 2. Browser/App settings
    if (request.headers?.['accept-language']) {
      const browserLocales = this.parseAcceptLanguage(
        request.headers['accept-language']
      );
      signals.push({
        source: 'browser',
        locale: browserLocales[0].locale,
        confidence: 0.8
      });
    }
    
    // 3. GeoIP location
    if (request.ipAddress) {
      const geoData = await this.geoIP.lookup(request.ipAddress);
      if (geoData.country) {
        const countryLocale = this.getCountryDefaultLocale(geoData.country);
        signals.push({
          source: 'geo_ip',
          locale: countryLocale,
          confidence: 0.6
        });
      }
    }
    
    // 4. Domain/URL
    if (request.domain) {
      const domainLocale = this.extractLocaleFromDomain(request.domain);
      if (domainLocale) {
        signals.push({
          source: 'domain',
          locale: domainLocale,
          confidence: 0.7
        });
      }
    }
    
    // 5. Previous session
    if (request.sessionId) {
      const sessionLocale = await this.getSessionLocale(request.sessionId);
      if (sessionLocale) {
        signals.push({
          source: 'session',
          locale: sessionLocale,
          confidence: 0.9
        });
      }
    }
    
    // Select best locale
    const selected = this.selectBestLocale(signals);
    
    return {
      locale: selected.locale,
      confidence: selected.confidence,
      source: selected.source,
      
      // Additional context
      alternatives: signals.filter(s => s.locale !== selected.locale),
      
      // Regional information
      region: await this.getRegionForLocale(selected.locale),
      
      // Supported check
      isSupported: this.isLocaleSupported(selected.locale),
      fallback: this.getFallbackLocale(selected.locale)
    };
  }
  
  private parseAcceptLanguage(header: string): ParsedLocale[] {
    // Parse Accept-Language header
    // Example: "en-US,en;q=0.9,es;q=0.8"
    
    return header
      .split(',')
      .map(lang => {
        const [locale, q] = lang.trim().split(';q=');
        return {
          locale: locale,
          quality: q ? parseFloat(q) : 1.0
        };
      })
      .sort((a, b) => b.quality - a.quality);
  }
}
```

## UI Localization

### Component Localization

```tsx
// Localized React Components
import { useLocale, useTranslation } from '@plinto/i18n';

export function LocalizedLoginForm() {
  const locale = useLocale();
  const t = useTranslation();
  
  return (
    <form className={`login-form ${locale.rtl ? 'rtl' : 'ltr'}`}>
      {/* Localized labels and placeholders */}
      <Input
        label={t('auth.email.label')}
        placeholder={t('auth.email.placeholder')}
        type="email"
        dir={locale.rtl ? 'rtl' : 'ltr'}
        
        // Locale-specific validation
        validation={{
          pattern: locale.emailPattern,
          message: t('auth.email.invalid')
        }}
      />
      
      <Input
        label={t('auth.password.label')}
        placeholder={t('auth.password.placeholder')}
        type="password"
        dir={locale.rtl ? 'rtl' : 'ltr'}
        
        // Region-specific password requirements
        validation={{
          minLength: locale.passwordMinLength,
          pattern: locale.passwordPattern,
          message: t('auth.password.requirements', {
            minLength: locale.passwordMinLength
          })
        }}
      />
      
      {/* Culturally appropriate social login */}
      <SocialLogins>
        {locale.socialProviders.map(provider => (
          <SocialButton
            key={provider}
            provider={provider}
            text={t(`auth.social.${provider}`)}
            icon={locale.socialIcons[provider]}
          />
        ))}
      </SocialLogins>
      
      {/* Localized legal text */}
      <LegalText>
        {t('auth.legal.terms', {
          terms: <Link href={locale.termsUrl}>{t('auth.legal.termsLink')}</Link>,
          privacy: <Link href={locale.privacyUrl}>{t('auth.legal.privacyLink')}</Link>
        })}
      </LegalText>
      
      <Button type="submit">
        {t('auth.submit')}
      </Button>
    </form>
  );
}

// Localization Provider
export function LocalizationProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = useState<Locale>();
  
  useEffect(() => {
    // Detect and load locale
    detectLocale().then(detected => {
      loadLocale(detected.locale).then(setLocale);
    });
  }, []);
  
  if (!locale) {
    return <LoadingSpinner />;
  }
  
  return (
    <LocaleContext.Provider value={locale}>
      <DirectionProvider dir={locale.rtl ? 'rtl' : 'ltr'}>
        <TranslationProvider translations={locale.translations}>
          {children}
        </TranslationProvider>
      </DirectionProvider>
    </LocaleContext.Provider>
  );
}
```

### Dynamic Content Localization

```typescript
class DynamicLocalization {
  async localizeContent(
    content: Content,
    targetLocale: string
  ): Promise<LocalizedContent> {
    // Check cache first
    const cached = await this.cache.get(`${content.id}:${targetLocale}`);
    if (cached) return cached;
    
    // Perform localization
    const localized = {
      ...content,
      
      // Translate text fields
      title: await this.translate(content.title, targetLocale),
      description: await this.translate(content.description, targetLocale),
      body: await this.translateRichText(content.body, targetLocale),
      
      // Localize media
      images: await this.localizeImages(content.images, targetLocale),
      videos: await this.localizeVideos(content.videos, targetLocale),
      
      // Format dates and numbers
      dates: this.localizeDates(content.dates, targetLocale),
      numbers: this.localizeNumbers(content.numbers, targetLocale),
      
      // Cultural adaptation
      culturalAdaptations: await this.applyCulturalAdaptations(
        content,
        targetLocale
      )
    };
    
    // Cache result
    await this.cache.set(`${content.id}:${targetLocale}`, localized);
    
    return localized;
  }
  
  private async translateRichText(
    richText: RichText,
    targetLocale: string
  ): Promise<RichText> {
    // Parse rich text structure
    const parsed = this.parseRichText(richText);
    
    // Translate text nodes
    for (const node of parsed.nodes) {
      if (node.type === 'text') {
        node.content = await this.translate(node.content, targetLocale);
      } else if (node.type === 'link') {
        // Localize link text and potentially URL
        node.text = await this.translate(node.text, targetLocale);
        node.href = this.localizeUrl(node.href, targetLocale);
      }
    }
    
    // Rebuild rich text
    return this.buildRichText(parsed);
  }
}
```

## Currency & Payment Localization

### Multi-Currency Support

```typescript
class CurrencyLocalization {
  async getLocalCurrency(countryCode: string): Promise<CurrencyConfig> {
    const currency = this.countryToCurrency[countryCode];
    
    return {
      code: currency.code,
      symbol: currency.symbol,
      name: currency.name,
      
      // Formatting
      format: {
        decimal: currency.decimalSeparator,
        thousand: currency.thousandSeparator,
        precision: currency.decimalPlaces,
        pattern: currency.pattern // e.g., "¤#,##0.00"
      },
      
      // Conversion
      exchangeRate: await this.getExchangeRate(currency.code),
      
      // Payment methods
      paymentMethods: await this.getLocalPaymentMethods(countryCode),
      
      // Tax configuration
      tax: {
        type: currency.taxType, // 'VAT', 'GST', 'Sales Tax'
        rate: currency.taxRate,
        included: currency.taxIncluded
      }
    };
  }
  
  async formatPrice(
    amount: number,
    currency: string,
    locale: string
  ): Promise<string> {
    // Use Intl.NumberFormat for accurate formatting
    const formatter = new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
    
    return formatter.format(amount);
  }
  
  async convertCurrency(
    amount: number,
    fromCurrency: string,
    toCurrency: string
  ): Promise<ConvertedAmount> {
    const rate = await this.getExchangeRate(fromCurrency, toCurrency);
    
    return {
      originalAmount: amount,
      originalCurrency: fromCurrency,
      convertedAmount: amount * rate,
      convertedCurrency: toCurrency,
      exchangeRate: rate,
      timestamp: new Date(),
      
      // Include fees if applicable
      fees: this.calculateConversionFees(amount, fromCurrency, toCurrency)
    };
  }
}

// Payment method localization
class PaymentLocalization {
  async getLocalPaymentMethods(
    countryCode: string
  ): Promise<PaymentMethod[]> {
    const methods: PaymentMethod[] = [];
    
    // Global methods
    methods.push(
      { type: 'card', name: 'Credit/Debit Card', available: true },
      { type: 'paypal', name: 'PayPal', available: this.isPayPalAvailable(countryCode) }
    );
    
    // Regional methods
    switch (this.getRegion(countryCode)) {
      case 'europe':
        methods.push(
          { type: 'sepa', name: 'SEPA Direct Debit', available: true },
          { type: 'ideal', name: 'iDEAL', available: countryCode === 'NL' },
          { type: 'sofort', name: 'Sofort', available: ['DE', 'AT', 'CH'].includes(countryCode) }
        );
        break;
        
      case 'asia':
        methods.push(
          { type: 'alipay', name: 'Alipay', available: countryCode === 'CN' },
          { type: 'wechat', name: 'WeChat Pay', available: countryCode === 'CN' },
          { type: 'paytm', name: 'Paytm', available: countryCode === 'IN' }
        );
        break;
        
      case 'latam':
        methods.push(
          { type: 'boleto', name: 'Boleto Bancário', available: countryCode === 'BR' },
          { type: 'oxxo', name: 'OXXO', available: countryCode === 'MX' }
        );
        break;
    }
    
    return methods.filter(m => m.available);
  }
}
```

## Date & Time Localization

### Timezone Management

```typescript
class TimezoneService {
  async getUserTimezone(userId: string): Promise<TimezoneInfo> {
    // Get user's preferred timezone
    const user = await this.users.get(userId);
    
    if (user.timezone) {
      return this.getTimezoneInfo(user.timezone);
    }
    
    // Detect from location
    const location = await this.getUserLocation(userId);
    return this.getTimezoneByLocation(location);
  }
  
  async formatDateTime(
    date: Date,
    locale: string,
    timezone: string,
    format?: string
  ): Promise<string> {
    // Use locale-specific format
    const localeFormat = format || this.getDefaultFormat(locale);
    
    // Convert to target timezone
    const zonedDate = this.convertToTimezone(date, timezone);
    
    // Format using Intl.DateTimeFormat
    const formatter = new Intl.DateTimeFormat(locale, {
      timeZone: timezone,
      year: 'numeric',
      month: localeFormat.month,
      day: 'numeric',
      hour: localeFormat.hour,
      minute: '2-digit',
      second: localeFormat.includeSeconds ? '2-digit' : undefined,
      hour12: localeFormat.hour12
    });
    
    return formatter.format(zonedDate);
  }
  
  async getBusinessHours(
    timezone: string,
    countryCode: string
  ): Promise<BusinessHours> {
    const country = this.countries[countryCode];
    
    return {
      // Working days (accounting for different work weeks)
      workingDays: country.workingDays || [1, 2, 3, 4, 5],
      
      // Business hours in local timezone
      openTime: country.businessHours?.open || '09:00',
      closeTime: country.businessHours?.close || '17:00',
      
      // Lunch break (if applicable)
      lunchBreak: country.lunchBreak ? {
        start: country.lunchBreak.start,
        end: country.lunchBreak.end
      } : undefined,
      
      // Public holidays
      holidays: await this.getPublicHolidays(countryCode),
      
      // Support hours
      supportHours: {
        available: this.isSupportAvailable(timezone),
        nextAvailable: this.getNextSupportWindow(timezone)
      }
    };
  }
}
```

## Legal & Compliance Localization

### Regional Legal Requirements

```typescript
class LegalLocalization {
  async getRegionalLegalRequirements(
    countryCode: string
  ): Promise<LegalRequirements> {
    const requirements: LegalRequirements = {
      // Data protection
      dataProtection: await this.getDataProtectionRequirements(countryCode),
      
      // Age restrictions
      ageRestrictions: {
        minimumAge: this.getMinimumAge(countryCode),
        parentalConsentAge: this.getParentalConsentAge(countryCode),
        verificationRequired: this.isAgeVerificationRequired(countryCode)
      },
      
      // Consent requirements
      consent: {
        explicitConsentRequired: this.isExplicitConsentRequired(countryCode),
        cookieConsentRequired: this.isCookieConsentRequired(countryCode),
        marketingConsentRequired: this.isMarketingConsentRequired(countryCode),
        
        // Consent text templates
        templates: await this.getConsentTemplates(countryCode)
      },
      
      // Identity verification
      identityVerification: {
        required: this.isIdentityVerificationRequired(countryCode),
        methods: this.getAllowedVerificationMethods(countryCode),
        documents: this.getAcceptedDocuments(countryCode)
      },
      
      // Data residency
      dataResidency: {
        required: this.isDataResidencyRequired(countryCode),
        allowedRegions: this.getAllowedDataRegions(countryCode),
        restrictions: this.getDataTransferRestrictions(countryCode)
      }
    };
    
    return requirements;
  }
  
  async generateLocalizedLegalDocuments(
    organizationId: string,
    locale: string
  ): Promise<LegalDocuments> {
    const templates = await this.getLegalTemplates(locale);
    const organization = await this.orgs.get(organizationId);
    
    return {
      // Terms of Service
      termsOfService: await this.generateDocument(
        templates.termsOfService,
        {
          organization,
          locale,
          effectiveDate: new Date(),
          jurisdiction: this.getJurisdiction(locale)
        }
      ),
      
      // Privacy Policy
      privacyPolicy: await this.generateDocument(
        templates.privacyPolicy,
        {
          organization,
          locale,
          dataController: organization.legalEntity,
          contactInfo: organization.privacyContact
        }
      ),
      
      // Cookie Policy
      cookiePolicy: await this.generateDocument(
        templates.cookiePolicy,
        {
          organization,
          locale,
          cookieTypes: this.getCookieTypes(organization),
          optOutInstructions: this.getOptOutInstructions(locale)
        }
      ),
      
      // DPA (if required)
      dataProcessingAgreement: this.isDPARequired(locale) ?
        await this.generateDPA(organization, locale) : undefined
    };
  }
}
```

## RTL (Right-to-Left) Support

### RTL Implementation

```typescript
class RTLSupport {
  applyRTL(element: HTMLElement, locale: string): void {
    const isRTL = this.isRTLLocale(locale);
    
    if (isRTL) {
      // Set direction
      element.dir = 'rtl';
      
      // Add RTL class for custom styling
      element.classList.add('rtl');
      
      // Mirror UI elements
      this.mirrorUIElements(element);
      
      // Adjust text alignment
      this.adjustTextAlignment(element);
      
      // Fix form inputs
      this.fixFormInputs(element);
    }
  }
  
  private mirrorUIElements(element: HTMLElement): void {
    // Mirror horizontal positioning
    const elementsToMirror = element.querySelectorAll('[data-mirror]');
    
    elementsToMirror.forEach(el => {
      const styles = window.getComputedStyle(el);
      
      // Swap left/right margins
      if (styles.marginLeft !== '0px') {
        el.style.marginRight = styles.marginLeft;
        el.style.marginLeft = '0';
      }
      
      // Swap left/right padding
      if (styles.paddingLeft !== '0px') {
        el.style.paddingRight = styles.paddingLeft;
        el.style.paddingLeft = '0';
      }
      
      // Mirror absolute positioning
      if (styles.position === 'absolute') {
        if (styles.left !== 'auto') {
          el.style.right = styles.left;
          el.style.left = 'auto';
        }
      }
    });
  }
  
  generateRTLStyles(): string {
    return `
      /* RTL Base Styles */
      .rtl {
        direction: rtl;
        text-align: right;
      }
      
      /* Form inputs */
      .rtl input,
      .rtl textarea,
      .rtl select {
        direction: rtl;
        text-align: right;
      }
      
      /* Buttons and icons */
      .rtl .icon-left {
        margin-right: 0;
        margin-left: 0.5rem;
      }
      
      .rtl .icon-right {
        margin-left: 0;
        margin-right: 0.5rem;
      }
      
      /* Navigation */
      .rtl .nav-item {
        float: right;
      }
      
      /* Dropdowns */
      .rtl .dropdown-menu {
        right: auto;
        left: 0;
      }
      
      /* Progress bars */
      .rtl .progress-bar {
        float: right;
        transform: scaleX(-1);
      }
      
      /* Breadcrumbs */
      .rtl .breadcrumb-item::before {
        content: '\\';
        transform: scaleX(-1);
      }
    `;
  }
}
```

## Testing & Quality Assurance

### Localization Testing

```typescript
class LocalizationTesting {
  async runLocalizationTests(
    locales: string[]
  ): Promise<TestResults> {
    const results: TestResult[] = [];
    
    for (const locale of locales) {
      // Translation completeness
      const translationTest = await this.testTranslationCompleteness(locale);
      results.push(translationTest);
      
      // UI rendering
      const uiTest = await this.testUIRendering(locale);
      results.push(uiTest);
      
      // Character encoding
      const encodingTest = await this.testCharacterEncoding(locale);
      results.push(encodingTest);
      
      // Date/time formatting
      const dateTimeTest = await this.testDateTimeFormatting(locale);
      results.push(dateTimeTest);
      
      // Number/currency formatting
      const numberTest = await this.testNumberFormatting(locale);
      results.push(numberTest);
      
      // RTL layout (if applicable)
      if (this.isRTLLocale(locale)) {
        const rtlTest = await this.testRTLLayout(locale);
        results.push(rtlTest);
      }
      
      // Legal compliance
      const complianceTest = await this.testLegalCompliance(locale);
      results.push(complianceTest);
    }
    
    return {
      results,
      summary: this.generateTestSummary(results),
      recommendations: this.generateRecommendations(results)
    };
  }
  
  async testTranslationCompleteness(locale: string): Promise<TestResult> {
    const translations = await this.loadTranslations(locale);
    const defaultKeys = await this.getDefaultTranslationKeys();
    
    const missing = defaultKeys.filter(key => !translations[key]);
    const coverage = ((defaultKeys.length - missing.length) / defaultKeys.length) * 100;
    
    return {
      test: 'translation_completeness',
      locale,
      passed: coverage >= 95,
      coverage,
      missing,
      
      details: {
        totalKeys: defaultKeys.length,
        translatedKeys: defaultKeys.length - missing.length,
        missingKeys: missing.length,
        criticalMissing: missing.filter(k => this.isCriticalKey(k))
      }
    };
  }
}
```

## Best Practices

### 1. Content Strategy
- Separate content from code
- Use translation keys consistently
- Maintain glossaries
- Regular translation reviews

### 2. Cultural Sensitivity
- Research local customs
- Avoid cultural assumptions
- Use appropriate imagery
- Consider color meanings

### 3. Performance
- Lazy load translations
- Cache aggressively
- Optimize font loading
- Use CDN for assets

### 4. Testing
- Test with native speakers
- Verify all locales
- Check edge cases
- Monitor user feedback

### 5. Maintenance
- Regular updates
- Version control translations
- Track changes
- Automated testing

## Support & Resources

- i18n Documentation: https://docs.plinto.dev/i18n
- Translation Portal: https://translate.plinto.dev
- Locale Testing: https://test.plinto.dev/locales
- Support: i18n@plinto.dev