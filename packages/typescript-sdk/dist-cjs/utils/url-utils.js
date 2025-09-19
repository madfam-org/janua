"use strict";
/**
 * URL and HTTP utilities
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.HttpStatusUtils = exports.UrlUtils = void 0;
class UrlUtils {
    /**
     * Build a URL with path and optional query parameters
     */
    static buildUrl(baseUrl, path, params) {
        // Ensure baseUrl doesn't end with slash and path starts with slash
        const cleanBase = baseUrl.replace(/\/$/, '');
        const cleanPath = path.startsWith('/') ? path : `/${path}`;
        let url = `${cleanBase}${cleanPath}`;
        if (params && Object.keys(params).length > 0) {
            const queryString = this.buildQueryString(params);
            url += `?${queryString}`;
        }
        return url;
    }
    /**
     * Build a query string from parameters
     */
    static buildQueryString(params) {
        return Object.entries(params)
            .filter(([_, value]) => value !== undefined && value !== null)
            .map(([key, value]) => {
            if (Array.isArray(value)) {
                return value.map(v => `${encodeURIComponent(key)}=${encodeURIComponent(v)}`).join('&');
            }
            return `${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
        })
            .join('&');
    }
    /**
     * Parse a query string into an object
     */
    static parseQueryString(queryString) {
        const params = {};
        if (!queryString)
            return params;
        // Remove leading ? if present
        const cleanQuery = queryString.startsWith('?') ? queryString.slice(1) : queryString;
        cleanQuery.split('&').forEach(param => {
            const [key, value] = param.split('=').map(decodeURIComponent);
            if (key in params) {
                // Convert to array if multiple values
                if (Array.isArray(params[key])) {
                    params[key].push(value);
                }
                else {
                    params[key] = [params[key], value];
                }
            }
            else {
                params[key] = value;
            }
        });
        return params;
    }
    /**
     * Join URL paths safely
     */
    static joinPaths(...paths) {
        return paths
            .map((path, index) => {
            // Remove leading slash except for first path
            if (index > 0) {
                path = path.replace(/^\/+/, '');
            }
            // Remove trailing slash except for last path
            if (index < paths.length - 1) {
                path = path.replace(/\/+$/, '');
            }
            return path;
        })
            .filter(Boolean)
            .join('/');
    }
    /**
     * Extract domain from URL
     */
    static extractDomain(url) {
        try {
            const urlObj = new URL(url);
            return urlObj.hostname;
        }
        catch {
            return '';
        }
    }
    /**
     * Check if URL is absolute
     */
    static isAbsoluteUrl(url) {
        return /^https?:\/\//.test(url);
    }
    /**
     * Add or update query parameter in URL
     */
    static setQueryParam(url, key, value) {
        const urlObj = new URL(url);
        urlObj.searchParams.set(key, value);
        return urlObj.toString();
    }
    /**
     * Remove query parameter from URL
     */
    static removeQueryParam(url, key) {
        const urlObj = new URL(url);
        urlObj.searchParams.delete(key);
        return urlObj.toString();
    }
}
exports.UrlUtils = UrlUtils;
/**
 * HTTP status code utilities
 */
class HttpStatusUtils {
    /**
     * Check if status code is successful (2xx)
     */
    static isSuccess(status) {
        return status >= 200 && status < 300;
    }
    /**
     * Check if status code is redirect (3xx)
     */
    static isRedirect(status) {
        return status >= 300 && status < 400;
    }
    /**
     * Check if status code is client error (4xx)
     */
    static isClientError(status) {
        return status >= 400 && status < 500;
    }
    /**
     * Check if status code is server error (5xx)
     */
    static isServerError(status) {
        return status >= 500 && status < 600;
    }
    /**
     * Check if status code is error (4xx or 5xx)
     */
    static isError(status) {
        return status >= 400;
    }
    /**
     * Get status text for common status codes
     */
    static getStatusText(status) {
        const statusTexts = {
            200: 'OK',
            201: 'Created',
            204: 'No Content',
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            409: 'Conflict',
            422: 'Unprocessable Entity',
            429: 'Too Many Requests',
            500: 'Internal Server Error',
            502: 'Bad Gateway',
            503: 'Service Unavailable',
            504: 'Gateway Timeout'
        };
        return statusTexts[status] || 'Unknown Status';
    }
}
exports.HttpStatusUtils = HttpStatusUtils;
//# sourceMappingURL=url-utils.js.map