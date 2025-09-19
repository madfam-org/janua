"use strict";
/**
 * Core types and interfaces for the Plinto TypeScript SDK
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.WebhookEventType = exports.OAuthProvider = exports.OrganizationRole = exports.UserStatus = void 0;
// User Status
var UserStatus;
(function (UserStatus) {
    UserStatus["ACTIVE"] = "active";
    UserStatus["SUSPENDED"] = "suspended";
    UserStatus["DELETED"] = "deleted";
})(UserStatus || (exports.UserStatus = UserStatus = {}));
// Organization Roles
var OrganizationRole;
(function (OrganizationRole) {
    OrganizationRole["OWNER"] = "owner";
    OrganizationRole["ADMIN"] = "admin";
    OrganizationRole["MEMBER"] = "member";
    OrganizationRole["VIEWER"] = "viewer";
})(OrganizationRole || (exports.OrganizationRole = OrganizationRole = {}));
// OAuth Providers
var OAuthProvider;
(function (OAuthProvider) {
    OAuthProvider["GOOGLE"] = "google";
    OAuthProvider["GITHUB"] = "github";
    OAuthProvider["MICROSOFT"] = "microsoft";
    OAuthProvider["DISCORD"] = "discord";
    OAuthProvider["TWITTER"] = "twitter";
})(OAuthProvider || (exports.OAuthProvider = OAuthProvider = {}));
// Webhook Event Types
var WebhookEventType;
(function (WebhookEventType) {
    WebhookEventType["USER_CREATED"] = "user.created";
    WebhookEventType["USER_UPDATED"] = "user.updated";
    WebhookEventType["USER_DELETED"] = "user.deleted";
    WebhookEventType["USER_SIGNED_IN"] = "user.signed_in";
    WebhookEventType["USER_SIGNED_OUT"] = "user.signed_out";
    WebhookEventType["SESSION_CREATED"] = "session.created";
    WebhookEventType["SESSION_EXPIRED"] = "session.expired";
    WebhookEventType["ORGANIZATION_CREATED"] = "organization.created";
    WebhookEventType["ORGANIZATION_UPDATED"] = "organization.updated";
    WebhookEventType["ORGANIZATION_DELETED"] = "organization.deleted";
    WebhookEventType["ORGANIZATION_MEMBER_ADDED"] = "organization.member_added";
    WebhookEventType["ORGANIZATION_MEMBER_REMOVED"] = "organization.member_removed";
})(WebhookEventType || (exports.WebhookEventType = WebhookEventType = {}));
//# sourceMappingURL=types.js.map