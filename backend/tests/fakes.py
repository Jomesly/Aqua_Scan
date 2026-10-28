class FakeScreener:
    """Test double for the YOLO screener: returns one fixed detection."""

    available = True
    name = "fake"
    error = None
    names = {0: "Healthy", 1: "Aeromonas", 2: "TiLV"}

    def __init__(self, cls="Healthy", conf=0.9):
        self.cls, self.conf = cls, conf

    def predict(self, img, conf):
        h, w = img.shape[:2]
        return [{"cls": self.cls, "conf": self.conf, "box": [0, 0, w, h]}] if self.conf >= conf else []

    def info(self):
        return {"name": self.name, "available": True, "error": None, "classes": list(self.names.values())}
