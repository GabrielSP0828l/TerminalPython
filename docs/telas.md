# Telas e navegação

Voltar para [[00-index]]. Padrão em [[design-system]] e portrait em [[layout-vertical]].

## Container e fullscreen

`MainWindow` contém um único `QStackedWidget` expansível. Somente a janela raiz usa `showFullScreen()`; páginas não abrem janelas independentes. O display/compositor determina a orientação real.

## Inventário revisado

| Tela | Função | Navegação ativa | Situação visual |
|---|---|---:|---|
| `TelaBemVindos` | entrada e acesso local à manutenção | sim | tema central, portrait |
| `AdminAuthScreen` | senha obrigatória antes da administração | sim | tema central, teclado alfanumérico reutilizado |
| `CadastroTerminalScreen` | QR e polling de ativação | sim | tema central, reflow portrait/landscape |
| `ConfiguracaoScreen` | menu administrativo com subpáginas, reset e encerramento | sim, após senha | tema central, 1024×600 |
| `WifiScreen` | estado, scan, conexão e desconexão NetworkManager | somente dentro da administração | tema central, teclado completo e cards touch |
| `DisplayScreen` | orientação horizontal/vertical do compositor | somente dentro da administração | tema central, ações touch |
| `TerminalScreen` | scanner, grid, total e Finalizar | sim | catálogo rolável; 3 colunas em 1024×600 |
| `ConfirmacaoCompraScreen` | resumo antes do Point | sim | nova; lê o carrinho atual |
| `PagamentoScreen` | preparação, instrução Point, processamento e falha | sim | páginas fullscreen semânticas |
| `ConfirmacaoScreen` | resultado aprovado e ações pós-compra | sim | verde fullscreen; reset somente em Finalizar |
| `OfflineOverlay` | indisponibilidade, reconexão e acesso autenticado ao Wi-Fi | sim | tema central |
| `AppPaymentScreen` | checkout legado por QR | sem entrada no carrinho | preservada e migrada visualmente |
| `LoginScreen` | identificação legada | não | preservada e migrada visualmente |
| `TecladoScreen` | teclado da identificação legada | não | preservada, touch targets corrigidos |

Não existe `PixScreen` fonte no worktree atual; apenas bytecode histórico indicava uma implementação removida.

## Acesso administrativo

O acesso existente foi preservado: toque longo de dois segundos no logotipo da `TelaBemVindos`. O sinal de `HoldToExitLabel` continua chamando `MainWindow.abrir_configuracoes()`, mas esse método agora abre primeiro `AdminAuthScreen`:

```text
toque longo no logotipo
  -> ACESSO RESTRITO
      -> senha incorreta: mensagem e permanência na autenticação
      -> cancelar: volta exatamente à página anterior
      -> senha correta: ConfiguracaoScreen existente
          -> Configurar Wi-Fi
          -> Orientação da tela
          -> Restaurar padrões de fábrica
          -> Fechar Terminal
          -> Voltar: encerra a sessão administrativa
```

A senha vem de `TERMINAL_ADMIN_PASSWORD` no ambiente. Não existe fallback ou senha hardcoded; configuração vazia bloqueia a entrada. O campo usa `QLineEdit.Password`, o teclado alfanumérico touchscreen existente com alternância `ABC/abc` e comparação sem logs. Ao sair do menu, a autorização é descartada. Cada novo toque longo exige nova senha.

“Restaurar padrões de fábrica” preserva o marcador/backup recuperável existente e a confirmação final. “Fechar Terminal” pede apenas confirmação, com aviso específico para compra ou pagamento ativo; nenhuma cobrança é cancelada localmente. O encerramento para timers, workers, listener de pagamento, sync, heartbeat e sockets antes de `QApplication.quit()`.

`Esc` e solicitações comuns de fechamento da janela não encerram o quiosque. A saída normal pela interface é o menu autenticado.

## Wi-Fi e orientação

As duas funções novas vivem dentro da `ConfiguracaoScreen` existente. Um `QStackedWidget` interno alterna menu, [[wifi]] e [[display]]; voltar de uma subpágina preserva a autenticação, enquanto sair do painel a invalida.

`WifiScreen` apresenta estado/SSID/sinal/IP, redes deduplicadas, senha mascarada com teclado alfanumérico/símbolos, loading e mensagens humanas. Os cards possuem ao menos 76 px e as operações usam worker com timeout. Em estado offline, o overlay permite abrir o mesmo fluxo de senha administrativa para recuperar a rede.

`DisplayScreen` mostra orientação atual e apenas `HORIZONTAL`/`VERTICAL`. A alteração é bloqueada enquanto houver compra ou pagamento e não gira widgets. Após sucesso, a janela reaplica fullscreen para responder à geometria entregue pelo compositor.

## Fluxo ativo

```text
TelaBemVindos
  -> TerminalScreen
      -> FINALIZAR
          -> ConfirmacaoCompraScreen
              -> VOLTAR: TerminalScreen, mesmo carrinho
              -> CONFIRMAR E PAGAR: PagamentoScreen
                  -> preparando Point
                  -> aguardando maquininha/backend
                  -> aprovado: ConfirmacaoScreen
                  -> falha: TENTAR NOVAMENTE -> TerminalScreen
```

`PAGAR NO APP` e `PAGAR AGORA` não existem mais na tela da compra. `AppPaymentScreen` não foi apagada porque ainda representa um fluxo legado separado; não há rota ativa até ela.

## Carrinho

O catálogo ocupa a área flexível e usa `QGridLayout` real dentro de `QScrollArea`. Em `1024×600`, são 3 colunas com cards de `292×224`; a largura responsiva fica entre 250 e 292 px, limitada a quatro colunas. O espaçamento é 12 px, a barra horizontal fica desativada e a altura do container acompanha a quantidade de linhas para o scroll vertical não sobrepor cards.

Cada card mostra nome em até duas linhas (26 px), preço/subtotal (34 px), quantidade (22 px) e `REMOVER`; dados técnicos não aparecem. Scanner/peso permanecem operacionais. O footer horizontal mantém `TOTAL` (28 px), valor (46 px), “Cancelar compra” e “Finalizar” (26 px/72 px) fora do scroll. `Finalizar` não cria Carrinho remoto, Order ou cobrança.

## Confirmação pré-pagamento

`ConfirmacaoCompraScreen` não possui `Carrinho`. A propriedade `carrinho` sempre retorna `MainWindow.terminal.carrinho`. `mostrar_resumo()` reconstrói apenas widgets de apresentação com quantidade total, linhas e total atual. Voltar preserva itens. Confirmar desabilita imediatamente a ação e chama o método Point já existente.

No display físico, o título usa 40 px; nome usa 26 px; quantidade/preço usam 24 px; o total usa fundo branco sólido, texto escuro e valor de 48 px. Os dois botões usam 26 px e altura mínima de 72 px.

## Pagamento e resultado

Preparação mostra loading antes do worker HTTP. Depois de uma resposta Point válida com `orderId`, `WAITING_PAYMENT`/`ACTION_REQUIRED` exibem laranja fullscreen, `alert.svg` branco e a instrução para pressionar o botão verde. `PROCESSING` volta a um loading neutro. Perda de conexão continua em reconciliação e não vira recusa.

`REJECTED`, `FAILED`, `CANCELED/CANCELLED`, `EXPIRED` e `REFUNDED` exibem vermelho fullscreen, `error.svg` branco, motivo humano e “TENTAR NOVAMENTE” no rodapé. A ação invalida os IDs da tentativa anterior e retorna ao carrinho preservado; nunca cria cobrança automaticamente.

`APPROVED`/equivalentes correlacionados abrem verde fullscreen com `checked.svg` branco, total e quatro ações: `FINALIZAR`, `ADICIONAR CPF`, `ENVIAR COMPROVANTE POR E-MAIL` e `ENVIAR COMPROVANTE POR WHATSAPP`. Não existe mais reset após cinco segundos. Eventos aprovados duplicados são idempotentes e não interrompem a ação em curso. Como o backend atual não possui os três contratos pós-compra, esses botões informam indisponibilidade sem persistir dados ou simular envio; o pagamento permanece aprovado.

## Testes visuais

Os testes Qt offscreen cobrem todas as páginas acima em `768x1360`, targets visíveis de pelo menos 56 px, nome longo, preço grande, grid/resumo, erro e overlay. O carrinho possui validação específica em `1024×600` para três colunas, dimensões, fontes e ausência de scroll horizontal. Cadastro também continua coberto em `600x1024`, `1024x600` e `800x480`. O menu, Wi-Fi, teclado de símbolos e orientação possuem cobertura adicional em `1024×600`.
