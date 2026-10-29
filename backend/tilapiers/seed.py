"""First-start data: an administrator, FAQ and About Us pages, and (demo mode only)
two example ponds with several completed sampling rounds. Everything the demo
creates is stored with source='demo' and labeled "Demo data" in the UI."""

import json
import math
import os
import random
from datetime import date, timedelta

from .rules import health

FAQS = """## Setting up the sampling station
1. Print the sampling board from **Maintenance → Board**, or from the link on the sampling page. Print it at **100 % scale**; do not use "fit to page".
2. Glue the print onto a flat, matte board. Measure the inner rectangle between the markers with a ruler. If it differs from the printed size, enter the measured size in Maintenance.
3. Fix the phone on a stand so it points straight down at the board.

## Taking the photographs
- Photograph **both sides** of every sampled fish: Side A and Side B.
- All **four corner markers** must be visible and uncovered.
- The whole fish, **including the tail fin**, must lie inside the markers.
- Avoid deep shade, direct glare and motion blur. If a photo fails the check, the app tells you why. Retake it while the fish is still on the board.
- After the photos, weigh the fish on the facility scale and measure its total length with the ruler, then enter both values.

## Reading the Health status
- **Normal**: no visible defect was flagged and the condition factor is in range.
- **Watch**: a possible defect below the referral cutoff, or a condition factor outside the range.
- **Refer to technician**: a visible skin defect flagged at or above the referral cutoff. Set the fish apart until the technician checks it.
- Screening is **not a diagnosis** and does not name a disease. A confirmed diagnosis needs laboratory tests.

## What the defect flags mean
- **Skin erosion**: worn or eroded skin, missing scales or pale patches.
- **Red sores**: red, bleeding sores, ulcers or reddened fins.
- **No visible defect**: nothing was flagged on the photographed sides.

## Reading the Harvest readiness status
- The status combines five indicators: the share of fish at the target size, weight uniformity (CV), growth, condition factor K, and days of culture.
- **Ready** is shown only when all five are met **and** the pond Health status is Normal. Otherwise the status reads *"Size reached - health review needed"*.
- The status describes the pond at the sampling round. It is not a harvest-date forecast, and the harvest decision stays with the caretaker and the technician.

## What do "provisional" and "demo data" mean?
- **Provisional cutoff**: the value has not been confirmed with the BFAR technician yet.
- **Provisional weight model**: weights come from a standard length-weight curve until enough fish with scale weights are recorded and the administrator fits the regression.
- **Demo data**: example records created for presentations. They are never mixed into real results unless an administrator chooses to.
"""

ABOUT = """**Tilapiers** is a smart, web-based hybrid framework of YOLO detectors, image-analysis measurements, regression models and rule-based logic. It supports health monitoring, weight estimation and harvest readiness assessment in outdoor Nile tilapia (*Oreochromis niloticus*) ponds.

It turns the caretaker's routine inspection into a standardized, recorded process. The only equipment it needs is a smartphone on a stand, a sampling board with four corner markers, and the facility's scale and ruler. No sensors are installed at the ponds.

### Modules
- **Fish Health Monitoring**: flags visible skin defects on each sampled fish (skin erosion, red sores) and gives the fish and the pond a status: Normal, Watch or Refer to technician.
- **Fish Weight Estimation**: measures length and area on the corrected board photo, estimates weight by regression, and gives the sample's average weight and the pond's biomass.
- **Harvest Readiness Assessment**: combines size, uniformity, growth, condition and days of culture into Not Ready, Approaching or Ready, with health as a clearance check.

### Researchers
John Lawrence S. Castillo · Nick Jamesly M. Figuracion · Ferdinand T. Masi Jr. · Julian J. Urbano
College of Computer Studies, Technological Institute of the Philippines, Quezon City
CS 307 Thesis · Adviser: Ms. Janice Capule · in cooperation with BFAR

*Tilapiers supports, and does not replace, the decisions of the caretaker and the technician.*
"""


def seed_base(svc, demo=False):
    if not svc.db.one("SELECT id FROM users LIMIT 1"):
        if demo:
            for role in ("admin", "caretaker", "technician"):
                svc.create_user({"username": role, "password": role + "123", "role": role,
                                 "full_name": {"admin": "Administrator", "caretaker": "Pond Caretaker",
                                               "technician": "BFAR Technician"}[role]})
        else:
            pw = os.environ.get("TILAPIERS_ADMIN_PASSWORD", "admin123")
            svc.create_user({"username": "admin", "password": pw, "role": "admin", "full_name": "Administrator"})
    if not svc.db.one("SELECT key FROM content WHERE key = 'faqs'"):
        svc.set_content("faqs", "Frequently asked questions", FAQS)
    if not svc.db.one("SELECT key FROM content WHERE key = 'about'"):
        svc.set_content("about", "About Tilapiers", ABOUT)
    if demo and not svc.db.one("SELECT id FROM ponds LIMIT 1"):
        seed_demo(svc)


# (name, stocked count, days of culture per round, logistic growth: max g, rate, midpoint, CV, capture)
DEMO_PONDS = [
    ("Pond 1 - Earthen (demo)", 1500, [30, 60, 90, 120, 150], (450, 0.035, 110), 0.15),
    ("Pond 2 - Earthen (demo)", 1200, [30, 60, 90, 110], (480, 0.040, 90), 0.17),
]
CONDITIONS = ["open sunlight", "shade", "overcast"]
FISH_PER_ROUND = 20


def _mean_weight(day, params):
    top, rate, mid = params
    return top / (1 + math.exp(-rate * (day - mid)))


def seed_demo(svc):
    rng = random.Random(26)
    stocked = date.today() - timedelta(days=160)
    plan = []
    for p_i, (name, count, days, growth, cv) in enumerate(DEMO_PONDS):
        pond = svc.create_pond({"name": name, "location": "BFAR demo site", "setup": "Earthen pond",
                                "stocked_at": stocked.isoformat(), "stocked_count": count}, source="demo")
        for r_i, doc in enumerate(days):
            rnd = svc.create_round(pond["id"], {"sampled_at": (stocked + timedelta(days=doc)).isoformat(),
                                                "days_of_culture": doc, "board_mode": True,
                                                "capture_condition": CONDITIONS[(r_i + p_i) % 3]},
                                   "caretaker", source="demo")
            mean = _mean_weight(doc, growth)
            latest = r_i == len(days) - 1
            for k in range(FISH_PER_ROUND):
                w = max(5.0, rng.gauss(mean, cv * mean))
                ruler = (w / 0.0145) ** (1 / 3) * rng.uniform(0.985, 1.015)
                img_len = ruler * rng.uniform(0.97, 1.03)
                area = 0.21 * img_len ** 2 * rng.uniform(0.96, 1.04)
                cls, conf = health.NO_DEFECT, round(rng.uniform(0.82, 0.97), 3)
                if p_i == 1 and latest and k in (3, 11):
                    cls, conf = health.RED_SORES, (0.62, 0.71)[k == 11]
                fish = svc.add_fish(rnd["id"], {"scale_weight_g": round(w, 1), "ruler_length_cm": round(ruler, 1)},
                                    source="demo")
                svc.db.update("fish", fish["id"], {"cls": cls, "conf": conf, "sides": 2,
                                                   "length_cm": round(img_len, 2), "area_cm2": round(area, 2)})
            plan.append((rnd["id"], p_i, r_i, latest))

    svc.fit_weight_model("seed", include_demo=True)
    t, model = svc.thresholds(), svc.active_weight_model()
    for rid, p_i, r_i, latest in plan:
        for f in svc.db.all("SELECT id FROM fish WHERE round_id = ?", (rid,)):
            svc._derive(f["id"], t, model)
        done = svc.complete_round(rid)
        a = done["assessment"]
        # Technician's independent assessments for the earlier rounds (the latest ones wait in the queue)
        if not latest:
            tech_h = a["health"]["status"]
            tech_r = a["readiness"]["status"]
            if tech_r not in ("Not Ready", "Approaching", "Ready"):
                tech_r = "Approaching"
            if (p_i, r_i) == (0, 2):
                tech_r = "Approaching"  # one disagreement, as in real life
            svc.set_round_assessment(rid, tech_h if tech_h in ("Normal", "Watch", "Refer to technician") else None,
                                     tech_r, "technician")
            for f in svc.db.all("SELECT id, cls FROM fish WHERE round_id = ? LIMIT 6", (rid,)):
                svc.review_fish(f["id"], "none" if f["cls"] == health.NO_DEFECT else "red_sores", None, "technician")
        elif p_i == 0:
            svc.set_round_assessment(rid, health.NORMAL, "Ready", "technician")
    svc.db.set_setting("demo_seeded", json.dumps(True))
