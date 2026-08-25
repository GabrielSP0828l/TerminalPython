import logging
import os
import threading
from datetime import datetime
from pathlib import Path

import requests

from config import (
    API_URL,
    DATABASE_PATH,
    LAST_SYNC_PATH,
    PRODUCT_SYNC_INTERVAL_SECONDS,
    TERMINAL_CONFIG_PATH,
)
from database.DatabaseProdutos import DatabaseProdutos
from model.Produtos import Produtos
from model.Terminal import Terminal


logger = logging.getLogger(__name__)


class SyncService:

    def __init__(
        self,
        api_url=API_URL,
        db_path=DATABASE_PATH,
        last_sync_path=LAST_SYNC_PATH,
        terminal_path=TERMINAL_CONFIG_PATH,
        interval_seconds=PRODUCT_SYNC_INTERVAL_SECONDS,
        session=None,
        database_factory=DatabaseProdutos,
    ):
        self.api_url = (api_url or "").rstrip("/")
        self.db_path = Path(db_path).resolve()
        self.last_sync_path = Path(last_sync_path).resolve()
        self.terminal_path = Path(terminal_path).resolve()
        self.interval_seconds = interval_seconds
        self.session = session or requests.Session()
        self.database_factory = database_factory

        self.sync_in_progress = False
        self.sync_pending = False
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._scheduler_thread = None
        self._worker_thread = None

    @staticmethod
    def _is_valid_cursor(value):
        if not isinstance(value, str) or not value.strip():
            return False
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return parsed.tzinfo is not None
        except ValueError:
            return False

    def get_last_sync(self):
        try:
            value = self.last_sync_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        if self._is_valid_cursor(value):
            return value
        logger.warning(
            "[SYNC] Cursor legado/inválido ignorado; será executado FULL SYNC"
        )
        try:
            self.last_sync_path.unlink()
        except OSError as error:
            logger.warning("[SYNC] Não foi possível remover cursor inválido: %s", error)
        return None

    def get_cache_state(self):
        database = self.database_factory(self.db_path)
        try:
            return database.obter_estado_catalogo()
        finally:
            database.close()

    def save_last_sync(self, sync_at):
        if not self._is_valid_cursor(sync_at):
            raise ValueError("syncAt inválido")
        self.last_sync_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.last_sync_path.with_suffix(
            f"{self.last_sync_path.suffix}.tmp"
        )
        temporary_path.write_text(sync_at, encoding="utf-8")
        os.replace(temporary_path, self.last_sync_path)

    @staticmethod
    def _map_product(data):
        if not isinstance(data, dict):
            raise ValueError("produto do UPSERT não é um objeto JSON")
        required = ("id", "codigo", "nome", "preco")
        missing = [field for field in required if data.get(field) in (None, "")]
        if missing:
            raise ValueError(
                "produto sem campos obrigatórios: " + ", ".join(missing)
            )
        return Produtos(
            id=str(data["id"]),
            codigo=str(data["codigo"]),
            nome=data["nome"],
            preco=data["preco"],
            quantidade=data.get("quantidade"),
            categoria=data.get("categoria"),
            unidade_medida=data.get("unidadeMedida"),
            descricao=data.get("descricao"),
            foto=data.get("foto"),
            peso=data.get("peso"),
            peso_tolerancia=data.get("pesoTolerancia"),
            create_at=data.get("createdAt"),
            update_at=data.get("updatedAt"),
            status=data.get("ativo", True),
        )

    @classmethod
    def _parse_response(cls, payload):
        if not isinstance(payload, dict):
            raise ValueError("resposta de sync deve ser um objeto JSON")
        sync_at = payload.get("syncAt")
        full_sync = payload.get("fullSync")
        raw_changes = payload.get("changes")
        if not cls._is_valid_cursor(sync_at):
            raise ValueError("resposta sem syncAt UTC válido")
        if not isinstance(full_sync, bool):
            raise ValueError("resposta sem fullSync booleano")
        if not isinstance(raw_changes, list):
            raise ValueError("resposta sem lista changes")

        changes = []
        seen_ids = set()
        for item in raw_changes:
            if not isinstance(item, dict):
                raise ValueError("change não é um objeto JSON")
            product_id = item.get("productId")
            operation = item.get("operation")
            if product_id in (None, ""):
                raise ValueError("change sem productId")
            product_id = str(product_id)
            if product_id in seen_ids:
                raise ValueError("resposta contém productId duplicado")
            seen_ids.add(product_id)

            if operation == "UPSERT":
                product = cls._map_product(item.get("produto"))
                if product.id != product_id:
                    raise ValueError("productId diverge de produto.id")
                changes.append((operation, product_id, product))
            elif operation == "REMOVE":
                if item.get("produto") is not None:
                    raise ValueError("REMOVE deve possuir produto nulo")
                changes.append((operation, product_id, None))
            else:
                raise ValueError(f"operação de sync desconhecida: {operation}")
        if full_sync and any(operation != "UPSERT" for operation, _, _ in changes):
            raise ValueError("FULL SYNC deve conter somente UPSERT")
        return sync_at, full_sync, changes

    def sincronizar_produtos(self, origin="MANUAL"):
        logger.info("[SYNC] requisitada: %s", origin)
        logger.info("[SYNC] iniciando")
        logger.info("[SYNC] SQLite path: %s", self.db_path)

        terminal = Terminal.load(self.terminal_path)
        if terminal is None or not terminal.activated or not terminal.ativo:
            logger.warning("[SYNC] Terminal ainda não está ativado; sincronização adiada")
            return False
        if not self.api_url:
            logger.error("[SYNC] API_URL não configurada")
            return False

        endpoint = "/produtos/sync"

        try:
            cache_state = self.get_cache_state()
            persisted_cursor = self.get_last_sync()
            last_sync = persisted_cursor if cache_state["consistent"] else None
            logger.info(
                "[SYNC-DIAG] sqlite=%s localProducts=%s activeProducts=%s "
                "catalogInitialized=%s cacheConsistent=%s lastSync=%s",
                self.db_path,
                cache_state["total"],
                cache_state["ativos"],
                str(cache_state["initialized"]).lower(),
                str(cache_state["consistent"]).lower(),
                persisted_cursor or "<ausente>",
            )
            if not cache_state["consistent"]:
                logger.warning(
                    "[SYNC] Cache local não inicializado/inconsistente (%s); "
                    "ignorando lastSync e solicitando FULL SYNC",
                    cache_state["reason"],
                )
            logger.info("[SYNC] lastSync=%s", last_sync or "<FULL SYNC>")

            params = {"uuidTerminal": terminal.terminalId}
            if last_sync is not None:
                params["lastSync"] = last_sync
            response = self.session.get(
                f"{self.api_url}{endpoint}", params=params, timeout=10
            )
            if response.status_code != 200:
                logger.warning(
                    "[SYNC] Falha HTTP %s; endpoint=%s",
                    response.status_code,
                    endpoint,
                )
                return False

            payload = response.json()
            sync_at, full_sync, changes = self._parse_response(payload)
            if last_sync is None and not full_sync:
                raise ValueError(
                    "backend retornou incremental para requisição de FULL SYNC"
                )
            upserts = sum(operation == "UPSERT" for operation, _, _ in changes)
            removes = sum(operation == "REMOVE" for operation, _, _ in changes)
            logger.info("[SYNC] fullSync=%s", str(full_sync).lower())
            logger.info("[SYNC] upserts=%s removes=%s", upserts, removes)

            database = self.database_factory(self.db_path)
            try:
                result = database.aplicar_sync(full_sync, changes)
            finally:
                database.close()

            logger.info(
                "[SYNC] commit OK; produtosAtivos=%s",
                result["active_products"],
            )
            self.save_last_sync(sync_at)
            logger.info("[SYNC] syncAt salvo: %s", sync_at)
            return True
        except requests.RequestException as error:
            logger.warning("[SYNC] Backend indisponível; endpoint=%s erro=%s", endpoint, error)
        except (ValueError, TypeError) as error:
            logger.warning("[SYNC] Resposta inválida; endpoint=%s erro=%s", endpoint, error)
        except Exception:
            logger.exception("[SYNC] Falha ao aplicar alterações; endpoint=%s", endpoint)
        return False

    def request_sync(self, origin="MANUAL"):
        with self._state_lock:
            if self._stop_event.is_set():
                return False
            if self.sync_in_progress:
                self.sync_pending = True
                logger.info("[SYNC] já em andamento; marcando sync_pending")
                return False
            self.sync_in_progress = True
            self._worker_thread = threading.Thread(
                target=self._run_requested_sync,
                args=(origin,),
                name="product-sync-worker",
                daemon=True,
            )
            self._worker_thread.start()
            return True

    def _run_requested_sync(self, origin):
        current_origin = origin
        while not self._stop_event.is_set():
            try:
                self.sincronizar_produtos(current_origin)
            finally:
                with self._state_lock:
                    if self.sync_pending and not self._stop_event.is_set():
                        self.sync_pending = False
                        current_origin = "PENDING"
                        logger.info(
                            "[SYNC] sync pendente detectada; executando novamente"
                        )
                        continue
                    self.sync_in_progress = False
                    self._worker_thread = None
                    return
        with self._state_lock:
            self.sync_in_progress = False
            self.sync_pending = False
            self._worker_thread = None

    def _run_scheduler(self):
        self.request_sync("STARTUP")
        while not self._stop_event.wait(self.interval_seconds):
            self.request_sync("PERIODIC")

    def iniciar_sync_em_thread(self):
        if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
            return self._scheduler_thread
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(
            target=self._run_scheduler,
            name="product-sync-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        return self._scheduler_thread

    def stop(self):
        self._stop_event.set()
        scheduler = self._scheduler_thread
        worker = self._worker_thread
        if scheduler and scheduler.is_alive():
            scheduler.join(timeout=2)
        if worker and worker.is_alive():
            worker.join(timeout=2)
