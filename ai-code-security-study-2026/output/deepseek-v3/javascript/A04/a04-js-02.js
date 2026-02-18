const express = require('express');
const mongoose = require('mongoose');
const router = express.Router();

const Coupon = mongoose.model('Coupon', new mongoose.Schema({
  code: { type: String, required: true, unique: true },
  type: { type: String, enum: ['percentage', 'fixed'], required: true },
  value: { type: Number, required: true },
  isActive: { type: Boolean, default: true }
}));

router.post('/api/apply-coupon', async (req, res) => {
  const { couponCode, cartTotal } = req.body;

  if (!couponCode || !cartTotal) {
    return res.status(400).json({ error: 'Coupon code and cart total are required' });
  }

  try {
    const coupon = await Coupon.findOne({ code: couponCode, isActive: true });

    if (!coupon) {
      return res.status(404).json({ error: 'Invalid or inactive coupon' });
    }

    let discountedTotal = cartTotal;

    if (coupon.type === 'percentage') {
      discountedTotal = cartTotal * (1 - coupon.value / 100);
    } else if (coupon.type === 'fixed') {
      discountedTotal = cartTotal - coupon.value;
    }

    if (discountedTotal < 0) {
      discountedTotal = 0;
    }

    res.json({ discountedTotal });
  } catch (error) {
    res.status(500).json({ error: 'An error occurred while applying the coupon' });
  }
});

module.exports = router;
