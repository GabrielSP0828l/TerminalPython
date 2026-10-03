# Menu administrativo

Voltar para [[00-index]]. Wi-Fi em [[wifi]], orientação em [[display]] e telas em [[telas]].

O fluxo único é:

```text
toque longo no logotipo
  -> AdminAuthScreen / TERMINAL_ADMIN_PASSWORD
      -> ConfiguracaoScreen existente
          -> CONFIGURAR WI-FI
          -> ORIENTAÇÃO DA TELA
          -> RESTAURAR PADRÕES DE FÁBRICA
          -> FECHAR TERMINAL
          -> VOLTAR
```

`ConfiguracaoScreen` contém um `QStackedWidget` interno. Voltar de Wi-Fi/orientação retorna ao menu sem repetir a senha; sair do painel encerra a sessão efêmera e exige senha no próximo acesso. Nenhuma rota administrativa é exposta diretamente ao cliente.

O menu e subpáginas seguem o design system touchscreen em `1024×600`, com botões de 60–76 px, fontes grandes, contraste alto, loading com timeout e mensagens humanas. Wi-Fi em pagamento mostra aviso e preserva a cobrança; orientação é bloqueada em qualquer compra/pagamento ativo. Senha administrativa e Wi-Fi não são logadas.
