import requests
from datetime import datetime


class Produtos:

    def __init__(self,
                 nome,
                 quantidade,
                 preco,
                 categoria,
                 codigo,
                 unidade_medida=None,
                 descricao=None,
                 foto=None,
                 peso=None,
                 peso_tolerancia=None,
                 create_at=None,
                 update_at=None,
                 status=True,
                 id=None):


        self.id = id
        self.codigo = codigo
        self.nome = nome
        self.quantidade = quantidade
        self.preco = preco
        self.categoria = categoria
        self.unidade_medida = unidade_medida
        self.descricao = descricao
        self.foto = foto
        self.peso = peso
        self.peso_tolerancia = peso_tolerancia
        self.create_at = create_at if create_at else datetime.now().isoformat()
        self.update_at = update_at
        self.status = status

    def __repr__(self):

        return (
            f"Produto("
            f"id={self.id}, "
            f"nome={self.nome}, "
            f"peso={self.peso}, "
            f"tolerancia={self.peso_tolerancia}, "
            f"preco={self.preco}"
            f")"
        )
    @staticmethod
    def get_produtos_api(url_base, page=0, size=50):
        try:
            url = f"{url_base}?page={page}&size={size}"

            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                print(f"Erro API: {response.status_code}")
                return [], None

            data = response.json()

            content = data.get("content", [])

            produtos = []

            for item in content:
                produtos.append(
                    Produtos(
                        id=item.get("id"),
                        codigo=item.get("codigo"),
                        nome=item.get("nome"),
                        quantidade=item.get("quantidade"),
                        preco=item.get("preco"),
                        categoria=item.get("categoria"),
                        unidade_medida=item.get("unidade_medida"),
                        descricao=item.get("descricao"),
                        foto=item.get("foto"),
                        peso=item.get("peso"),
                        peso_tolerancia=item.get("pesoTolerancia"),
                        create_at=item.get("createAt"),
                        update_at=item.get("updateAt"),
                        status=item.get("status", True)
                    )
                )

            # retorna também info da pagina
            page_info = {
                "page": data.get("number"),
                "size": data.get("size"),
                "total_pages": data.get("totalPages"),
                "total_elements": data.get("totalElements")
            }

            return produtos, page_info

        except Exception as e:
            print(f"Erro ao buscar produtos: {e}")
            return [], None

    @classmethod
    def from_tuple(cls, data):

        return cls(

            id=data[0],
            codigo=data[1],
            nome=data[2],
            preco=data[3],
            quantidade=data[4],
            categoria=data[5],
            unidade_medida=data[6],
            descricao=data[7],
            foto=data[8],
            peso=data[9],
            peso_tolerancia=data[10],
            create_at=data[11],
            update_at=data[12],
            status=bool(data[13])

        )
