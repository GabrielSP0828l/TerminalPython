# AGENTS.md — Terminal Python App 24/7

## Projeto

Este repositório contém o software do terminal físico de autoatendimento do sistema App 24/7.

O terminal já possui uma implementação funcional significativa.

**Não reescreva o projeto do zero.**

Antes de realizar alterações:

1. analise a implementação existente;
2. identifique o fluxo atual;
3. preserve funcionalidades que já funcionam;
4. faça alterações incrementais;
5. valide compatibilidade com o backend.

---

# Arquitetura

O terminal Python é um cliente do backend Spring Boot do App 24/7.

A arquitetura de negócio é:
# Documentação obrigatória

A documentação faz parte do projeto e deve permanecer sincronizada com o código.

## Documentação específica do Terminal

O Vault Obsidian do Terminal está em:

Terminal_app24/7/

A pasta:

Terminal_app24/.obsidian/

contém apenas configurações do Obsidian e NÃO deve receber documentação.

Os documentos técnicos do Terminal devem ser mantidos em:

Terminal_app24/7/
├── 00-index.md
├── contexto.md
├── arquitetura.md
├── fluxo-compra.md
├── telas.md
├── api-backend.md
├── websocket.md
├── sqlite.md
├── mercado-pago.md
├── compatibilidade-backend.md
├── auditoria-bugs.md
└── melhorias.md

## Documentação compartilhada com o backend

A documentação do sistema App 24/7 e do backend está em:

../app247/24por7_contexto/

Essa documentação deve ser CONSULTADA sempre que uma alteração envolver:

- API;
- DTOs;
- Carrinho;
- Items;
- Order;
- Pagamento;
- Mercado Pago;
- Terminal;
- Empresa;
- Condomínio;
- Estoque;
- WebSocket.

O código real é a fonte de verdade.

Se código e documentação divergirem, registre a divergência e não invente comportamento.

# Regra obrigatória de atualização

Toda alteração funcional ou estrutural relevante deve atualizar a documentação correspondente.

Exemplos:

mudança em telas
→ Terminal_app24/telas.md

mudança no fluxo da compra
→ Terminal_app24/fluxo-compra.md

mudança em endpoint utilizado
→ Terminal_app24/api-backend.md

mudança em WebSocket
→ Terminal_app24/websocket.md

mudança no SQLite/cache
→ Terminal_app24/sqlite.md

mudança no fluxo de pagamento
→ Terminal_app24/mercado-pago.md
→ Terminal_app24/fluxo-compra.md

bug encontrado
→ Terminal_app24/auditoria-bugs.md

bug corrigido
→ atualizar status em auditoria-bugs.md

melhoria identificada ou implementada
→ Terminal_app24/melhorias.md

incompatibilidade com backend
→ Terminal_app24/compatibilidade-backend.md

Se a alteração também modificar o contrato ou arquitetura compartilhada com o backend, atualize o documento correspondente em:

../app247/24por7_contexto/

# Regra de conclusão

Uma tarefa que altera comportamento relevante e deixa a documentação incompatível NÃO está concluída.

Ao terminar uma tarefa relevante:

1. execute os testes aplicáveis;
2. atualize a documentação afetada;
3. informe quais arquivos de código foram alterados;
4. informe quais arquivos de documentação foram alterados.

# Obsidian

Utilize wikilinks entre documentos quando apropriado:

[[contexto]]
[[arquitetura]]
[[fluxo-compra]]
[[telas]]
[[api-backend]]
[[websocket]]
[[sqlite]]
[[compatibilidade-backend]]
[[auditoria-bugs]]
[[melhorias]]
[[padrão das tela e cores]]

Não altere `.obsidian/` sem necessidade explícita.
```text
Empresa
   |
   v
Condomínio
   |
   v
Terminal
```

Cada terminal físico pertence a um condomínio.

Cada condomínio pertence a uma empresa.

O terminal não deve escolher arbitrariamente empresa ou condomínio.

O backend deve identificar isso através do cadastro do terminal.

---

# Documentação

Antes de modificar integrações com o backend, consulte a documentação compartilhada do App 24/7.

Todas as telas tem que seguir o mesmo padrão de stilo e cores

A documentação pode estar no projeto backend, em:

```text
../app247/24por7_contexto/
```

Ajuste esse caminho somente se a estrutura real de diretórios for diferente.

Documentos principais:

```text
../app247/24por7_contexto/00-index.md
../app247/24por7_contexto/contexto.md
../app247/24por7_contexto/api.md
../app247/24por7_contexto/arquitetura-geral.md
../app247/24por7_contexto/terminal-python.md
../app247/24por7_contexto/mercado-pago.md
../app247/24por7_contexto/estoque.md
```

Para alterações que envolvam contratos HTTP ou WebSocket, `api.md` e o código atual do backend devem ser consultados.

Se documentação e implementação divergirem, identifique a divergência antes de alterar comportamento.

---

# Stack do terminal

Analise o projeto para confirmar as versões e bibliotecas utilizadas.

A aplicação utiliza principalmente:

* Python;
* PyQt/PyQt5;
* SQLite;
* HTTP;
* WebSocket;
* Raspberry Pi.

Não substitua bibliotecas ou frameworks existentes sem necessidade.

---

# Responsabilidade do terminal

O terminal é responsável principalmente por:

* interface de autoatendimento;
* leitura de produtos;
* montagem visual do carrinho;
* cache local;
* sincronização com backend;
* identificação da instalação;
* solicitação de checkout;
* exibição do estado do pagamento;
* comunicação HTTP;
* comunicação WebSocket;
* recuperação de conexão;
* reset após conclusão da compra.

---

# Fonte de verdade

O terminal NÃO é a fonte de verdade para:

* Empresa;
* Condomínio;
* estoque;
* Carrinho persistido;
* Items persistidos;
* Order;
* Pagamento;
* status financeiro;
* credenciais Mercado Pago.

Essas responsabilidades pertencem ao backend.

O armazenamento local do terminal deve ser tratado como cache/estado operacional quando aplicável.

---

# Identificação do terminal

O terminal deve possuir uma identificação persistente, como:

```text
uuidTerminal
```

ou o mecanismo equivalente já existente.

O fluxo conceitual é:

```text
Terminal físico
      ↓
uuidTerminal
      ↓
Backend
      ↓
Terminal
      ↓
Condomínio
      ↓
Empresa
```

Não introduza `empresaId` ou `condominioId` arbitrários no terminal quando o backend puder derivá-los da identidade do terminal.

---

# Produtos

Os produtos pertencem ao catálogo da empresa:

```text
Empresa -> Produto
```

Mas a disponibilidade pertence ao condomínio:

```text
Empresa
   ↓
Condomínio
   ↓
EstoqueCondominio
   ↓
Produto
```

Portanto o terminal deve sincronizar os produtos disponíveis para o seu próprio condomínio.

Não presuma que todos os produtos da empresa estão disponíveis em todos os terminais.

---

# Carrinho

O cliente escaneia os produtos no terminal.

Fluxo conceitual:

```text
Scanner
   ↓
Terminal Python
   ↓
Carrinho local/visual
   ↓
Backend
   ↓
Carrinho + Items persistidos
```

Antes de modificar esse fluxo, analise completamente como o código existente:

* cria carrinho;
* adiciona item;
* remove item;
* atualiza quantidade;
* calcula subtotal;
* envia itens;
* recebe resposta do backend.

Não duplique operações de persistência sem verificar o comportamento atual.

---

# Pagamento Mercado Pago Point

Existe integração real com uma maquininha física Mercado Pago Point.

O fluxo atual deve ser preservado e aprimorado, não substituído sem necessidade.

O fluxo conceitual é:

```text
Terminal Python
      ↓
envia compra para Backend
      ↓
Backend cria Order/Pagamento
      ↓
Backend identifica Terminal
      ↓
Backend identifica Empresa
      ↓
Backend obtém credenciais Mercado Pago
      ↓
Backend envia cobrança para Mercado Pago
      ↓
Mercado Pago envia cobrança para maquininha
      ↓
Cliente paga fisicamente
      ↓
Mercado Pago
      ↓
Webhook/backend
      ↓
Backend confirma resultado
      ↓
WebSocket
      ↓
Terminal Python
```

---

# Mercado Pago

O terminal Python NÃO deve possuir:

* access token;
* refresh token;
* client secret;
* credenciais OAuth da empresa.

As credenciais pertencem a:

```text
Empresa
   ↓
MercadoPagoConta
```

A identificação da maquininha pertence ao Terminal cadastrado no backend:

```text
Terminal
   ↓
mercadoPagoTerminalId
```

O backend combina:

```text
Empresa -> MercadoPagoConta -> accessToken
```

com:

```text
Terminal -> mercadoPagoTerminalId
```

para criar a cobrança.

---

# Regra crítica de pagamento

O terminal NÃO deve considerar uma compra aprovada simplesmente porque a criação da cobrança retornou sucesso.

A criação da cobrança significa apenas que o pagamento foi iniciado/aceito para processamento.

O resultado definitivo deve vir do backend após confirmação do Mercado Pago.

Fluxo:

```text
Criar cobrança
      ↓
Aguardar pagamento
      ↓
Mercado Pago processa
      ↓
Backend confirma
      ↓
Terminal recebe estado
```

---

# WebSocket

O terminal recebe atualizações do backend em tempo real.

Antes de alterar WebSocket:

1. identifique os endpoints atuais;
2. identifique como o terminal é associado à conexão;
3. identifique como Order/Pagamento são correlacionados;
4. consulte a implementação correspondente no backend;
5. preserve compatibilidade entre ambos.

Uma atualização destinada ao Terminal A nunca deve liberar o Terminal B.

---

# Estados de pagamento

O terminal deve trabalhar preferencialmente com estados internos fornecidos pelo backend.

Exemplos conceituais:

```text
PROCESSING
APPROVED
REJECTED
CANCELLED
```

Não replique no Python toda a lógica de interpretação dos status do Mercado Pago.

O mapeamento:

```text
Mercado Pago -> estado interno
```

deve ficar centralizado no backend.

---

# APPROVED

Quando receber confirmação definitiva de aprovação:

```text
Backend
   ↓
APPROVED
   ↓
Terminal
   ↓
Tela de sucesso
   ↓
Finalizar compra
   ↓
Limpar estado local
   ↓
Reset
```

Não resetar antes da confirmação.

---

# REJECTED

Quando receber recusa:

```text
Backend
   ↓
REJECTED
   ↓
Terminal
```

o terminal deve apresentar o estado ao cliente e seguir o fluxo existente de nova tentativa/cancelamento.

Não invente comportamento diferente sem analisar a implementação atual.

---

# CANCELLED

Quando receber cancelamento:

```text
Backend
   ↓
CANCELLED
   ↓
Terminal
```

o terminal deve retornar ao estado apropriado definido pelo fluxo existente.

A devolução/liberação de estoque é responsabilidade do backend.

---

# PROCESSING

Enquanto o pagamento estiver em processamento:

```text
PROCESSING
```

o terminal não deve liberar a compra.

Deve permanecer aguardando estado definitivo ou seguir mecanismo de timeout/reconsulta já implementado.

---

# Estoque

O terminal não deve executar diretamente baixa ou devolução do estoque oficial.

O backend é responsável por:

* reserva;
* venda;
* cancelamento;
* devolução;
* movimentação;
* idempotência.

O terminal pode exibir informações recebidas do backend, mas não deve ser a autoridade sobre estoque.

---

# Offline e reconexão

Preserve mecanismos existentes de funcionamento offline e monitoramento de conexão.

Quando houver perda de conexão durante pagamento:

**nunca assuma aprovação ou recusa localmente.**

Após reconectar:

```text
Terminal
   ↓
Backend
   ↓
consultar estado atual
   ↓
sincronizar interface
```

quando esse fluxo estiver disponível.

---

# SQLite

Antes de alterar banco local:

1. analise tabelas existentes;
2. identifique finalidade de cada tabela;
3. identifique sincronização;
4. preserve dados necessários;
5. evite transformar SQLite em fonte de verdade de dados que pertencem ao backend.

Mudanças de schema local devem considerar instalações existentes.

---

# Requisições HTTP

Não espalhe URLs do backend por várias classes.

Se já existir um client/service HTTP centralizado, utilize-o.

Se não existir e houver duplicação significativa, proponha centralização antes de realizar refatoração ampla.

Sempre trate:

* timeout;
* conexão indisponível;
* resposta HTTP inválida;
* JSON inválido;
* erros 4xx;
* erros 5xx.

Não deixe erro de rede derrubar a interface gráfica.

---

# Interface PyQt

Não execute operações HTTP lentas diretamente na thread principal da interface.

Antes de modificar código de rede, verifique se a implementação utiliza:

* threads;
* workers;
* signals/slots;
* mecanismos assíncronos.

Evite congelar a interface durante:

* sincronização;
* criação de Order;
* espera por pagamento;
* reconexão;
* chamadas HTTP.

---

# Tratamento de erros

Evite:

```python
try:
    ...
except Exception:
    pass
```

Erros relevantes devem ser registrados.

Entretanto não exiba stack traces técnicos diretamente ao cliente final.

Separe:

* mensagem para usuário;
* log técnico.

---

# Logs

Nunca registre:

* tokens;
* credenciais;
* senhas;
* dados sensíveis completos.

Logs importantes devem permitir rastrear:

```text
terminal
carrinho
order
pagamento
estado
```

quando os identificadores estiverem disponíveis.

---

# Refatorações

Não faça grandes refatorações automaticamente.

Antes:

1. identifique problema;
2. explique impacto;
3. determine arquivos envolvidos;
4. preserve contratos existentes;
5. implemente incrementalmente;
6. teste.

Não renomeie endpoints do backend apenas para melhorar o código Python.

---

# Compatibilidade com backend

Sempre que uma alteração envolver API:

1. consulte `api.md`;
2. analise o DTO utilizado pelo terminal;
3. compare com a resposta real do backend;
4. identifique campos obrigatórios/opcionais;
5. trate mudanças de contrato explicitamente.

Não adivinhe contratos.

---

# Auditoria inicial

Antes da primeira grande alteração neste projeto, faça uma auditoria do código existente.

Documente:

## Estrutura

* arquivos;
* packages/modules;
* telas;
* services;
* models;
* banco SQLite;
* HTTP;
* WebSocket.

## Fluxo de inicialização

Identifique:

```text
start
 ↓
configuração
 ↓
identificação
 ↓
sincronização
 ↓
tela inicial
```

## Fluxo de compra

Identifique o fluxo REAL:

```text
scanner
 ↓
produto
 ↓
carrinho
 ↓
backend
 ↓
Order
 ↓
pagamento
 ↓
WebSocket
 ↓
resultado
```

## Integrações

Liste todos os endpoints HTTP utilizados.

Liste todos os endpoints WebSocket utilizados.

Compare com a documentação atual do backend.

## Bugs

Procure especialmente:

* bloqueio da UI;
* race conditions;
* requisições sem timeout;
* conexões WebSocket duplicadas;
* carrinho duplicado;
* Items duplicados;
* estado local inconsistente;
* reset prematuro;
* pagamento aprovado não reconhecido;
* pagamento de outra Order liberando terminal;
* reconexão;
* SQLite desatualizado;
* endpoints antigos;
* DTOs incompatíveis.

---

# Testes

Antes de concluir alterações relevantes:

1. execute testes existentes;
2. valide inicialização;
3. valide sincronização;
4. valide leitura de produto;
5. valide carrinho;
6. valide envio ao backend;
7. valide pagamento aprovado;
8. valide pagamento recusado;
9. valide cancelamento;
10. valide timeout/reconexão quando possível.

Não faça chamadas financeiras reais automaticamente durante testes.

Não inicie cobranças reais no Mercado Pago sem que a tarefa explicitamente exija isso.

---

# Documentação

Depois de alterações relevantes, atualize:

```text
../app247/24por7_contexto/terminal-python.md
```

Se alterar contrato com backend, atualize também:

```text
../app247/24por7_contexto/api.md
```

Se alterar fluxo de pagamento:

```text
../app247/24por7_contexto/mercado-pago.md
```

Se encontrar divergência entre documentação e código, registre-a.

---

# Regra principal

Antes de modificar qualquer funcionalidade importante:

```text
LER CÓDIGO EXISTENTE
        ↓
ENTENDER FLUXO
        ↓
CONSULTAR DOCUMENTAÇÃO
        ↓
IDENTIFICAR IMPACTO NO BACKEND
        ↓
ALTERAR
        ↓
TESTAR
        ↓
ATUALIZAR DOCUMENTAÇÃO
```

O objetivo é evoluir o terminal existente, não reconstruí-lo.
