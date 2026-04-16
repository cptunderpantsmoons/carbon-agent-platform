/**
 * Clerk Integration for Open WebUI - The Intelligence Hub
 *
 * This module intercepts Open WebUI initialization, extracts the Clerk session
 * token from the browser, calls the orchestrator to get the user's API key,
 * and injects it into Open WebUI configuration automatically.
 *
 * Loaded by Open WebUI to enable seamless Clerk authentication integration.
 */

(function () {
  'use strict';

  // Configuration
  const CONFIG = {
    orchestratorUrl: window.__ORCHESTRATOR_URL__ || 'http://localhost:8000',
    adapterUrl: window.__ADAPTER_URL__ || 'http://localhost:8001',
    clerkPublishableKey: window.__CLERK_PUBLISHABLE_KEY__ || '',
    sessionRefreshInterval: 300000, // 5 minutes
    apiKeyEndpoint: '/api/v1/auth/get-api-key',
    maxRetryAttempts: 3,
    retryDelay: 1000, // 1 second
  };

  // State
  let clerkSession = null;
  let apiKeyCache = null;
  let tokenRefreshTimer = null;
  let isInitialized = false;

  // Logger
  const logger = {
    info: (msg, data) => console.log('[Clerk Integration]', msg, data || ''),
    warn: (msg, data) => console.warn('[Clerk Integration]', msg, data || ''),
    error: (msg, data) => console.error('[Clerk Integration]', msg, data || ''),
    debug: (msg, data) => {
      if (window.__DEBUG_MODE__) {
        console.debug('[Clerk Integration]', msg, data || '');
      }
    },
  };

  /**
   * Extract Clerk session token from browser storage or cookies.
   * Tries multiple strategies to find the active session.
   *
   * @returns {string|null} The Clerk session token or null
   */
  function extractClerkSessionToken() {
    try {
      // Strategy 1: Check for Clerk cookie (__session)
      const cookies = document.cookie.split(';').reduce((acc, cookie) => {
        const [name, value] = cookie.trim().split('=');
        acc[name] = value;
        return acc;
      }, {});

      if (cookies['__session']) {
        logger.debug('Found session token in __session cookie');
        return cookies['__session'];
      }

      // Strategy 2: Check localStorage for Clerk session
      const clerkStorageKeys = [
        '__clerk_db_jwt',
        'clerk-session',
        'clerk:session',
      ];

      for (const key of clerkStorageKeys) {
        const token = localStorage.getItem(key);
        if (token) {
          logger.debug(`Found session token in ${key}`);
          return token;
        }
      }

      // Strategy 3: Check for Clerk object on window (if Clerk JS SDK is loaded)
      if (window.Clerk && window.Clerk.session) {
        const sessionToken = window.Clerk.session?.getToken?.();
        if (sessionToken) {
          logger.debug('Found session token via Clerk SDK');
          return sessionToken;
        }
      }

      logger.debug('No Clerk session token found');
      return null;
    } catch (error) {
      logger.error('Failed to extract Clerk session token', error.message);
      return null;
    }
  }

  /**
   * Decode JWT payload without verification to extract user info.
   *
   * @param {string} token - JWT token
   * @returns {object|null} Decoded payload or null
   */
  function decodeJwtPayload(token) {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) {
        return null;
      }
      const payload = JSON.parse(atob(parts[1]));
      return payload;
    } catch (error) {
      logger.error('Failed to decode JWT payload', error.message);
      return null;
    }
  }

  /**
   * Check if a JWT token is expired.
   *
   * @param {string} token - JWT token
   * @returns {boolean} True if token is expired
   */
  function isTokenExpired(token) {
    const payload = decodeJwtPayload(token);
    if (!payload) return true;

    const expiry = payload.exp;
    if (!expiry) return false;

    // Add 30 second buffer to prevent edge cases
    return (Date.now() / 1000) >= (expiry - 30);
  }

  /**
   * Get user's API key from the orchestrator using Clerk authentication.
   *
   * @param {string} clerkToken - Clerk session token
   * @returns {Promise<string|null>} API key or null
   */
  async function fetchApiKey(clerkToken) {
    const url = `${CONFIG.orchestratorUrl}${CONFIG.apiKeyEndpoint}`;

    for (let attempt = 1; attempt <= CONFIG.maxRetryAttempts; attempt++) {
      try {
        logger.debug(`Fetching API key (attempt ${attempt}/${CONFIG.maxRetryAttempts})`);

        const response = await fetch(url, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${clerkToken}`,
            'Content-Type': 'application/json',
            'X-Clerk-Integration': 'true',
          },
          // Include credentials for cookie-based auth
          credentials: 'include',
        });

        if (response.ok) {
          const data = await response.json();
          if (data.api_key) {
            logger.info('API key retrieved successfully');
            return data.api_key;
          }
          logger.warn('API key not found in response', data);
          return null;
        }

        if (response.status === 401) {
          logger.warn('Clerk token expired, cannot fetch API key');
          return null;
        }

        if (response.status === 404) {
          logger.warn('API key endpoint not found, check orchestrator configuration');
          return null;
        }

        logger.warn(`Failed to fetch API key (status: ${response.status})`);

      } catch (error) {
        logger.error(`Error fetching API key (attempt ${attempt})`, error.message);
      }

      // Wait before retrying
      if (attempt < CONFIG.maxRetryAttempts) {
        await sleep(CONFIG.retryDelay * attempt);
      }
    }

    return null;
  }

  /**
   * Inject API key into Open WebUI configuration.
   *
   * @param {string} apiKey - API key to inject
   */
  function injectApiKey(apiKey) {
    try {
      // Store in sessionStorage for the current session
      sessionStorage.setItem('openwebui_api_key', apiKey);
      apiKeyCache = apiKey;

      // Try to inject into Open WebUI's internal state if accessible
      if (window.__OPEN_WEBUI_STATE__) {
        window.__OPEN_WEBUI_STATE__.settings = window.__OPEN_WEBUI_STATE__.settings || {};
        window.__OPEN_WEBUI_STATE__.settings.apiKey = apiKey;
        logger.debug('API key injected into Open WebUI state');
      }

      // Dispatch custom event for Open WebUI to pick up
      window.dispatchEvent(new CustomEvent('clerk-api-key-injected', {
        detail: { apiKey },
      }));

      logger.info('API key injected successfully');
    } catch (error) {
      logger.error('Failed to inject API key', error.message);
    }
  }

  /**
   * Initialize Clerk integration.
   * This is the main entry point called when Open WebUI loads.
   */
  async function initialize() {
    if (isInitialized) {
      logger.debug('Already initialized, skipping');
      return;
    }

    logger.info('Initializing Clerk integration...');

    try {
      // Extract Clerk session token
      const clerkToken = extractClerkSessionToken();

      if (!clerkToken) {
        logger.warn('No Clerk session found - user not authenticated');
        // Fallback: Open WebUI will use its default auth flow
        window.dispatchEvent(new CustomEvent('clerk-session-missing', {
          detail: { fallback: true },
        }));
        return;
      }

      // Check if token is expired
      if (isTokenExpired(clerkToken)) {
        logger.warn('Clerk token expired, waiting for refresh');
        // The Clerk SDK should handle refresh automatically
        // We'll retry after a short delay
        await sleep(2000);

        const refreshedToken = extractClerkSessionToken();
        if (!refreshedToken || isTokenExpired(refreshedToken)) {
          logger.error('Token still expired after refresh attempt');
          return;
        }

        clerkSession = refreshedToken;
      } else {
        clerkSession = clerkToken;
      }

      // Fetch user's API key
      const apiKey = await fetchApiKey(clerkSession);

      if (apiKey) {
        injectApiKey(apiKey);
      } else {
        logger.warn('Failed to retrieve API key - user may not have one assigned');
        window.dispatchEvent(new CustomEvent('clerk-api-key-missing', {
          detail: { clerkUserId: decodeJwtPayload(clerkSession)?.sub },
        }));
      }

      // Set up token refresh timer
      setupTokenRefresh();

      isInitialized = true;
      logger.info('Clerk integration initialized successfully');

      // Dispatch success event
      window.dispatchEvent(new CustomEvent('clerk-integration-ready', {
        detail: {
          hasApiKey: !!apiKey,
          clerkUserId: decodeJwtPayload(clerkSession)?.sub,
        },
      }));

    } catch (error) {
      logger.error('Initialization failed', error.message);
      window.dispatchEvent(new CustomEvent('clerk-integration-error', {
        detail: { error: error.message },
      }));
    }
  }

  /**
   * Set up automatic token refresh handling.
   */
  function setupTokenRefresh() {
    // Clear any existing timer
    if (tokenRefreshTimer) {
      clearInterval(tokenRefreshTimer);
    }

    tokenRefreshTimer = setInterval(async () => {
      logger.debug('Checking for token refresh...');

      const clerkToken = extractClerkSessionToken();
      if (!clerkToken) {
        logger.warn('Session lost, attempting re-initialization');
        isInitialized = false;
        await initialize();
        return;
      }

      if (isTokenExpired(clerkToken)) {
        logger.info('Token expired, refreshing API key');
        clerkSession = clerkToken;

        const apiKey = await fetchApiKey(clerkToken);
        if (apiKey) {
          injectApiKey(apiKey);
        }
      } else {
        logger.debug('Token still valid');
      }
    }, CONFIG.sessionRefreshInterval);
  }

  /**
   * Utility: Sleep for specified milliseconds.
   *
   * @param {number} ms - Milliseconds to sleep
   * @returns {Promise<void>}
   */
  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Manual API key refresh - can be called by Open WebUI when needed.
   *
   * @returns {Promise<boolean>} Success status
   */
  async function refreshApiKey() {
    logger.info('Manual API key refresh requested');

    const clerkToken = extractClerkSessionToken();
    if (!clerkToken) {
      logger.warn('No session available for refresh');
      return false;
    }

    const apiKey = await fetchApiKey(clerkToken);
    if (apiKey) {
      injectApiKey(apiKey);
      return true;
    }

    return false;
  }

  /**
   * Get the current cached API key.
   *
   * @returns {string|null} Cached API key or null
   */
  function getApiKey() {
    return apiKeyCache || sessionStorage.getItem('openwebui_api_key');
  }

  /**
   * Check if Clerk integration is active and working.
   *
   * @returns {boolean} Integration status
   */
  function isActive() {
    return isInitialized && !!clerkSession;
  }

  /**
   * Clean up resources and stop token refresh.
   */
  function destroy() {
    if (tokenRefreshTimer) {
      clearInterval(tokenRefreshTimer);
      tokenRefreshTimer = null;
    }
    isInitialized = false;
    clerkSession = null;
    apiKeyCache = null;
    logger.info('Clerk integration destroyed');
  }

  // Expose public API
  window.ClerkIntegration = {
    initialize,
    refreshApiKey,
    getApiKey,
    isActive,
    destroy,
  };

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
  } else {
    initialize();
  }

  // Also try to hook into Open WebUI's initialization
  // This ensures we run even if Open WebUI loads before DOMContentLoaded
  const originalFetch = window.fetch;
  window.fetch = function (...args) {
    // Intercept fetch calls to inject API key into adapter requests
    const url = args[0];
    if (typeof url === 'string' && (url.includes('/v1/') || url.includes('/adapter/'))) {
      const apiKey = getApiKey();
      if (apiKey) {
        logger.debug('Injecting API key into fetch request', url);

        // If headers are passed as second argument
        if (args[1]) {
          args[1].headers = {
            ...args[1].headers,
            'X-API-Key': apiKey,
          };
        } else {
          args[1] = {
            headers: {
              'X-API-Key': apiKey,
            },
          };
        }
      }
    }

    return originalFetch.apply(this, args);
  };

  // Also intercept XMLHttpRequest for older code paths
  const originalXHROpen = XMLHttpRequest.prototype.open;
  const originalXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (...args) {
    this._url = args[1];
    return originalXHROpen.apply(this, args);
  };

  XMLHttpRequest.prototype.send = function (...args) {
    const apiKey = getApiKey();
    if (apiKey && this._url && (this._url.includes('/v1/') || this._url.includes('/adapter/'))) {
      logger.debug('Injecting API key into XHR request', this._url);
      this.setRequestHeader('X-API-Key', apiKey);
    }
    return originalXHRSend.apply(this, args);
  };

  logger.info('Clerk integration module loaded');
})();
