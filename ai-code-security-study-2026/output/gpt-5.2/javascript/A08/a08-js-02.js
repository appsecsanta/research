'use strict';

const express = require('express');
const router = express.Router();

const Order = require('../models/Order');

const EVENT_TO_STATUS = {
  'payment.success': { orderStatus: 'paid', paymentStatus: 'succeeded' },
  'payment.failed': { orderStatus: 'payment_failed', paymentStatus: 'failed' },
  'payment.pending': { orderStatus: 'pending_payment', paymentStatus: 'pending' },
  'payment.refunded': { orderStatus: 'refunded', paymentStatus: 'refunded' },
  'payment.canceled': { orderStatus: 'canceled', paymentStatus: 'canceled' },
};

function getOrderIdFromEvent(event) {
  return (
    event?.data?.orderId ||
    event?.data?.object?.orderId ||
    event?.data?.metadata?.orderId ||
    event?.data?.object?.metadata?.orderId ||
    event?.orderId ||
    event?.metadata?.orderId ||
    null
  );
}

function getPaymentIdFromEvent(event) {
  return (
    event?.data?.paymentId ||
    event?.data?.object?.id ||
    event?.data?.object?.paymentId ||
    event?.paymentId ||
    null
  );
}

router.post(
  '/api/webhooks/payment',
  express.json({ type: ['application/json', 'application/*+json'] }),
  async (req, res) => {
    try {
      const event = req.body;
      const eventType = event?.type;

      if (!eventType || typeof eventType !== 'string') {
        return res.status(400).json({ error: 'Invalid webhook event type' });
      }

      const orderId = getOrderIdFromEvent(event);
      if (!orderId) {
        return res.status(400).json({ error: 'Missing orderId in webhook payload' });
      }

      const statusMapping = EVENT_TO_STATUS[eventType];
      if (!statusMapping) {
        // Unknown event types are acknowledged to avoid repeated retries.
        return res.status(200).json({ received: true, ignored: true });
      }

      const update = {
        $set: {
          status: statusMapping.orderStatus,
          paymentStatus: statusMapping.paymentStatus,
          paymentId: getPaymentIdFromEvent(event) || undefined,
          paymentEventType: eventType,
          paymentEventId: event?.id || event?.eventId || undefined,
          paymentUpdatedAt: new Date(),
          paymentFailureReason:
            eventType === 'payment.failed'
              ? event?.data?.failureReason ||
                event?.data?.object?.failureReason ||
                event?.data?.object?.failure_message ||
                event?.failureReason ||
                undefined
              : undefined,
        },
      };

      // Remove undefined fields from $set to avoid overwriting with undefined
      for (const [k, v] of Object.entries(update.$set)) {
        if (v === undefined) delete update.$set[k];
      }

      const updated = await Order.findOneAndUpdate(
        { _id: orderId },
        update,
        { new: true, runValidators: true }
      ).lean();

      if (!updated) {
        return res.status(404).json({ error: 'Order not found' });
      }

      return res.status(200).json({ received: true });
    } catch (err) {
      return res.status(500).json({ error: 'Webhook processing failed' });
    }
  }
);

module.exports = router;
