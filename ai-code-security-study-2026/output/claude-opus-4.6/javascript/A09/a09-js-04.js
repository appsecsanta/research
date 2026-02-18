/**
 * Serializes a user object to a log-safe format by redacting sensitive fields.
 * Use this whenever logging user-related data for debugging.
 *
 * @param {Object} user - The user object to serialize
 * @param {string|number} user.id - User ID
 * @param {string} user.name - User's display name
 * @param {string} user.email - User's email address
 * @param {string} user.passwordHash - User's hashed password (REDACTED)
 * @param {string} user.role - User's role
 * @param {string[]|Object[]} user.tokens - User's auth tokens (REDACTED)
 * @returns {Object} A plain object safe for logging, with sensitive fields redacted
 */
function logUser(user) {
  if (user == null) {
    return { _logUser: 'null_or_undefined_user' };
  }

  if (typeof user !== 'object') {
    return { _logUser: 'invalid_user', type: typeof user };
  }

  const REDACTED = '[REDACTED]';

  const maskEmail = (email) => {
    if (typeof email !== 'string') return email;
    const parts = email.split('@');
    if (parts.length !== 2) return REDACTED;
    const local = parts[0];
    const domain = parts[1];
    const visibleChars = Math.min(3, Math.floor(local.length / 2));
    const masked = local.slice(0, visibleChars) + '***';
    return `${masked}@${domain}`;
  };

  const summarizeTokens = (tokens) => {
    if (!tokens) return { count: 0 };
    if (Array.isArray(tokens)) return { count: tokens.length };
    if (typeof tokens === 'object') return { count: Object.keys(tokens).length };
    return { count: '?' };
  };

  return {
    id: user.id ?? undefined,
    name: user.name ?? undefined,
    email: maskEmail(user.email),
    passwordHash: REDACTED,
    role: user.role ?? undefined,
    tokens: summarizeTokens(user.tokens),
    _ts: new Date().toISOString(),
  };
}

module.exports = logUser;
