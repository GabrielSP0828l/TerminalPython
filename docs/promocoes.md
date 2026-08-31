# Promoções no Terminal

Voltar para [[00-index]].

O Terminal não calcula regras promocionais. O backend envia `precoOriginal`, `preco`, `emPromocao`, `promocaoId` e `promocaoNome`. `Produtos` conserva os dois valores com `Decimal`; o card mostra “De”, “Por” e o selo de promoção, sempre formatados em duas casas apenas para exibição.

O SQLite armazena `preco_original` e `preco` como `TEXT` normalizado em seis casas, mais os metadados promocionais. A inicialização migra atomicamente a tabela antiga com `REAL`. Carrinho e payload usam o `Decimal` preciso recebido, nunca o texto visual.

Cada item enviado a `POST /carrinho` inclui `expectedUnitPrice`. Um `409 PRICE_CHANGED` atualiza todos os itens com os preços devolvidos, solicita sincronização e retorna o cliente ao carrinho. Nenhuma cobrança maior ocorre sem nova confirmação.
