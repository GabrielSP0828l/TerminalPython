# Heartbeat

Heartbeat e telemetria têm ciclos distintos. O heartbeat padrão continua em 10 segundos e é a autoridade da presença. Após persistir `lastPing`, o backend renova Redis com TTL e usa o próprio `lastPing` como fallback. A telemetria, a cada 60 segundos por padrão, descreve saúde sem inflar o heartbeat. Veja [[telemetria]].

`TerminalSocket` permanece ativo no lifecycle da aplicação e envia `{terminalId,status:ONLINE}` para `/terminal-socket` a cada 10 segundos. O backend atualiza e força persistência de `lastPing`, então responde `HEARTBEAT_ACK {terminalId,status,lastPing}`. O cliente só registra sucesso após validar o ACK.

Falha fecha/recria o socket após 5 segundos, sem popup nem interrupção da compra. Terminal inativo/não ativado não envia. Consulte [[websocket]], [[arquitetura-atual]] e [[compatibilidade-backend]].
