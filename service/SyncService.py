import threading

import requests

from config import API_URL
from database.DatabaseProdutos import DatabaseProdutos
from model.Produtos import Produtos


class SyncService:

    def get_last_sync(self):
        try:
            with open("database/last_sync.txt", "r") as file:
                return file.read()
        except FileNotFoundError:
            return "2000-01-01T00:00:00"

    def save_last_sync(self, data):
        with open("database/last_sync.txt", "w") as file:
            file.write(data)

    def sincronizar_produtos(self):
        db = DatabaseProdutos()
        try:
            last_sync = self.get_last_sync()

            response = requests.get(
                f"{API_URL}/produtos/sync",
                params={"lastSync": last_sync},
                timeout=10
            )

            if response.status_code != 200:
                print(f"Erro API: {response.status_code}")
                return

            produtos = response.json()

            ultima_data = last_sync

            for p in produtos:
                db.salvar_ou_atualizar(
                    Produtos(
                        id=p.get("id"),
                        codigo=p.get("codigo"),
                        nome=p.get("nome"),
                        preco=p.get("preco"),
                        quantidade=p.get("quantidade"),
                        categoria=p.get("categoria"),
                        unidade_medida=p.get("unidadeMedida"),
                        descricao=p.get("descricao"),
                        foto=p.get("foto"),
                        peso=p.get("peso"),
                        peso_tolerancia=p.get("pesoTolerancia"),
                        create_at=p.get("createAt"),
                        update_at=p.get("updateAt"),
                        status=p.get("status")
                    )
                )

                if p.get("updateAt") and p["updateAt"] > ultima_data:
                    ultima_data = p["updateAt"]

            self.save_last_sync(ultima_data)

            print("Sincronização concluída!")

        except Exception as e:
            print(f"Erro no sync: {e}")

    def iniciar_sync_em_thread(self):
        thread = threading.Thread(
            target=self.sincronizar_produtos,
            daemon=True
        )
        thread.start()
        return thread
