"""Composable seed builder framework for the Patient Portal environment.

Provides :class:`PatientPortalSeedContext` and a registry of builder
functions that generate deterministic healthcare test data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

from webagentbench.backend.models.patient_portal import (
    Appointment,
    ClinicalMessage,
    EmergencyContact,
    Immunization,
    InsuranceClaim,
    InsurancePlan,
    LabResult,
    Pharmacy,
    Prescription,
    Provider,
    Referral,
    ScreeningRecommendation,
    SlotInfo,
)


# ---------------------------------------------------------------------------
# ResolvedActor (shared shape with Gmail / Robinhood)
# ---------------------------------------------------------------------------

@dataclass
class ResolvedActor:
    """A named person with a deterministically-generated email address."""

    name: str
    email: str
    first_name: str


# ---------------------------------------------------------------------------
# Hardcoded provider name templates by specialty
# ---------------------------------------------------------------------------

_PROVIDER_NAMES: dict[str, list[str]] = {
    "pcp": [
        "Dr. Sarah Mitchell", "Dr. David Chen", "Dr. Lisa Patel",
        "Dr. James Rivera", "Dr. Emily Brooks",
    ],
    "cardiology": [
        "Dr. Robert Kim", "Dr. Ana Rodriguez", "Dr. Michael Torres",
        "Dr. Patricia Nguyen", "Dr. Steven Wright",
    ],
    "endocrinology": [
        "Dr. Karen Singh", "Dr. Thomas Garcia", "Dr. Maria Lopez",
        "Dr. Brian Morris", "Dr. Jennifer Adams",
    ],
    "dermatology": [
        "Dr. Sandra Lee", "Dr. Andrew Park", "Dr. Rachel Green",
        "Dr. Kevin Pham", "Dr. Laura Martinez",
    ],
    "orthopedics": [
        "Dr. William Clark", "Dr. Diana Flores", "Dr. Mark Sullivan",
        "Dr. Christine Yang", "Dr. Peter Walsh",
    ],
    "neurology": [
        "Dr. Helen Cho", "Dr. Daniel Murphy", "Dr. Samantha Price",
        "Dr. Richard Tanaka", "Dr. Olivia Bennett",
    ],
    "radiology": [
        "Dr. Paul Hoffman", "Dr. Natalie Russo", "Dr. Gregory Lin",
        "Dr. Catherine Stone", "Dr. Derek Foster",
    ],
    "billing": [
        "Billing Department", "Claims Office", "Patient Accounts",
    ],
    "admin": [
        "Front Desk", "Patient Services", "Medical Records",
    ],
}

_SPECIALTY_DEPARTMENTS: dict[str, str] = {
    "pcp": "Primary Care",
    "cardiology": "Cardiology",
    "endocrinology": "Endocrinology",
    "dermatology": "Dermatology",
    "orthopedics": "Orthopedics",
    "neurology": "Neurology",
    "radiology": "Radiology",
    "billing": "Billing",
    "admin": "Administration",
}

# ---------------------------------------------------------------------------
# Screening pools
# ---------------------------------------------------------------------------

_SCREENING_ALL: list[dict[str, Any]] = [
    {"name": "Colonoscopy", "min_age": 45, "frequency": "every 10 years"},
    {"name": "Lipid Panel", "min_age": 20, "frequency": "every 5 years"},
    {"name": "Blood Pressure Screening", "min_age": 18, "frequency": "annually"},
    {"name": "Diabetes Screening", "min_age": 35, "frequency": "every 3 years"},
    {"name": "Lung Cancer Screening", "min_age": 50, "frequency": "annually"},
]

_SCREENING_FEMALE: list[dict[str, Any]] = [
    {"name": "Mammogram", "min_age": 40, "frequency": "every 2 years"},
    {"name": "Cervical Cancer Screening", "min_age": 21, "frequency": "every 3 years"},
    {"name": "Bone Density Scan", "min_age": 65, "frequency": "every 2 years"},
]

# ---------------------------------------------------------------------------
# Medication pool
# ---------------------------------------------------------------------------

_MEDICATIONS: list[dict[str, Any]] = [
    {"name": "Lisinopril 10mg", "dosage": "10mg", "frequency": "once daily"},
    {"name": "Metformin 500mg", "dosage": "500mg", "frequency": "twice daily"},
    {"name": "Atorvastatin 20mg", "dosage": "20mg", "frequency": "once daily at bedtime"},
    {"name": "Amlodipine 5mg", "dosage": "5mg", "frequency": "once daily"},
    {"name": "Losartan 50mg", "dosage": "50mg", "frequency": "once daily"},
    {"name": "Warfarin 5mg", "dosage": "5mg", "frequency": "once daily"},
    {"name": "Omeprazole 20mg", "dosage": "20mg", "frequency": "once daily before breakfast"},
    {"name": "Levothyroxine 75mcg", "dosage": "75mcg", "frequency": "once daily on empty stomach"},
    {"name": "Gabapentin 300mg", "dosage": "300mg", "frequency": "three times daily"},
    {"name": "Sertraline 50mg", "dosage": "50mg", "frequency": "once daily"},
]

# Known drug interaction pairs
_INTERACTION_PAIRS: list[tuple[str, str]] = [
    ("Warfarin 5mg", "Atorvastatin 20mg"),
    ("Lisinopril 10mg", "Losartan 50mg"),
    ("Metformin 500mg", "Gabapentin 300mg"),
]

# ---------------------------------------------------------------------------
# Lab test pool
# ---------------------------------------------------------------------------

_LAB_TESTS: list[dict[str, Any]] = [
    {"name": "HbA1c", "code": "4548-4", "unit": "%", "ref": "4.0-5.6", "normal": "5.2", "abnormal": "7.1", "critical": "10.5"},
    {"name": "LDL Cholesterol", "code": "2089-1", "unit": "mg/dL", "ref": "0-130", "normal": "110", "abnormal": "155", "critical": "220"},
    {"name": "HDL Cholesterol", "code": "2085-9", "unit": "mg/dL", "ref": "40-60", "normal": "52", "abnormal": "32", "critical": "22"},
    {"name": "Triglycerides", "code": "2571-8", "unit": "mg/dL", "ref": "0-150", "normal": "120", "abnormal": "210", "critical": "550"},
    {"name": "Total Cholesterol", "code": "2093-3", "unit": "mg/dL", "ref": "0-200", "normal": "180", "abnormal": "245", "critical": "320"},
    {"name": "TSH", "code": "3016-3", "unit": "mIU/L", "ref": "0.4-4.0", "normal": "2.1", "abnormal": "6.8", "critical": "15.0"},
    {"name": "Creatinine", "code": "2160-0", "unit": "mg/dL", "ref": "0.6-1.2", "normal": "0.9", "abnormal": "1.8", "critical": "4.5"},
    {"name": "Glucose Fasting", "code": "1558-6", "unit": "mg/dL", "ref": "70-100", "normal": "88", "abnormal": "135", "critical": "350"},
    {"name": "INR", "code": "6301-6", "unit": "", "ref": "0.8-1.2", "normal": "1.0", "abnormal": "2.8", "critical": "5.0"},
    {"name": "CBC WBC", "code": "6690-2", "unit": "10^3/uL", "ref": "4.5-11.0", "normal": "7.2", "abnormal": "14.5", "critical": "25.0"},
]

_LIPID_PANEL_COMPONENTS = ["LDL Cholesterol", "HDL Cholesterol", "Triglycerides", "Total Cholesterol"]

# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

_CLINICAL_SUBJECTS: list[str] = [
    "Follow-up on recent lab results",
    "Medication adjustment recommendation",
    "Appointment reminder",
    "Test results available",
    "Care plan update",
]

_BILLING_SUBJECTS: list[str] = [
    "Statement for recent visit",
    "Insurance claim update",
    "Outstanding balance notification",
]

_RX_RENEWAL_SUBJECTS: list[str] = [
    "Prescription renewal request",
    "Refill authorization needed",
    "Medication renewal due",
]

# ---------------------------------------------------------------------------
# Vaccine pool
# ---------------------------------------------------------------------------

_VACCINES: list[dict[str, Any]] = [
    {"name": "Influenza (Flu)", "series": False, "annual": True},
    {"name": "COVID-19 Booster", "series": False, "annual": True},
    {"name": "Tdap (Tetanus)", "series": False, "annual": False, "interval_years": 10},
    {"name": "Shingles (Shingrix)", "series": True, "doses": 2, "interval_months": 2},
    {"name": "Hepatitis B", "series": True, "doses": 3, "interval_months": 1},
    {"name": "Pneumococcal (PCV20)", "series": False, "annual": False, "min_age": 65},
    {"name": "HPV", "series": True, "doses": 3, "interval_months": 2, "max_age": 45},
]

# ---------------------------------------------------------------------------
# Pharmacy pool
# ---------------------------------------------------------------------------

_PHARMACY_TEMPLATES: list[dict[str, str]] = [
    {"name": "CVS Pharmacy #4821", "address": "1200 Market St, Springfield, IL 62701", "phone": "(555) 234-5678"},
    {"name": "Walgreens #09832", "address": "450 Oak Ave, Springfield, IL 62702", "phone": "(555) 345-6789"},
    {"name": "CVS Pharmacy #4833", "address": "890 Pine Blvd, Springfield, IL 62703", "phone": "(555) 456-7890"},
    {"name": "Rite Aid #1155", "address": "320 Elm St, Springfield, IL 62704", "phone": "(555) 567-8901"},
]

_MAIL_ORDER_PHARMACY: dict[str, str] = {
    "name": "Express Scripts Mail Order",
    "address": "PO Box 21100, Tempe, AZ 85285",
    "phone": "(800) 555-1234",
}


# ---------------------------------------------------------------------------
# PatientPortalSeedContext
# ---------------------------------------------------------------------------

class PatientPortalSeedContext:
    """Mutable accumulator threaded through every Patient Portal builder step."""

    def __init__(
        self,
        seed: int,
        rng: random.Random,
        fake: Any,
        now: datetime,
        base: dict[str, Any],
    ) -> None:
        self.seed = seed
        self.rng = rng
        self.fake = fake
        self.now = now
        self.base = base
        self.actors: dict[str, ResolvedActor] = {}
        self.outputs: dict[str, Any] = {}
        self.counters: dict[str, int] = {}

    def next_id(self, prefix: str) -> str:
        """Return a monotonically increasing id like ``prov_1``."""
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}_{self.counters[prefix]}"

    def get_provider_by_specialty(self, specialty: str) -> dict | None:
        """Return the first provider dict matching *specialty*, or None."""
        for prov in self.base.get("providers", []):
            if prov.get("specialty") == specialty:
                return prov
        return None

    def get_pcp(self) -> dict:
        """Return the PCP provider dict.  Raises if none found."""
        pcp_id = self.base.get("patient", {}).get("pcp_id")
        if pcp_id:
            for prov in self.base.get("providers", []):
                if prov.get("id") == pcp_id:
                    return prov
        raise ValueError("No PCP found in base state")

    def email_for_name(self, name: str, domain: str = "thornton.com") -> str:
        local = "".join(
            ch.lower() for ch in name if ch.isalnum() or ch == " "
        ).replace(" ", ".")
        local = ".".join(part for part in local.split(".") if part) or "contact"
        return f"{local}@{domain}"

    def resolve_actor(
        self,
        key: str,
        domain: str = "thornton.com",
        name: str | None = None,
        is_vip: bool = False,
    ) -> ResolvedActor:
        """Generate a deterministic actor and cache it under *key*."""
        if key in self.actors:
            return self.actors[key]
        if name is None:
            name = self.fake.name()
        first_name = name.split()[0]
        email = self.email_for_name(name, domain)
        actor = ResolvedActor(name=name, email=email, first_name=first_name)
        self.actors[key] = actor
        return actor


# ---------------------------------------------------------------------------
# Builder registry
# ---------------------------------------------------------------------------

BuilderFn = Callable[["PatientPortalSeedContext", dict[str, Any]], dict[str, Any]]

PATIENT_PORTAL_BUILDER_REGISTRY: dict[str, BuilderFn] = {}


def _register(name: str) -> Callable[[BuilderFn], BuilderFn]:
    def decorator(fn: BuilderFn) -> BuilderFn:
        PATIENT_PORTAL_BUILDER_REGISTRY[name] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# 1. patient_profile
# ---------------------------------------------------------------------------

_INSURANCE_TIERS: dict[str, dict[str, Any]] = {
    "basic": {"copay": Decimal("50"), "deductible": Decimal("5000"), "plan_prefix": "Bronze"},
    "standard": {"copay": Decimal("30"), "deductible": Decimal("2000"), "plan_prefix": "Silver"},
    "premium": {"copay": Decimal("15"), "deductible": Decimal("500"), "plan_prefix": "Gold"},
}


@_register("patient_profile")
def build_patient_profile(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Create the patient singleton, insurance, emergency contact, and PCP assignment.

    Params: allergies (list[str]), conditions (list[str]), insurance_tier (str)
    Outputs: patient_name, pcp_id, pcp_name, insurance_plan_name, member_id,
             conditions_list, applicable_screening_names
    """
    allergies = params.get("allergies", [])
    conditions = params.get("conditions", [])
    tier_key = params.get("insurance_tier", "standard")
    tier = _INSURANCE_TIERS.get(tier_key, _INSURANCE_TIERS["standard"])

    # Generate patient demographics
    patient_name = ctx.fake.name()
    sex = ctx.rng.choice(["male", "female"])
    # Age between 25 and 75
    age = ctx.rng.randint(25, 75)
    dob = date(ctx.now.year - age, ctx.rng.randint(1, 12), ctx.rng.randint(1, 28))
    phone = f"(555) {ctx.rng.randint(100, 999)}-{ctx.rng.randint(1000, 9999)}"
    email = ctx.email_for_name(patient_name)

    # Emergency contact
    ec_name = ctx.fake.name()
    ec_phone = f"(555) {ctx.rng.randint(100, 999)}-{ctx.rng.randint(1000, 9999)}"
    ec_rel = ctx.rng.choice(["Spouse", "Parent", "Sibling", "Child", "Friend"])

    # Insurance plan
    plan_name = f"{tier['plan_prefix']} {ctx.rng.choice(['PPO', 'HMO', 'EPO'])} Plan"
    member_id = f"MBR-{ctx.rng.randint(1000000, 9999999)}"
    group_number = f"GRP-{ctx.rng.randint(10000, 99999)}"
    deductible_met = Decimal(str(ctx.rng.randint(0, int(tier['deductible']))))

    # PCP assignment -- the PCP provider will be created by provider_directory,
    # but we reserve the ID here for cross-reference.
    pcp_id = "prov_1"

    # Build applicable screenings based on age and sex
    eligible: list[dict[str, Any]] = []
    for s in _SCREENING_ALL:
        if age >= s["min_age"]:
            eligible.append(s)
    if sex == "female":
        for s in _SCREENING_FEMALE:
            if age >= s["min_age"]:
                eligible.append(s)

    # Pick 3-5 from eligible
    num_screenings = min(len(eligible), ctx.rng.randint(3, 5))
    ctx.rng.shuffle(eligible)
    selected_screenings = eligible[:num_screenings]

    screening_models: list[dict[str, Any]] = []
    for s in selected_screenings:
        # Random last_completed in the past 0-5 years (some may be None)
        if ctx.rng.random() > 0.3:
            years_ago = ctx.rng.randint(0, 5)
            last_completed = date(ctx.now.year - years_ago, ctx.rng.randint(1, 12), ctx.rng.randint(1, 28))
            # Compute next_due based on frequency
            freq_years = _parse_frequency_years(s["frequency"])
            next_due = date(last_completed.year + freq_years, last_completed.month, last_completed.day)
        else:
            last_completed = None
            next_due = date(ctx.now.year, ctx.rng.randint(1, 12), ctx.rng.randint(1, 28))

        screening_models.append({
            "screening_name": s["name"],
            "recommended_age_start": s["min_age"],
            "frequency": s["frequency"],
            "last_completed": last_completed.isoformat() if last_completed else None,
            "next_due": next_due.isoformat() if next_due else None,
        })

    patient_dict = {
        "id": "patient_1",
        "name": patient_name,
        "sex": sex,
        "dob": dob.isoformat(),
        "phone": phone,
        "email": email,
        "insurance_plan": {
            "plan_name": plan_name,
            "member_id": member_id,
            "group_number": group_number,
            "copay": str(tier["copay"]),
            "deductible": str(tier["deductible"]),
            "deductible_met": str(deductible_met),
        },
        "pcp_id": pcp_id,
        "allergies": allergies,
        "conditions": conditions,
        "pharmacy_ids": [],
        "emergency_contact": {
            "name": ec_name,
            "phone": ec_phone,
            "relationship": ec_rel,
        },
        "applicable_screenings": screening_models,
    }

    ctx.base["patient"] = patient_dict

    return {
        "patient_name": patient_name,
        "pcp_id": pcp_id,
        "pcp_name": "",  # Will be filled by provider_directory
        "insurance_plan_name": plan_name,
        "member_id": member_id,
        "conditions_list": conditions,
        "applicable_screening_names": [s["screening_name"] for s in screening_models],
    }


def _parse_frequency_years(freq: str) -> int:
    """Parse a screening frequency string into years."""
    if "10 years" in freq:
        return 10
    if "5 years" in freq:
        return 5
    if "3 years" in freq:
        return 3
    if "2 years" in freq:
        return 2
    return 1  # annually


# ---------------------------------------------------------------------------
# 2. provider_directory
# ---------------------------------------------------------------------------

@_register("provider_directory")
def build_provider_directory(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Create N providers across requested specialties with realistic available slots.

    Params: count (int), specialties (list[str]), must_include (list[str])
    Outputs: provider_ids, providers_by_specialty
    """
    specialties = params.get("specialties", ["pcp"])
    must_include = set(params.get("must_include", []))
    # Ensure must_include specialties are in the specialties list
    all_specialties = list(dict.fromkeys(specialties + list(must_include)))

    if "providers" not in ctx.base:
        ctx.base["providers"] = []

    provider_ids: list[str] = []
    providers_by_specialty: dict[str, list[str]] = {}

    for spec in all_specialties:
        names_pool = _PROVIDER_NAMES.get(spec, [f"Dr. {ctx.fake.name()}"])
        dept = _SPECIALTY_DEPARTMENTS.get(spec, spec.title())

        # For PCP, always use prov_1 to match patient.pcp_id
        if spec == "pcp" and not any(p.get("id") == "prov_1" for p in ctx.base["providers"]):
            prov_id = "prov_1"
            # Consume counter to stay in sync
            ctx.counters["prov"] = max(ctx.counters.get("prov", 0), 1)
        else:
            prov_id = ctx.next_id("prov")

        prov_name = ctx.rng.choice(names_pool)
        accepting = spec not in ("billing", "admin")
        npi = f"{ctx.rng.randint(1000000000, 9999999999)}"

        # Generate 3-6 available slots over the next 2 weeks
        num_slots = ctx.rng.randint(3, 6)
        slots: list[dict[str, Any]] = []
        for _ in range(num_slots):
            days_ahead = ctx.rng.randint(1, 14)
            hour = ctx.rng.randint(9, 16)
            slot_dt = ctx.now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
            slot_type = ctx.rng.choice(["in-person", "telehealth"])
            slots.append({
                "datetime": slot_dt.isoformat(),
                "type": slot_type,
                "duration_minutes": 30,
            })
        # Sort slots by datetime
        slots.sort(key=lambda s: s["datetime"])

        prov_dict = {
            "id": prov_id,
            "name": prov_name,
            "specialty": spec,
            "department": dept,
            "npi": npi,
            "accepting_new": accepting,
            "available_slots": slots,
        }
        ctx.base["providers"].append(prov_dict)
        provider_ids.append(prov_id)
        providers_by_specialty.setdefault(spec, []).append(prov_id)

    # Update PCP name in outputs if we created a PCP
    if "pcp" in providers_by_specialty:
        pcp_prov = next(
            (p for p in ctx.base["providers"] if p["id"] == "prov_1"), None
        )
        if pcp_prov:
            ctx.outputs["pcp_name"] = pcp_prov["name"]

    return {
        "provider_ids": provider_ids,
        "providers_by_specialty": providers_by_specialty,
    }


# ---------------------------------------------------------------------------
# 3. pharmacy_list
# ---------------------------------------------------------------------------

@_register("pharmacy_list")
def build_pharmacy_list(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Create pharmacies with one default. Optional mail-order.

    Params: count (2-3), include_mail_order (bool)
    Outputs: pharmacy_ids, default_pharmacy_id, mail_order_pharmacy_id
    """
    count = params.get("count", 2)
    include_mail_order = params.get("include_mail_order", False)

    if "pharmacies" not in ctx.base:
        ctx.base["pharmacies"] = []

    templates = list(_PHARMACY_TEMPLATES)
    ctx.rng.shuffle(templates)
    selected = templates[:min(count, len(templates))]

    pharmacy_ids: list[str] = []
    default_pharmacy_id: str = ""
    mail_order_pharmacy_id: str | None = None

    for i, tmpl in enumerate(selected):
        pharm_id = ctx.next_id("pharm")
        is_default = i == 0
        dispensing_fee = Decimal(str(ctx.rng.choice([5, 8, 10, 12])))

        pharm_dict = {
            "id": pharm_id,
            "name": tmpl["name"],
            "address": tmpl["address"],
            "phone": tmpl["phone"],
            "is_default": is_default,
            "is_mail_order": False,
            "dispensing_fee": str(dispensing_fee),
        }
        ctx.base["pharmacies"].append(pharm_dict)
        pharmacy_ids.append(pharm_id)
        if is_default:
            default_pharmacy_id = pharm_id

    if include_mail_order:
        pharm_id = ctx.next_id("pharm")
        pharm_dict = {
            "id": pharm_id,
            "name": _MAIL_ORDER_PHARMACY["name"],
            "address": _MAIL_ORDER_PHARMACY["address"],
            "phone": _MAIL_ORDER_PHARMACY["phone"],
            "is_default": False,
            "is_mail_order": True,
            "dispensing_fee": "0",
            "cost_per_90day_supply": str(Decimal(str(ctx.rng.randint(15, 45)))),
        }
        ctx.base["pharmacies"].append(pharm_dict)
        pharmacy_ids.append(pharm_id)
        mail_order_pharmacy_id = pharm_id

    # Update patient's pharmacy_ids
    if "patient" in ctx.base:
        ctx.base["patient"]["pharmacy_ids"] = pharmacy_ids

    return {
        "pharmacy_ids": pharmacy_ids,
        "default_pharmacy_id": default_pharmacy_id,
        "mail_order_pharmacy_id": mail_order_pharmacy_id,
    }


# ---------------------------------------------------------------------------
# 4. appointment_history
# ---------------------------------------------------------------------------

@_register("appointment_history")
def build_appointment_history(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Create a mix of upcoming, completed, and cancelled appointments.

    Params: upcoming_count, completed_count, cancelled_count,
            include_specialist (bool), conflict_pair (bool)
    Outputs: upcoming_ids, completed_ids, cancelled_ids, next_appointment_id,
             conflict_apt_ids, pcp_apt_id, specialist_apt_id, telehealth_apt_id
    """
    upcoming_count = params.get("upcoming_count", 2)
    completed_count = params.get("completed_count", 2)
    cancelled_count = params.get("cancelled_count", 1)
    include_specialist = params.get("include_specialist", True)
    conflict_pair = params.get("conflict_pair", False)

    if "appointments" not in ctx.base:
        ctx.base["appointments"] = []

    providers = ctx.base.get("providers", [])
    if not providers:
        raise ValueError("provider_directory must run before appointment_history")

    pcp_provider = next((p for p in providers if p["specialty"] == "pcp"), providers[0])
    specialist_providers = [p for p in providers if p["specialty"] not in ("pcp", "billing", "admin")]

    upcoming_ids: list[str] = []
    completed_ids: list[str] = []
    cancelled_ids: list[str] = []
    conflict_apt_ids: list[str] = []
    pcp_apt_id: str | None = None
    specialist_apt_id: str | None = None
    telehealth_apt_id: str | None = None
    next_appointment_id: str | None = None

    # --- Upcoming appointments ---
    for i in range(upcoming_count):
        apt_id = ctx.next_id("apt")
        days_ahead = ctx.rng.randint(1, 21)
        hour = ctx.rng.randint(9, 16)
        apt_dt = ctx.now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)

        # First upcoming is PCP, rest alternate
        if i == 0:
            prov = pcp_provider
        elif include_specialist and specialist_providers:
            prov = ctx.rng.choice(specialist_providers)
        else:
            prov = pcp_provider

        apt_type = ctx.rng.choice(["in-person", "telehealth"])
        booked_at = ctx.now - timedelta(days=ctx.rng.randint(1, 14))

        apt_dict = {
            "id": apt_id,
            "provider_id": prov["id"],
            "datetime": apt_dt.isoformat(),
            "type": apt_type,
            "status": "scheduled",
            "reason": ctx.rng.choice(["Follow-up", "Routine checkup", "Medication review", "Annual physical"]),
            "notes": "",
            "booked_at": booked_at.isoformat(),
            "location": "Main Campus" if apt_type == "in-person" else "Telehealth",
        }
        ctx.base["appointments"].append(apt_dict)
        upcoming_ids.append(apt_id)

        if i == 0:
            pcp_apt_id = apt_id
        if i == 0 or (next_appointment_id is None):
            next_appointment_id = apt_id
        if include_specialist and specialist_providers and prov != pcp_provider and specialist_apt_id is None:
            specialist_apt_id = apt_id
        if apt_type == "telehealth" and telehealth_apt_id is None:
            telehealth_apt_id = apt_id

    # --- Completed appointments ---
    for _ in range(completed_count):
        apt_id = ctx.next_id("apt")
        days_ago = ctx.rng.randint(7, 90)
        hour = ctx.rng.randint(9, 16)
        apt_dt = ctx.now.replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
        prov = ctx.rng.choice(providers)
        booked_at = apt_dt - timedelta(days=ctx.rng.randint(7, 30))

        apt_dict = {
            "id": apt_id,
            "provider_id": prov["id"],
            "datetime": apt_dt.isoformat(),
            "type": ctx.rng.choice(["in-person", "telehealth"]),
            "status": "completed",
            "reason": ctx.rng.choice(["Follow-up", "Lab review", "Consultation"]),
            "notes": "Patient doing well. Continue current treatment plan.",
            "booked_at": booked_at.isoformat(),
            "location": "Main Campus",
        }
        ctx.base["appointments"].append(apt_dict)
        completed_ids.append(apt_id)

    # --- Cancelled appointments ---
    for _ in range(cancelled_count):
        apt_id = ctx.next_id("apt")
        days_ago = ctx.rng.randint(1, 30)
        hour = ctx.rng.randint(9, 16)
        apt_dt = ctx.now.replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
        prov = ctx.rng.choice(providers)
        booked_at = apt_dt - timedelta(days=ctx.rng.randint(7, 21))

        apt_dict = {
            "id": apt_id,
            "provider_id": prov["id"],
            "datetime": apt_dt.isoformat(),
            "type": "in-person",
            "status": "cancelled",
            "reason": "Patient requested cancellation",
            "notes": "",
            "booked_at": booked_at.isoformat(),
            "location": "Main Campus",
        }
        ctx.base["appointments"].append(apt_dict)
        cancelled_ids.append(apt_id)

    # --- Conflict pair: two overlapping scheduled appointments ---
    if conflict_pair and len(providers) >= 2:
        conflict_dt = ctx.now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=ctx.rng.randint(3, 10))
        for j in range(2):
            apt_id = ctx.next_id("apt")
            prov = providers[j % len(providers)]
            booked_at = ctx.now - timedelta(days=ctx.rng.randint(1, 7))

            apt_dict = {
                "id": apt_id,
                "provider_id": prov["id"],
                "datetime": conflict_dt.isoformat(),
                "type": "in-person",
                "status": "scheduled",
                "reason": "Follow-up",
                "notes": "",
                "booked_at": booked_at.isoformat(),
                "location": "Main Campus",
            }
            ctx.base["appointments"].append(apt_dict)
            conflict_apt_ids.append(apt_id)
            upcoming_ids.append(apt_id)

    return {
        "upcoming_ids": upcoming_ids,
        "completed_ids": completed_ids,
        "cancelled_ids": cancelled_ids,
        "next_appointment_id": next_appointment_id,
        "conflict_apt_ids": conflict_apt_ids,
        "pcp_apt_id": pcp_apt_id,
        "specialist_apt_id": specialist_apt_id,
        "telehealth_apt_id": telehealth_apt_id,
    }


# ---------------------------------------------------------------------------
# 5. prescription_cabinet
# ---------------------------------------------------------------------------

@_register("prescription_cabinet")
def build_prescription_cabinet(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Generate prescriptions with varying refill states.

    Params: active_count (int), expired_count (int), zero_refill_count (int),
            expiring_soon_count (int), interaction_pair (bool)
    Outputs: active_rx_ids, zero_refill_rx_id, expiring_rx_ids,
             interacting_rx_ids, interacting_medications
    """
    active_count = params.get("active_count", 3)
    expired_count = params.get("expired_count", 0)
    zero_refill_count = params.get("zero_refill_count", 0)
    expiring_soon_count = params.get("expiring_soon_count", 0)
    interaction_pair = params.get("interaction_pair", False)

    if "prescriptions" not in ctx.base:
        ctx.base["prescriptions"] = []

    providers = ctx.base.get("providers", [])
    pharmacies = ctx.base.get("pharmacies", [])
    pcp_id = ctx.base.get("patient", {}).get("pcp_id", "prov_1")
    default_pharm_id = next((p["id"] for p in pharmacies if p.get("is_default")), "pharm_1") if pharmacies else "pharm_1"

    # Shuffle the medication pool
    med_pool = list(_MEDICATIONS)
    ctx.rng.shuffle(med_pool)
    med_idx = 0

    active_rx_ids: list[str] = []
    zero_refill_rx_id: str | None = None
    expiring_rx_ids: list[str] = []
    interacting_rx_ids: list[str] = []
    interacting_medications: list[str] = []

    def _make_rx(med: dict, status: str, refills: int, expires_days: int) -> dict[str, Any]:
        nonlocal med_idx
        rx_id = ctx.next_id("rx")
        provider_id = ctx.rng.choice([p["id"] for p in providers]) if providers else pcp_id
        pharm_id = ctx.rng.choice([p["id"] for p in pharmacies]) if pharmacies else default_pharm_id
        last_filled = ctx.now - timedelta(days=ctx.rng.randint(7, 60))
        expires_at = ctx.now + timedelta(days=expires_days)

        return {
            "id": rx_id,
            "medication": med["name"],
            "dosage": med["dosage"],
            "frequency": med["frequency"],
            "provider_id": provider_id,
            "pharmacy_id": pharm_id,
            "refills_remaining": refills,
            "last_filled": last_filled.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": status,
            "interactions": [],
        }

    # Active prescriptions (normal refills)
    for _ in range(active_count):
        if med_idx >= len(med_pool):
            break
        med = med_pool[med_idx]
        med_idx += 1
        rx = _make_rx(med, "active", ctx.rng.randint(2, 6), ctx.rng.randint(90, 365))
        ctx.base["prescriptions"].append(rx)
        active_rx_ids.append(rx["id"])

    # Zero-refill prescriptions
    for _ in range(zero_refill_count):
        if med_idx >= len(med_pool):
            break
        med = med_pool[med_idx]
        med_idx += 1
        rx = _make_rx(med, "active", 0, ctx.rng.randint(30, 180))
        ctx.base["prescriptions"].append(rx)
        active_rx_ids.append(rx["id"])
        if zero_refill_rx_id is None:
            zero_refill_rx_id = rx["id"]

    # Expiring-soon prescriptions
    for _ in range(expiring_soon_count):
        if med_idx >= len(med_pool):
            break
        med = med_pool[med_idx]
        med_idx += 1
        rx = _make_rx(med, "active", ctx.rng.randint(0, 2), ctx.rng.randint(5, 25))
        ctx.base["prescriptions"].append(rx)
        active_rx_ids.append(rx["id"])
        expiring_rx_ids.append(rx["id"])

    # Expired prescriptions
    for _ in range(expired_count):
        if med_idx >= len(med_pool):
            break
        med = med_pool[med_idx]
        med_idx += 1
        rx = _make_rx(med, "expired", 0, -ctx.rng.randint(1, 90))
        ctx.base["prescriptions"].append(rx)

    # Interaction pair -- two active meds with mutual conflict entries
    if interaction_pair and len(_INTERACTION_PAIRS) > 0:
        pair = ctx.rng.choice(_INTERACTION_PAIRS)
        pair_meds = [
            next((m for m in _MEDICATIONS if m["name"] == pair[0]), None),
            next((m for m in _MEDICATIONS if m["name"] == pair[1]), None),
        ]
        if pair_meds[0] and pair_meds[1]:
            rx_ids_pair: list[str] = []
            for k, pm in enumerate(pair_meds):
                # Check if this medication is already in prescriptions
                existing = next((r for r in ctx.base["prescriptions"] if r["medication"] == pm["name"]), None)
                if existing:
                    rx_ids_pair.append(existing["id"])
                else:
                    rx = _make_rx(pm, "active", ctx.rng.randint(1, 4), ctx.rng.randint(60, 200))
                    ctx.base["prescriptions"].append(rx)
                    active_rx_ids.append(rx["id"])
                    rx_ids_pair.append(rx["id"])

            # Set interactions on both
            for rx_dict in ctx.base["prescriptions"]:
                if rx_dict["id"] == rx_ids_pair[0]:
                    rx_dict["interactions"] = [pair[1]]
                elif rx_dict["id"] == rx_ids_pair[1]:
                    rx_dict["interactions"] = [pair[0]]

            interacting_rx_ids = rx_ids_pair
            interacting_medications = list(pair)

    return {
        "active_rx_ids": active_rx_ids,
        "zero_refill_rx_id": zero_refill_rx_id,
        "expiring_rx_ids": expiring_rx_ids,
        "interacting_rx_ids": interacting_rx_ids,
        "interacting_medications": interacting_medications,
    }


# ---------------------------------------------------------------------------
# 6. lab_results_panel
# ---------------------------------------------------------------------------

@_register("lab_results_panel")
def build_lab_results_panel(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Generate lab results across dates and statuses.

    Params: resulted_count (int), pending_count (int), abnormal_count (int),
            critical_count (int), trend_test (str), trend_values (list[str])
    Outputs: resulted_lab_ids, pending_lab_ids, abnormal_lab_ids, critical_lab_id,
             trend_lab_ids, trend_test_name
    """
    resulted_count = params.get("resulted_count", 3)
    pending_count = params.get("pending_count", 1)
    abnormal_count = params.get("abnormal_count", 1)
    critical_count = params.get("critical_count", 0)
    trend_test = params.get("trend_test", None)
    trend_values = params.get("trend_values", None)

    if "lab_results" not in ctx.base:
        ctx.base["lab_results"] = []

    providers = ctx.base.get("providers", [])
    pcp_id = ctx.base.get("patient", {}).get("pcp_id", "prov_1")

    # Available ordering providers (non-billing, non-admin)
    ordering_providers = [p["id"] for p in providers if p.get("specialty") not in ("billing", "admin")]
    if not ordering_providers:
        ordering_providers = [pcp_id]

    lab_pool = list(_LAB_TESTS)
    ctx.rng.shuffle(lab_pool)
    lab_idx = 0

    resulted_lab_ids: list[str] = []
    pending_lab_ids: list[str] = []
    abnormal_lab_ids: list[str] = []
    critical_lab_id: str | None = None
    trend_lab_ids: list[str] = []
    trend_test_name: str | None = None

    def _pick_lab() -> dict[str, Any]:
        nonlocal lab_idx
        lab = lab_pool[lab_idx % len(lab_pool)]
        lab_idx += 1
        return lab

    def _make_lab(test: dict, flag: str, status: str, days_ago: int, value_override: str | None = None) -> dict[str, Any]:
        lab_id = ctx.next_id("lab")
        collected_at = ctx.now - timedelta(days=days_ago)
        value = value_override or test[flag] if flag in test else test["normal"]
        ordered_by = ctx.rng.choice(ordering_providers)
        return {
            "id": lab_id,
            "test_name": test["name"],
            "test_code": test["code"],
            "ordered_by": ordered_by,
            "collected_at": collected_at.isoformat(),
            "value": value,
            "unit": test["unit"],
            "reference_range": test["ref"],
            "flag": flag,
            "status": status,
        }

    # Normal resulted labs
    normal_count = max(0, resulted_count - abnormal_count - critical_count)
    for _ in range(normal_count):
        test = _pick_lab()
        # Check if this is a Lipid Panel component -- if the test name matches a
        # lipid component, it's already individual.  We generate panel tests
        # only when explicitly requested via trend_test.
        lab = _make_lab(test, "normal", "resulted", ctx.rng.randint(1, 60))
        ctx.base["lab_results"].append(lab)
        resulted_lab_ids.append(lab["id"])

    # Abnormal labs
    for _ in range(abnormal_count):
        test = _pick_lab()
        lab = _make_lab(test, "abnormal", "resulted", ctx.rng.randint(1, 30))
        ctx.base["lab_results"].append(lab)
        resulted_lab_ids.append(lab["id"])
        abnormal_lab_ids.append(lab["id"])

    # Critical labs
    for _ in range(critical_count):
        test = _pick_lab()
        lab = _make_lab(test, "critical", "resulted", ctx.rng.randint(0, 3))
        ctx.base["lab_results"].append(lab)
        resulted_lab_ids.append(lab["id"])
        abnormal_lab_ids.append(lab["id"])
        if critical_lab_id is None:
            critical_lab_id = lab["id"]

    # Pending labs
    for _ in range(pending_count):
        test = _pick_lab()
        lab_id = ctx.next_id("lab")
        collected_at = ctx.now - timedelta(days=ctx.rng.randint(0, 2))
        ordered_by = ctx.rng.choice(ordering_providers)
        lab = {
            "id": lab_id,
            "test_name": test["name"],
            "test_code": test["code"],
            "ordered_by": ordered_by,
            "collected_at": collected_at.isoformat(),
            "value": "",
            "unit": test["unit"],
            "reference_range": test["ref"],
            "flag": "normal",
            "status": "pending",
        }
        ctx.base["lab_results"].append(lab)
        pending_lab_ids.append(lab_id)

    # Trend test -- create a time series of the same test
    if trend_test and trend_values:
        trend_test_info = next((t for t in _LAB_TESTS if t["name"] == trend_test), None)
        if trend_test_info:
            trend_test_name = trend_test
            for i, val in enumerate(trend_values):
                days_ago = (len(trend_values) - i) * 90  # quarterly spacing
                flag = "normal"
                try:
                    # Determine flag from reference range
                    ref_parts = trend_test_info["ref"].split("-")
                    if len(ref_parts) == 2:
                        low, high = float(ref_parts[0]), float(ref_parts[1])
                        v = float(val)
                        if v > high * 1.5 or v < low * 0.5:
                            flag = "critical"
                        elif v > high or v < low:
                            flag = "abnormal"
                except (ValueError, IndexError):
                    pass

                lab = _make_lab(trend_test_info, flag, "resulted", days_ago, value_override=val)
                ctx.base["lab_results"].append(lab)
                trend_lab_ids.append(lab["id"])

    return {
        "resulted_lab_ids": resulted_lab_ids,
        "pending_lab_ids": pending_lab_ids,
        "abnormal_lab_ids": abnormal_lab_ids,
        "critical_lab_id": critical_lab_id,
        "trend_lab_ids": trend_lab_ids,
        "trend_test_name": trend_test_name,
    }


# ---------------------------------------------------------------------------
# 7. message_threads
# ---------------------------------------------------------------------------

@_register("message_threads")
def build_message_threads(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Create message threads with realistic clinical conversations.

    Params: thread_count (int), unread_count (int), categories (list[str]),
            include_billing (bool), include_rx_renewal (bool)
    Outputs: thread_ids, unread_msg_ids, billing_thread_id, rx_renewal_thread_id,
             all_msg_ids
    """
    thread_count = params.get("thread_count", 3)
    unread_count = params.get("unread_count", 2)
    categories = params.get("categories", ["clinical"])
    include_billing = params.get("include_billing", False)
    include_rx_renewal = params.get("include_rx_renewal", False)

    if "messages" not in ctx.base:
        ctx.base["messages"] = []

    providers = ctx.base.get("providers", [])
    clinical_providers = [p for p in providers if p.get("specialty") not in ("billing", "admin")]
    billing_providers = [p for p in providers if p.get("specialty") == "billing"]
    pcp_id = ctx.base.get("patient", {}).get("pcp_id", "prov_1")

    thread_ids: list[str] = []
    unread_msg_ids: list[str] = []
    all_msg_ids: list[str] = []
    billing_thread_id: str | None = None
    rx_renewal_thread_id: str | None = None
    unread_assigned = 0

    for t in range(thread_count):
        thread_id = ctx.next_id("thread")
        thread_ids.append(thread_id)

        # Decide category for this thread
        if include_billing and billing_thread_id is None and t == thread_count - 2:
            cat = "billing"
        elif include_rx_renewal and rx_renewal_thread_id is None and t == thread_count - 1:
            cat = "rx_renewal"
        elif categories:
            cat = ctx.rng.choice(categories)
        else:
            cat = "clinical"

        # Pick provider for the thread
        if cat == "billing" and billing_providers:
            prov_id = billing_providers[0]["id"]
        elif clinical_providers:
            prov_id = ctx.rng.choice(clinical_providers)["id"]
        else:
            prov_id = pcp_id

        # Pick subject
        if cat == "billing":
            subject = ctx.rng.choice(_BILLING_SUBJECTS)
        elif cat == "rx_renewal":
            subject = ctx.rng.choice(_RX_RENEWAL_SUBJECTS)
        else:
            subject = ctx.rng.choice(_CLINICAL_SUBJECTS)

        # Create 2-4 messages per thread (alternating provider/patient)
        msgs_in_thread = ctx.rng.randint(2, 4)
        for m in range(msgs_in_thread):
            msg_id = ctx.next_id("msg")
            from_type = "provider" if m % 2 == 0 else "patient"
            timestamp = ctx.now - timedelta(
                days=ctx.rng.randint(0, 14),
                hours=ctx.rng.randint(0, 23),
            )

            # Last message in unread threads should be unread (from provider)
            is_last = m == msgs_in_thread - 1
            is_read = True
            if is_last and from_type == "provider" and unread_assigned < unread_count:
                is_read = False
                unread_assigned += 1

            body = ctx.fake.paragraph(nb_sentences=ctx.rng.randint(2, 4))
            msg_dict = {
                "id": msg_id,
                "from_type": from_type,
                "provider_id": prov_id,
                "subject": subject,
                "body": body,
                "thread_id": thread_id,
                "timestamp": timestamp.isoformat(),
                "is_read": is_read,
                "category": cat,
            }
            ctx.base["messages"].append(msg_dict)
            all_msg_ids.append(msg_id)
            if not is_read:
                unread_msg_ids.append(msg_id)

        if cat == "billing":
            billing_thread_id = thread_id
        elif cat == "rx_renewal":
            rx_renewal_thread_id = thread_id

    return {
        "thread_ids": thread_ids,
        "unread_msg_ids": unread_msg_ids,
        "billing_thread_id": billing_thread_id,
        "rx_renewal_thread_id": rx_renewal_thread_id,
        "all_msg_ids": all_msg_ids,
    }


# ---------------------------------------------------------------------------
# 8. referral_chain
# ---------------------------------------------------------------------------

@_register("referral_chain")
def build_referral_chain(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Create referrals in various states.

    Params: approved_count (int), pending_count (int), denied_count (int),
            with_prior_auth (bool), expiring_soon (bool)
    Outputs: approved_ref_ids, pending_ref_ids, denied_ref_ids,
             prior_auth_ref_id, expiring_ref_id
    """
    approved_count = params.get("approved_count", 1)
    pending_count = params.get("pending_count", 1)
    denied_count = params.get("denied_count", 0)
    with_prior_auth = params.get("with_prior_auth", False)
    expiring_soon = params.get("expiring_soon", False)

    if "referrals" not in ctx.base:
        ctx.base["referrals"] = []

    providers = ctx.base.get("providers", [])
    pcp_id = ctx.base.get("patient", {}).get("pcp_id", "prov_1")
    specialist_specs = [p for p in providers if p.get("specialty") not in ("pcp", "billing", "admin")]

    # Specialties available for referrals
    available_specialties = list({p["specialty"] for p in specialist_specs}) or ["cardiology", "dermatology"]

    approved_ref_ids: list[str] = []
    pending_ref_ids: list[str] = []
    denied_ref_ids: list[str] = []
    prior_auth_ref_id: str | None = None
    expiring_ref_id: str | None = None

    def _make_ref(status: str, expires_days: int, prior_auth: bool = False) -> dict[str, Any]:
        ref_id = ctx.next_id("ref")
        specialty = ctx.rng.choice(available_specialties)
        to_prov = next((p for p in specialist_specs if p["specialty"] == specialty), None)
        to_prov_id = to_prov["id"] if to_prov else None
        reason = ctx.rng.choice([
            "Specialist consultation",
            "Further evaluation needed",
            "Follow-up recommended by PCP",
            "Diagnostic imaging required",
        ])
        prior_auth_status = "not_required"
        if prior_auth:
            prior_auth_status = "approved" if status == "approved" else "pending"

        return {
            "id": ref_id,
            "from_provider_id": pcp_id,
            "to_specialty": specialty,
            "to_provider_id": to_prov_id,
            "reason": reason,
            "status": status,
            "prior_auth_required": prior_auth,
            "prior_auth_status": prior_auth_status,
            "expires_at": (ctx.now + timedelta(days=expires_days)).isoformat(),
            "notes": "",
        }

    # Approved
    for i in range(approved_count):
        needs_auth = with_prior_auth and prior_auth_ref_id is None and i == 0
        ref = _make_ref("approved", ctx.rng.randint(60, 180), prior_auth=needs_auth)
        ctx.base["referrals"].append(ref)
        approved_ref_ids.append(ref["id"])
        if needs_auth:
            prior_auth_ref_id = ref["id"]

    # Pending
    for _ in range(pending_count):
        ref = _make_ref("requested", ctx.rng.randint(30, 90))
        ctx.base["referrals"].append(ref)
        pending_ref_ids.append(ref["id"])

    # Denied
    for _ in range(denied_count):
        ref = _make_ref("denied", ctx.rng.randint(30, 90))
        ctx.base["referrals"].append(ref)
        denied_ref_ids.append(ref["id"])

    # Expiring soon referral
    if expiring_soon:
        ref = _make_ref("approved", ctx.rng.randint(3, 10))
        ctx.base["referrals"].append(ref)
        approved_ref_ids.append(ref["id"])
        expiring_ref_id = ref["id"]

    return {
        "approved_ref_ids": approved_ref_ids,
        "pending_ref_ids": pending_ref_ids,
        "denied_ref_ids": denied_ref_ids,
        "prior_auth_ref_id": prior_auth_ref_id,
        "expiring_ref_id": expiring_ref_id,
    }


# ---------------------------------------------------------------------------
# 9. insurance_claims
# ---------------------------------------------------------------------------

@_register("insurance_claims")
def build_insurance_claims(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Create insurance claims in various statuses.

    Params: approved_count (int), denied_count (int), processing_count (int),
            with_eob (bool), near_appeal_deadline (bool)
    Outputs: approved_claim_ids, denied_claim_ids, processing_claim_ids,
             appealable_claim_id, total_patient_responsibility
    """
    approved_count = params.get("approved_count", 1)
    denied_count = params.get("denied_count", 0)
    processing_count = params.get("processing_count", 0)
    with_eob = params.get("with_eob", False)
    near_appeal_deadline = params.get("near_appeal_deadline", False)

    if "claims" not in ctx.base:
        ctx.base["claims"] = []

    providers = ctx.base.get("providers", [])
    appointments = ctx.base.get("appointments", [])
    completed_apts = [a for a in appointments if a.get("status") == "completed"]

    approved_claim_ids: list[str] = []
    denied_claim_ids: list[str] = []
    processing_claim_ids: list[str] = []
    appealable_claim_id: str | None = None
    total_patient_responsibility = Decimal("0")

    # Procedure and diagnosis code pools
    proc_codes = ["99213", "99214", "99215", "93000", "80053", "71046", "36415"]
    diag_codes = ["E11.65", "I10", "J06.9", "M54.5", "Z00.00", "K21.0", "R51"]

    def _make_claim(status: str, appeal_days: int, eob: bool = False) -> dict[str, Any]:
        clm_id = ctx.next_id("clm")
        service_date = (ctx.now - timedelta(days=ctx.rng.randint(7, 120))).date()

        # Link to a completed appointment if available
        apt = completed_apts.pop(0) if completed_apts else None
        apt_id = apt["id"] if apt else ctx.next_id("apt")
        prov_id = apt["provider_id"] if apt else (ctx.rng.choice([p["id"] for p in providers]) if providers else "prov_1")

        amount_billed = Decimal(str(ctx.rng.randint(100, 2000)))
        if status == "approved":
            amount_covered = Decimal(str(round(float(amount_billed) * ctx.rng.uniform(0.6, 0.9), 2)))
            patient_resp = amount_billed - amount_covered
        elif status == "denied":
            amount_covered = Decimal("0")
            patient_resp = amount_billed
        else:  # processing
            amount_covered = Decimal("0")
            patient_resp = Decimal("0")

        return {
            "id": clm_id,
            "service_date": service_date.isoformat(),
            "provider_id": prov_id,
            "appointment_id": apt_id,
            "procedure_code": ctx.rng.choice(proc_codes),
            "diagnosis_code": ctx.rng.choice(diag_codes),
            "status": status,
            "amount_billed": str(amount_billed),
            "amount_covered": str(amount_covered),
            "patient_responsibility": str(patient_resp),
            "eob_available": eob,
            "appeal_deadline": (ctx.now + timedelta(days=appeal_days)).isoformat(),
        }

    # Approved claims
    for _ in range(approved_count):
        claim = _make_claim("approved", ctx.rng.randint(30, 90), eob=with_eob)
        ctx.base["claims"].append(claim)
        approved_claim_ids.append(claim["id"])
        total_patient_responsibility += Decimal(claim["patient_responsibility"])

    # Denied claims
    for i in range(denied_count):
        is_near = near_appeal_deadline and appealable_claim_id is None and i == 0
        appeal_days = ctx.rng.randint(3, 7) if is_near else ctx.rng.randint(30, 60)
        claim = _make_claim("denied", appeal_days, eob=with_eob)
        ctx.base["claims"].append(claim)
        denied_claim_ids.append(claim["id"])
        if is_near:
            appealable_claim_id = claim["id"]

    # Processing claims
    for _ in range(processing_count):
        claim = _make_claim("processing", ctx.rng.randint(60, 120))
        ctx.base["claims"].append(claim)
        processing_claim_ids.append(claim["id"])

    return {
        "approved_claim_ids": approved_claim_ids,
        "denied_claim_ids": denied_claim_ids,
        "processing_claim_ids": processing_claim_ids,
        "appealable_claim_id": appealable_claim_id,
        "total_patient_responsibility": str(total_patient_responsibility),
    }


# ---------------------------------------------------------------------------
# 10. immunization_record
# ---------------------------------------------------------------------------

@_register("immunization_record")
def build_immunization_record(ctx: PatientPortalSeedContext, params: dict[str, Any]) -> dict[str, Any]:
    """Create a mix of completed and due immunizations.

    Params: completed_count (int), due_count (int), series_incomplete (bool)
    Outputs: completed_imm_ids, due_imm_ids, incomplete_series_imm_id, due_vaccine_names
    """
    completed_count = params.get("completed_count", 3)
    due_count = params.get("due_count", 1)
    series_incomplete = params.get("series_incomplete", False)

    if "immunizations" not in ctx.base:
        ctx.base["immunizations"] = []

    providers = ctx.base.get("providers", [])
    # Constraint: administering_provider_id must reference a provider with available slots
    providers_with_slots = [
        p for p in providers
        if p.get("available_slots") and p.get("specialty") not in ("billing", "admin")
    ]
    if not providers_with_slots:
        providers_with_slots = [p for p in providers if p.get("specialty") not in ("billing", "admin")]
    if not providers_with_slots:
        providers_with_slots = providers[:1] if providers else [{"id": "prov_1"}]

    vaccine_pool = list(_VACCINES)
    ctx.rng.shuffle(vaccine_pool)
    vax_idx = 0

    completed_imm_ids: list[str] = []
    due_imm_ids: list[str] = []
    incomplete_series_imm_id: str | None = None
    due_vaccine_names: list[str] = []

    # Completed immunizations
    for _ in range(completed_count):
        if vax_idx >= len(vaccine_pool):
            vax_idx = 0
        vax = vaccine_pool[vax_idx]
        vax_idx += 1
        imm_id = ctx.next_id("imm")
        admin_prov = ctx.rng.choice(providers_with_slots)
        administered_at = ctx.now - timedelta(days=ctx.rng.randint(30, 730))

        # Next due depends on vaccine type
        if vax.get("annual"):
            next_due = administered_at + timedelta(days=365)
        elif vax.get("interval_years"):
            next_due = administered_at + timedelta(days=vax["interval_years"] * 365)
        else:
            next_due = None  # Series complete, no next due

        imm_dict = {
            "id": imm_id,
            "vaccine_name": vax["name"],
            "administered_at": administered_at.isoformat(),
            "next_due_at": next_due.isoformat() if next_due else None,
            "series_complete": True,
            "administering_provider_id": admin_prov["id"],
        }
        ctx.base["immunizations"].append(imm_dict)
        completed_imm_ids.append(imm_id)

    # Due immunizations (next_due_at is in the past)
    for _ in range(due_count):
        if vax_idx >= len(vaccine_pool):
            vax_idx = 0
        vax = vaccine_pool[vax_idx]
        vax_idx += 1
        imm_id = ctx.next_id("imm")
        admin_prov = ctx.rng.choice(providers_with_slots)
        administered_at = ctx.now - timedelta(days=ctx.rng.randint(365, 1095))
        # next_due is in the past (overdue)
        next_due = ctx.now - timedelta(days=ctx.rng.randint(1, 60))

        imm_dict = {
            "id": imm_id,
            "vaccine_name": vax["name"],
            "administered_at": administered_at.isoformat(),
            "next_due_at": next_due.isoformat(),
            "series_complete": True,
            "administering_provider_id": admin_prov["id"],
        }
        ctx.base["immunizations"].append(imm_dict)
        due_imm_ids.append(imm_id)
        due_vaccine_names.append(vax["name"])

    # Incomplete series
    if series_incomplete:
        # Find a multi-dose vaccine
        series_vax = next((v for v in _VACCINES if v.get("series") and v.get("doses", 0) >= 2), _VACCINES[3])
        imm_id = ctx.next_id("imm")
        admin_prov = ctx.rng.choice(providers_with_slots)
        administered_at = ctx.now - timedelta(days=ctx.rng.randint(30, 180))
        interval = series_vax.get("interval_months", 2) * 30
        next_due = administered_at + timedelta(days=interval)

        imm_dict = {
            "id": imm_id,
            "vaccine_name": series_vax["name"],
            "administered_at": administered_at.isoformat(),
            "next_due_at": next_due.isoformat(),
            "series_complete": False,
            "administering_provider_id": admin_prov["id"],
        }
        ctx.base["immunizations"].append(imm_dict)
        incomplete_series_imm_id = imm_id
        if series_vax["name"] not in due_vaccine_names:
            due_vaccine_names.append(series_vax["name"])

    return {
        "completed_imm_ids": completed_imm_ids,
        "due_imm_ids": due_imm_ids,
        "incomplete_series_imm_id": incomplete_series_imm_id,
        "due_vaccine_names": due_vaccine_names,
    }
