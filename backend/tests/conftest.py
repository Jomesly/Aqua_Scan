import io
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tilapiers.config import Settings
from tilapiers.main import create_app


@pytest.fixture
def make_client(tmp_path):
    def _make(**overrides):
        values = dict(data_dir=tmp_path / "data", demo=False, sensor_mode="off",
                      notify_channel="none", ingest_token="secret")
        values.update(overrides)
        settings = Settings.from_env(**values)
        app = create_app(settings, start_monitor=False)
        return TestClient(app)
    return _make


@pytest.fixture
def client(make_client):
    with make_client() as c:
        yield c


@pytest.fixture
def pond(client):
    r = client.post("/api/ponds", json={"name": "Test pond", "stocked_at": time.time() - 100 * 86400})
    assert r.status_code == 201
    return r.json()


def board_photo(seed=0, size=(800, 600)):
    """A textured synthetic 'fish on a board' photo that passes the quality check."""
    rng = np.random.default_rng(seed)
    img = np.full((size[1], size[0], 3), 200, np.uint8)
    img += rng.integers(0, 40, img.shape, dtype=np.uint8)
    img[200:400, 100:700] = [150, 120, 100]
    img[250:350, 180:240] = [190, 70, 70]
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="JPEG")
    return buf.getvalue()
