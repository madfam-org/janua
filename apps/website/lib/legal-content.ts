export type LegalSection = {
  title: string
  content: string
  subsections?: { title: string; content: string }[]
}

export const privacyPolicy = {
  title: 'Privacy Policy',
  subtitle: 'How Janua handles identity and account data',
  lastUpdated: 'June 15, 2026',
  intro:
    'Innovaciones MADFAM, S.A. de C.V. ("MADFAM", "we", "us") operates Janua, an identity and authentication platform. This policy describes how we process personal data when you visit janua.dev, use app.janua.dev, or interact with Janua-managed services.',
  sections: [
    {
      title: 'Data controller',
      content:
        'Innovaciones MADFAM, S.A. de C.V. is the data controller for Janua marketing and managed-cloud services. Contact: privacy@janua.dev. For self-hosted deployments, your organization is the controller of end-user identity data stored in your instance.',
    },
    {
      title: 'Information we collect',
      content:
        'Depending on how you use Janua, we may process: account identifiers (name, email, organization), authentication metadata (login timestamps, MFA enrollment status, session IDs), billing and subscription records, support communications, and technical telemetry (IP address, browser type, error logs) necessary to operate the service.',
      subsections: [
        {
          title: 'Website visitors',
          content:
            'We collect standard web analytics (page views, referrers) via privacy-respecting analytics when enabled. We do not sell visitor data.',
        },
        {
          title: 'End users of customer applications',
          content:
            'When you authenticate through a customer\'s Janua deployment, that customer determines what data is collected. Janua processes credentials and profile fields required to complete authentication on their behalf.',
        },
      ],
    },
    {
      title: 'How we use data',
      content:
        'We use personal data to provide and secure the Janua platform, authenticate users, detect abuse, deliver support, process billing, comply with legal obligations, and improve reliability. We do not use authentication data for unrelated advertising.',
    },
    {
      title: 'Legal bases (where applicable)',
      content:
        'For users in jurisdictions requiring a legal basis: contract performance (providing the service), legitimate interests (security, fraud prevention, product improvement), consent (optional marketing communications), and legal obligation (tax, compliance, lawful requests).',
    },
    {
      title: 'Data retention',
      content:
        'Account data is retained while your subscription or trial is active and for a limited period afterward for billing and legal compliance. Audit logs follow tier-based retention (30–365 days). You may request deletion subject to applicable law and backup cycles.',
    },
    {
      title: 'Sharing and subprocessors',
      content:
        'We share data with infrastructure providers (hosting, email delivery, payment processors) under data processing agreements. A current subprocessor list is available on request at privacy@janua.dev. We do not sell personal data.',
    },
    {
      title: 'International transfers',
      content:
        'Janua infrastructure may process data in the United States and other regions where our providers operate. We apply appropriate safeguards for cross-border transfers as required by applicable law.',
    },
    {
      title: 'Your rights',
      content:
        'Depending on your location, you may have rights to access, correct, delete, restrict, or port your data, and to object to certain processing. Mexican residents may exercise ARCO rights under LFPDPPP. Submit requests to privacy@janua.dev; we respond within applicable statutory timelines.',
    },
    {
      title: 'Security',
      content:
        'We implement encryption in transit, access controls, audit logging, and regular security review. No system is perfectly secure; report vulnerabilities to security@janua.dev.',
    },
    {
      title: 'Changes',
      content:
        'We may update this policy. Material changes will be posted on janua.dev with an updated effective date. Continued use after changes constitutes acceptance where permitted by law.',
    },
  ] satisfies LegalSection[],
}

export const termsOfService = {
  title: 'Terms of Service',
  subtitle: 'Terms governing use of Janua managed services',
  lastUpdated: 'June 15, 2026',
  intro:
    'These Terms of Service ("Terms") govern access to Janua cloud and managed services operated by Innovaciones MADFAM, S.A. de C.V. Self-hosted deployments under AGPL-3.0 are governed by that license in addition to these Terms where applicable.',
  sections: [
    {
      title: 'Acceptance',
      content:
        'By creating an account, accessing app.janua.dev, or using paid Janua services, you agree to these Terms and our Privacy Policy. If you accept on behalf of an organization, you represent that you have authority to bind that organization.',
    },
    {
      title: 'Service description',
      content:
        'Janua provides identity, authentication, and related developer infrastructure. Features, limits, and availability depend on your plan and documentation at docs.janua.dev. We may modify features with reasonable notice for material changes affecting paid plans.',
    },
    {
      title: 'Accounts and responsibilities',
      content:
        'You are responsible for safeguarding credentials, configuring MFA where available, and all activity under your account. You must provide accurate registration information and notify us promptly of unauthorized access.',
    },
    {
      title: 'Acceptable use',
      content:
        'You may not use Janua to violate law, infringe rights, distribute malware, conduct credential stuffing or phishing, circumvent rate limits, or interfere with platform integrity. We may suspend accounts that pose security or legal risk.',
    },
    {
      title: 'Customer data',
      content:
        'You retain ownership of end-user data processed through your Janua deployment. You grant us a limited license to host, process, and transmit that data solely to provide the service. You are responsible for obtaining necessary consents from your users.',
    },
    {
      title: 'Fees and billing',
      content:
        'Paid plans are billed according to the pricing page and order form. Fees are non-refundable except where required by law or explicitly stated. Failure to pay may result in service suspension after notice.',
    },
    {
      title: 'Open source software',
      content:
        'Janua source code is available under AGPL-3.0. Use of the open-source edition does not include managed hosting, SLAs, or support unless separately agreed. AGPL obligations apply to network-deployed modified versions.',
    },
    {
      title: 'Disclaimer of warranties',
      content:
        'The service is provided "as is" to the maximum extent permitted by law. We disclaim implied warranties of merchantability, fitness for a particular purpose, and non-infringement. Beta features are experimental and may change without notice.',
    },
    {
      title: 'Limitation of liability',
      content:
        'To the maximum extent permitted by law, MADFAM\'s aggregate liability arising from these Terms is limited to fees paid by you in the twelve months preceding the claim. We are not liable for indirect, incidental, or consequential damages.',
    },
    {
      title: 'Termination',
      content:
        'Either party may terminate per plan terms. Upon termination, access ceases and data export may be available for a limited window. Provisions that by nature should survive (payment, liability limits, governing law) remain in effect.',
    },
    {
      title: 'Governing law',
      content:
        'These Terms are governed by the laws of Mexico, without regard to conflict-of-law principles. Disputes shall be resolved in the courts of Mexico City unless mandatory consumer protection law requires otherwise.',
    },
    {
      title: 'Contact',
      content: 'Questions about these Terms: legal@janua.dev.',
    },
  ] satisfies LegalSection[],
}

export const cookiePolicy = {
  title: 'Cookie Policy',
  subtitle: 'How janua.dev uses cookies and similar technologies',
  lastUpdated: 'June 15, 2026',
  intro:
    'This policy explains how Janua uses cookies and local storage on janua.dev and related marketing properties. Authentication cookies on app.janua.dev are covered separately in product documentation.',
  sections: [
    {
      title: 'What we use',
      content:
        'We use essential cookies for security and session continuity where applicable, preference cookies (such as theme selection), and analytics cookies when you have not opted out. We do not use cookies for third-party advertising on janua.dev.',
    },
    {
      title: 'Essential cookies',
      content:
        'Required for basic site operation, CSRF protection, and load balancing. These cannot be disabled without breaking core functionality.',
    },
    {
      title: 'Preference cookies',
      content:
        'Store choices such as light/dark theme so returning visits match your settings. Stored locally or in short-lived cookies with minimal personal data.',
    },
    {
      title: 'Analytics',
      content:
        'When enabled, we use privacy-oriented analytics to understand page performance and navigation patterns. IP addresses may be truncated. You can limit tracking via browser settings or Do Not Track where supported.',
    },
    {
      title: 'Managing cookies',
      content:
        'Most browsers let you block or delete cookies. Blocking essential cookies may affect site functionality. For app.janua.dev session cookies, signing out clears authentication tokens per product configuration.',
    },
    {
      title: 'Updates',
      content:
        'We may update this policy as our tooling changes. Check the last updated date above. Contact privacy@janua.dev with questions.',
    },
  ] satisfies LegalSection[],
}
