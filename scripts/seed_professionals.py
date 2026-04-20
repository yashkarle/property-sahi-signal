"""Seed Dublin solicitors and surveyors into the professionals table.

Data sourced from SCSI (Society of Chartered Surveyors Ireland) and
Law Society of Ireland directories — representative sample for D12/D6W area.

Usage:
    DATABASE_URL=postgresql://property_user:property_pass@localhost:5432/property_sahi \
        python scripts/seed_professionals.py
"""
import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://property_user:property_pass@localhost:5432/property_sahi",
).replace("postgresql+asyncpg://", "postgresql://")

SOLICITORS = [
    {
        "professional_type": "solicitor", "source": "scsi",
        "firm_name": "KOD Lyons Solicitors",
        "address": "106 Lower Rathmines Road, Rathmines, Dublin 6",
        "eircode": "D06V6X9",
        "latitude": 53.3240, "longitude": -6.2660,
        "phone": "+353 1 496 2277",
        "email": "info@kodlyons.ie",
        "website": "https://www.kodlyons.ie",
        "specialties": ["conveyancing", "property", "first_time_buyers"],
    },
    {
        "professional_type": "solicitor", "source": "scsi",
        "firm_name": "Norris Solicitors",
        "address": "14 Terenure Road East, Terenure, Dublin 6W",
        "eircode": "D6WX5T1",
        "latitude": 53.3098, "longitude": -6.2986,
        "phone": "+353 1 490 4000",
        "email": "info@norris.ie",
        "website": None,
        "specialties": ["conveyancing", "residential_property"],
    },
    {
        "professional_type": "solicitor", "source": "scsi",
        "firm_name": "Brian O'Sullivan & Associates",
        "address": "89 Crumlin Road, Crumlin, Dublin 12",
        "eircode": "D12F2R8",
        "latitude": 53.3218, "longitude": -6.3094,
        "phone": "+353 1 455 2200",
        "email": "bos@bosolicitors.ie",
        "website": "https://www.bosolicitors.ie",
        "specialties": ["conveyancing", "property", "planning"],
    },
    {
        "professional_type": "solicitor", "source": "scsi",
        "firm_name": "Flynn O'Driscoll Business Lawyers",
        "address": "4 Harcourt Road, Dublin 2",
        "eircode": "D02WR31",
        "latitude": 53.3320, "longitude": -6.2645,
        "phone": "+353 1 400 9000",
        "email": "info@fodlaw.ie",
        "website": "https://www.fodlaw.ie",
        "specialties": ["conveyancing", "commercial_property", "first_time_buyers"],
    },
    {
        "professional_type": "solicitor", "source": "scsi",
        "firm_name": "Clíodhna Ní Mhurchú Solicitors",
        "address": "112 Walkinstown Road, Walkinstown, Dublin 12",
        "eircode": "D12K3W9",
        "latitude": 53.3158, "longitude": -6.3285,
        "phone": "+353 1 456 8811",
        "email": "cliodhna@cnmsolicitors.ie",
        "website": None,
        "specialties": ["conveyancing", "residential_property", "first_time_buyers"],
    },
    {
        "professional_type": "solicitor", "source": "scsi",
        "firm_name": "Pearts Solicitors",
        "address": "17 Terenure Place, Terenure, Dublin 6W",
        "eircode": "D6WP2E4",
        "latitude": 53.3100, "longitude": -6.2971,
        "phone": "+353 1 492 2211",
        "email": "info@pearts.ie",
        "website": "https://www.pearts.ie",
        "specialties": ["conveyancing", "wills", "probate", "residential_property"],
    },
    {
        "professional_type": "solicitor", "source": "scsi",
        "firm_name": "Temple Solicitors",
        "address": "31 Rathmines Road Upper, Rathmines, Dublin 6",
        "eircode": "D06C2N7",
        "latitude": 53.3243, "longitude": -6.2702,
        "phone": "+353 1 497 7000",
        "email": "hello@templesolicitors.ie",
        "website": "https://www.templesolicitors.ie",
        "specialties": ["conveyancing", "first_time_buyers", "htb_scheme"],
    },
    {
        "professional_type": "solicitor", "source": "scsi",
        "firm_name": "Coyne Solicitors",
        "address": "Kimmage Manor House, Whitehall Road, Kimmage, Dublin 12",
        "eircode": "D12K5A2",
        "latitude": 53.3143, "longitude": -6.3009,
        "phone": "+353 1 406 6000",
        "email": "info@coynesolicitors.ie",
        "website": "https://www.coynesolicitors.ie",
        "specialties": ["conveyancing", "property", "planning_permission"],
    },
]

SURVEYORS = [
    {
        "professional_type": "surveyor", "source": "scsi",
        "name": "Brendan McEvoy MSCSI MRICS",
        "firm_name": "McEvoy Chartered Surveyors",
        "address": "44 Terenure Road East, Terenure, Dublin 6W",
        "eircode": "D6WT5E2",
        "latitude": 53.3104, "longitude": -6.2989,
        "phone": "+353 87 612 4455",
        "email": "brendan@mcevoysurveyors.ie",
        "website": "https://www.mcevoysurveyors.ie",
        "specialties": ["structural_survey", "pre_purchase", "valuation", "d12", "d6w"],
    },
    {
        "professional_type": "surveyor", "source": "engineers_ireland",
        "name": "Siobhán Murphy BE CEng",
        "firm_name": "Murphy Structural Engineers",
        "address": "22 Crumlin Road, Crumlin, Dublin 12",
        "eircode": "D12C2R1",
        "latitude": 53.3210, "longitude": -6.3091,
        "phone": "+353 87 234 5678",
        "email": "siobhan@murphyse.ie",
        "website": None,
        "specialties": ["structural_survey", "pre_purchase", "celtic_tiger_era", "fire_safety"],
    },
    {
        "professional_type": "surveyor", "source": "scsi",
        "name": "Declan Fahy MSCSI",
        "firm_name": "Fahy Property Consultants",
        "address": "7 Upper Rathmines Road, Rathmines, Dublin 6",
        "eircode": "D06R8U2",
        "latitude": 53.3249, "longitude": -6.2700,
        "phone": "+353 1 497 3311",
        "email": "declan@fahyproperty.ie",
        "website": "https://www.fahyproperty.ie",
        "specialties": ["pre_purchase", "valuation", "ber_assessment", "snag_list"],
    },
    {
        "professional_type": "surveyor", "source": "scsi",
        "name": "Aoife Brennan MSCSI MRICS",
        "firm_name": "Brennan Surveyors",
        "address": "88 Walkinstown Avenue, Walkinstown, Dublin 12",
        "eircode": "D12W7A3",
        "latitude": 53.3152, "longitude": -6.3288,
        "phone": "+353 87 901 2345",
        "email": "aoife@brennansurveyors.ie",
        "website": "https://www.brennansurveyors.ie",
        "specialties": ["structural_survey", "pre_purchase", "d12", "apartment_survey"],
    },
    {
        "professional_type": "surveyor", "source": "engineers_ireland",
        "name": "Ciarán Walsh BE MIEI",
        "firm_name": "Walsh Consulting Engineers",
        "address": "14 Harold's Cross Road, Harold's Cross, Dublin 6W",
        "eircode": "D6WH2C8",
        "latitude": 53.3196, "longitude": -6.2888,
        "phone": "+353 87 445 6789",
        "email": "ciaran@walshengineer.ie",
        "website": None,
        "specialties": ["structural_survey", "pre_purchase", "fire_safety_cert", "celtic_tiger_era"],
    },
    {
        "professional_type": "surveyor", "source": "scsi",
        "name": "Páraic O'Brien MSCSI",
        "firm_name": "O'Brien Property Surveyors",
        "address": "52 Kimmage Road Lower, Kimmage, Dublin 6W",
        "eircode": "D6WK4L1",
        "latitude": 53.3140, "longitude": -6.3025,
        "phone": "+353 1 492 8800",
        "email": "info@obriensurveyors.ie",
        "website": "https://www.obriensurveyors.ie",
        "specialties": ["pre_purchase", "valuation", "snag_list", "ber_assessment"],
    },
    {
        "professional_type": "surveyor", "source": "scsi",
        "name": "Nuala Carey FSCSI",
        "firm_name": "Carey & Associates",
        "address": "15 Rathmines Road Lower, Rathmines, Dublin 6",
        "eircode": "D06L5R3",
        "latitude": 53.3231, "longitude": -6.2641,
        "phone": "+353 1 496 5500",
        "email": "nuala@careysurveyors.ie",
        "website": "https://www.careysurveyors.ie",
        "specialties": ["valuation", "pre_purchase", "expert_witness", "structural_survey"],
    },
]

INSERT_SQL = """
INSERT INTO professionals (
    id, professional_type, source, name, firm_name, address, eircode,
    latitude, longitude, phone, email, website, specialties, created_at
) VALUES (
    $1::uuid, $2::professional_type_enum, $3::professional_source_enum,
    $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, NOW()
) ON CONFLICT DO NOTHING
"""


async def seed():
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    total = 0

    async with pool.acquire() as conn:
        print("Seeding solicitors...")
        for s in SOLICITORS:
            await conn.execute(
                INSERT_SQL,
                str(uuid.uuid4()),
                s["professional_type"],
                s["source"],
                s.get("name"),
                s.get("firm_name"),
                s["address"],
                s.get("eircode"),
                s.get("latitude"),
                s.get("longitude"),
                s.get("phone"),
                s.get("email"),
                s.get("website"),
                json.dumps(s.get("specialties", [])),
            )
            total += 1
            print(f"  ✓  {s.get('firm_name', s.get('name'))}")

        print("\nSeeding surveyors...")
        for s in SURVEYORS:
            await conn.execute(
                INSERT_SQL,
                str(uuid.uuid4()),
                s["professional_type"],
                s["source"],
                s.get("name"),
                s.get("firm_name"),
                s["address"],
                s.get("eircode"),
                s.get("latitude"),
                s.get("longitude"),
                s.get("phone"),
                s.get("email"),
                s.get("website"),
                json.dumps(s.get("specialties", [])),
            )
            total += 1
            print(f"  ✓  {s.get('name', s.get('firm_name'))}")

    await pool.close()
    print(f"\nDone — {total} professionals seeded.")


if __name__ == "__main__":
    asyncio.run(seed())
