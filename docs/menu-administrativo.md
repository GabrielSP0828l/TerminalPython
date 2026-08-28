# Menu administrativo

Voltar para [[00-index]]. Telas em [[telas]], Wi-Fi em [[wifi]] e display em [[display]].

## Acesso único

O painel existente foi preservado:

```text
toque longo no logotipo
  -> AdminAuthScreen
      -> TERMINAL_ADMIN_PASSWORD válida
          -> ConfiguracaoScreen
              -> CONFIGURAR WI-FI
              -> ORIENTAÇÃO DA TELA
              -> RESTAURAR PADRÕES DE FÁBRICA
              -> FECHAR TERMINAL
              -> VOLTAR
```

`ConfiguracaoScreen` contém um `QStackedWidget` interno para menu, Wi-Fi e orientação. Voltar de uma subpágina mantém a mesma sessão autenticada; voltar do menu encerra a sessão, limpa a senha e exige autenticação na próxima entrada. Nenhuma opção fica acessível ao cliente comum.

Em `1024×600`, o card administrativo usa botões de 60–72 px, fonte do design system e alto contraste. Confirmações sensíveis mostram `CANCELAR` e a ação explícita.

## Guardas operacionais

- Wi-Fi durante pagamento: mostra aviso, não cancela cobrança e deixa a reconciliação existente intacta.
- Orientação durante compra ou pagamento: é bloqueada.
- Reset/encerramento: preservam as guardas e confirmações anteriores.
- Operações externas: rodam em workers Qt com timeout; sair do painel invalida callbacks antigos.
- Segredos: senha administrativa e senha Wi-Fi não são logadas.

O menu configura apenas recursos locais. Ele não duplica heartbeat, WebSocket, sincronização, regras de backend ou estado financeiro.
