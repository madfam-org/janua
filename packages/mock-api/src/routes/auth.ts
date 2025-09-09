import { Router, Request, Response } from 'express';
import { db } from '../database';
import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';

export const authRouter = Router();

const JWT_SECRET = process.env.JWT_SECRET || 'mock-secret-key';

// Sign up
authRouter.post('/signup', async (req: Request, res: Response) => {
  const { email, password, name } = req.body;
  
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }
  
  // Check if user exists
  const existingUser = await db.getUserByEmail(email);
  if (existingUser) {
    return res.status(409).json({ error: 'User already exists' });
  }
  
  // Hash password
  const hashedPassword = await bcrypt.hash(password, 10);
  
  // Create user
  const user = await db.createUser({
    email,
    password: hashedPassword,
    name: name || email.split('@')[0]
  });
  
  // Generate token
  const token = jwt.sign(
    { userId: user.id, email: user.email },
    JWT_SECRET,
    { expiresIn: '24h' }
  );
  
  res.status(201).json({
    user: {
      id: user.id,
      email: user.email,
      name: user.name
    },
    token
  });
});

// Sign in
authRouter.post('/signin', async (req: Request, res: Response) => {
  const { email, password } = req.body;
  
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }
  
  // Find user
  const user = await db.getUserByEmail(email);
  if (!user) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }
  
  // Verify password
  const validPassword = await bcrypt.compare(password, user.password);
  if (!validPassword) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }
  
  // Generate token
  const token = jwt.sign(
    { userId: user.id, email: user.email },
    JWT_SECRET,
    { expiresIn: '24h' }
  );
  
  res.json({
    user: {
      id: user.id,
      email: user.email,
      name: user.name
    },
    token
  });
});

// Sign out
authRouter.post('/signout', (req: Request, res: Response) => {
  // In a real app, you'd invalidate the token here
  res.json({ message: 'Signed out successfully' });
});

// Refresh token
authRouter.post('/refresh', (req: Request, res: Response) => {
  const token = req.headers.authorization?.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ error: 'No token provided' });
  }
  
  try {
    const decoded = jwt.verify(token, JWT_SECRET) as any;
    const newToken = jwt.sign(
      { userId: decoded.userId, email: decoded.email },
      JWT_SECRET,
      { expiresIn: '24h' }
    );
    
    res.json({ token: newToken });
  } catch (error) {
    res.status(401).json({ error: 'Invalid token' });
  }
});