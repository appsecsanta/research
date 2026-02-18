const express = require('express');
const mongoose = require('mongoose');
const multer = require('multer');
const path = require('path');
const fs = require('fs');

// --- Environment Configuration ---
const PORT = process.env.PORT || 3000;
const MONGO_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/user-uploads-db';
const UPLOADS_FOLDER = 'uploads';
const UPLOADS_DIR = path.join(__dirname, UPLOADS_FOLDER);

// Ensure the uploads directory exists
if (!fs.existsSync(UPLOADS_DIR)) {
    fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}

// --- Express App Initialization ---
const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve uploaded files statically
app.use(`/${UPLOADS_FOLDER}`, express.static(UPLOADS_DIR));

// --- Database Connection ---
mongoose.connect(MONGO_URI, {
    useNewUrlParser: true,
    useUnifiedTopology: true,
})
.then(() => console.log('MongoDB connected successfully.'))
.catch(err => {
    console.error('MongoDB connection error:', err);
    process.exit(1);
});

// --- Mongoose Schema and Model ---
const UserSchema = new mongoose.Schema({
    name: {
        type: String,
        required: true,
    },
    email: {
        type: String,
        required: true,
        unique: true,
        trim: true,
        lowercase: true,
    },
    profilePicture: {
        type: String,
        default: '',
    },
}, { timestamps: true });

const User = mongoose.model('User', UserSchema);

// --- Multer Configuration ---
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, UPLOADS_DIR);
    },
    filename: (req, file, cb) => {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        const extension = path.extname(file.originalname);
        cb(null, `${file.fieldname}-${uniqueSuffix}${extension}`);
    },
});

const fileFilter = (req, file, cb) => {
    const allowedMimeTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (allowedMimeTypes.includes(file.mimetype)) {
        cb(null, true);
    } else {
        cb(new Error('Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed.'), false);
    }
};

const upload = multer({
    storage: storage,
    limits: {
        fileSize: 1024 * 1024 * 5, // 5MB file size limit
    },
    fileFilter: fileFilter,
});

// --- Middleware ---

// Mock authentication middleware to simulate a logged-in user.
// In a real application, this would involve token verification (e.g., JWT).
const mockAuth = async (req, res, next) => {
    try {
        // For demonstration, we'll find or create a default user.
        const email = 'testuser@example.com';
        let user = await User.findOne({ email });
        if (!user) {
            user = await User.create({ name: 'Test User', email });
        }
        req.user = user; // Attach user to the request object
        next();
    } catch (error) {
        res.status(500).json({ message: 'Authentication simulation failed', error: error.message });
    }
};

// --- API Routes ---

/**
 * @route   POST /api/upload
 * @desc    Uploads a user's profile picture.
 * @access  Private (simulated via mockAuth)
 */
app.post(
    '/api/upload',
    mockAuth,
    upload.single('profilePicture'),
    async (req, res, next) => {
        try {
            if (!req.file) {
                return res.status(400).json({ message: 'No file was uploaded.' });
            }

            const user = await User.findById(req.user.id);
            if (!user) {
                return res.status(404).json({ message: 'User not found.' });
            }

            // Construct the publicly accessible URL path
            const filePath = `/${UPLOADS_FOLDER}/${req.file.filename}`;
            user.profilePicture = filePath;
            await user.save();

            res.status(200).json({
                message: 'Profile picture uploaded successfully.',
                user: {
                    id: user._id,
                    name: user.name,
                    email: user.email,
                    profilePicture: user.profilePicture,
                },
            });
        } catch (error) {
            // Pass error to the global error handler
            next(error);
        }
    }
);

// --- Global Error Handler ---
app.use((err, req, res, next) => {
    console.error(err);

    if (err instanceof multer.MulterError) {
        if (err.code === 'LIMIT_FILE_SIZE') {
            return res.status(400).json({ message: 'File is too large. Maximum size is 5MB.' });
        }
        return res.status(400).json({ message: err.message });
    }

    if (err.message.startsWith('Invalid file type')) {
        return res.status(400).json({ message: err.message });
    }

    res.status(500).json({ message: 'An internal server error occurred.', error: err.message });
});

// --- Server Start ---
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
    console.log(`Uploads will be saved to: ${UPLOADS_DIR}`);
});
