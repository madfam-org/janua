import { Request, Response, NextFunction } from 'express';
import getRawBody from 'raw-body';

export interface RawBodyRequest extends Request {
  rawBody?: Buffer;
}

/**
 * Middleware to capture raw request body for webhook signature validation
 * This preserves the original request body before Express parses it
 */
export async function rawBodyMiddleware(
  req: RawBodyRequest,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    // Only capture raw body for webhook endpoints
    if (!req.url.includes('/webhooks/')) {
      return next();
    }

    // Skip if body is already parsed
    if (req.body && Object.keys(req.body).length > 0) {
      return next();
    }

    // Capture raw body
    const rawBody = await getRawBody(req, {
      length: req.headers['content-length'],
      limit: '10mb',
      encoding: 'utf8'
    });

    // Store raw body for signature validation
    req.rawBody = Buffer.from(rawBody);

    // Parse JSON body manually
    try {
      req.body = JSON.parse(rawBody.toString());
    } catch (error) {
      // If not JSON, store as string
      req.body = rawBody.toString();
    }

    next();
  } catch (error) {
    next(error);
  }
}