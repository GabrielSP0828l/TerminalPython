# Heartbeat do terminal

Voltar para [o índice](00-index.md). Visão dos sockets em [[websocket]] e API em [[api-backend]].

## Lifecycle e frequência

`MainWindow.iniciar_operacao_terminal()` cria uma única instância de `TerminalSocket` depois da ativação. A thread permanece ativa em boas-vindas, carrinho e pagamento. O intervalo padrão é 10 segundos, centralizado em `HEARTBEAT_INTERVAL_SECONDS`; retry padrão é 5 segundos.

No fechamento da aplicação, `MainWindow.closeEvent` solicita parada, fecha o socket e aguarda brevemente a thread.

## Confirmação persistida

O cliente envia o UUID canônico em `/terminal-socket`. `TerminalService.updateStatus` executa em transação, define `lastPing = LocalDateTime.now()` e usa `saveAndFlush`. O handler responde `HEARTBEAT_ACK` com o mesmo terminal e o `lastPing` persistido. Um simples `send()` não é mais registrado como sucesso.

O cliente recarrega a ativação antes de abrir uma conexão. Terminal ausente, inativo ou não ativado aguarda sem fingir sucesso.

## Falhas e recuperação

Erros são logados tecnicamente, sem popup para o cliente e sem afetar compra/pagamento. A conexão é recriada no próximo retry. Quando o backend volta, um ACK válido restaura automaticamente o ciclo normal.

## Verificação real

Em 24 de agosto de 2026, foi enviado um heartbeat pelo mesmo `WS_URL` configurado no Terminal. O backend respondeu com `HEARTBEAT_ACK` e `lastPing=2026-08-24T13:35:29.763624625`; consulta direta ao MySQL confirmou o terminal `ONLINE` e `last_ping=2026-08-24 13:35:31` (um batimento subsequente).
