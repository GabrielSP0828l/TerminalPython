# Product sync e promoções

Voltar para [[00-index]]. Documento-base: [[sincronizacao]].

O payload UPSERT inclui o preço normal e o preço aplicado pelo backend. Criação, edição, mudança de status ou produtos e transições de início/fim geram `PRODUCT_SYNC_REQUIRED` para os Terminais afetados.

O evento apenas antecipa o refresh. Na recuperação, `GET /produtos/sync?uuidTerminal=...&lastSync=...` considera transições temporais no intervalo do cursor. Assim, ao reconectar, o Terminal recebe tanto promoções iniciadas quanto encerradas enquanto esteve offline.

Valores JSON são decodificados com `parse_float=Decimal` quando suportado e normalizados antes da gravação. O cursor só avança depois do commit SQLite completo.
