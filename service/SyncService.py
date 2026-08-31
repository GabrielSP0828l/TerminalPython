import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests
from decimal import Decimal

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
        self.last_sync_started_at = None
        self.last_sync_completed_at = None
        # O banco é aberto somente no ciclo de sync; isso evita I/O de schema
        # durante a construção do serviço/UI.
        self.last_successful_sync_at = self._read_legacy_cursor()
        self.last_sync_error = None

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _complete_sync(self, error=None, successful_at=None):
        self.last_sync_completed_at = self._utc_now()
        self.last_sync_error = str(error)[:300] if error else None
        if successful_at:
            self.last_successful_sync_at = successful_at

    @staticmethod
    def _is_valid_cursor(value):
        if not isinstance(value, str) or not value.strip():
            return False
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return parsed.tzinfo is not None
        except ValueError:
            return False

    def _read_legacy_cursor(self):
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

    def get_last_sync(self):
        database = self.database_factory(self.db_path)
        try:
            database_cursor = database.obter_ultimo_sync()
        finally:
            database.close()
        if self._is_valid_cursor(database_cursor):
            return database_cursor
        return self._read_legacy_cursor()

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
        required = ("id", "nome", "preco")
        missing = [field for field in required if data.get(field) in (None, "")]
        if missing:
            raise ValueError(
                "produto sem campos obrigatórios: " + ", ".join(missing)
            )
        raw_codes = data.get("codigosBarras")
        if raw_codes is None:
            legacy_code = data.get("codigo")
            raw_codes = ([{
                "codigo": str(legacy_code), "tipo": "LEGACY",
                "principal": True, "ativo": True,
            }] if legacy_code not in (None, "") else [])
        if not isinstance(raw_codes, list):
            raise ValueError("codigosBarras deve ser uma lista")
        codes = []
        seen_codes = set()
        for code in raw_codes:
            if not isinstance(code, dict) or code.get("codigo") in (None, ""):
                raise ValueError("código de barras inválido no produto")
            normalized = str(code["codigo"])
            if normalized in seen_codes:
                raise ValueError("código de barras duplicado no produto")
            seen_codes.add(normalized)
            codes.append({
                "codigo": normalized,
                "tipo": str(code.get("tipo") or "INTERNO"),
                "principal": bool(code.get("principal")),
                "ativo": code.get("ativo") is not False,
            })
        principal = next((c["codigo"] for c in codes if c["principal"] and c["ativo"]), None)
        codigo_interno = data.get("codigoInterno") or data.get("codigo")
        if codigo_interno in (None, ""):
            raise ValueError("produto sem codigoInterno")
        return Produtos(
            id=str(data["id"]),
            codigo=principal or str(data.get("codigo") or codigo_interno),
            codigo_interno=str(codigo_interno),
            codigos_barras=codes,
            nome=data["nome"],
            preco=data["preco"],
            preco_original=data.get("precoOriginal", data["preco"]),
            em_promocao=data.get("emPromocao", False),
            promocao_id=data.get("promocaoId"),
            promocao_nome=data.get("promocaoNome"),
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
        self.last_sync_started_at = self._utc_now()
        self.last_sync_error = None
        logger.info("[SYNC] requisitada: %s", origin)
        logger.info("[SYNC] iniciando")
        logger.info("[SYNC] SQLite path: %s", self.db_path)

        terminal = Terminal.load(self.terminal_path)
        if terminal is None or not terminal.activated or not terminal.ativo:
            logger.warning("[SYNC] Terminal ainda não está ativado; sincronização adiada")
            self._complete_sync("Terminal ainda não está ativado")
            return False
        if not self.api_url:
            logger.error("[SYNC] API_URL não configurada")
            self._complete_sync("API_URL não configurada")
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
                self._complete_sync(f"HTTP {response.status_code}")
                return False

            try:
                payload = response.json(parse_float=Decimal)
            except TypeError:
                # Compatibilidade com clientes/dublês que expõem json() sem
                # os argumentos opcionais do requests. A normalização final
                # continua sendo feita por Decimal(str(valor)).
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
                result = database.aplicar_sync(full_sync, changes, sync_at)
            finally:
                database.close()

            logger.info(
                "[SYNC] commit OK; produtosAtivos=%s",
                result["active_products"],
            )
            try:
                self.save_last_sync(sync_at)
            except OSError as error:
                logger.warning("[SYNC] Cursor legado não pôde ser espelhado: %s", error)
            self._complete_sync(successful_at=sync_at)
            logger.info("[SYNC] syncAt salvo: %s", sync_at)
            return True
        except requests.RequestException as error:
            self._complete_sync("Backend indisponível")
            logger.warning("[SYNC] Backend indisponível; endpoint=%s erro=%s", endpoint, error)
        except (ValueError, TypeError) as error:
            self._complete_sync(str(error))
            logger.warning("[SYNC] Resposta inválida; endpoint=%s erro=%s", endpoint, error)
        except Exception:
            self._complete_sync("Falha ao aplicar sincronização")
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
