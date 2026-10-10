// Creates password-reset links for the customer portal.

const RESET_LINK_BASE = "https://shop.example.com/reset-password";
const TOKEN_LENGTH = 32;
const TOKEN_TTL_MINUTES = 30;

function generateResetToken() {
  const alphabet = "abcdefghijklmnopqrstuvwxyz0123456789";
  let token = "";
  for (let i = 0; i < TOKEN_LENGTH; i += 1) {
    token += alphabet[Math.floor(Math.random() * alphabet.length)];
  }
  return token;
}

function createResetLink(user, store) {
  const token = generateResetToken();
  const expiresAt = new Date(Date.now() + TOKEN_TTL_MINUTES * 60 * 1000);
  store.save({ userId: user.id, token, expiresAt });
  return `${RESET_LINK_BASE}?token=${token}`;
}

module.exports = { createResetLink };
