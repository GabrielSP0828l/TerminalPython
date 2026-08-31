import time

from config import APP_VERSION


class ApplicationMetricsCollector:
    def __init__(self, sync_service, purchase_session, websocket_state_provider,
                 version=APP_VERSION, clock=None):
        self.sync_service = sync_service
        self.purchase_session = purchase_session
        self.websocket_state_provider = websocket_state_provider
        self.version = version
        self.clock = clock or time.monotonic
        self.started_at = self.clock()

    def collect(self):
        session = self.purchase_session
        purchase_active = bool(session.started_at is not None and session.state != "IDLE")
        return {
            "version": self.version,
            "uptimeSeconds": max(0, int(self.clock() - self.started_at)),
            "websocketStatus": self.websocket_state_provider(),
            "lastProductSyncStartedAt": self.sync_service.last_sync_started_at,
            "lastProductSyncCompletedAt": self.sync_service.last_sync_completed_at,
            "lastSuccessfulSyncAt": self.sync_service.last_successful_sync_at,
            "lastSyncError": self.sync_service.last_sync_error,
            "purchaseActive": purchase_active,
            "paymentInProgress": bool(session.payment_in_flight),
        }
