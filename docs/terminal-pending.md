# Terminal — Pendências

Data da auditoria: 27 de setembro de 2026. Cada item abaixo é verificável e deriva do código executável. Veja [[terminal-review-2026-09]] e [[terminal-audit-architecture]].

## P0

- [ ] PARCIAL — `.env` saiu do índice, `.env.example` contém placeholders e runtime usa `0600`; ainda é obrigatório rotacionar a senha exposta e higienizar o histórico Git coordenadamente.
- [ ] PARCIAL — banco, identidade, backups, runtime, logs e bytecode estão ignorados/removidos do índice atual; o H2 local do backend também saiu do índice. Dados presentes no histórico antigo ainda precisam de limpeza coordenada.
- [x] Reset administrativo e aplicação do marcador no boot bloqueiam qualquer checkpoint/estado financeiro ativo ou incerto.
- [x] `X-Terminal-Token` usa credencial individual revogável por Terminal e é validado em HTTP/WS; o segredo legado não é fallback operacional.
- [x] Handshake de `/payment-socket/{terminalId}` valida credencial e Terminal antes de registrar a sessão.
- [x] Identidade ausente/corrompida com `active_payment` abre recovery exclusivo e reconcilia antes de permitir reativação.

## P1

- [x] `APP_ENV=production` usa `showFullScreen`; development permanece normal em `1024x600` e refresh preserva o modo.
- [x] Tela de ativação abre somente Wi-Fi antes do vínculo, sem liberar o menu administrativo completo.
- [x] `integrity_check` falho entra em modo seguro, preserva o banco e bloqueia compra/reset destrutivo.
- [ ] PARCIAL — catálogo v2 e migração aditiva de `active_payment` existem; falta versionamento unificado e matriz de upgrades antigos.
- [ ] Evitar bloqueio da thread Qt quando o sync escreve no SQLite, usando estratégia comprovada de WAL/timeout curto/worker de leitura ou cache consistente.
- [x] Workers financeiros/Wi-Fi/display/app limpam referência e `deleteLater` em `finished`; single-flight impede acúmulo.
- [x] Shutdown espera os timeouts máximos dos workers HTTP antes da destruição Qt.
- [ ] Persistir resultado aprovado suficiente para recuperar a tela verde/Order após crash entre `APPROVED` e `FINALIZAR`.
- [ ] Bloquear tentativas administrativas repetidas, exigir segredo forte e documentar rotação/provisionamento sem Git.
- [x] `Pillow` está declarado em `requirements.txt` para geração do QR.
- [ ] PARCIAL — pacote `onedir`, serviço, usuário/permissões e diretórios foram preparados; dependências físicas, rotação de logs e validação ARM64 no Raspberry permanecem.
- [ ] Validar no Raspberry real `1024x600`, touch, scanner HID, NetworkManager, labwc/Wayland, rotação 90/270, reboot e recovery sem cobrança real.

## P2

- [ ] Criar parser central de scanner com tipos `PRODUCT_BARCODE`, `CUSTOMER_LINK_TOKEN` e `COUPON_TOKEN`, incluindo framing e limites de tamanho.
- [ ] Implementar o fluxo “Deseja salvar esta compra no histórico?” sem inserir CPF/tenant arbitrários no Terminal.
- [ ] Integrar `APP247:LINK:<token>` com `POST /terminal/customer-link/consume`, usando credencial de dispositivo segura e Order correlacionada.
- [ ] Definir com o backend o contrato de `CPF_HISTORY` e habilitar `ADICIONAR CPF` somente após validação autoritativa; não criar conta no Terminal.
- [ ] Integrar `APP247:COUPON:<token>` com `POST /terminal/coupons/apply`; não calcular desconto localmente.
- [ ] Exibir `COUPON_MINIMUM_NOT_REACHED` com mínimo, valor atual e diferença retornados pelo backend.
- [ ] Exibir e reconciliar cupom `RESERVED` durante cancelamento/recovery, respeitando a liberação autoritativa do backend.
- [ ] Adicionar decremento unitário de item ou documentar explicitamente a UX scanner+remoção total.
- [ ] Implementar ou remover a UI de peso; hoje `peso_total_venda` permanece zero e não existe leitura de balança.
- [ ] Definir debounce/framing do scanner sem impedir leituras legítimas repetidas e testar dois EANs rápidos.
- [ ] Substituir `QMessageBox` do fluxo de scanner por feedback touch não modal e temporizado.
- [ ] Tratar criação de carrinho com resposta perdida para evitar carrinhos órfãos, idealmente com idempotency key local.
- [ ] Validar configuração numérica no startup e apresentar erro operacional legível em vez de abortar o import.
- [ ] Iniciar telemetria/diagnóstico mínimo também no estado não ativado, sem inventar vínculo de Empresa/Condomínio.
- [ ] Implementar logging persistente/rotativo ou envio central com retenção, mantendo mascaramento de dados pessoais e segredos.
- [ ] Remover ou isolar `LoginScreen`, `TecladoScreen`, `AppPaymentScreen` e `Produtos.get_produtos_api` para que artefatos legados não sejam confundidos com fluxo suportado.
- [x] Documentação do hardening sincronizada; documentos históricos mantêm contexto e apontam a atualização vigente.

## P3

- [ ] Eliminar `print` de geometria do bootstrap e helpers legados em favor do logger comum.
- [ ] Alinhar o `.venv` ao `requirements.txt` ou recriá-lo de forma reproduzível; `python-dotenv` instalado está abaixo do pin declarado.
- [ ] Adicionar metadados de projeto/teste (`pyproject.toml` ou equivalente) e um comando único de CI.
- [ ] Documentar quais warnings de ambiente Qt/Wayland são esperados em execução offscreen e quais bloqueiam produção.
- [ ] Adicionar checksum/contagem autoritativa ao FULL sync se o backend precisar detectar snapshot válido porém incompleto.

## Testes pendentes específicos

- [ ] PARCIAL — ausência, corrupção e `active_payment` têm cobertura; banco bloqueado/schema futuro ainda faltam.
- [ ] PARCIAL — fluxo de recovery sem identidade foi implementado; falta teste Qt integrado com respostas backend sucessivas.
- [x] Política cobre `STARTING_PAYMENT`, `PENDING`, `WAITING_PAYMENT`, `PROCESSING`, `UNKNOWN`, `CANCELLING` e recovery.
- [ ] Testar estoque negativo explicitamente para garantir que produto ativo continua escaneável.
- [ ] Testar ativação offline, 404, JSON inválido, persistência falha e retorno do backend.
- [ ] Testar EAN inexistente, leituras distintas rápidas, QR de cliente e QR de cupom.
- [ ] Testar Point física offline, cancelamento apenas do método, nova escolha de método e aprovação atrasada.
- [ ] Testar webhook perdido com reconciliação real em ambiente controlado.
- [ ] Testar restart de processo/Raspberry em cada janela entre cart, Order, attempt, aceite remoto e aprovação.
- [ ] Testar overflow/renderização de todas as telas em hardware `1024x600`, não apenas geometria Qt offscreen.
- [ ] Testar autostart, crash loop, falta de disco, log cheio, subtensão e throttling no Raspberry.
- [ ] PARCIAL — headers, credencial individual e handshake autenticado têm testes; falta teste E2E de sessão duplicada/forjada.
