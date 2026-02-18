const express = require('express');
const mongoose = require('mongoose');
const router = express.Router();

const Order = mongoose.model('Order', {
  _id: mongoose.Schema.Types.ObjectId,
  status: String
});

router.post('/api/webhooks/payment', express.json(), async (req, res) => {
  try {
    const { type, data } = req.body;
    if (!type || !data) {
      return res.status(400).send('Invalid webhook event');
    }

    const orderId = data.order_id;
    const order = await Order.findById(orderId);
    if (!order) {
      return res.status(404).send(`Order ${orderId} not found`);
    }

    switch (type) {
      case 'payment.success':
        order.status = 'paid';
        break;
      case 'payment.failed':
        order.status = 'payment_failed';
        break;
      // Add more cases for other event types as needed
      default:
        return res.status(400).send(`Unsupported event type: ${type}`);
    }

    await order.save();
    res.send(`Order ${orderId} updated to ${order.status}`);
  } catch (error) {
    console.error(error);
    res.status(500).send('Internal Server Error');
  }
});

module.exports = router;
