var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// .wrangler/tmp/bundle-qQpNw1/checked-fetch.js
var urls = /* @__PURE__ */ new Set();
function checkURL(request, init) {
  const url = request instanceof URL ? request : new URL(
    (typeof request === "string" ? new Request(request, init) : request).url
  );
  if (url.port && url.port !== "443" && url.protocol === "https:") {
    if (!urls.has(url.toString())) {
      urls.add(url.toString());
      console.warn(
        `WARNING: known issue with \`fetch()\` requests to custom HTTPS ports in published Workers:
 - ${url.toString()} - the custom port will be ignored when the Worker is published using the \`wrangler deploy\` command.
`
      );
    }
  }
}
__name(checkURL, "checkURL");
globalThis.fetch = new Proxy(globalThis.fetch, {
  apply(target, thisArg, argArray) {
    const [request, init] = argArray;
    checkURL(request, init);
    return Reflect.apply(target, thisArg, argArray);
  }
});

// src/index.ts
var src_default = {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return handleCORS(request, env);
    }
    try {
      const response = await handleRequest(request, env, ctx);
      return addCORSHeaders(response, request, env);
    } catch (error) {
      console.error("API Gateway error:", error);
      const errorResponse = new Response(
        JSON.stringify({
          error: "Internal Server Error",
          message: error instanceof Error ? error.message : "Unknown error"
        }),
        {
          status: 500,
          headers: { "Content-Type": "application/json" }
        }
      );
      return addCORSHeaders(errorResponse, request, env);
    }
  }
};
async function handleRequest(request, env, _ctx) {
  const originCheck = validateOrigin(request, env);
  if (!originCheck.valid) {
    return new Response(
      JSON.stringify({
        error: "Forbidden",
        message: "Origin not allowed"
      }),
      {
        status: 403,
        headers: { "Content-Type": "application/json" }
      }
    );
  }
  const authHeader = request.headers.get("Authorization");
  let decodedToken = null;
  if (authHeader?.startsWith("Bearer ")) {
    const token = authHeader.substring(7);
    decodedToken = await verifyFirebaseToken(token, env);
    if (!decodedToken) {
      return new Response(
        JSON.stringify({
          error: "Unauthorized",
          message: "Invalid authentication token"
        }),
        {
          status: 401,
          headers: { "Content-Type": "application/json" }
        }
      );
    }
  } else {
    const clientIP = request.headers.get("CF-Connecting-IP") || "anonymous";
    decodedToken = {
      uid: `guest_${clientIP}`,
      isGuest: true
    };
  }
  return await forwardRequest(request, decodedToken, env);
}
__name(handleRequest, "handleRequest");
function handleCORS(request, env) {
  const origin = request.headers.get("Origin") || "";
  const allowedOrigins = parseAllowedOrigins(env);
  const headers = {
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-User-ID",
    "Access-Control-Max-Age": "86400"
  };
  if (isOriginAllowed(origin, allowedOrigins)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Access-Control-Allow-Credentials"] = "true";
  }
  return new Response(null, { status: 204, headers });
}
__name(handleCORS, "handleCORS");
function validateOrigin(request, env) {
  if (request.method === "GET" && !request.headers.get("Origin") && !request.headers.get("Referer")) {
    return { valid: true };
  }
  const origin = request.headers.get("Origin");
  const referer = request.headers.get("Referer");
  const allowedOrigins = parseAllowedOrigins(env);
  if (origin && isOriginAllowed(origin, allowedOrigins)) {
    return { valid: true };
  }
  if (referer && isOriginAllowed(referer, allowedOrigins)) {
    return { valid: true };
  }
  return { valid: false };
}
__name(validateOrigin, "validateOrigin");
function parseAllowedOrigins(env) {
  if (!env.ALLOWED_ORIGINS) return [];
  return env.ALLOWED_ORIGINS.split(",").map((o) => o.trim());
}
__name(parseAllowedOrigins, "parseAllowedOrigins");
function isOriginAllowed(originOrUrl, allowedOrigins) {
  let origin = originOrUrl;
  try {
    const url = new URL(originOrUrl);
    origin = url.origin;
  } catch (_e) {
  }
  if (allowedOrigins.includes(origin)) {
    return true;
  }
  for (const allowed of allowedOrigins) {
    if (allowed && origin.startsWith(allowed)) {
      return true;
    }
  }
  if (origin.match(/^https:\/\/((.*?\.)?paperterrace\.page|(.*?\.)?pages\.dev)$/)) {
    return true;
  }
  return false;
}
__name(isOriginAllowed, "isOriginAllowed");
async function verifyFirebaseToken(token, env) {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) {
      console.error("Invalid token format: expected 3 parts");
      return null;
    }
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    const payload = JSON.parse(new TextDecoder().decode(bytes));
    const uid = payload.sub || payload.user_id;
    if (!uid) {
      console.error("Token payload missing UID (sub/user_id)");
      return null;
    }
    if (!payload.aud) {
      console.error("Token payload missing audience (aud)");
      return null;
    }
    if (env.FIREBASE_PROJECT_ID && payload.aud !== env.FIREBASE_PROJECT_ID) {
      console.error(
        `Project ID mismatch: expected ${env.FIREBASE_PROJECT_ID}, got ${payload.aud}`
      );
      return null;
    } else if (!env.FIREBASE_PROJECT_ID) {
      console.warn(
        "FIREBASE_PROJECT_ID not set in environment, skipping audience check"
      );
    }
    if (payload.exp && payload.exp < Date.now() / 1e3) {
      console.error("Token expired", {
        exp: payload.exp,
        now: Date.now() / 1e3
      });
      return null;
    }
    return {
      uid,
      email: payload.email,
      ...payload
    };
  } catch (error) {
    console.error("Token verification error:", error);
    return null;
  }
}
__name(verifyFirebaseToken, "verifyFirebaseToken");
async function forwardRequest(request, decodedToken, env) {
  const url = new URL(request.url);
  const backendUrl = new URL(url.pathname + url.search, env.BACKEND_TUNNEL_URL);
  const headers = new Headers(request.headers);
  headers.set("X-User-ID", decodedToken.uid);
  headers.set("X-Forwarded-For", request.headers.get("CF-Connecting-IP") || "");
  headers.set("X-Real-IP", request.headers.get("CF-Connecting-IP") || "");
  if (env.CLIENT_ID && env.CLIENT_SECRET) {
    headers.set("CF-Access-Client-Id", env.CLIENT_ID);
    headers.set("CF-Access-Client-Secret", env.CLIENT_SECRET);
  } else {
    console.warn("CLIENT_ID or CLIENT_SECRET missing, skipping Access headers");
  }
  if (decodedToken.email)
    headers.set("X-User-Email", decodedToken.email);
  if (decodedToken.name)
    headers.set("X-User-Name", decodedToken.name);
  if (decodedToken.picture)
    headers.set("X-User-Picture", decodedToken.picture);
  if (decodedToken.firebase?.sign_in_provider) {
    headers.set(
      "X-User-Provider",
      decodedToken.firebase.sign_in_provider
    );
  }
  if (decodedToken.email_verified !== void 0) {
    headers.set("X-User-Email-Verified", String(decodedToken.email_verified));
  }
  headers.delete("Authorization");
  const response = await fetch(backendUrl.toString(), {
    method: request.method,
    headers,
    body: request.method !== "GET" && request.method !== "HEAD" ? request.body : void 0
  });
  return response;
}
__name(forwardRequest, "forwardRequest");
function addCORSHeaders(response, request, env) {
  const origin = request.headers.get("Origin");
  const allowedOrigins = parseAllowedOrigins(env);
  if (!origin || !isOriginAllowed(origin, allowedOrigins)) {
    return response;
  }
  const newHeaders = new Headers(response.headers);
  newHeaders.set("Access-Control-Allow-Origin", origin);
  newHeaders.set("Access-Control-Allow-Credentials", "true");
  newHeaders.set(
    "Access-Control-Allow-Methods",
    "GET, POST, PUT, DELETE, OPTIONS"
  );
  newHeaders.set(
    "Access-Control-Allow-Headers",
    "Content-Type, Authorization, X-Requested-With, X-User-ID"
  );
  newHeaders.set(
    "Access-Control-Expose-Headers",
    "Content-Length, X-Request-ID"
  );
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders
  });
}
__name(addCORSHeaders, "addCORSHeaders");

// ../node_modules/wrangler/templates/middleware/middleware-ensure-req-body-drained.ts
var drainBody = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } finally {
    try {
      if (request.body !== null && !request.bodyUsed) {
        const reader = request.body.getReader();
        while (!(await reader.read()).done) {
        }
      }
    } catch (e) {
      console.error("Failed to drain the unused request body.", e);
    }
  }
}, "drainBody");
var middleware_ensure_req_body_drained_default = drainBody;

// ../node_modules/wrangler/templates/middleware/middleware-miniflare3-json-error.ts
function reduceError(e) {
  return {
    name: e?.name,
    message: e?.message ?? String(e),
    stack: e?.stack,
    cause: e?.cause === void 0 ? void 0 : reduceError(e.cause)
  };
}
__name(reduceError, "reduceError");
var jsonError = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } catch (e) {
    const error = reduceError(e);
    return Response.json(error, {
      status: 500,
      headers: { "MF-Experimental-Error-Stack": "true" }
    });
  }
}, "jsonError");
var middleware_miniflare3_json_error_default = jsonError;

// .wrangler/tmp/bundle-qQpNw1/middleware-insertion-facade.js
var __INTERNAL_WRANGLER_MIDDLEWARE__ = [
  middleware_ensure_req_body_drained_default,
  middleware_miniflare3_json_error_default
];
var middleware_insertion_facade_default = src_default;

// ../node_modules/wrangler/templates/middleware/common.ts
var __facade_middleware__ = [];
function __facade_register__(...args) {
  __facade_middleware__.push(...args.flat());
}
__name(__facade_register__, "__facade_register__");
function __facade_invokeChain__(request, env, ctx, dispatch, middlewareChain) {
  const [head, ...tail] = middlewareChain;
  const middlewareCtx = {
    dispatch,
    next(newRequest, newEnv) {
      return __facade_invokeChain__(newRequest, newEnv, ctx, dispatch, tail);
    }
  };
  return head(request, env, ctx, middlewareCtx);
}
__name(__facade_invokeChain__, "__facade_invokeChain__");
function __facade_invoke__(request, env, ctx, dispatch, finalMiddleware) {
  return __facade_invokeChain__(request, env, ctx, dispatch, [
    ...__facade_middleware__,
    finalMiddleware
  ]);
}
__name(__facade_invoke__, "__facade_invoke__");

// .wrangler/tmp/bundle-qQpNw1/middleware-loader.entry.ts
var __Facade_ScheduledController__ = class ___Facade_ScheduledController__ {
  constructor(scheduledTime, cron, noRetry) {
    this.scheduledTime = scheduledTime;
    this.cron = cron;
    this.#noRetry = noRetry;
  }
  static {
    __name(this, "__Facade_ScheduledController__");
  }
  #noRetry;
  noRetry() {
    if (!(this instanceof ___Facade_ScheduledController__)) {
      throw new TypeError("Illegal invocation");
    }
    this.#noRetry();
  }
};
function wrapExportedHandler(worker) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return worker;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  const fetchDispatcher = /* @__PURE__ */ __name(function(request, env, ctx) {
    if (worker.fetch === void 0) {
      throw new Error("Handler does not export a fetch() function.");
    }
    return worker.fetch(request, env, ctx);
  }, "fetchDispatcher");
  return {
    ...worker,
    fetch(request, env, ctx) {
      const dispatcher = /* @__PURE__ */ __name(function(type, init) {
        if (type === "scheduled" && worker.scheduled !== void 0) {
          const controller = new __Facade_ScheduledController__(
            Date.now(),
            init.cron ?? "",
            () => {
            }
          );
          return worker.scheduled(controller, env, ctx);
        }
      }, "dispatcher");
      return __facade_invoke__(request, env, ctx, dispatcher, fetchDispatcher);
    }
  };
}
__name(wrapExportedHandler, "wrapExportedHandler");
function wrapWorkerEntrypoint(klass) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return klass;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  return class extends klass {
    #fetchDispatcher = /* @__PURE__ */ __name((request, env, ctx) => {
      this.env = env;
      this.ctx = ctx;
      if (super.fetch === void 0) {
        throw new Error("Entrypoint class does not define a fetch() function.");
      }
      return super.fetch(request);
    }, "#fetchDispatcher");
    #dispatcher = /* @__PURE__ */ __name((type, init) => {
      if (type === "scheduled" && super.scheduled !== void 0) {
        const controller = new __Facade_ScheduledController__(
          Date.now(),
          init.cron ?? "",
          () => {
          }
        );
        return super.scheduled(controller);
      }
    }, "#dispatcher");
    fetch(request) {
      return __facade_invoke__(
        request,
        this.env,
        this.ctx,
        this.#dispatcher,
        this.#fetchDispatcher
      );
    }
  };
}
__name(wrapWorkerEntrypoint, "wrapWorkerEntrypoint");
var WRAPPED_ENTRY;
if (typeof middleware_insertion_facade_default === "object") {
  WRAPPED_ENTRY = wrapExportedHandler(middleware_insertion_facade_default);
} else if (typeof middleware_insertion_facade_default === "function") {
  WRAPPED_ENTRY = wrapWorkerEntrypoint(middleware_insertion_facade_default);
}
var middleware_loader_entry_default = WRAPPED_ENTRY;
export {
  __INTERNAL_WRANGLER_MIDDLEWARE__,
  middleware_loader_entry_default as default
};
//# sourceMappingURL=index.js.map
