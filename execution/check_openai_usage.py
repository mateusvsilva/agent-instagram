"""
check_openai_usage.py
---------------------
Layer 3 - Execution Script

Fetch OpenAI organization costs and token usage for a date range.

Usage:
    python execution/check_openai_usage.py
    python execution/check_openai_usage.py --days 7
    python execution/check_openai_usage.py --start-date 2026-02-01 --end-date 2026-02-22

Required env:
    OPENAI_ADMIN_API_KEY

Optional env:
    OPENAI_ORG_ID

Output:
    .tmp/openai_usage.json

Notes:
    - Costs and usage use official organization endpoints.
    - Credit balance endpoint availability can vary by account and may return unavailable.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

OUTPUT_PATH = Path(".tmp/openai_usage.json")
BASE_URL = "https://api.openai.com/v1"


def parse_iso_date(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format.") from exc


def to_unix_seconds_start(value: date) -> int:
    dt = datetime.combine(value, time.min, tzinfo=timezone.utc)
    return int(dt.timestamp())


def to_unix_seconds_end_exclusive(value: date) -> int:
    next_day = value + timedelta(days=1)
    dt = datetime.combine(next_day, time.min, tzinfo=timezone.utc)
    return int(dt.timestamp())


def get_env(key: str, required: bool = True) -> str:
    raw = os.getenv(key, "").strip()
    if required and not raw:
        console.print(f"[red]Missing environment variable: {key}[/red]")
        sys.exit(1)
    return raw


def build_headers(admin_key: str, org_id: str | None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {admin_key}",
        "Content-Type": "application/json",
    }
    if org_id:
        headers["OpenAI-Organization"] = org_id
    return headers


def get_json(url: str, headers: dict[str, str], params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError:
            payload = {"error": {"message": response.text}}
        message = payload.get("error", {}).get("message", "Unknown OpenAI API error.")
        raise RuntimeError(f"OpenAI API request failed ({response.status_code}): {message}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("OpenAI API returned invalid JSON.") from exc


def fetch_costs(headers: dict[str, str], start_time: int, end_time: int) -> dict[str, Any]:
    return get_json(
        f"{BASE_URL}/organization/costs",
        headers=headers,
        params={
            "start_time": start_time,
            "end_time": end_time,
            "bucket_width": "1d",
            "limit": 31,
        },
    )


def fetch_completions_usage(headers: dict[str, str], start_time: int, end_time: int) -> dict[str, Any]:
    return get_json(
        f"{BASE_URL}/organization/usage/completions",
        headers=headers,
        params={
            "start_time": start_time,
            "end_time": end_time,
            "bucket_width": "1d",
            "limit": 31,
            "group_by[]": "model",
        },
    )


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def sum_cost_usd(costs_payload: dict[str, Any]) -> float:
    total = 0.0
    for bucket in costs_payload.get("data", []):
        results = bucket.get("results", [])
        for result in results:
            total += safe_float(result.get("amount", {}).get("value"))
    return total


def sum_tokens(usage_payload: dict[str, Any]) -> dict[str, int]:
    input_tokens = 0
    output_tokens = 0
    cached_input_tokens = 0
    total_requests = 0

    for bucket in usage_payload.get("data", []):
        results = bucket.get("results", [])
        for result in results:
            input_tokens += int(result.get("input_tokens", 0) or 0)
            output_tokens += int(result.get("output_tokens", 0) or 0)
            cached_input_tokens += int(result.get("input_cached_tokens", 0) or 0)
            total_requests += int(result.get("num_model_requests", 0) or 0)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "total_tokens": input_tokens + output_tokens,
        "num_model_requests": total_requests,
    }


def fetch_credit_balance_if_available(admin_headers: dict[str, str]) -> dict[str, Any]:
    """
    Try to fetch credit balance.
    This endpoint may be unavailable depending on account type/permissions.
    """
    # Try with admin headers first.
    attempts = [
        {
            "headers": admin_headers,
            "label": "admin_key",
        },
        {
            "headers": {
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '').strip()}",
                "Content-Type": "application/json",
            },
            "label": "api_key",
        },
    ]

    for attempt in attempts:
        auth_header = attempt["headers"].get("Authorization", "")
        if not auth_header or auth_header.endswith("Bearer "):
            continue

        try:
            resp = requests.get(
                "https://api.openai.com/dashboard/billing/credit_grants",
                headers=attempt["headers"],
                timeout=20,
            )
            if resp.status_code >= 400:
                continue
            payload = resp.json()
            total_granted = safe_float(payload.get("total_granted"))
            total_used = safe_float(payload.get("total_used"))
            total_available = safe_float(payload.get("total_available"))
            return {
                "available_usd": round(total_available, 6),
                "used_usd": round(total_used, 6),
                "granted_usd": round(total_granted, 6),
                "source": f"credit_grants/{attempt['label']}",
            }
        except (requests.RequestException, ValueError):
            continue

    return {
        "available_usd": None,
        "used_usd": None,
        "granted_usd": None,
        "source": "unavailable",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check OpenAI organization costs and usage.")
    parser.add_argument("--days", type=int, default=30, help="Rolling window in days (default: 30).")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD).")
    args = parser.parse_args()

    if args.start_date and not args.end_date:
        raise ValueError("--end-date is required when --start-date is provided.")
    if args.end_date and not args.start_date:
        raise ValueError("--start-date is required when --end-date is provided.")
    if args.days <= 0:
        raise ValueError("--days must be >= 1.")

    if args.start_date and args.end_date:
        start_d = parse_iso_date(args.start_date, "--start-date")
        end_d = parse_iso_date(args.end_date, "--end-date")
        if end_d < start_d:
            raise ValueError("--end-date must be on or after --start-date.")
    else:
        end_d = datetime.now(timezone.utc).date()
        start_d = end_d - timedelta(days=args.days - 1)

    start_time = to_unix_seconds_start(start_d)
    end_time = to_unix_seconds_end_exclusive(end_d)

    admin_key = get_env("OPENAI_ADMIN_API_KEY", required=True)
    org_id = get_env("OPENAI_ORG_ID", required=False) or None
    headers = build_headers(admin_key, org_id)

    console.print(
        f"[cyan]Fetching OpenAI usage from {start_d.isoformat()} to {end_d.isoformat()} (UTC)...[/cyan]"
    )

    costs_payload = fetch_costs(headers, start_time, end_time)
    usage_payload = fetch_completions_usage(headers, start_time, end_time)

    totals = {
        "cost_usd": round(sum_cost_usd(costs_payload), 6),
        **sum_tokens(usage_payload),
    }
    credits = fetch_credit_balance_if_available(headers)

    result = {
        "window": {
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "start_time_unix": start_time,
            "end_time_unix_exclusive": end_time,
        },
        "totals": totals,
        "credits": credits,
        "costs_raw": costs_payload,
        "usage_raw": usage_payload,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    console.print(f"[green]Saved: {OUTPUT_PATH}[/green]")
    console.print(f"[bold]Total cost (USD):[/bold] {totals['cost_usd']}")
    console.print(f"[bold]Input tokens:[/bold] {totals['input_tokens']}")
    console.print(f"[bold]Output tokens:[/bold] {totals['output_tokens']}")
    console.print(f"[bold]Total tokens:[/bold] {totals['total_tokens']}")
    console.print(f"[bold]Model requests:[/bold] {totals['num_model_requests']}")
    console.print(f"[bold]Credit balance (USD):[/bold] {credits['available_usd']}")


if __name__ == "__main__":
    main()
