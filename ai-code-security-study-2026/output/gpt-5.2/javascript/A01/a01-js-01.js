import express from "express";
import jwt from "jsonwebtoken";
import mongoose from "mongoose";
import User from "./models/User.js";

const router = express.Router();

const auth = (req, res, next) => {
  try {
    const header = req.headers.authorization || "";
    const [scheme, token] = header.split(" ");

    if (scheme !== "Bearer" || !token) {
      return res.status(401).json({ error: "Unauthorized" });
    }

    const payload = jwt.verify(token, process.env.JWT_SECRET);
    req.user = payload;
    return next();
  } catch {
    return res.status(401).json({ error: "Unauthorized" });
  }
};

router.get("/api/users/:id", auth, async (req, res) => {
  const { id } = req.params;

  if (!mongoose.Types.ObjectId.isValid(id)) {
    return res.status(400).json({ error: "Invalid user id" });
  }

  const user = await User.findById(id).select("-password -__v").lean();

  if (!user) {
    return res.status(404).json({ error: "User not found" });
  }

  return res.json(user);
});

export default router;
