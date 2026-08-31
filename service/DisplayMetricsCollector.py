class DisplayMetricsCollector:
    def __init__(self, screen_provider):
        self.screen_provider = screen_provider

    def collect(self):
        try:
            screen = self.screen_provider()
            size = screen.size()
            width, height = int(size.width()), int(size.height())
            return {"width": width, "height": height,
                    "orientation": "HORIZONTAL" if width >= height else "VERTICAL"}
        except Exception:
            return {"width": None, "height": None, "orientation": None}
