#!/usr/bin/env python3
"""
CLI Value-Based Pricing, Agency Floor-Price, and Vendor Tier Break-Even Calculator.
Run: python3 scripts/roi_and_pricing_calculator.py
"""

def calculate_agency_floor_price(
    monthly_fulfillment_hours: float,
    target_hourly_rate_usd: float,
    base_tool_and_usage_cost_usd: float,
) -> float:
    """
    Formula: [(Monthly Fulfillment Hours * Target Hourly Rate) + (Base Tool & Usage Costs * 1.20)] * 1.30
    """
    buffered_tools = base_tool_and_usage_cost_usd * 1.20
    labor = monthly_fulfillment_hours * target_hourly_rate_usd
    return round((labor + buffered_tools) * 1.30, 2)


def calculate_client_roi_and_value_price(
    missed_calls_per_week: int,
    avg_ticket_value_usd: float,
    close_rate: float = 0.25,
    conservative_recovery_rate: float = 0.30,
    agency_value_capture_share: float = 0.25,
) -> dict:
    monthly_missed_calls = missed_calls_per_week * 4.33
    monthly_lost_revenue = monthly_missed_calls * avg_ticket_value_usd * close_rate
    monthly_recovered_revenue = monthly_lost_revenue * conservative_recovery_rate
    recommended_retainer = monthly_recovered_revenue * agency_value_capture_share
    return {
        "monthly_missed_calls": round(monthly_missed_calls, 1),
        "monthly_lost_revenue_usd": round(monthly_lost_revenue, 2),
        "projected_monthly_recovered_usd": round(monthly_recovered_revenue, 2),
        "recommended_value_retainer_usd": round(recommended_retainer, 2),
        "client_net_roi_multiple": round(monthly_recovered_revenue / max(recommended_retainer, 1), 2),
    }


def evaluate_bland_tier_trap(monthly_minutes: int) -> dict:
    """
    Demonstrates the vendor subscription upgrade trap:
    - Start (Free): $0/mo + $0.14/min
    - Build ($299/mo): $299/mo + $0.12/min (Break-even vs Start = 14,950 mins)
    - Scale ($499/mo): $499/mo + $0.11/min (Break-even vs Build = 20,000 mins)
    """
    start_cost = monthly_minutes * 0.14
    build_cost = 299.0 + (monthly_minutes * 0.12)
    scale_cost = 499.0 + (monthly_minutes * 0.11)
    optimal = min(
        [("Start (Free)", start_cost), ("Build ($299/mo)", build_cost), ("Scale ($499/mo)", scale_cost)],
        key=lambda x: x[1],
    )
    return {
        "monthly_minutes": monthly_minutes,
        "start_tier_total_usd": round(start_cost, 2),
        "build_tier_total_usd": round(build_cost, 2),
        "scale_tier_total_usd": round(scale_cost, 2),
        "optimal_tier": optimal[0],
    }


if __name__ == "__main__":
    print("=== 1. AGENCY MINIMUM VIABLE FLOOR PRICE ===")
    floor = calculate_agency_floor_price(
        monthly_fulfillment_hours=8,
        target_hourly_rate_usd=100,
        base_tool_and_usage_cost_usd=166.67,
    )
    print(f"Minimum Monthly Floor Retainer (8 hrs @ $100/hr + $200 buffered tools): ${floor:,.2f}/mo\n")

    print("=== 2. LIVE DISCOVERY CALL VALUE-BASED PRICING MATH ===")
    roi = calculate_client_roi_and_value_price(
        missed_calls_per_week=15,
        avg_ticket_value_usd=850.0,
        close_rate=0.25,
        conservative_recovery_rate=0.35,
        agency_value_capture_share=0.25,
    )
    for k, v in roi.items():
        print(f"  {k}: {v}")

    print("\n=== 3. VENDOR TIER BREAK-EVEN AUDIT (5,000 Monthly Minutes) ===")
    trap = evaluate_bland_tier_trap(5000)
    for k, v in trap.items():
        print(f"  {k}: {v}")
