const logUser = (user) => {
  if (!user) return null;

  const safeUser = {
    id: user.id,
    name: user.name,
    email: user.email,
    role: user.role,
    tokens: user.tokens ? user.tokens.length : 0
  };

  return safeUser;
};

module.exports = logUser;
