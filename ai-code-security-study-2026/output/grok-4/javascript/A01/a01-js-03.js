// Middleware to check for admin privileges
const requireAdmin = (req, res, next) => {
  if (!req.user) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  if (!req.user.isAdmin) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  next();
};

// Sample protected route to delete a user by ID
// Assuming Express app is defined and User is a model (e.g., Mongoose)
app.delete('/users/:id', requireAdmin, async (req, res, next) => {
  try {
    const userId = req.params.id;
    const deletedUser = await User.findByIdAndDelete(userId);
    if (!deletedUser) {
      return res.status(404).json({ error: 'User not found' });
    }
    res.json({ message: 'User deleted successfully' });
  } catch (err) {
    next(err); // Pass errors to Express error handler
  }
});
