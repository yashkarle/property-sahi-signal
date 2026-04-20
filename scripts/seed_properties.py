"""Seed realistic Dublin property data into Postgres + OpenSearch.

Generates ~30 properties across D12 (Crumlin/Walkinstown/Perrystown)
and D6W (Kimmage/Terenure) matching Yash's target search area.

Usage:
    cd /home/user/property-sahi-signal
    DATABASE_URL=postgresql://property_user:property_pass@localhost:5432/property_sahi \
        python scripts/seed_properties.py
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://property_user:property_pass@localhost:5432/property_sahi",
).replace("postgresql+asyncpg://", "postgresql://")

PROPERTIES = [
    # ── D12 Crumlin ──────────────────────────────────────────────────────────
    {
        "source": "daft", "source_id": "d12001", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/semi-detached-house-sperrin-road-crumlin-dublin-12/1001",
        "title": "3 Bed Semi-Detached House, Sperrin Road, Crumlin, Dublin 12",
        "address": "14 Sperrin Road, Crumlin, Dublin 12", "eircode": "D12X3P4",
        "price": 310000, "bedrooms": 3, "bathrooms": 1, "carpet_area_sqm": 88,
        "property_type": "house", "ber_rating": "D1", "heating_type": "gas",
        "year_built": 1958, "is_chain_free": True, "is_south_facing": False,
        "is_htb_eligible": False, "days_on_market": 18,
        "estate_agent": "DNG Crumlin", "latitude": 53.3211, "longitude": -6.3145,
        "description": "Extended 3-bed semi in quiet residential road. Chain-free. New kitchen fitted 2022. Gas central heating. Walking distance to Crumlin village and bus routes.",
        "missing_data_flags": ["bathrooms"],
    },
    {
        "source": "daft", "source_id": "d12002", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/terraced-house-sundrive-road-crumlin-dublin-12/1002",
        "title": "2 Bed Terraced House, Sundrive Road, Crumlin, Dublin 12",
        "address": "78 Sundrive Road, Crumlin, Dublin 12", "eircode": "D12V5K1",
        "price": 275000, "bedrooms": 2, "bathrooms": 1, "carpet_area_sqm": 72,
        "property_type": "house", "ber_rating": "E1", "heating_type": "electric_storage",
        "year_built": 1945, "is_chain_free": True, "is_south_facing": True,
        "is_htb_eligible": False, "days_on_market": 42,
        "estate_agent": "Sherry FitzGerald Rathmines", "latitude": 53.3198, "longitude": -6.3088,
        "description": "Two-bed mid-terrace on popular Sundrive Road. South-facing rear garden. Electric storage heating — upgrade cost approx €8k for gas. Excellent transport links.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d12003", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/semi-detached-perrystown-avenue-dublin-12/1003",
        "title": "3 Bed Semi-Detached, Perrystown Avenue, Dublin 12",
        "address": "22 Perrystown Avenue, Perrystown, Dublin 12", "eircode": "D12W9N2",
        "price": 335000, "bedrooms": 3, "bathrooms": 2, "carpet_area_sqm": 95,
        "property_type": "house", "ber_rating": "C2", "heating_type": "gas",
        "year_built": 1972, "is_chain_free": False, "is_south_facing": True,
        "is_htb_eligible": False, "days_on_market": 7,
        "estate_agent": "REA Grimes", "latitude": 53.3155, "longitude": -6.3192,
        "description": "Beautifully presented 3-bed semi on mature residential avenue. South-facing garden. BER C2. Gas central heating. Two bathrooms including en-suite. Off-street parking.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d12004", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/apartment-walkinstown-crossroads-dublin-12/1004",
        "title": "2 Bed Apartment, Walkinstown Crossroads, Dublin 12",
        "address": "Apt 14, Walkinstown Green, Walkinstown, Dublin 12", "eircode": "D12H4T7",
        "price": 245000, "bedrooms": 2, "bathrooms": 2, "carpet_area_sqm": 74,
        "property_type": "apartment", "ber_rating": "C3", "heating_type": "gas",
        "year_built": 2005, "management_fee_eur": 1800, "is_chain_free": True,
        "is_south_facing": False, "is_htb_eligible": True, "days_on_market": 29,
        "estate_agent": "Hunters Estate Agent", "latitude": 53.3161, "longitude": -6.3301,
        "description": "Modern 2-bed, 2-bath apartment in well-managed scheme. Celtic Tiger era build — architect's fire safety cert available. HTB eligible. Annual management fee €1,800. Secure underground parking.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d12005", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/detached-house-clogher-road-crumlin-dublin-12/1005",
        "title": "4 Bed Detached House, Clogher Road, Crumlin, Dublin 12",
        "address": "5 Clogher Road, Crumlin, Dublin 12", "eircode": "D12K8E3",
        "price": 390000, "bedrooms": 4, "bathrooms": 2, "carpet_area_sqm": 128,
        "property_type": "house", "ber_rating": "D2", "heating_type": "gas",
        "year_built": 1962, "is_chain_free": True, "is_south_facing": False,
        "is_htb_eligible": False, "days_on_market": 55,
        "estate_agent": "DNG Crumlin", "latitude": 53.3220, "longitude": -6.3095,
        "description": "Spacious 4-bed detached on large site. GFCH. Two reception rooms. Double garage. Significant extension potential (STPP). Quiet cul-de-sac setting.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d12006", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/semi-detached-house-mourne-road-dublin-12/1006",
        "title": "3 Bed Semi-Detached, Mourne Road, Dublin 12",
        "address": "63 Mourne Road, Crumlin, Dublin 12", "eircode": "D12R2A1",
        "price": 298000, "bedrooms": 3, "bathrooms": 1, "carpet_area_sqm": None,
        "property_type": "house", "ber_rating": "D2", "heating_type": "gas",
        "year_built": 1953, "is_chain_free": False, "is_south_facing": False,
        "is_htb_eligible": False, "days_on_market": 12,
        "estate_agent": "Sherry FitzGerald Terenure", "latitude": 53.3183, "longitude": -6.3127,
        "description": "Classic 3-bed semi in sought-after location. Gas central heating. Original period features. Floor area to be confirmed at viewing — typical for this house type approx 85sqm.",
        "missing_data_flags": ["carpet_area_sqm"],
    },
    {
        "source": "daft", "source_id": "d12007", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/terraced-house-blarney-park-dublin-12/1007",
        "title": "3 Bed Terraced House, Blarney Park, Kimmage, Dublin 12",
        "address": "8 Blarney Park, Kimmage, Dublin 12", "eircode": "D12N6F2",
        "price": 320000, "bedrooms": 3, "bathrooms": 1, "carpet_area_sqm": 82,
        "property_type": "house", "ber_rating": "C3", "heating_type": "gas",
        "year_built": 1968, "is_chain_free": True, "is_south_facing": True,
        "is_htb_eligible": False, "days_on_market": 21,
        "estate_agent": "REA Grimes", "latitude": 53.3141, "longitude": -6.3182,
        "description": "Attractive chain-free 3-bed terrace on tranquil estate. South-facing rear garden. BER C3. GFCH. Walk to Kimmage shops and Luas Rathfarnham line.",
        "missing_data_flags": ["bathrooms"],
    },
    # ── D6W Kimmage / Terenure ────────────────────────────────────────────────
    {
        "source": "daft", "source_id": "d6w001", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/semi-detached-house-kimmage-road-west-dublin-6w/2001",
        "title": "3 Bed Semi-Detached, Kimmage Road West, Dublin 6W",
        "address": "101 Kimmage Road West, Kimmage, Dublin 6W", "eircode": "D6WK5N1",
        "price": 365000, "bedrooms": 3, "bathrooms": 2, "carpet_area_sqm": 98,
        "property_type": "house", "ber_rating": "C1", "heating_type": "gas",
        "year_built": 1978, "is_chain_free": True, "is_south_facing": False,
        "is_htb_eligible": False, "days_on_market": 14,
        "estate_agent": "Sherry FitzGerald Terenure", "latitude": 53.3131, "longitude": -6.3021,
        "description": "Superb 3-bed semi with extended kitchen-diner. Two bathrooms inc en-suite master. BER C1. GFCH. Large private rear garden. Off-street parking for two cars.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d6w002", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/semi-detached-house-terenure-road-east-dublin-6w/2002",
        "title": "4 Bed Semi-Detached, Terenure Road East, Dublin 6W",
        "address": "45 Terenure Road East, Terenure, Dublin 6W", "eircode": "D6WT3E8",
        "price": 420000, "bedrooms": 4, "bathrooms": 2, "carpet_area_sqm": 118,
        "property_type": "house", "ber_rating": "C2", "heating_type": "gas",
        "year_built": 1966, "is_chain_free": False, "is_south_facing": True,
        "is_htb_eligible": False, "days_on_market": 5,
        "estate_agent": "Knight Frank Ireland", "latitude": 53.3108, "longitude": -6.2984,
        "description": "Substantial 4-bed family home on premium road. South-facing rear garden. Two receptions. Recently refurbished. Close to Terenure village, schools, Rathgar shops.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d6w003", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/apartment-kimmage-manor-dublin-6w/2003",
        "title": "2 Bed Apartment, Kimmage Manor, Dublin 6W",
        "address": "Apt 7, Kimmage Manor, Kimmage, Dublin 6W", "eircode": "D6WH2A3",
        "price": 285000, "bedrooms": 2, "bathrooms": 2, "carpet_area_sqm": 77,
        "property_type": "apartment", "ber_rating": "B3", "heating_type": "gas",
        "year_built": 2016, "management_fee_eur": 2100, "is_chain_free": True,
        "is_south_facing": False, "is_htb_eligible": True, "days_on_market": 33,
        "estate_agent": "Lisney", "latitude": 53.3148, "longitude": -6.3005,
        "description": "Modern 2-bed, 2-bath apartment in boutique development. BER B3. Gas central heating. Secure parking. Management fee €2,100/yr. HTB eligible for first-time buyers.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d6w004", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/semi-detached-house-harold-cross-road-dublin-6w/2004",
        "title": "3 Bed Semi-Detached, Harold's Cross Road, Dublin 6W",
        "address": "18 Harold's Cross Road, Harold's Cross, Dublin 6W", "eircode": "D6WF8P6",
        "price": 355000, "bedrooms": 3, "bathrooms": 1, "carpet_area_sqm": 91,
        "property_type": "house", "ber_rating": "D1", "heating_type": "gas",
        "year_built": 1960, "is_chain_free": True, "is_south_facing": False,
        "is_htb_eligible": False, "days_on_market": 9,
        "estate_agent": "DNG Rathmines", "latitude": 53.3199, "longitude": -6.2891,
        "description": "Well-proportioned 3-bed semi on popular road near Harold's Cross park. Chain-free. GFCH. Scope for rear extension (STPP). Excellent Luas access at Kimmage stop.",
        "missing_data_flags": ["bathrooms"],
    },
    {
        "source": "daft", "source_id": "d6w005", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/terraced-house-leinster-road-rathmines-dublin-6w/2005",
        "title": "2 Bed Terraced House, Leinster Road, Rathmines, Dublin 6W",
        "address": "52 Leinster Road West, Rathmines, Dublin 6W", "eircode": "D6WL1R9",
        "price": 340000, "bedrooms": 2, "bathrooms": 1, "carpet_area_sqm": 70,
        "property_type": "house", "ber_rating": "E2", "heating_type": "gas",
        "year_built": 1935, "is_chain_free": False, "is_south_facing": True,
        "is_htb_eligible": False, "days_on_market": 28,
        "estate_agent": "Sherry FitzGerald Rathmines", "latitude": 53.3177, "longitude": -6.2922,
        "description": "Charming Victorian terrace in prime Rathmines location. South-facing rear courtyard. Period features throughout. Scope to extend into attic.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d6w006", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/detached-house-fortfield-road-dublin-6w/2006",
        "title": "5 Bed Detached House, Fortfield Road, Terenure, Dublin 6W",
        "address": "3 Fortfield Road, Terenure, Dublin 6W", "eircode": "D6WP4T2",
        "price": 695000, "bedrooms": 5, "bathrooms": 3, "carpet_area_sqm": 185,
        "property_type": "house", "ber_rating": "B2", "heating_type": "heat_pump",
        "year_built": 2019, "is_chain_free": True, "is_south_facing": True,
        "is_htb_eligible": False, "days_on_market": 11,
        "estate_agent": "Lisney", "latitude": 53.3092, "longitude": -6.3011,
        "description": "Magnificent new-build 5-bed on large private site. A-rated heat pump. South-facing landscaped garden. Premium finishes throughout. Separate home office. Electric car charging point.",
        "missing_data_flags": [],
    },
    # ── Additional D12 / D6W mix ──────────────────────────────────────────────
    {
        "source": "daft", "source_id": "d12008", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/semi-detached-house-windmill-road-crumlin-dublin-12/1008",
        "title": "3 Bed Semi-Detached, Windmill Road, Crumlin, Dublin 12",
        "address": "31 Windmill Road, Crumlin, Dublin 12", "eircode": "D12C3W7",
        "price": 305000, "bedrooms": 3, "bathrooms": 2, "carpet_area_sqm": 87,
        "property_type": "house", "ber_rating": "C3", "heating_type": "gas",
        "year_built": 1965, "is_chain_free": True, "is_south_facing": False,
        "is_htb_eligible": False, "days_on_market": 3,
        "estate_agent": "REA Grimes", "latitude": 53.3229, "longitude": -6.3151,
        "description": "Well-maintained 3-bed semi with two bathrooms. GFCH. New boiler 2023. Back garden accessed by side passage. Close to Crumlin Children's Hospital and Cork Street bus corridor.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d12009", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/apartment-tymonville-park-dublin-12/1009",
        "title": "2 Bed Apartment, Tymonville Park, Walkinstown, Dublin 12",
        "address": "Apt 22, Tymonville Park, Walkinstown, Dublin 12", "eircode": "D12T8Y4",
        "price": 235000, "bedrooms": 2, "bathrooms": 1, "carpet_area_sqm": 66,
        "property_type": "apartment", "ber_rating": "D1", "heating_type": "electric_storage",
        "year_built": 2003, "management_fee_eur": 1600, "is_chain_free": True,
        "is_south_facing": False, "is_htb_eligible": True, "days_on_market": 47,
        "estate_agent": "Hunters Estate Agent", "latitude": 53.3101, "longitude": -6.3320,
        "description": "Celtic Tiger era apartment — fire safety cert from 2022 inspection available. Electric storage heating. HTB eligible. Low annual fee €1,600. Ground floor unit with patio.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d12010", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/semi-detached-house-captain-neville-road-dublin-12/1010",
        "title": "3 Bed Semi-Detached, Captain Neville Road, Walkinstown, Dublin 12",
        "address": "19 Captain Neville Road, Walkinstown, Dublin 12", "eircode": "D12N4C9",
        "price": 325000, "bedrooms": 3, "bathrooms": 1, "carpet_area_sqm": 92,
        "property_type": "house", "ber_rating": "C1", "heating_type": "gas",
        "year_built": 1970, "is_chain_free": False, "is_south_facing": True,
        "is_htb_eligible": False, "days_on_market": 19,
        "estate_agent": "DNG Crumlin", "latitude": 53.3148, "longitude": -6.3278,
        "description": "Immaculate 3-bed semi, lovingly maintained by same family for 40 years. Upgraded insulation, BER C1. South-facing garden with mature planting. Walking distance to Walkinstown shopping centre.",
        "missing_data_flags": ["bathrooms"],
    },
    {
        "source": "daft", "source_id": "d6w007", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/own-door-apartment-terenure-village-dublin-6w/2007",
        "title": "2 Bed Own-Door Apartment, Terenure Village, Dublin 6W",
        "address": "2A The Courtyard, Terenure Village, Dublin 6W", "eircode": "D6WV5A1",
        "price": 310000, "bedrooms": 2, "bathrooms": 2, "carpet_area_sqm": 80,
        "property_type": "own_door_apartment", "ber_rating": "B2", "heating_type": "gas",
        "year_built": 2018, "management_fee_eur": 1950, "is_chain_free": True,
        "is_south_facing": False, "is_htb_eligible": True, "days_on_market": 15,
        "estate_agent": "Lisney", "latitude": 53.3088, "longitude": -6.2976,
        "description": "Stylish own-door 2-bed near Terenure village. BER B2. Gas heating. Private patio. Management fee €1,950. Allocated parking. HTB eligible for FTBs. Walk to restaurants, bars, shops.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d6w008", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/terraced-house-ayrfield-road-kimmage-dublin-6w/2008",
        "title": "3 Bed Terraced House, Ayrfield Road, Kimmage, Dublin 6W",
        "address": "67 Ayrfield Road, Kimmage, Dublin 6W", "eircode": "D6WA9R2",
        "price": 345000, "bedrooms": 3, "bathrooms": 1, "carpet_area_sqm": 86,
        "property_type": "house", "ber_rating": "C2", "heating_type": "gas",
        "year_built": 1975, "is_chain_free": True, "is_south_facing": False,
        "is_htb_eligible": False, "days_on_market": 8,
        "estate_agent": "REA Grimes", "latitude": 53.3127, "longitude": -6.3044,
        "description": "Charming chain-free 3-bed terrace on quiet residential road. GFCH. New combi boiler 2021. Large rear garden with outdoor kitchen. Close to Kimmage Manor and Templeville Road shops.",
        "missing_data_flags": ["bathrooms"],
    },
    {
        "source": "daft", "source_id": "d12011", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/semi-detached-house-cashel-avenue-crumlin-dublin-12/1011",
        "title": "3 Bed Semi-Detached, Cashel Avenue, Crumlin, Dublin 12",
        "address": "44 Cashel Avenue, Crumlin, Dublin 12", "eircode": "D12C7H1",
        "price": 315000, "bedrooms": 3, "bathrooms": 2, "carpet_area_sqm": 93,
        "property_type": "house", "ber_rating": "C2", "heating_type": "gas",
        "year_built": 1967, "is_chain_free": False, "is_south_facing": True,
        "is_htb_eligible": False, "days_on_market": 25,
        "estate_agent": "DNG Crumlin", "latitude": 53.3196, "longitude": -6.3168,
        "description": "Well-presented 3-bed with south-facing garden. Two bathrooms. Recent attic conversion (2022). GFCH. Off-street parking. Within catchment of popular national schools.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d12012", "dublin_district": "D12",
        "url": "https://www.daft.ie/for-sale/semi-detached-house-loreto-road-crumlin-dublin-12/1012",
        "title": "4 Bed Semi-Detached, Loreto Road, Crumlin, Dublin 12",
        "address": "2 Loreto Road, Crumlin, Dublin 12", "eircode": "D12L9E4",
        "price": 370000, "bedrooms": 4, "bathrooms": 2, "carpet_area_sqm": 115,
        "property_type": "house", "ber_rating": "C1", "heating_type": "gas",
        "year_built": 1962, "is_chain_free": True, "is_south_facing": False,
        "is_htb_eligible": False, "days_on_market": 2,
        "estate_agent": "Sherry FitzGerald Terenure", "latitude": 53.3178, "longitude": -6.3201,
        "description": "Extended 4-bed semi — significant rear and side extension adds impressive floor area. Modern fitted kitchen. BER C1. GFCH. Chain-free. Mature rear garden. Close to Crumlin Cross.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d6w009", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/detached-house-bushy-park-road-terenure-dublin-6w/2009",
        "title": "4 Bed Detached House, Bushy Park Road, Terenure, Dublin 6W",
        "address": "11 Bushy Park Road, Terenure, Dublin 6W", "eircode": "D6WB6P5",
        "price": 545000, "bedrooms": 4, "bathrooms": 3, "carpet_area_sqm": 152,
        "property_type": "house", "ber_rating": "B3", "heating_type": "gas",
        "year_built": 1990, "is_chain_free": False, "is_south_facing": True,
        "is_htb_eligible": False, "days_on_market": 6,
        "estate_agent": "Knight Frank Ireland", "latitude": 53.3065, "longitude": -6.2996,
        "description": "Exceptional 4-bed detached on one of Terenure's most sought-after roads. South-facing garden with direct gate access to Bushy Park. Three bathrooms. Large study. Double garage.",
        "missing_data_flags": [],
    },
    {
        "source": "daft", "source_id": "d6w010", "dublin_district": "D6W",
        "url": "https://www.daft.ie/for-sale/apartment-harold-cross-park-dublin-6w/2010",
        "title": "2 Bed Apartment, Harold's Cross Park, Dublin 6W",
        "address": "Apt 5, Harold's Cross Park, Dublin 6W", "eircode": "D6WH3C2",
        "price": 270000, "bedrooms": 2, "bathrooms": 1, "carpet_area_sqm": 68,
        "property_type": "apartment", "ber_rating": "B3", "heating_type": "gas",
        "year_built": 2014, "management_fee_eur": 1750, "is_chain_free": True,
        "is_south_facing": False, "is_htb_eligible": True, "days_on_market": 22,
        "estate_agent": "Hunters Estate Agent", "latitude": 53.3187, "longitude": -6.2855,
        "description": "Well-presented 2-bed apartment in modern scheme near Harold's Cross Green. Gas heating. Balcony. Allocated parking. HTB eligible. Close to Portobello, Rathmines, and the Grand Canal.",
        "missing_data_flags": [],
    },
]


INSERT_SQL = """
INSERT INTO properties (
    id, source, source_id, url, title, address, eircode,
    latitude, longitude, dublin_district,
    price, bedrooms, bathrooms, carpet_area_sqm,
    property_type, ber_rating, heating_type, year_built,
    management_fee_eur, is_chain_free, is_south_facing, is_htb_eligible,
    days_on_market, estate_agent, description,
    missing_data_flags, features_list, is_active,
    created_at, updated_at
) VALUES (
    $1::uuid, $2::source_enum, $3, $4, $5, $6, $7,
    $8, $9, $10,
    $11, $12, $13, $14,
    $15::property_type_enum, $16, $17::heating_type_enum, $18,
    $19, $20, $21, $22,
    $23, $24, $25,
    $26::jsonb, '[]'::jsonb, true,
    NOW(), NOW()
) ON CONFLICT (url) DO UPDATE SET
    price = EXCLUDED.price,
    bedrooms = EXCLUDED.bedrooms,
    bathrooms = EXCLUDED.bathrooms,
    carpet_area_sqm = EXCLUDED.carpet_area_sqm,
    ber_rating = EXCLUDED.ber_rating,
    heating_type = EXCLUDED.heating_type,
    days_on_market = EXCLUDED.days_on_market,
    missing_data_flags = EXCLUDED.missing_data_flags,
    updated_at = NOW()
"""


async def seed():
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    inserted = 0
    updated = 0
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        for p in PROPERTIES:
            prop_id = str(uuid.uuid4())
            await conn.execute(
                INSERT_SQL,
                prop_id,
                p["source"],
                p["source_id"],
                p["url"],
                p["title"],
                p["address"],
                p.get("eircode"),
                p.get("latitude"),
                p.get("longitude"),
                p.get("dublin_district"),
                p.get("price"),
                p.get("bedrooms"),
                p.get("bathrooms"),
                p.get("carpet_area_sqm"),
                p.get("property_type"),
                p.get("ber_rating"),
                p.get("heating_type"),
                p.get("year_built"),
                p.get("management_fee_eur"),
                p.get("is_chain_free"),
                p.get("is_south_facing"),
                p.get("is_htb_eligible"),
                p.get("days_on_market"),
                p.get("estate_agent"),
                p.get("description"),
                json.dumps(p.get("missing_data_flags", [])),
            )
            inserted += 1
            print(f"  ✓  {p['address']}")

    await pool.close()
    print(f"\nDone — {inserted} properties seeded into Postgres.")
    print("Run 'python scripts/backfill_embeddings.py' to push to OpenSearch.")


if __name__ == "__main__":
    asyncio.run(seed())
