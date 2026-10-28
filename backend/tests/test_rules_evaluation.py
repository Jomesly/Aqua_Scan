from tilapiers.rules import evaluation

LABELS = ["Normal", "Watch", "Refer to technician"]


def test_perfect_agreement_kappa_one():
    pairs = [("Normal", "Normal"), ("Watch", "Watch"), ("Refer to technician", "Refer to technician")]
    r = evaluation.agreement(pairs, LABELS)
    assert r["accuracy"] == 1.0 and r["kappa_w"] == 1.0


def test_neighbor_disagreement_gets_partial_credit():
    near = [("Normal", "Normal"), ("Watch", "Normal"), ("Refer to technician", "Refer to technician"), ("Watch", "Watch")]
    far = [("Normal", "Normal"), ("Refer to technician", "Normal"), ("Refer to technician", "Refer to technician"), ("Watch", "Watch")]
    assert evaluation.agreement(near, LABELS)["kappa_w"] > evaluation.agreement(far, LABELS)["kappa_w"]


def test_refer_recall():
    pairs = [("Refer to technician", "Refer to technician"), ("Normal", "Refer to technician"), ("Normal", "Normal")]
    assert evaluation.refer_recall(pairs) == 0.5


def test_error_stats():
    r = evaluation.error_stats([(10, 11), (20, 18)])
    assert r["n"] == 2 and r["mae"] == 1.5
