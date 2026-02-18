const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const mongoose = require('mongoose');

const router = express.Router();

const User =
  mongoose.models.User ||
  mongoose.model(
    'User',
    new mongoose.Schema(
      {
        profilePicturePath: { type: String, default: '' },
      },
      { timestamps: true }
    )
  );

const UPLOADS_DIR = path.resolve(process.cwd(), 'uploads');
fs.mkdirSync(UPLOADS_DIR, { recursive: true });

const allowedMimeTypes = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
]);

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOADS_DIR),
  filename: (req, file, cb) => {
    const ext = (path.extname(file.originalname) || '').toLowerCase();
    const safeExt = /^[a-z0-9.]+$/i.test(ext) ? ext : '';
    const name = `${Date.now()}-${crypto.randomBytes(16).toString('hex')}${safeExt}`;
    cb(null, name);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 5 * 1024 * 1024 }, // 5MB
  fileFilter: (req, file, cb) => {
    if (!allowedMimeTypes.has(file.mimetype)) {
      const err = new multer.MulterError('LIMIT_UNEXPECTED_FILE', file.fieldname);
      err.message = 'Only image uploads are allowed.';
      return cb(err);
    }
    cb(null, true);
  },
});

router.post('/api/upload', upload.single('profilePicture'), async (req, res, next) => {
  try {
    const userId = req.user?.id || req.user?._id || req.body?.userId;

    if (!userId || !mongoose.Types.ObjectId.isValid(userId)) {
      if (req.file?.path) fs.promises.unlink(req.file.path).catch(() => {});
      return res.status(400).json({ error: 'Valid userId is required.' });
    }

    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded. Use field name "profilePicture".' });
    }

    const relativePath = path.posix.join('uploads', req.file.filename);

    const user = await User.findById(userId).select('profilePicturePath').lean();
    if (!user) {
      fs.promises.unlink(req.file.path).catch(() => {});
      return res.status(404).json({ error: 'User not found.' });
    }

    await User.updateOne({ _id: userId }, { $set: { profilePicturePath: relativePath } });

    if (user.profilePicturePath) {
      const oldAbsolute = path.resolve(process.cwd(), user.profilePicturePath);
      if (oldAbsolute.startsWith(UPLOADS_DIR + path.sep)) {
        fs.promises.unlink(oldAbsolute).catch(() => {});
      }
    }

    return res.status(200).json({ profilePicturePath: relativePath });
  } catch (err) {
    if (req.file?.path) fs.promises.unlink(req.file.path).catch(() => {});
    next(err);
  }
});

router.use((err, req, res, next) => {
  if (err instanceof multer.MulterError) {
    const status = err.code === 'LIMIT_FILE_SIZE' ? 413 : 400;
    return res.status(status).json({ error: err.message || 'Upload failed.' });
  }
  return res.status(500).json({ error: 'Internal server error.' });
});

module.exports = router;
