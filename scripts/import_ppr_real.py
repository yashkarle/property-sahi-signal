"""
Import real PPR data for Firhouse/Killininny area into ppr_sales.
Covers D24, D16, D18 — haversine filter in ML pipeline handles proximity.
YOY growth: stored as-is; time_adjustment step in ML pipeline applies 8%/yr uplift.
"""
import asyncio
import csv
import io
import re
import uuid
from datetime import datetime

import asyncpg

DATABASE_URL = "postgresql://property_user:property_pass@localhost:5432/property_sahi"

# Centroid coords by eircode prefix — fallback when street not matched
EIRCODE_COORDS = {
    "D24": (53.2870, -6.3350),   # Firhouse / Killininny / Ballycullen
    "D16": (53.2960, -6.3200),   # Knocklyon / Rathfarnham
    "D18": (53.2870, -6.2200),   # Stillorgan / Sandyford / Leopardstown
}

# Street-level coords for D24/D16 neighbourhood
STREET_COORDS = {
    "old court":        (53.2872, -6.3348),
    "killinin":         (53.2880, -6.3360),
    "firhouse rd":      (53.2840, -6.3390),
    "firhouse road":    (53.2840, -6.3390),
    "oldcourt":         (53.2875, -6.3355),
    "ballycullen":      (53.2850, -6.3380),
    "knocklyon":        (53.2920, -6.3280),
    "templeogue":       (53.2970, -6.3230),
    "millbrook":        (53.2860, -6.3500),
    "swiftbrook":       (53.2830, -6.3420),
    "aylesbury":        (53.2920, -6.3600),
    "kilnamanagh":      (53.2980, -6.3450),
    "castletymon":      (53.2900, -6.3550),
    "tymon":            (53.2890, -6.3520),
    "ellensborough":    (53.2870, -6.3480),
    "belgard":          (53.2950, -6.3680),
    "tallaght":         (53.2894, -6.3744),
    "citywest":         (53.2820, -6.3900),
    "saggart":          (53.2760, -6.4000),
    "kingswood":        (53.2980, -6.3900),
    "walnut":           (53.2980, -6.3900),
    "rathfarnham":      (53.3030, -6.3100),
    "dundrum":          (53.2930, -6.2440),
    "sandyford":        (53.2760, -6.2270),
    "leopardstown":     (53.2830, -6.2260),
    "stillorgan":       (53.2870, -6.2050),
    "foxrock":          (53.2740, -6.1830),
    "cabinteely":       (53.2680, -6.1760),
    "churchtown":       (53.3020, -6.2640),
    "goatstown":        (53.2970, -6.2550),
    # D16 south-east — Taylors Hill / Nutgrove / Ballinteer area
    "taylors hill":     (53.2880, -6.2720),
    "taylor's hill":    (53.2880, -6.2720),
    "nutgrove":         (53.2940, -6.2780),
    "ballinteer":       (53.2860, -6.2610),
    "marlay":           (53.2850, -6.2700),
    "stocking":         (53.2800, -6.2980),
    "scholarstown":     (53.2830, -6.3050),
    "eden":             (53.2900, -6.2850),
    "mount merrion":    (53.2990, -6.2440),
}

PRICE_RE = re.compile(r"[€,\xa3\s]")


def parse_price(raw: str) -> int | None:
    cleaned = PRICE_RE.sub("", raw).strip().rstrip("0").rstrip(".")
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


def get_price(row: dict) -> int | None:
    for key in row:
        if "price" in key.lower():
            return parse_price(row[key])
    return None


def parse_date(raw: str) -> str | None:
    try:
        return datetime.strptime(raw.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def get_coords(address: str, eircode: str) -> tuple[float, float] | None:
    addr_lower = address.lower()
    for keyword, coords in STREET_COORDS.items():
        if keyword in addr_lower:
            return coords
    prefix = (eircode or "")[:3].upper()
    return EIRCODE_COORDS.get(prefix)


def load_csv(path: str) -> list[dict]:
    with open(path, encoding="cp1252") as f:
        content = f.read()
    return list(csv.DictReader(io.StringIO(content)))


async def main():
    files = [
        "data/PPR-2024-Dublin.csv",
        "data/PPR-2025-Dublin.csv",
        "data/PPR-2026-Dublin.csv",
    ]

    focus_eircodes = {"D24", "D16", "D18"}
    rows_to_insert = []
    seen: set[tuple] = set()

    for path in files:
        try:
            rows = load_csv(path)
        except FileNotFoundError:
            print(f"  skip {path} (not found)")
            continue

        for row in rows:
            if row.get("Not Full Market Price", "No").strip().lower() == "yes":
                continue
            if row.get("VAT Exclusive", "No").strip().lower() == "yes":
                continue

            eircode     = row.get("Eircode", "").strip()
            address     = row.get("Address", "").strip()
            county      = row.get("County", "").strip()
            description = row.get("Description of Property", "").strip()

            eircode_prefix = eircode[:3].upper() if eircode else ""
            addr_upper     = address.upper()

            in_area = (
                eircode_prefix in focus_eircodes
                or any(f"DUBLIN {d}" in addr_upper for d in ("24", "16", "18"))
                or "D24" in addr_upper
            )
            if not in_area:
                continue

            date_str = parse_date(row.get("Date of Sale (dd/mm/yyyy)", ""))
            price    = get_price(row)

            if not date_str or not price or price < 150_000 or price > 850_000:
                continue

            dedup_key = (address.upper(), date_str, price)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            coords = get_coords(address, eircode)
            lat, lon = coords if coords else (None, None)

            district = None
            if eircode_prefix == "D24" or "DUBLIN 24" in addr_upper:
                district = "D24"
            elif eircode_prefix == "D16" or "DUBLIN 16" in addr_upper:
                district = "D16"
            elif eircode_prefix == "D18" or "DUBLIN 18" in addr_upper:
                district = "D18"

            rows_to_insert.append({
                "id":                   str(uuid.uuid4()),
                "address":              address,
                "eircode":              eircode or None,
                "county":               county,
                "date_of_sale":         date_str,
                "price_eur":            price,
                "not_full_market_price": False,
                "vat_exclusive":        False,
                "property_description": description,
                "latitude":             lat,
                "longitude":            lon,
                "dublin_district":      district,
                "source_file":          path.split("/")[-1],
            })

    print(f"  Parsed {len(rows_to_insert)} D24/D16/D18 records from PPR CSVs")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        deleted = await conn.execute(
            "DELETE FROM ppr_sales WHERE source_file LIKE 'ppr_%' OR source_file LIKE 'PPR-%'"
        )
        print(f"  Cleared old data: {deleted}")

        inserted = 0
        for r in rows_to_insert:
            try:
                await conn.execute("""
                    INSERT INTO ppr_sales (
                        id, address, eircode, county, date_of_sale, price_eur,
                        not_full_market_price, vat_exclusive, property_description,
                        latitude, longitude, dublin_district, source_file
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    ON CONFLICT (address, date_of_sale, price_eur) DO NOTHING
                """,
                    uuid.UUID(r["id"]), r["address"], r["eircode"], r["county"],
                    datetime.strptime(r["date_of_sale"], "%Y-%m-%d").date(),
                    r["price_eur"], r["not_full_market_price"], r["vat_exclusive"],
                    r["property_description"], r["latitude"], r["longitude"],
                    r["dublin_district"], r["source_file"],
                )
                inserted += 1
            except Exception as e:
                print(f"  skip {r['address']}: {e}")

        print(f"  Inserted {inserted} real PPR records")

        # Show nearby Firhouse/D24 records with coords
        nearby = await conn.fetch("""
            SELECT address, date_of_sale, price_eur
            FROM ppr_sales
            WHERE latitude BETWEEN 53.27 AND 53.31
              AND longitude BETWEEN -6.41 AND -6.31
            ORDER BY date_of_sale DESC
            LIMIT 40
        """)
        print(f"\n  Records near Firhouse/Killininny with coordinates ({len(nearby)}):")
        for r in nearby:
            print(f"    {r['date_of_sale']}  €{r['price_eur']:>9,}  {r['address'][:65]}")

        for d in ("D24", "D16", "D18"):
            total = await conn.fetchval(
                "SELECT count(*) FROM ppr_sales WHERE dublin_district=$1", d
            )
            with_coords = await conn.fetchval(
                "SELECT count(*) FROM ppr_sales WHERE dublin_district=$1 AND latitude IS NOT NULL", d
            )
            print(f"  {d}: {total} records total, {with_coords} with coordinates")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
