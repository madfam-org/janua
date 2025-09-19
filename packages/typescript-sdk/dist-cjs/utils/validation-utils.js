"use strict";
/**
 * Validation utilities for input validation and data verification
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ValidationUtils = void 0;
class ValidationUtils {
    /**
     * Validate email format
     */
    static isValidEmail(email) {
        // More strict email validation - reject invalid formats
        if (!email || email.length < 5 || email.length > 254) {
            return false;
        }
        // Reject emails that start or end with special characters
        if (email.startsWith('@') || email.endsWith('@') || email.startsWith('.') || email.endsWith('.')) {
            return false;
        }
        // Reject emails with consecutive dots
        if (email.includes('..')) {
            return false;
        }
        // Must have exactly one @ symbol
        const atCount = (email.match(/@/g) || []).length;
        if (atCount !== 1) {
            return false;
        }
        const [localPart, domainPart] = email.split('@');
        // Check local part
        if (!localPart || localPart.length === 0 || localPart.length > 64) {
            return false;
        }
        // Check domain part
        if (!domainPart || domainPart.length === 0 || !domainPart.includes('.')) {
            return false;
        }
        const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
        return emailRegex.test(email);
    }
    /**
     * Validate password strength
     */
    static isValidPassword(password) {
        if (!password || password.length < 8) {
            return false;
        }
        // Must contain at least one uppercase letter
        if (!/[A-Z]/.test(password)) {
            return false;
        }
        // Must contain at least one lowercase letter
        if (!/[a-z]/.test(password)) {
            return false;
        }
        // Must contain at least one number
        if (!/[0-9]/.test(password)) {
            return false;
        }
        // Must contain at least one special character
        if (!/[!@#$%^&*(),.?\":{}|<>]/.test(password)) {
            return false;
        }
        return true;
    }
    /**
     * Comprehensive password validation with detailed rules
     */
    static validatePassword(password) {
        const errors = [];
        if (password.length < 8) {
            errors.push('Password must be at least 8 characters long');
        }
        if (!/[A-Z]/.test(password)) {
            errors.push('Password must contain at least one uppercase letter');
        }
        if (!/[a-z]/.test(password)) {
            errors.push('Password must contain at least one lowercase letter');
        }
        if (!/[0-9]/.test(password)) {
            errors.push('Password must contain at least one number');
        }
        if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
            errors.push('Password must contain at least one special character');
        }
        return {
            isValid: errors.length === 0,
            errors
        };
    }
    /**
     * Validate username format
     */
    static isValidUsername(username) {
        // Username must be 3-30 characters, alphanumeric with underscores and hyphens
        const usernameRegex = /^[a-zA-Z0-9_-]{3,30}$/;
        return usernameRegex.test(username);
    }
    /**
     * Validate phone number format
     */
    static isValidPhoneNumber(phone) {
        // Basic international phone number validation
        const phoneRegex = /^\+?[1-9]\d{1,14}$/;
        return phoneRegex.test(phone.replace(/[\s()-]/g, ''));
    }
    /**
     * Validate URL format
     */
    static isValidUrl(url) {
        try {
            new URL(url);
            return true;
        }
        catch {
            return false;
        }
    }
    /**
     * Validate UUID format
     */
    static isValidUuid(uuid) {
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        return uuidRegex.test(uuid);
    }
    /**
     * Validate slug format (lowercase letters, numbers, and hyphens only)
     */
    static isValidSlug(slug) {
        // Slug must be 1-100 characters, lowercase letters, numbers, and hyphens only
        // Cannot start or end with hyphen
        const slugRegex = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
        return slug.length >= 1 && slug.length <= 100 && slugRegex.test(slug);
    }
    /**
     * Validate date string format
     */
    static isValidDateString(dateString) {
        const date = new Date(dateString);
        return !isNaN(date.getTime());
    }
    /**
     * Validate timezone format
     */
    static isValidTimezone(timezone) {
        try {
            Intl.DateTimeFormat(undefined, { timeZone: timezone });
            return true;
        }
        catch {
            return false;
        }
    }
    /**
     * Validate locale format
     */
    static isValidLocale(locale) {
        try {
            new Intl.Locale(locale);
            return true;
        }
        catch {
            return false;
        }
    }
    /**
     * Sanitize string input
     */
    static sanitizeString(input) {
        return input
            .trim()
            .replace(/[<>]/g, '') // Remove basic HTML tags
            .slice(0, 1000); // Limit length
    }
    /**
     * Validate object against schema
     */
    static validateObject(obj, requiredFields) {
        const missingFields = requiredFields.filter(field => !(field in obj));
        return {
            isValid: missingFields.length === 0,
            missingFields: missingFields
        };
    }
}
exports.ValidationUtils = ValidationUtils;
//# sourceMappingURL=validation-utils.js.map