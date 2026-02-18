const express = require('express');
const mongoose = require('mongoose');

// Coupon Schema
const couponSchema = new mongoose.Schema({
  code: {
    type: String,
    required: true,
    unique: true,
    uppercase: true,
    trim: true,
  },
  discountType: {
    type: String,
    required: true,
    enum: ['percentage', 'fixed'],
  },
  discountValue: {
    type: Number,
    required: true,
    min: 0,
  },
  minCartTotal: {
    type: Number,
    default: 0,
    min: 0,
  },
  maxDiscountAmount: {
    type: Number,
    default: null,
  },
  isActive: {
    type: Boolean,
    default: true,
  },
  expiresAt: {
    type: Date,
    default: null,
  },
  usageLimit: {
    type: Number,
    default: null,
  },
  usageCount: {
    type: Number,
    default: 0,
  },
}, { timestamps: true });

const Coupon = mongoose.model('Coupon', couponSchema);

// Express app setup
const app = express();
app.use(express.json());

// MongoDB connection
const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017/coupon-service';

mongoose.connect(MONGO_URI)
  .then(() => console.log('Connected to MongoDB'))
  .catch((err) => console.error('MongoDB connection error:', err));

// POST /api/apply-coupon
app.post('/api/apply-coupon', async (req, res) => {
  try {
    const { couponCode, cartTotal } = req.body;

    // Validate request body
    if (!couponCode || typeof couponCode !== 'string') {
      return res.status(400).json({
        success: false,
        message: 'A valid coupon code is required.',
      });
    }

    if (cartTotal == null || typeof cartTotal !== 'number' || cartTotal < 0) {
      return res.status(400).json({
        success: false,
        message: 'A valid cart total (non-negative number) is required.',
      });
    }

    // Look up coupon in database
    const coupon = await Coupon.findOne({
      code: couponCode.toUpperCase().trim(),
    });

    if (!coupon) {
      return res.status(404).json({
        success: false,
        message: 'Coupon not found.',
      });
    }

    // Check if coupon is active
    if (!coupon.isActive) {
      return res.status(400).json({
        success: false,
        message: 'This coupon is no longer active.',
      });
    }

    // Check expiration
    if (coupon.expiresAt && new Date() > coupon.expiresAt) {
      return res.status(400).json({
        success: false,
        message: 'This coupon has expired.',
      });
    }

    // Check usage limit
    if (coupon.usageLimit !== null && coupon.usageCount >= coupon.usageLimit) {
      return res.status(400).json({
        success: false,
        message: 'This coupon has reached its usage limit.',
      });
    }

    // Check minimum cart total
    if (cartTotal < coupon.minCartTotal) {
      return res.status(400).json({
        success: false,
        message: `Minimum cart total of $${coupon.minCartTotal.toFixed(2)} is required to use this coupon.`,
      });
    }

    // Calculate discount
    let discountAmount = 0;

    if (coupon.discountType === 'percentage') {
      discountAmount = (cartTotal * coupon.discountValue) / 100;

      // Apply max discount cap if set
      if (coupon.maxDiscountAmount !== null && discountAmount > coupon.maxDiscountAmount) {
        discountAmount = coupon.maxDiscountAmount;
      }
    } else if (coupon.discountType === 'fixed') {
      discountAmount = coupon.discountValue;
    }

    // Ensure discount doesn't exceed cart total
    discountAmount = Math.min(discountAmount, cartTotal);

    // Round to 2 decimal places
    discountAmount = Math.round(discountAmount * 100) / 100;
    const discountedTotal = Math.round((cartTotal - discountAmount) * 100) / 100;

    // Increment usage count
    await Coupon.findByIdAndUpdate(coupon._id, {
      $inc: { usageCount: 1 },
    });

    return res.status(200).json({
      success: true,
      message: 'Coupon applied successfully.',
      data: {
        couponCode: coupon.code,
        discountType: coupon.discountType,
        discountValue: coupon.discountValue,
        originalTotal: cartTotal,
        discountAmount,
        discountedTotal,
      },
    });
  } catch (error) {
    console.error('Error applying coupon:', error);
    return res.status(500).json({
      success: false,
      message: 'Internal server error.',
    });
  }
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

module.exports = { app, Coupon };
