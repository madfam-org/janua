import { Router } from 'express';
import { WebhookController } from '../controllers/webhook.controller';
import { rawBodyMiddleware } from '../middleware/raw-body.middleware';
import { rateLimitMiddleware } from '../middleware/rate-limit.middleware';
import { errorHandler } from '../middleware/error-handler.middleware';

export function createWebhookRoutes(webhookController: WebhookController): Router {
  const router = Router();

  // Apply rate limiting to all webhook endpoints
  router.use(rateLimitMiddleware({
    windowMs: 60 * 1000, // 1 minute
    max: 100, // 100 requests per minute
    message: 'Too many webhook requests'
  }));

  // Conekta webhook endpoint
  router.post(
    '/webhooks/conekta',
    rawBodyMiddleware, // Preserve raw body for signature validation
    async (req, res, next) => {
      await webhookController.handleConektaWebhook(req, res, next);
    }
  );

  // Fungies webhook endpoint
  router.post(
    '/webhooks/fungies',
    rawBodyMiddleware,
    async (req, res, next) => {
      await webhookController.handleFungiesWebhook(req, res, next);
    }
  );

  // Stripe webhook endpoint
  router.post(
    '/webhooks/stripe',
    rawBodyMiddleware,
    async (req, res, next) => {
      await webhookController.handleStripeWebhook(req, res, next);
    }
  );

  // Health check endpoint for webhook service
  router.get('/webhooks/health', (req, res) => {
    res.json({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      endpoints: {
        conekta: '/webhooks/conekta',
        fungies: '/webhooks/fungies',
        stripe: '/webhooks/stripe'
      }
    });
  });

  // Apply error handler
  router.use(errorHandler);

  return router;
}