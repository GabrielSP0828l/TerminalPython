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
| `ConfiguracaoScreen` | menu administrativo, reset e encerramento | sim, após senha | tema central |
| `TerminalScreen` | scanner, lista, total e Finalizar | sim | tema central, lista rolável |
| `ConfirmacaoCompraScreen` | resumo antes do Point | sim | nova; lê o carrinho atual |
| `PagamentoScreen` | preparação, instrução Point, processamento e falha | sim | páginas fullscreen semânticas |
| `ConfirmacaoScreen` | resultado aprovado e ações pós-compra | sim | verde fullscreen; reset somente em Finalizar |
| `OfflineOverlay` | indisponibilidade e reconexão | monitor hoje desativado | tema central |
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
          -> Restaurar padrões de fábrica
          -> Fechar Terminal
          -> Voltar: encerra a sessão administrativa
```

A senha vem de `TERMINAL_ADMIN_PASSWORD` no ambiente. Não existe fallback ou senha hardcoded; configuração vazia bloqueia a entrada. O campo usa `QLineEdit.Password`, o teclado alfanumérico touchscreen existente com alternância `ABC/abc` e comparação sem logs. Ao sair do menu, a autorização é descartada. Cada novo toque longo exige nova senha.

“Restaurar padrões de fábrica” preserva o marcador/backup recuperável existente e a confirmação final. “Fechar Terminal” pede apenas confirmação, com aviso específico para compra ou pagamento ativo; nenhuma cobrança é cancelada localmente. O encerramento para timers, workers, listener de pagamento, sync, heartbeat e sockets antes de `QApplication.quit()`.

`Esc` e solicitações comuns de fechamento da janela não encerram o quiosque. A saída normal pela interface é o menu autenticado.

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

A lista ocupa a área flexível e usa cards com nome quebrável, quantidade, preço, código e subtotal. O botão remover mede 56 × 56. Scanner/peso permanecem operacionais. Total, “Cancelar compra” e “Finalizar” ficam visíveis fora do scroll. `Finalizar` não cria Carrinho remoto, Order ou cobrança.

## Confirmação pré-pagamento

`ConfirmacaoCompraScreen` não possui `Carrinho`. A propriedade `carrinho` sempre retorna `MainWindow.terminal.carrinho`. `mostrar_resumo()` reconstrói apenas widgets de apresentação com quantidade total, linhas e total atual. Voltar preserva itens. Confirmar desabilita imediatamente a ação e chama o método Point já existente.

## Pagamento e resultado

Preparação mostra loading antes do worker HTTP. Depois de uma resposta Point válida com `orderId`, `WAITING_PAYMENT`/`ACTION_REQUIRED` exibem laranja fullscreen, `alert.svg` branco e a instrução para pressionar o botão verde. `PROCESSING` volta a um loading neutro. Perda de conexão continua em reconciliação e não vira recusa.

`REJECTED`, `FAILED`, `CANCELED/CANCELLED`, `EXPIRED` e `REFUNDED` exibem vermelho fullscreen, `error.svg` branco, motivo humano e “TENTAR NOVAMENTE” no rodapé. A ação invalida os IDs da tentativa anterior e retorna ao carrinho preservado; nunca cria cobrança automaticamente.

`APPROVED`/equivalentes correlacionados abrem verde fullscreen com `checked.svg` branco, total e quatro ações: `FINALIZAR`, `ADICIONAR CPF`, `ENVIAR COMPROVANTE POR E-MAIL` e `ENVIAR COMPROVANTE POR WHATSAPP`. Não existe mais reset após cinco segundos. Eventos aprovados duplicados são idempotentes e não interrompem a ação em curso. Como o backend atual não possui os três contratos pós-compra, esses botões informam indisponibilidade sem persistir dados ou simular envio; o pagamento permanece aprovado.

## Testes visuais

Os testes Qt offscreen cobrem todas as páginas acima em `768x1360`, targets visíveis de pelo menos 56 px, nome longo, preço grande, lista/resumo, erro e overlay. Cadastro também continua coberto em `600x1024`, `1024x600` e `800x480`.
