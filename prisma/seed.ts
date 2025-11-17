import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  console.log("🌱 Starting database seeding...");

  // Create demo tenant
  const demoTenant = await prisma.tenant.upsert({
    where: { slug: "demo" },
    update: {},
    create: {
      name: "Demo Company",
      slug: "demo",
      domain: "demo.plinto.dev",
      subdomain: "demo",
      billing_plan: "professional",
      isolation_level: "shared",
      features: {
        multi_tenancy: true,
        advanced_rbac: true,
        payment_processing: true,
        monitoring: true,
        audit_logs: true,
      },
      limits: {
        max_users: 100,
        max_teams: 10,
        max_monthly_transactions: 10000,
        storage_gb: 100,
      },
      settings: {
        timezone: "UTC",
        currency: "USD",
        date_format: "YYYY-MM-DD",
        language: "en",
      },
    },
  });

  console.log("✅ Created demo tenant:", demoTenant.name);

  // Create enterprise tenant
  const enterpriseTenant = await prisma.tenant.upsert({
    where: { slug: "enterprise" },
    update: {},
    create: {
      name: "Enterprise Corp",
      slug: "enterprise",
      domain: "enterprise.plinto.dev",
      subdomain: "enterprise",
      billing_plan: "enterprise",
      isolation_level: "fully-isolated",
      database_host: "enterprise-db.plinto.dev",
      database_port: 5432,
      database_name: "enterprise_plinto",
      storage_bucket: "enterprise-plinto-storage",
      storage_prefix: "enterprise/",
      features: {
        multi_tenancy: true,
        advanced_rbac: true,
        payment_processing: true,
        monitoring: true,
        audit_logs: true,
        sso: true,
        advanced_analytics: true,
        white_labeling: true,
      },
      limits: {
        max_users: 10000,
        max_teams: 100,
        max_monthly_transactions: 1000000,
        storage_gb: 1000,
      },
    },
  });

  console.log("✅ Created enterprise tenant:", enterpriseTenant.name);

  // Create admin user for demo tenant
  const hashedPassword = await bcrypt.hash("demo123!", 12);
  const adminUser = await prisma.user.upsert({
    where: { email: "admin@demo.plinto.dev" },
    update: {},
    create: {
      tenant_id: demoTenant.id,
      email: "admin@demo.plinto.dev",
      first_name: "Demo",
      last_name: "Admin",
      password_hash: hashedPassword,
      email_verified: true,
      status: "active",
      timezone: "UTC",
      locale: "en-US",
      metadata: {
        source: "seed",
        initial_setup: true,
      },
    },
  });

  console.log("✅ Created admin user:", adminUser.email);

  // Create roles
  const adminRole = await prisma.role.upsert({
    where: { name: "admin" },
    update: {},
    create: {
      name: "admin",
      display_name: "Administrator",
      description: "Full system administrator with all permissions",
      permissions: [
        "user:*",
        "team:*",
        "billing:*",
        "payment:*",
        "audit:*",
        "system:*",
        "tenant:*",
      ],
      is_system_role: true,
      priority: 1000,
    },
  });

  const userRole = await prisma.role.upsert({
    where: { name: "user" },
    update: {},
    create: {
      name: "user",
      display_name: "Standard User",
      description: "Standard user with basic permissions",
      permissions: [
        "user:read",
        "user:update_own",
        "team:read",
        "payment:read_own",
      ],
      is_system_role: true,
      priority: 100,
    },
  });

  const teamLeadRole = await prisma.role.upsert({
    where: { name: "team_lead" },
    update: {},
    create: {
      name: "team_lead",
      display_name: "Team Lead",
      description: "Team leader with member management permissions",
      permissions: [
        "user:read",
        "user:update_own",
        "team:read",
        "team:update_own",
        "team:manage_members",
        "payment:read_own",
      ],
      is_system_role: true,
      priority: 500,
    },
  });

  console.log("✅ Created system roles");

  // Assign admin role to admin user
  await prisma.roleAssignment.create({
    data: {
      tenant_id: demoTenant.id,
      user_id: adminUser.id,
      role_id: adminRole.id,
      scope_type: "organization",
      scope_id: demoTenant.id,
      assigned_by: adminUser.id,
    },
  });

  console.log("✅ Assigned admin role to demo admin");

  // Create demo team
  const demoTeam = await prisma.team.create({
    data: {
      tenant_id: demoTenant.id,
      name: "Engineering",
      description: "Engineering team responsible for product development",
      status: "active",
      settings: {
        default_role: "user",
        auto_join: false,
        visibility: "private",
      },
    },
  });

  // Add admin to demo team
  await prisma.teamMember.create({
    data: {
      tenant_id: demoTenant.id,
      team_id: demoTeam.id,
      user_id: adminUser.id,
      role: "admin",
      added_by: adminUser.id,
    },
  });

  console.log("✅ Created demo team and added admin");

  // Create demo subscription
  const demoSubscription = await prisma.subscription.create({
    data: {
      tenant_id: demoTenant.id,
      plan_id: "professional_monthly",
      status: "active",
      billing_interval: "month",
      price_amount: 9900, // $99.00
      price_currency: "USD",
      trial_ends_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
      current_period_start: new Date(),
      current_period_end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
      metadata: {
        source: "seed",
        features: ["multi_tenancy", "advanced_rbac", "payment_processing"],
      },
    },
  });

  console.log("✅ Created demo subscription");

  // Create payment providers configuration
  const stripeProvider = await prisma.paymentProvider.create({
    data: {
      name: "stripe",
      display_name: "Stripe",
      type: "card_processor",
      status: "active",
      supported_countries: [
        "US",
        "CA",
        "GB",
        "AU",
        "DE",
        "FR",
        "IT",
        "ES",
        "NL",
        "BE",
      ],
      supported_currencies: ["USD", "EUR", "GBP", "CAD", "AUD"],
      supported_payment_methods: ["card", "bank_transfer", "wallet"],
      features: {
        recurring_billing: true,
        instant_payouts: true,
        fraud_protection: true,
        "3d_secure": true,
        webhooks: true,
      },
      configuration: {
        api_version: "2023-10-16",
        webhook_tolerance: 300,
        requires_3ds: false,
      },
      is_default: true,
      priority: 100,
    },
  });

  const conektaProvider = await prisma.paymentProvider.create({
    data: {
      name: "conekta",
      display_name: "Conekta",
      type: "local_processor",
      status: "active",
      supported_countries: ["MX"],
      supported_currencies: ["MXN"],
      supported_payment_methods: ["card", "oxxo", "spei", "bank_transfer"],
      features: {
        recurring_billing: true,
        instant_payouts: false,
        fraud_protection: true,
        "3d_secure": true,
        webhooks: true,
        installments: true,
        cash_payments: true,
      },
      configuration: {
        api_version: "v2.0",
        webhook_tolerance: 300,
        default_installments: 1,
        max_installments: 24,
      },
      priority: 200,
    },
  });

  console.log("✅ Created payment providers");

  // Create routing rules
  await prisma.paymentRoutingRule.createMany({
    data: [
      {
        name: "Mexico Local Payments",
        priority: 100,
        conditions: {
          country: ["MX"],
          currency: ["MXN"],
        },
        provider_id: conektaProvider.id,
        is_active: true,
      },
      {
        name: "Global Fallback",
        priority: 50,
        conditions: {},
        provider_id: stripeProvider.id,
        is_active: true,
      },
    ],
  });

  console.log("✅ Created payment routing rules");

  // Create some demo audit logs
  await prisma.auditLog.createMany({
    data: [
      {
        tenant_id: demoTenant.id,
        user_id: adminUser.id,
        action: "LOGIN",
        resource_type: "User",
        resource_id: adminUser.id,
        details: { method: "email_password", success: true },
        ip_address: "192.168.1.100",
        user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        risk_level: "low",
      },
      {
        tenant_id: demoTenant.id,
        user_id: adminUser.id,
        action: "CREATE",
        resource_type: "Team",
        resource_id: demoTeam.id,
        details: { team_name: "Engineering" },
        ip_address: "192.168.1.100",
        user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        risk_level: "low",
      },
    ],
  });

  console.log("✅ Created demo audit logs");

  // Create API keys for demo tenant
  await prisma.apiKey.create({
    data: {
      tenant_id: demoTenant.id,
      name: "Demo API Key",
      key_hash: await bcrypt.hash("demo_pk_test_12345", 12),
      key_prefix: "pk_test",
      permissions: [
        "payment:read",
        "payment:write",
        "customer:read",
        "customer:write",
      ],
      status: "active",
      created_by: adminUser.id,
    },
  });

  console.log("✅ Created demo API key");

  console.log("🎉 Database seeding completed successfully!");
  console.log("\n📊 Seeded data summary:");
  console.log("- 2 tenants (demo, enterprise)");
  console.log("- 1 admin user (admin@demo.plinto.dev / demo123!)");
  console.log("- 3 system roles (admin, user, team_lead)");
  console.log("- 1 demo team (Engineering)");
  console.log("- 1 active subscription");
  console.log("- 2 payment providers (Stripe, Conekta)");
  console.log("- 2 payment routing rules");
  console.log("- Sample audit logs");
  console.log("- 1 API key for testing");
  console.log("\n🚀 Ready for development and testing!");
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error("❌ Seeding failed:", e);
    await prisma.$disconnect();
    process.exit(1);
  });
