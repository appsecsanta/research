import express from "express";

export function requireAdmin(req, res, next) {
  const user = req.user;

  const isAdmin =
    Boolean(user?.isAdmin) ||
    user?.role === "admin" ||
    (Array.isArray(user?.roles) && user.roles.includes("admin"));

  if (!isAdmin) {
    return res.status(403).json({ error: "Forbidden" });
  }

  next();
}

const asyncHandler =
  (fn) =>
  (req, res, next) =>
    Promise.resolve(fn(req, res, next)).catch(next);

// Example: replace with your actual User model/data access layer.
const User = {
  async deleteById(id) {
    // return { deletedCount: 1 } or null if not found (example behavior)
    return { deletedCount: 1 };
  },
};

export const router = express.Router();

router.delete(
  "/users/:id",
  requireAdmin,
  asyncHandler(async (req, res) => {
    const { id } = req.params;

    if (!id) {
      return res.status(400).json({ error: "User id is required" });
    }

    const result = await User.deleteById(id);

    if (!result || result.deletedCount === 0) {
      return res.status(404).json({ error: "User not found" });
    }

    return res.status(204).send();
  })
);
