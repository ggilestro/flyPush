"""Subscription plan configuration and helpers."""

from app.db.models import PlanTier, SubscriptionStatus

# Max users per plan (None = unlimited)
PLAN_LIMITS: dict[PlanTier, int | None] = {
    PlanTier.LIGHT: 5,
    PlanTier.PRO: None,
    PlanTier.LIFE: None,
}

PLAN_DISPLAY_NAMES: dict[PlanTier, str] = {
    PlanTier.LIGHT: "Light",
    PlanTier.PRO: "Pro",
    PlanTier.LIFE: "Life",
}

# Yearly price in GBP (None = not purchasable)
PLAN_PRICES: dict[PlanTier, int | None] = {
    PlanTier.LIGHT: 120,
    PlanTier.PRO: 240,
    PlanTier.LIFE: None,
}


def get_max_users(
    plan: PlanTier,
    subscription_status: SubscriptionStatus,
    override: int | None = None,
) -> int | None:
    """Return the effective max-user limit for a tenant.

    Args:
        plan: The tenant's plan tier.
        subscription_status: The tenant's subscription status.
        override: Optional per-tenant manual override.

    Returns:
        int | None: Max users allowed, or None for unlimited.
    """
    if override is not None:
        return override
    # Trialing tenants get unlimited (Pro-level) access
    if subscription_status == SubscriptionStatus.TRIALING:
        return None
    return PLAN_LIMITS.get(plan)


def check_user_limit(
    plan: PlanTier,
    subscription_status: SubscriptionStatus,
    current_count: int,
    override: int | None = None,
) -> None:
    """Raise ValueError if adding another user would exceed the plan limit.

    Args:
        plan: The tenant's plan tier.
        subscription_status: The tenant's subscription status.
        current_count: Current number of users in the tenant.
        override: Optional per-tenant manual override.

    Raises:
        ValueError: If user limit would be exceeded.
    """
    limit = get_max_users(plan, subscription_status, override)
    if limit is not None and current_count >= limit:
        plan_name = PLAN_DISPLAY_NAMES.get(plan, plan.value)
        raise ValueError(
            f"Your {plan_name} plan allows a maximum of {limit} users. "
            "Please upgrade your plan or contact support to add more members."
        )
