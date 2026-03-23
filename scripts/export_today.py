"""
scripts/export_today.py — Manual one-shot export for today's bookings.

Usage: python scripts/export_today.py [YYYY-MM-DD]
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date


async def main() -> None:
    from app.db.session import AsyncSessionLocal
    from app.exports.excel_exporter import generate_daily_export

    if len(sys.argv) > 1:
        export_date = date.fromisoformat(sys.argv[1])
    else:
        import pytz
        from datetime import datetime
        export_date = datetime.now(pytz.timezone("Africa/Casablanca")).date()

    print(f"Exporting bookings for {export_date}...")
    async with AsyncSessionLocal() as session:
        path = await generate_daily_export(session, export_date)
        await session.commit()
    if path:
        print(f"✅ Export saved to: {path}")
    else:
        print("❌ Export failed — check logs.")


if __name__ == "__main__":
    asyncio.run(main())
