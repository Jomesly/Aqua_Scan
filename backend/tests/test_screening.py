import numpy as np

from tilapiers.vision.screening import Screener


class _Boxes:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        for cls, conf, xyxy in self.rows:
            yield type("Box", (), {"cls": cls, "conf": conf, "xyxy": np.array([xyxy], dtype=float)})()


class FakeYolo:
    """Records the image it was given and returns one box in that image's pixel space."""

    def __init__(self):
        self.seen = None

    def predict(self, img, **kw):
        self.seen = img.shape[:2]
        return [type("Res", (), {"boxes": _Boxes([(2, 0.9, [64, 160, 320, 480])])})()]


def _screener(model):
    s = Screener(None)
    s._model, s.available, s.names = model, True, {0: "Healthy", 1: "Aeromonas", 2: "TiLV"}
    return s


def test_photo_is_stretched_to_the_training_size():
    # The team's Roboflow export stretched every image to 640x640, so a long thin fish photo
    # must be stretched the same way rather than letterboxed.
    model = FakeYolo()
    _screener(model).predict(np.zeros((200, 600, 3), np.uint8), 0.25)
    assert model.seen == (640, 640)


def test_boxes_are_mapped_back_to_the_original_photo():
    out = _screener(FakeYolo()).predict(np.zeros((200, 600, 3), np.uint8), 0.25)
    assert out == [{"cls": "Skin erosion", "conf": 0.9, "box": [60.0, 50.0, 300.0, 150.0]}]
