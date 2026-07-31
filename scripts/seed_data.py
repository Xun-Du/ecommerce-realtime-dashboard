"""Create deterministic historical M1 Demo data in Supabase."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

from backend.app.core.database import initialize_database, reset_demo_data, write_batch
from scripts.data_generator import generate_batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic ecommerce demo data.")
    parser.add_argument(
        "--days", type=int, default=14, help="Historical window in days (default: 14)."
    )
    parser.add_argument(
        "--users", type=int, default=10_000, help="Users to generate (default: 10000)."
    )
    parser.add_argument(
        "--seed", type=int, default=20260731, help="Random seed (default: 20260731)."
    )
    parser.add_argument(
        "--b-uplift", type=float, default=0.20, help="B-group purchase uplift (default: 0.20)."
    )
    parser.add_argument(
        "--end-at",
        help="ISO 8601 window end in UTC; set it for reproducible runs.",
    )
    parser.add_argument(
        "--reset", action="store_true", help="Delete M1 Demo tables before generating data."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.days <= 0 or args.users <= 0:
        raise SystemExit("--days 和 --users 必须为正整数。")
    if args.b_uplift < 0:
        raise SystemExit("--b-uplift 不能为负数。")

    initialize_database()
    if args.reset:
        reset_demo_data()
        initialize_database()

    end_at = (
        datetime.fromisoformat(args.end_at).astimezone(UTC) if args.end_at else datetime.now(UTC)
    )
    start_at = end_at - timedelta(days=args.days)
    batch = generate_batch(
        start_at=start_at,
        end_at=end_at,
        user_count=args.users,
        seed=args.seed,
        b_uplift=args.b_uplift,
    )
    write_batch(batch)
    counts = batch.event_counts()
    group_counts = batch.experiment_counts()
    click_users = {event.user_id for event in batch.events if event.event_type == "click"}
    buy_users = {event.user_id for event in batch.events if event.event_type == "buy"}
    conversion = len(buy_users) / len(click_users) if click_users else 0
    print(
        "种子数据写入完成："
        f"users={len(batch.users)}, click={counts['click']}, "
        f"add_to_cart={counts['add_to_cart']}, buy={counts['buy']}, "
        f"A_click={group_counts['A']}, B_click={group_counts['B']}, "
        f"overall_conversion={conversion:.2%}"
    )


if __name__ == "__main__":
    main()
