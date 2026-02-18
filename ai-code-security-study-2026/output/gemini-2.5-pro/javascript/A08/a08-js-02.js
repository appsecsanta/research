/*
 * /api/webhooks/webhook.controller.js
 *
 * The controller that contains the business logic for handling
 * different types of payment webhook events.
 */

const Order = require('../../models/Order.model');

/**
 * Processes a payment success event.
 * @param {object} eventData - The data object from the webhook event.
 */
const processPaymentSuccess = async (eventData) => {
  const { paymentIntentId, amount, currency, metadata } = eventData;

  // Find the corresponding order in the database
  const order = await Order.findOne({ paymentIntentId });

  if (!order) {
    // This could happen if the order creation failed but the payment went through.
    // Log this for manual investigation.
    console.error(`Order not found for successful paymentIntentId: ${paymentIntentId}`);
    // Depending on business logic, you might create a new order here.
    return;
  }

  // Idempotency check: If the order is already completed, do nothing.
  if (order.status === 'completed') {
    console.log(`Order ${order._id} is already completed. Ignoring duplicate event.`);
    return;
  }

  // Update the order status to 'completed'
  order.status = 'completed';
  order.paymentDetails = eventData; // Store the full event data for reference
  await order.save();

  console.log(`Order ${order._id} status updated to 'completed'.`);
  // Here you would typically trigger other business logic,
  // like sending a confirmation email, dispatching the order, etc.
};

/**
 * Processes a payment failure event.
 * @param {object} eventData - The data object from the webhook event.
 */
const processPaymentFailure = async (eventData) => {
  const { paymentIntentId, failureReason } = eventData;

  const order = await Order.findOne({ paymentIntentId });

  if (!order) {
    console.error(`Order not found for failed paymentIntentId: ${paymentIntentId}`);
    return;
  }

  // Idempotency check
  if (order.status === 'failed') {
    console.log(`Order ${order._id} is already marked as failed. Ignoring duplicate event.`);
    return;
  }

  order.status = 'failed';
  order.paymentDetails = { failureReason, ...eventData };
  await order.save();

  console.log(`Order ${order._id} status updated to 'failed'. Reason: ${failureReason}`);
  // Here you might trigger logic to notify the customer that their payment failed.
};


/**
 * Main handler for all incoming payment webhooks.
 */
const handlePaymentWebhook = async (req, res) => {
  const event = req.body;

  // Basic validation of the event payload
  if (!event || !event.type || !event.data || !event.data.object) {
    console.error('Invalid webhook event structure received:', event);
    return res.status(400).json({ error: 'Invalid event structure.' });
  }

  console.log(`Received webhook event: ${event.type}`);

  try {
    // Route the event to the appropriate handler based on its type
    switch (event.type) {
      case 'payment.success':
        await processPaymentSuccess(event.data.object);
        break;

      case 'payment.failed':
        await processPaymentFailure(event.data.object);
        break;

      // Add other event types as needed
      // case 'payment.refunded':
      //   await processPaymentRefund(event.data.object);
      //   break;

      default:
        console.log(`Unhandled event type: ${event.type}`);
    }

    // Acknowledge receipt of the event to the payment processor
    res.status(200).json({ received: true });

  } catch (error) {
    console.error(`Error processing webhook event ${event.id}:`, error);
    // Send a 500 error to indicate a problem on our end.
    // The payment processor may try to resend the webhook.
    res.status(500).json({ error: 'Internal server error while processing webhook.' });
  }
};

module.exports = { handlePaymentWebhook };
