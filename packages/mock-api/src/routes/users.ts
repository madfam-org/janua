import { Router, Request, Response } from 'express';
import { db } from '../database';

export const usersRouter = Router();

// Get current user
usersRouter.get('/me', async (req: Request, res: Response) => {
  const userId = (req as any).userId;
  const user = await db.getUserById(userId);
  
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }
  
  res.json({
    id: user.id,
    email: user.email,
    name: user.name,
    createdAt: user.created_at,
    updatedAt: user.updated_at
  });
});

// Update current user
usersRouter.patch('/me', async (req: Request, res: Response) => {
  const userId = (req as any).userId;
  const { name, email } = req.body;
  
  const user = await db.updateUser(userId, { name, email });
  
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }
  
  res.json({
    id: user.id,
    email: user.email,
    name: user.name,
    updatedAt: user.updated_at
  });
});

// Get all users (admin only - simplified for mock)
usersRouter.get('/', (req: Request, res: Response) => {
  const users = db.getAllUsers();
  res.json(users.map(u => ({
    id: u.id,
    email: u.email,
    name: u.name,
    createdAt: u.created_at
  })));
});

// Get user by ID
usersRouter.get('/:id', async (req: Request, res: Response) => {
  const user = await db.getUserById(req.params.id);
  
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }
  
  res.json({
    id: user.id,
    email: user.email,
    name: user.name,
    createdAt: user.created_at
  });
});