# Email Migration Guide

This guide explains how to migrate existing email calls in MADFAM applications to use the centralized Janua email service.

## Overview

Each application currently has its own email implementation:
- **Dhanam**: Nodemailer with SMTP
- **Digifab-Quoting**: Multi-provider (SendGrid, SES, SMTP)
- **Avala**: Nodemailer with SMTP
- **Forj**: Placeholder email.service
- **madfam-site**: Direct Resend integration

After migration, all apps will use `JanuaEmailService` which routes through Janua's centralized Resend integration.

## Migration Steps by Application

---

## Dhanam

### Files to Modify

1. **`src/modules/email/email.service.ts`** - Update to use JanuaEmailService

### Before (Nodemailer)
```typescript
// email.service.ts
import * as nodemailer from 'nodemailer';

@Injectable()
export class EmailService {
  private transporter: nodemailer.Transporter;

  async sendWelcomeEmail(email: string, name: string) {
    await this.transporter.sendMail({
      to: email,
      subject: 'Welcome to Dhanam',
      html: `<h1>Welcome ${name}!</h1>`,
    });
  }
}
```

### After (JanuaEmailService)
```typescript
// email.service.ts
import { JanuaEmailService } from './janua-email.service';

@Injectable()
export class EmailService {
  constructor(
    private readonly januaEmail: JanuaEmailService,
    // Keep nodemailer as fallback
    private readonly configService: ConfigService,
  ) {}

  async sendWelcomeEmail(email: string, name: string) {
    // Try Janua first
    if (this.januaEmail.isAvailable()) {
      return this.januaEmail.sendWelcomeEmail(email, name);
    }
    
    // Fallback to nodemailer
    return this.sendViaNodemailer(email, 'Welcome', `<h1>Welcome ${name}!</h1>`);
  }
}
```

### Migration Checklist for Dhanam

- [ ] Import `JanuaEmailService` in EmailModule
- [ ] Update `sendWelcomeEmail` calls
- [ ] Update `sendPasswordResetEmail` calls
- [ ] Update `sendBudgetAlertEmail` calls
- [ ] Update `sendWeeklySummaryEmail` calls
- [ ] Update `sendMonthlyReportEmail` calls
- [ ] Test each email type
- [ ] Remove nodemailer dependency (optional, can keep as fallback)

---

## Digifab-Quoting

### Files to Modify

1. **`src/modules/email/email.service.ts`** - Update to use JanuaEmailService

### Before (Multi-provider)
```typescript
// email.service.ts
import * as sendgrid from '@sendgrid/mail';
import { SESClient } from '@aws-sdk/client-ses';

@Injectable()
export class EmailService {
  async sendQuoteReadyEmail(email: string, quoteNumber: string, amount: number) {
    if (this.provider === 'sendgrid') {
      await sendgrid.send({
        to: email,
        subject: `Quote ${quoteNumber} Ready`,
        html: `...`,
      });
    }
  }
}
```

### After (JanuaEmailService)
```typescript
// email.service.ts
import { JanuaEmailService } from './janua-email.service';

@Injectable()
export class EmailService {
  constructor(private readonly januaEmail: JanuaEmailService) {}

  async sendQuoteReadyEmail(
    email: string,
    quoteNumber: string,
    totalAmount: number,
    currency: string = 'USD',
    validUntil?: string,
  ) {
    return this.januaEmail.sendQuoteReadyEmail(
      email,
      quoteNumber,
      totalAmount,
      currency,
      validUntil,
    );
  }
}
```

### Migration Checklist for Digifab-Quoting

- [ ] Import `JanuaEmailService` in EmailModule
- [ ] Update `sendQuoteReadyEmail` calls
- [ ] Update `sendOrderConfirmationEmail` calls
- [ ] Update `sendInvoiceEmail` calls
- [ ] Update `sendShippingNotificationEmail` calls
- [ ] Remove SendGrid/SES dependencies (optional)
- [ ] Test B2B email flows

---

## Avala

### Files to Modify

1. **`src/modules/mail/mail.service.ts`** - Update to use JanuaEmailService

### Before (Nodemailer)
```typescript
// mail.service.ts
import * as nodemailer from 'nodemailer';

@Injectable()
export class MailService {
  async sendCertificateEmail(email: string, firstName: string, courseTitle: string, pdfBuffer: Buffer) {
    await this.transporter.sendMail({
      to: email,
      subject: `Tu constancia DC-3: ${courseTitle}`,
      attachments: [{
        filename: 'constancia.pdf',
        content: pdfBuffer,
      }],
    });
  }
}
```

### After (JanuaEmailService)
```typescript
// mail.service.ts
import { JanuaEmailService } from './janua-email.service';

@Injectable()
export class MailService {
  constructor(private readonly januaEmail: JanuaEmailService) {}

  async sendCertificateEmail(
    email: string,
    firstName: string,
    courseTitle: string,
    folio: string,
    pdfBuffer: Buffer,
  ) {
    return this.januaEmail.sendCertificateEmail(
      email,
      firstName,
      courseTitle,
      folio,
      pdfBuffer,
    );
  }
}
```

### Migration Checklist for Avala

- [ ] Import `JanuaEmailService` in MailModule
- [ ] Update `sendCertificateEmail` calls (with PDF attachment)
- [ ] Update `sendEnrollmentEmail` calls
- [ ] Update `sendCourseCompletionEmail` calls
- [ ] Update `sendPasswordResetEmail` calls
- [ ] Test DC-3 certificate delivery with attachments
- [ ] Remove nodemailer dependency (optional)

---

## Forj

### Files to Modify

1. **`src/services/email.service.ts`** - Already created, just use it

### Usage
```typescript
import { sendCreatorInviteEmail, sendOnboardingCompleteEmail } from '@/services/email.service';

// Send creator invitation
await sendCreatorInviteEmail(
  'creator@example.com',
  'https://forj.mx/invite/abc123',
  'creator',
  '7 days',
);

// Send onboarding complete
await sendOnboardingCompleteEmail(
  'creator@example.com',
  'John Doe',
  'My Awesome Store',
);
```

### Migration Checklist for Forj

- [ ] Replace placeholder email imports with actual implementation
- [ ] Update creator invitation flows
- [ ] Update onboarding email flows
- [ ] Test all email scenarios

---

## madfam-site

### Files to Modify

1. **`packages/email/src/index.tsx`** - Already exports Janua functions

### Before (Direct Resend)
```typescript
import { Resend } from 'resend';

const resend = new Resend(process.env.RESEND_API_KEY);

export async function sendEmail(to: string[], subject: string, react: React.ReactElement) {
  return resend.emails.send({
    from: 'MADFAM <hello@madfam.io>',
    to,
    subject,
    react,
  });
}
```

### After (JanuaEmailService)
```typescript
import { januaEmailSender, sendEmailViaJanua } from '@madfam/email';

// Option 1: Use convenience methods
await januaEmailSender.sendWelcomeEmail(['user@example.com'], { userName: 'John' });

// Option 2: Use generic send
await sendEmailViaJanua({
  to: ['user@example.com'],
  subject: 'Custom Subject',
  html: '<h1>Hello</h1>',
});
```

### Migration Checklist for madfam-site

- [ ] Update assessment result emails to use Janua
- [ ] Update ROI calculator result emails
- [ ] Update contact form notifications
- [ ] Keep direct Resend as fallback for React email templates
- [ ] Test all email scenarios

---

## Gradual Migration Strategy

### Phase 1: Parallel Running (Week 1-2)
1. Deploy Janua email service
2. Add JanuaEmailService to all apps (already done)
3. Run both old and new email systems in parallel
4. Log which system sends each email

### Phase 2: Feature Flags (Week 2-3)
```typescript
// Use feature flag to control routing
const useJanuaEmail = this.configService.get('USE_JANUA_EMAIL', false);

if (useJanuaEmail && this.januaEmail.isAvailable()) {
  return this.januaEmail.sendWelcomeEmail(email, name);
}
return this.legacyEmailService.sendWelcomeEmail(email, name);
```

### Phase 3: Migrate by Email Type (Week 3-4)
1. Start with low-volume emails (password reset)
2. Move to medium-volume (welcome, notifications)
3. End with high-volume (reports, alerts)

### Phase 4: Cleanup (Week 5)
1. Remove feature flags
2. Remove legacy email code
3. Remove unused dependencies (nodemailer, sendgrid, etc.)

---

## Testing Checklist

### Per Email Type
- [ ] Email renders correctly
- [ ] Subject line is correct
- [ ] Variables are substituted
- [ ] Attachments work (if applicable)
- [ ] Links are correct
- [ ] Unsubscribe link works (if applicable)

### Per Application
- [ ] All email types send successfully
- [ ] Fallback works when Janua is unavailable
- [ ] Logging captures send attempts
- [ ] Error handling works correctly

### Integration
- [ ] Cross-app email tracking works
- [ ] Analytics tags are correct (`source_app`, `source_type`)
- [ ] Resend dashboard shows all emails
- [ ] No duplicate emails sent

---

## Rollback Plan

If issues occur during migration:

1. **Immediate**: Set `USE_JANUA_EMAIL=false` in environment
2. **Per-app**: Each app still has fallback email code
3. **Full rollback**: Revert JanuaEmailService imports, restore old email.service.ts

---

## Support

For issues during migration:
- Check Janua logs: `docker logs janua-api`
- Check Resend dashboard for delivery status
- Review app logs for JanuaEmailService errors
- Contact platform team for assistance
