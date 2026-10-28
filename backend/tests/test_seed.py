from fakes import FakeScreener

from tilapiers.db import Database
from tilapiers.seed import seed_base
from tilapiers.services import Services


def test_demo_seed_statuses(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    svc = Services(Database(settings.db_path), settings, FakeScreener(), None)
    seed_base(svc, demo=True)
    d = {p["pond"]["name"]: p["latest"] for p in svc.dashboard()["ponds"]}
    p1, p2 = d["Pond 1 - Earthen (demo)"], d["Pond 2 - Earthen (demo)"]
    assert (p1["health"], p1["readiness"]) == ("Normal", "Ready")
    assert p2["readiness"] == "Approaching"
    assert p2["health"] == "Refer to technician"
    assert len(svc.review_queue()["fish"]) == 2
    assert svc.weight_model_info()["active"]["kind"] == "ols"
    assert svc.pond_overview(svc.list_ponds()[0]["id"])["growth"]["method"] == "polynomial"
    ev = svc.evaluation()
    assert ev["health"]["n"] >= 5 and ev["readiness"]["n"] >= 5


def test_non_demo_seed_creates_admin_only(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    svc = Services(Database(settings.db_path), settings, FakeScreener(), None)
    seed_base(svc, demo=False)
    assert [u["username"] for u in svc.list_users()] == ["admin"]
    assert svc.list_ponds() == []
    assert svc.get_content("faqs")["title"]
