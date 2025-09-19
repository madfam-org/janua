"use strict";
/**
 * Date and time utilities
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.DateUtils = void 0;
class DateUtils {
    /**
     * Check if a timestamp has expired
     */
    static isExpired(timestamp) {
        return Date.now() > timestamp;
    }
    /**
     * Format a date to ISO string
     */
    static formatISO(date) {
        return date.toISOString();
    }
    /**
     * Parse an ISO date string
     */
    static parseISO(dateString) {
        return new Date(dateString);
    }
    /**
     * Get current timestamp in seconds
     */
    static getCurrentTimestamp() {
        return Math.floor(Date.now() / 1000);
    }
    /**
     * Add seconds to a date
     */
    static addSeconds(date, seconds) {
        return new Date(date.getTime() + seconds * 1000);
    }
    /**
     * Add minutes to a date
     */
    static addMinutes(date, minutes) {
        return this.addSeconds(date, minutes * 60);
    }
    /**
     * Add hours to a date
     */
    static addHours(date, hours) {
        return this.addMinutes(date, hours * 60);
    }
    /**
     * Add days to a date
     */
    static addDays(date, days) {
        return this.addHours(date, days * 24);
    }
    /**
     * Format a date relative to now (e.g., "2 hours ago")
     */
    static formatRelative(date) {
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        if (days > 0) {
            return `${days} day${days === 1 ? '' : 's'} ago`;
        }
        if (hours > 0) {
            return `${hours} hour${hours === 1 ? '' : 's'} ago`;
        }
        if (minutes > 0) {
            return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
        }
        return 'just now';
    }
    /**
     * Check if a date is within a time range
     */
    static isWithinRange(date, startDate, endDate) {
        return date >= startDate && date <= endDate;
    }
    /**
     * Get the difference between two dates in seconds
     */
    static getDifferenceInSeconds(date1, date2) {
        return Math.abs(date1.getTime() - date2.getTime()) / 1000;
    }
    /**
     * Check if two dates are on the same day
     */
    static isSameDay(date1, date2) {
        return (date1.getFullYear() === date2.getFullYear() &&
            date1.getMonth() === date2.getMonth() &&
            date1.getDate() === date2.getDate());
    }
}
exports.DateUtils = DateUtils;
//# sourceMappingURL=date-utils.js.map