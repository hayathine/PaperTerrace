/**
 * PaperTerrace API Gateway - Cloudflare Workers
 * 
 * This worker acts as an API gateway that:
 * 1. Verifies Firebase Auth tokens
 * 2. Validates request origins
 * 3. Implements rate limiting
 * 4. Forwards authenticated requests to the backend via Cloudflare Tunnel
 */

interface Env {
  // Environment variables
  BACKEND_TUNNEL_URL: string;
  ALLOWED_ORIGINS: string;
  RATE_LIMIT_REQUESTS: string;
  RATE_LIMIT_WINDOW: string;
  
  // Secrets
  FIREBASE_PROJECT_ID: string;
  FIREBASE_CLIENT_EMAIL: string;
  FIREBASE_PRIVATE_KEY: string;
  
  // KV Namespace
  RATE_LIMIT: KVNamespace;
}

interface DecodedToken {
  uid: string;
  email?: string;
  [key: string]: any;
}

/**
 * Main request handler
 */
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    try {
      // Handle CORS preflight requests
      if (request.method === 'OPTIONS') {
        return handleCORS(request, env);
      }

      // Validate origin
      const originCheck = validateOrigin(request, env);
      if (!originCheck.valid) {
        return new Response(
          JSON.stringify({
            error: 'Forbidden',
            message: 'Origin not allowed'
          }),
          {
            status: 403,
            headers: { 'Content-Type': 'application/json' }
          }
        );
      }

      // Check rate limit
      const rateLimitCheck = await checkRateLimit(request, env);
      if (!rateLimitCheck.allowed) {
        return new Response(
          JSON.stringify({
            error: 'Too Many Requests',
            message: 'Rate limit exceeded'
          }),
          {
            status: 429,
            headers: {
              'Content-Type': 'application/json',
              'Retry-After': rateLimitCheck.retryAfter?.toString() || '60'
            }
          }
        );
      }

      // Verify Firebase Auth token
      const authHeader = request.headers.get('Authorization');
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return new Response(
          JSON.stringify({
            error: 'Unauthorized',
            message: 'Authorization header required'
          }),
          {
            status: 401,
            headers: { 'Content-Type': 'application/json' }
          }
        );
      }

      const token = authHeader.substring(7); // Remove 'Bearer ' prefix
      const decodedToken = await verifyFirebaseToken(token, env);
      
      if (!decodedToken) {
        return new Response(
          JSON.stringify({
            error: 'Unauthorized',
            message: 'Invalid authentication token'
          }),
          {
            status: 401,
            headers: { 'Content-Type': 'application/json' }
          }
        );
      }

      // Forward request to backend with user ID header
      const response = await forwardRequest(request, decodedToken, env);
      
      // Add CORS headers to response
      return addCORSHeaders(response, request, env);

    } catch (error) {
      console.error('API Gateway error:', error);
      return new Response(
        JSON.stringify({
          error: 'Internal Server Error',
          message: error instanceof Error ? error.message : 'Unknown error'
        }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }
  }
};

/**
 * Handle CORS preflight requests
 */
function handleCORS(request: Request, env: Env): Response {
  const origin = request.headers.get('Origin') || '';
  const allowedOrigins = env.ALLOWED_ORIGINS.split(',');
  
  const headers: Record<string, string> = {
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
    'Access-Control-Max-Age': '86400',
  };

  if (isOriginAllowed(origin, allowedOrigins)) {
    headers['Access-Control-Allow-Origin'] = origin;
    headers['Access-Control-Allow-Credentials'] = 'true';
  }

  return new Response(null, { status: 204, headers });
}

/**
 * Validate request origin
 */
function validateOrigin(request: Request, env: Env): { valid: boolean } {
  const origin = request.headers.get('Origin');
  const referer = request.headers.get('Referer');
  
  const allowedOrigins = env.ALLOWED_ORIGINS.split(',');
  
  // Check origin header
  if (origin && isOriginAllowed(origin, allowedOrigins)) {
    return { valid: true };
  }
  
  // Check referer header
  if (referer && isOriginAllowed(referer, allowedOrigins)) {
    return { valid: true };
  }
  
  return { valid: false };
}

/**
 * Check if origin is in allowed list
 */
function isOriginAllowed(origin: string, allowedOrigins: string[]): boolean {
  // Exact match
  if (allowedOrigins.includes(origin)) {
    return true;
  }
  
  // Check if origin starts with any allowed origin
  for (const allowed of allowedOrigins) {
    if (origin.startsWith(allowed)) {
      return true;
    }
  }
  
  // Check for Cloudflare Pages preview URLs
  if (origin.match(/https:\/\/.*\.(paperterrace\.page|pages\.dev)/)) {
    return true;
  }
  
  return false;
}

/**
 * Check rate limit for the client
 */
async function checkRateLimit(
  request: Request,
  env: Env
): Promise<{ allowed: boolean; retryAfter?: number }> {
  const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';
  const key = `ratelimit:${clientIP}`;
  
  const limit = parseInt(env.RATE_LIMIT_REQUESTS);
  const window = parseInt(env.RATE_LIMIT_WINDOW);
  
  // Get current count
  const currentCount = await env.RATE_LIMIT.get(key);
  const count = currentCount ? parseInt(currentCount) : 0;
  
  if (count >= limit) {
    // Get TTL to calculate retry-after
    const metadata = await env.RATE_LIMIT.getWithMetadata(key);
    const retryAfter = metadata.metadata?.expiresAt 
      ? Math.ceil((metadata.metadata.expiresAt as number - Date.now()) / 1000)
      : window;
    
    return { allowed: false, retryAfter };
  }
  
  // Increment count
  await env.RATE_LIMIT.put(key, (count + 1).toString(), {
    expirationTtl: window,
    metadata: { expiresAt: Date.now() + window * 1000 }
  });
  
  return { allowed: true };
}

/**
 * Verify Firebase Auth token
 * 
 * Note: This is a simplified implementation. In production, you should use
 * the Firebase Admin SDK or implement proper JWT verification with caching.
 */
async function verifyFirebaseToken(
  token: string,
  env: Env
): Promise<DecodedToken | null> {
  try {
    // Decode JWT without verification (for development)
    // In production, implement proper JWT verification with Firebase public keys
    const parts = token.split('.');
    if (parts.length !== 3) {
      return null;
    }
    
    const payload = JSON.parse(atob(parts[1]));
    
    // Basic validation
    if (!payload.uid || !payload.aud || payload.aud !== env.FIREBASE_PROJECT_ID) {
      return null;
    }
    
    // Check expiration
    if (payload.exp && payload.exp < Date.now() / 1000) {
      return null;
    }
    
    return {
      uid: payload.uid,
      email: payload.email,
      ...payload
    };
  } catch (error) {
    console.error('Token verification error:', error);
    return null;
  }
}

/**
 * Forward request to backend via Cloudflare Tunnel
 */
async function forwardRequest(
  request: Request,
  decodedToken: DecodedToken,
  env: Env
): Promise<Response> {
  const url = new URL(request.url);
  const backendUrl = new URL(url.pathname + url.search, env.BACKEND_TUNNEL_URL);
  
  // Create new headers with user ID
  const headers = new Headers(request.headers);
  headers.set('X-User-ID', decodedToken.uid);
  headers.set('X-Forwarded-For', request.headers.get('CF-Connecting-IP') || '');
  headers.set('X-Real-IP', request.headers.get('CF-Connecting-IP') || '');
  
  // Remove Authorization header (already verified)
  headers.delete('Authorization');
  
  // Forward request
  const response = await fetch(backendUrl.toString(), {
    method: request.method,
    headers,
    body: request.method !== 'GET' && request.method !== 'HEAD' 
      ? request.body 
      : undefined,
  });
  
  return response;
}

/**
 * Add CORS headers to response
 */
function addCORSHeaders(response: Response, request: Request, env: Env): Response {
  const origin = request.headers.get('Origin') || '';
  const allowedOrigins = env.ALLOWED_ORIGINS.split(',');
  
  if (!isOriginAllowed(origin, allowedOrigins)) {
    return response;
  }
  
  const newResponse = new Response(response.body, response);
  newResponse.headers.set('Access-Control-Allow-Origin', origin);
  newResponse.headers.set('Access-Control-Allow-Credentials', 'true');
  
  return newResponse;
}
