import pytest


@pytest.fixture
def settings(tmp_path):
    from tilapiers.config import Settings

    return Settings.from_env(data_dir=tmp_path / "data", demo=False, secret_key="test-secret",
                             yolo_weights=None, seg_weights=None)
