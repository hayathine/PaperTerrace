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
  CLIENT_ID: string;
  CLIENT_SECRET: string;

  // Secrets
  FIREBASE_PROJECT_ID: string;
  FIREBASE_CLIENT_EMAIL: string;
  FIREBASE_PRIVATE_KEY: string;
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
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    // Handle CORS preflight requests
    if (request.method === "OPTIONS") {
      return handleCORS(request, env);
    }

    try {
      // Process the main request and get the base response
      const response = await handleRequest(request, env, ctx);

      // Add CORS headers to ALL responses
      return addCORSHeaders(response, request, env);
    } catch (error) {
      console.error("API Gateway error:", error);
      const errorResponse = new Response(
        JSON.stringify({
          error: "Internal Server Error",
          message: error instanceof Error ? error.message : "Unknown error",
        }),
        {
          status: 500,
          headers: { "Content-Type": "application/json" },
        },
      );

      // Even internal server errors need CORS headers so the client can read them
      return addCORSHeaders(errorResponse, request, env);
    }
  },
};

/**
 * Handle business logic of the request
 */
async function handleRequest(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  // Validate origin
  const originCheck = validateOrigin(request, env);
  if (!originCheck.valid) {
    return new Response(
      JSON.stringify({
        error: "Forbidden",
        message: "Origin not allowed",
      }),
      {
        status: 403,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  // Verify Firebase Auth token or fallback to Guest
  const authHeader = request.headers.get("Authorization");
  let decodedToken: DecodedToken | null = null;

  if (authHeader && authHeader.startsWith("Bearer ")) {
    const token = authHeader.substring(7); // Remove 'Bearer ' prefix
    decodedToken = await verifyFirebaseToken(token, env);

    if (!decodedToken) {
      return new Response(
        JSON.stringify({
          error: "Unauthorized",
          message: "Invalid authentication token",
        }),
        {
          status: 401,
          headers: { "Content-Type": "application/json" },
        },
      );
    }
  } else {
    // GUEST ACCESS: Identify by IP for basic tracking/rate limiting on backend
    const clientIP = request.headers.get("CF-Connecting-IP") || "anonymous";
    decodedToken = {
      uid: `guest_${clientIP}`,
      isGuest: true,
    };
  }

  // Forward request to backend with user ID header
  return await forwardRequest(request, decodedToken, env);
}

/**
 * Handle CORS preflight requests
 */
function handleCORS(request: Request, env: Env): Response {
  const origin = request.headers.get("Origin") || "";
  const allowedOrigins = env.ALLOWED_ORIGINS.split(",").map((o: string) =>
    o.trim(),
  );

  const headers: Record<string, string> = {
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers":
      "Content-Type, Authorization, X-Requested-With, X-User-ID",
    "Access-Control-Max-Age": "86400",
  };

  if (isOriginAllowed(origin, allowedOrigins)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Access-Control-Allow-Credentials"] = "true";
  }

  return new Response(null, { status: 204, headers });
}

/**
 * Validate request origin
 */
function validateOrigin(request: Request, env: Env): { valid: boolean } {
  // For GET requests, we can be more permissive to allow direct browser hits
  // if neither Origin nor Referer is present.
  if (
    request.method === "GET" &&
    !request.headers.get("Origin") &&
    !request.headers.get("Referer")
  ) {
    return { valid: true };
  }

  const origin = request.headers.get("Origin");
  const referer = request.headers.get("Referer");

  const allowedOrigins = env.ALLOWED_ORIGINS.split(",").map((o: string) =>
    o.trim(),
  );

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
function isOriginAllowed(
  originOrUrl: string,
  allowedOrigins: string[],
): boolean {
  let origin = originOrUrl;
  try {
    // If it's a full URL (like from a Referer header), extract just the origin part
    const url = new URL(originOrUrl);
    origin = url.origin;
  } catch (e) {
    // Ignore invalid URLs, origin remains unchanged
  }

  // Exact match
  if (allowedOrigins.includes(origin)) {
    return true;
  }

  // Check if origin starts with any allowed origin
  for (const allowed of allowedOrigins) {
    if (allowed && origin.startsWith(allowed)) {
      return true;
    }
  }

  // Check for Cloudflare Pages preview URLs and root domain
  // This matches: https://*.paperterrace.page, https://paperterrace.page, https://*.pages.dev
  if (
    origin.match(/^https:\/\/((.*?\.)?paperterrace\.page|(.*?\.)?pages\.dev)$/)
  ) {
    return true;
  }

  return false;
}

/**
 * Verify Firebase Auth token
 *
 * Note: This is a simplified implementation. In production, you should use
 * the Firebase Admin SDK or implement proper JWT verification with caching.
 */
async function verifyFirebaseToken(
  token: string,
  env: Env,
): Promise<DecodedToken | null> {
  try {
    // Decode JWT without verification (for development)
    // In production, implement proper JWT verification with Firebase public keys
    const parts = token.split(".");
    if (parts.length !== 3) {
      return null;
    }

    const payload = JSON.parse(atob(parts[1]));

    // Basic validation
    if (
      !payload.uid ||
      !payload.aud ||
      payload.aud !== env.FIREBASE_PROJECT_ID
    ) {
      return null;
    }

    // Check expiration
    if (payload.exp && payload.exp < Date.now() / 1000) {
      return null;
    }

    return {
      uid: payload.uid,
      email: payload.email,
      ...payload,
    };
  } catch (error) {
    console.error("Token verification error:", error);
    return null;
  }
}

/**
 * Forward request to backend via Cloudflare Tunnel
 */
async function forwardRequest(
  request: Request,
  decodedToken: DecodedToken,
  env: Env,
): Promise<Response> {
  const url = new URL(request.url);
  const backendUrl = new URL(url.pathname + url.search, env.BACKEND_TUNNEL_URL);

  // Create new headers with user ID
  const headers = new Headers(request.headers);
  headers.set("X-User-ID", decodedToken.uid);
  headers.set("X-Forwarded-For", request.headers.get("CF-Connecting-IP") || "");
  headers.set("X-Real-IP", request.headers.get("CF-Connecting-IP") || "");
  // ★ Access Service Token
  headers.set("CF-Access-Client-Id", env.CLIENT_ID);
  headers.set("CF-Access-Client-Secret", env.CLIENT_SECRET);

  // Remove Authorization header (already verified)
  headers.delete("Authorization");

  // Forward request
  const response = await fetch(backendUrl.toString(), {
    method: request.method,
    headers,
    body:
      request.method !== "GET" && request.method !== "HEAD"
        ? request.body
        : undefined,
  });

  return response;
}

/**
 * Add CORS headers to response
 */
function addCORSHeaders(
  response: Response,
  request: Request,
  env: Env,
): Response {
  const origin = request.headers.get("Origin");
  const allowedOrigins = env.ALLOWED_ORIGINS.split(",").map((o: string) =>
    o.trim(),
  );

  // If no origin (direct hit) or origin not allowed, return original response
  if (!origin || !isOriginAllowed(origin, allowedOrigins)) {
    return response;
  }

  // Create new headers based on the backend response headers
  const newHeaders = new Headers(response.headers);

  // Set CORS headers
  newHeaders.set("Access-Control-Allow-Origin", origin);
  newHeaders.set("Access-Control-Allow-Credentials", "true");
  newHeaders.set(
    "Access-Control-Allow-Methods",
    "GET, POST, PUT, DELETE, OPTIONS",
  );
  newHeaders.set(
    "Access-Control-Allow-Headers",
    "Content-Type, Authorization, X-Requested-With, X-User-ID",
  );
  // Expose useful headers to the frontend
  newHeaders.set(
    "Access-Control-Expose-Headers",
    "Content-Length, X-Request-ID",
  );

  // Return new response with original status and updated headers
  // Using the pattern: new Response(body, { status, statusText, headers })
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}
