"""Stripe payment integration — checkout, webhook, order fulfillment."""

import logging
import os

import stripe

from gw2_progression.services.commerce_service import (
    create_order,
    mark_payment_event_failed,
    mark_payment_event_fulfilled,
    record_payment_event_received,
)
from gw2_progression.services.product_service import get_product

logger = logging.getLogger("gw2.stripe")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID_MAP = {}  # product_id -> stripe_price_id, populated by env

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


async def create_checkout_session(product_id: int, customer_email: str, success_url: str, cancel_url: str) -> str | None:
    """Create a Stripe Checkout Session and return the URL."""
    product = await get_product(product_id)
    if not product:
        return None

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=customer_email,
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": product["name"],
                            "description": product["description"][:100],
                        },
                        "unit_amount": product["price_copper"] // 100,  # copper to cents
                    },
                    "quantity": 1,
                }
            ],
            metadata={"product_id": str(product_id)},
            success_url=success_url,
            cancel_url=cancel_url,
        )
        logger.info("Stripe checkout session created: %s", session.id)
        return session.url
    except Exception as e:
        logger.warning("Stripe checkout failed: %s", e)
        return None


async def handle_webhook(payload: bytes, sig_header: str) -> str:
    """Process Stripe webhook events."""
    if not STRIPE_WEBHOOK_SECRET:
        return "webhook secret not configured"

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        return "invalid signature"

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        product_id = int(session.get("metadata", {}).get("product_id", 0))
        customer_email = session.get("customer_details", {}).get("email", "")
        if product_id and customer_email:
            idempotency_key = f"stripe:{event.get('id') or session.get('id') or product_id}"
            provider_event_id = str(event.get("id") or session.get("id") or idempotency_key)
            receipt = await record_payment_event_received(
                provider_event_id=provider_event_id,
                event_type=event["type"],
                idempotency_key=idempotency_key,
                product_id=product_id,
                customer_email=customer_email,
            )
            if receipt["status"] == "fulfilled":
                return "fulfilled"
            try:
                order = await create_order(product_id, customer_email, idempotency_key=idempotency_key)
                await mark_payment_event_fulfilled(provider_event_id, order["order_id"])
                logger.info("Order fulfilled via Stripe: %s -> license %s", order["order_id"], order["license_key"])
                return "fulfilled"
            except Exception as exc:
                await mark_payment_event_failed(provider_event_id, str(exc))
                raise

    return "received"
