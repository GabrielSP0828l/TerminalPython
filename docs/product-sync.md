# Product sync e promoções

Voltar para [[00-index]]. Documento-base: [[sincronizacao]].

O payload UPSERT inclui SKU (`codigoInterno`), todos os `codigosBarras`, preço normal e aplicado, quantidade/pesos decimais e promoção calculada. Criação/edição de produto ou barcode, disponibilidade, promoção e transições de início/fim geram `PRODUCT_SYNC_REQUIRED` para os Terminais afetados.

O evento apenas antecipa o refresh. Na recuperação, `GET /produtos/sync?uuidTerminal=...&lastSync=...` considera transições temporais no intervalo do cursor. Assim, ao reconectar, o Terminal recebe tanto promoções iniciadas quanto encerradas enquanto esteve offline.

Valores JSON são decodificados com `parse_float=Decimal` quando suportado. O SQLite normaliza dinheiro como `TEXT` com seis casas e quantidade/peso como `TEXT` com três. Produto, substituição integral de barcodes e cursor só avançam juntos no commit SQLite.

Alterar `111` para `222` produz UPSERT do produto: todos os códigos locais anteriores são removidos e a lista atual é inserida na mesma transação. Assim `111` deixa de localizar o produto imediatamente após o commit.
