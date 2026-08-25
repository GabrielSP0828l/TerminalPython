# Heartbeat

`TerminalSocket` permanece ativo no lifecycle da aplicação e envia `{terminalId,status:ONLINE}` para `/terminal-socket` a cada 10 segundos. O backend atualiza e força persistência de `lastPing`, então responde `HEARTBEAT_ACK {terminalId,status,lastPing}`. O cliente só registra sucesso após validar o ACK.

Falha fecha/recria o socket após 5 segundos, sem popup nem interrupção da compra. Terminal inativo/não ativado não envia. Consulte [[websocket]], [[arquitetura-atual]] e [[compatibilidade-backend]].
