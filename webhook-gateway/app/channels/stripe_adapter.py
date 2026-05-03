"""Stripe webhook channel adapter.

Handles Stripe webhook payloads for payment, invoice, subscription,
and customer events.

Reference: https://docs.stripe.com/webhooks
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class StripeAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "stripe"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        event_type = payload.get("type", "")
        data = payload.get("data", {})
        obj = data.get("object", {})

        text_parts = [f"Stripe: {event_type}"]

        # Payment
        if "payment_intent" in event_type or "charge" in event_type:
            amount = obj.get("amount", 0) / 100
            currency = obj.get("currency", "usd").upper()
            status = obj.get("status", "")
            customer = obj.get("customer", "")
            text_parts.append(f"Amount: {currency} {amount:.2f}")
            text_parts.append(f"Status: {status}")
            if customer:
                text_parts.append(f"Customer: {customer}")

        # Invoice
        elif "invoice" in event_type:
            amount = obj.get("amount_due", obj.get("total", 0)) / 100
            currency = obj.get("currency", "usd").upper()
            customer_email = obj.get("customer_email", "")
            status = obj.get("status", "")
            text_parts.append(f"Amount: {currency} {amount:.2f}")
            text_parts.append(f"Status: {status}")
            if customer_email:
                text_parts.append(f"Email: {customer_email}")

        # Subscription
        elif "subscription" in event_type:
            status = obj.get("status", "")
            plan = obj.get("plan", {})
            plan_name = plan.get("nickname", plan.get("id", "")) if isinstance(plan, dict) else ""
            text_parts.append(f"Status: {status}")
            if plan_name:
                text_parts.append(f"Plan: {plan_name}")

        # Customer
        elif "customer" in event_type:
            email = obj.get("email", "")
            name = obj.get("name", "")
            if name:
                text_parts.append(f"Name: {name}")
            if email:
                text_parts.append(f"Email: {email}")

        # Description
        description = obj.get("description", "")
        if description:
            text_parts.append(description[:500])

        return NormalizedMessage(
            channel_type="stripe",
            message_id=payload.get("id", ""),
            user_id=obj.get("customer", ""),
            text="\n".join(text_parts),
            source_type="financial",
            raw=payload,
            extra={
                "event_type": event_type,
                "object_id": obj.get("id", ""),
                "livemode": payload.get("livemode", False),
            },
        )
