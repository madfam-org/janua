# 📚 Plinto Documentation

Welcome to the Plinto documentation. This directory contains all project documentation organized by category.

> **Note**: This is the **repository documentation** for developers and team members. The public-facing developer documentation will be in `apps/docs` (docs.plinto.dev).

## 📂 Documentation Structure

```
docs/
├── README.md                    # This file - Documentation index
├── PROJECT_INDEX.md            # Complete project navigation map
│
├── architecture/               # System design & architecture
│   ├── ARCHITECTURE.md         # Core system architecture
│   └── SUBDOMAIN_ARCHITECTURE.md # Domain mapping & deployment
│
├── business/                   # Business & product documentation
│   └── BIZ_DEV.md             # Business strategy, pricing, GTM
│
├── technical/                  # Technical specifications
│   ├── DATABASE_DESIGN.md     # Database schema & models
│   └── SOFTWARE_SPEC.md       # Technical requirements
│
├── reference/                  # API & SDK references
│   └── API_SPECIFICATION.md   # REST API documentation
│
└── guides/                     # Development guides
    ├── CLAUDE.md              # AI assistant guidelines
    ├── IMPLEMENTATION_GUIDE.md # Development roadmap
    └── MARKETING_DESIGN.md    # Marketing site design guide
```

## 🚀 Quick Start

### For New Team Members
1. Start with [`PROJECT_INDEX.md`](./PROJECT_INDEX.md) for complete project overview
2. Review [`architecture/ARCHITECTURE.md`](./architecture/ARCHITECTURE.md) for system design
3. Check [`guides/IMPLEMENTATION_GUIDE.md`](./guides/IMPLEMENTATION_GUIDE.md) for current development status

### For Developers
- **API Reference**: [`reference/API_SPECIFICATION.md`](./reference/API_SPECIFICATION.md)
- **Database Schema**: [`technical/DATABASE_DESIGN.md`](./technical/DATABASE_DESIGN.md)
- **Development Guidelines**: [`guides/CLAUDE.md`](./guides/CLAUDE.md)

### For Product/Business
- **Business Strategy**: [`business/BIZ_DEV.md`](./business/BIZ_DEV.md)
- **Marketing Design**: [`guides/MARKETING_DESIGN.md`](./guides/MARKETING_DESIGN.md)

### For DevOps/Infrastructure
- **System Architecture**: [`architecture/ARCHITECTURE.md`](./architecture/ARCHITECTURE.md)
- **Deployment Strategy**: [`architecture/SUBDOMAIN_ARCHITECTURE.md`](./architecture/SUBDOMAIN_ARCHITECTURE.md)

## 📖 Documentation Categories

### 🏗️ Architecture
System design, infrastructure, and deployment architecture.
- [Core Architecture](./architecture/ARCHITECTURE.md) - Hexagonal architecture, domain model
- [Subdomain Architecture](./architecture/SUBDOMAIN_ARCHITECTURE.md) - Domain mapping, folder structure

### 💼 Business
Business strategy, pricing, and go-to-market plans.
- [Business Development](./business/BIZ_DEV.md) - Pricing tiers, GTM strategy, positioning

### 🔧 Technical
Technical specifications and database design.
- [Database Design](./technical/DATABASE_DESIGN.md) - PostgreSQL schema, relationships
- [Software Specification](./technical/SOFTWARE_SPEC.md) - Technical requirements, constraints

### 📋 Reference
API documentation and technical references.
- [API Specification](./reference/API_SPECIFICATION.md) - REST endpoints, authentication flows

### 📘 Guides
Development guides and best practices.
- [AI Guidelines](./guides/CLAUDE.md) - Claude AI development patterns
- [Implementation Guide](./guides/IMPLEMENTATION_GUIDE.md) - Development roadmap, milestones
- [Marketing Design](./guides/MARKETING_DESIGN.md) - UI/UX design specifications

## 🔄 Documentation Updates

### Adding New Documentation
1. Choose appropriate category folder
2. Use UPPERCASE_WITH_UNDERSCORES.md naming
3. Update this README with the new document
4. Update [`PROJECT_INDEX.md`](./PROJECT_INDEX.md) if significant

### Documentation Standards
- **Format**: Markdown (.md)
- **Naming**: UPPERCASE_WITH_UNDERSCORES.md
- **Structure**: Clear headings, table of contents for long docs
- **Cross-references**: Use relative links between documents

## 🔗 Related Resources

### Internal
- **Main README**: [`../README.md`](../README.md) - Project overview
- **API Code**: [`../apps/api/`](../apps/api/) - API implementation
- **Marketing Site**: [`../apps/marketing/`](../apps/marketing/) - Public website
- **Dashboard**: [`../apps/dashboard/`](../apps/dashboard/) - Customer portal

### External
- **Production**: [plinto.dev](https://plinto.dev)
- **Dashboard**: [app.plinto.dev](https://app.plinto.dev)
- **GitHub**: [github.com/madfam-io/plinto](https://github.com/madfam-io/plinto)

---

*For complete project navigation, see [`PROJECT_INDEX.md`](./PROJECT_INDEX.md)*