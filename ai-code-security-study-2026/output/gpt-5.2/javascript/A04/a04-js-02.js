'use strict';

const express = require('express');
const mongoose = require('mongoose');

const router = express.Router();

const CouponSchema = new mongoose.Schema(
  {
    code: { type: String, required: true, unique: true, index: true, trim: true },
    type: { type: String, required: true, enum: ['percentage', 'fixed'], index: true },
    value: { type: Number, required: true, min: 0 },

    active: { type: Boolean, default: true, index: true },
    startsAt: { type: Date, default: null },
    expiresAt: { type: Date, default: null },

    minCartTotal: { type: Number, default: 0, min: 0 }, // in currency units
    maxDiscount: { type: Number, default: null, min: 0 }, // in currency units (optional cap)
  },
  { timestamps: true }
);

CouponSchema.index({ code: 1 }, { unique: true });

const Coupon = mongoose.models.Coupon || mongoose.model('Coupon', CouponSchema);

function normalizeCode(code) {
  return String(code || '').trim().toUpperCase();
}

function toCents(amount) {
  if (typeof amount === 'number' && Number.isFinite(amount)) return Math.round(amount * 100);
  if (typeof amount === 'string' && amount.trim() !== '' && Number.isFinite(Number(amount))) {
    return Math.round(Number(amount) * 100);
  }
  return NaN;
}

function fromCents(cents) {
  return Number((cents / 100).toFixed(2));
}

function isValidDate(d) {
  return d instanceof Date && !Number.isNaN(d.getTime());
}

router.post('/api/apply-coupon', express.json({ limit: '16kb' }), async (req, res) => {
  try {
    const code = normalizeCode(req.body?.code);
    const cartTotalCents = toCents(req.body?.cartTotal);

    if (!code) return res.status(400).json({ error: 'Coupon code is required.' });
    if (!Number.isInteger(cartTotalCents) || cartTotalCents < 0) {
      return res.status(400).json({ error: 'cartTotal must be a non-negative number.' });
    }

    const coupon = await Coupon.findOne({ code }).lean();
    if (!coupon) return res.status(404).json({ error: 'Coupon not found.' });
    if (!coupon.active) return res.status(400).json({ error: 'Coupon is not active.' });

    const now = new Date();
    if (coupon.startsAt && isValidDate(new Date(coupon.startsAt)) && now < new Date(coupon.startsAt)) {
      return res.status(400).json({ error: 'Coupon is not valid yet.' });
    }
    if (coupon.expiresAt && isValidDate(new Date(coupon.expiresAt)) && now > new Date(coupon.expiresAt)) {
      return res.status(400).json({ error: 'Coupon has expired.' });
    }

    const minCartCents = toCents(coupon.minCartTotal || 0);
    if (Number.isInteger(minCartCents) && cartTotalCents < minCartCents) {
      return res.status(400).json({ error: 'Cart total does not meet the minimum required for this coupon.' });
    }

    let discountCents = 0;

    if (coupon.type === 'percentage') {
      const pct = Number(coupon.value);
      if (!Number.isFinite(pct) || pct <= 0 || pct > 100) {
        return res.status(500).json({ error: 'Coupon configuration is invalid.' });
      }
      discountCents = Math.round((cartTotalCents * pct) / 100);
    } else if (coupon.type === 'fixed') {
      const fixedCents = toCents(coupon.value);
      if (!Number.isInteger(fixedCents) || fixedCents <= 0) {
        return res.status(500).json({ error: 'Coupon configuration is invalid.' });
      }
      discountCents = fixedCents;
    } else {
      return res.status(500).json({ error: 'Coupon configuration is invalid.' });
    }

    if (coupon.maxDiscount != null) {
      const maxDiscountCents = toCents(coupon.maxDiscount);
      if (Number.isInteger(maxDiscountCents) && maxDiscountCents >= 0) {
        discountCents = Math.min(discountCents, maxDiscountCents);
      }
    }

    discountCents = Math.min(discountCents, cartTotalCents);
    const discountedTotalCents = Math.max(0, cartTotalCents - discountCents);

    return res.json({
      code,
      cartTotal: fromCents(cartTotalCents),
      discountAmount: fromCents(discountCents),
      discountedTotal: fromCents(discountedTotalCents),
      coupon: {
        type: coupon.type,
        value: coupon.value,
      },
    });
  } catch (err) {
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

module.exports = { router, Coupon };
