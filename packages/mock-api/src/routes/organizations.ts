import { Router, Request, Response } from 'express';
import { db } from '../database';

export const organizationsRouter = Router();

// Get user's organizations
organizationsRouter.get('/', (req: Request, res: Response) => {
  const userId = (req as any).userId;
  const orgs = db.getUserOrganizations(userId);
  
  res.json(orgs);
});

// Create organization
organizationsRouter.post('/', async (req: Request, res: Response) => {
  const userId = (req as any).userId;
  const { name, slug } = req.body;
  
  if (!name) {
    return res.status(400).json({ error: 'Name is required' });
  }
  
  const org = await db.createOrganization({
    name,
    slug: slug || name.toLowerCase().replace(/\s+/g, '-'),
    owner_id: userId
  });
  
  res.status(201).json(org);
});

// Get organization by ID
organizationsRouter.get('/:id', (req: Request, res: Response) => {
  const org = db.getOrganizationById(req.params.id);
  
  if (!org) {
    return res.status(404).json({ error: 'Organization not found' });
  }
  
  res.json(org);
});

// Update organization
organizationsRouter.patch('/:id', (req: Request, res: Response) => {
  const { name, slug } = req.body;
  const org = db.updateOrganization(req.params.id, { name, slug });
  
  if (!org) {
    return res.status(404).json({ error: 'Organization not found' });
  }
  
  res.json(org);
});

// Delete organization
organizationsRouter.delete('/:id', (req: Request, res: Response) => {
  const success = db.deleteOrganization(req.params.id);
  
  if (!success) {
    return res.status(404).json({ error: 'Organization not found' });
  }
  
  res.status(204).send();
});

// Get organization members
organizationsRouter.get('/:id/members', (req: Request, res: Response) => {
  const members = db.getOrganizationMembers(req.params.id);
  res.json(members);
});

// Add member to organization
organizationsRouter.post('/:id/members', (req: Request, res: Response) => {
  const { userId, role } = req.body;
  
  if (!userId) {
    return res.status(400).json({ error: 'User ID is required' });
  }
  
  const member = db.addOrganizationMember(req.params.id, userId, role || 'member');
  res.status(201).json(member);
});