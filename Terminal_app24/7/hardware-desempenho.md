# Hardware e desempenho

Voltar para [[00-index]]. Display em [[display]] e [[telas]], instalação em [[distribuicao-atualizacao]], melhorias em [[melhorias]] (MEL-039, MEL-040).

## Resumo

| Item | Mínimo | Recomendado |
|---|---|---|
| Placa | Raspberry Pi 4 Model B, 1 GB | Raspberry Pi 4 Model B, 2 GB ou mais (equipamento de campo atual) |
| Armazenamento | cartão SD A1/A2 de marca, 16 GB | SSD USB (durabilidade e queda de energia, não velocidade de venda) |
| Catálogo testado | 5 mil produtos | — |

O app trabalha praticamente num único núcleo: o que limita é a velocidade desse núcleo, não a quantidade de núcleos nem o tamanho do catálogo.

## Teste de carga de 25/11/2026

**Equipamento:** Raspberry Pi 4 Model B Rev 1.5 (4× Cortex-A72 a 1,8 GHz, 2 GB, SSD USB de 128 GB), display `1024×600` em pé (`HDMI-A-2`, transform 90), labwc/Wayland, app 1.0.8 rodando do código-fonte com o Python e o PyQt5 do build.

**Método:**

- o `app247-terminal` de produção ficou parado das 19:47 às 19:59 e voltou sozinho no fim;
- cada rodada abriu o app em tela cheia no display real, com dados isolados em `/tmp` e sem backend (`APP247_API_URL` vazio, workers de pagamento simulados);
- roteiro: 20 s ocioso no Bem-vindo; sync completo do catálogo numa thread, como o `SyncService`; 5 compras de 40 leituras (30 produtos distintos e 10 repetidos), confirmação e tela de pagamento;
- limites de CPU com `taskset` (núcleos) e `systemd-run --user --scope -p CPUQuota=… -p CPUQuotaPeriodSec=10ms` (fração do núcleo);
- a memória foi medida (`VmRSS`/`VmHWM`), não limitada: o controlador de memória não está delegado ao systemd de usuário;
- atraso da tela: quanto um timer de 20 ms do event loop dispara depois do previsto;
- temperatura entre 60 e 64 °C, sem redução de clock (`get_throttled=0x0`) em nenhuma rodada.

**Resultados** (5 mil produtos, salvo a primeira linha):

| Perfil de CPU | Abertura | Leitura de código (mediana / p95) | Abrir confirmação | Maior atraso da tela na compra | Memória (pico) |
|---|---|---|---|---|---|
| 4 núcleos, 1 mil produtos | 1,9 s | 39 / 60 ms | 165 ms | 174 ms | 163 MB |
| 4 núcleos | 2,0 s | 38 / 59 ms | 164 ms | 165 ms | 176 MB |
| 2 núcleos | 2,1 s | 38 / 60 ms | 163 ms | 165 ms | 175 MB |
| 1 núcleo | 2,1 s | 39 / 60 ms | 164 ms | 175 ms | 175 MB |
| 1 núcleo a 60% | 3,4 s | 53 / 89 ms | 273 ms | 326 ms | 174 MB |
| 1 núcleo a 40% | 8,0 s | 130 / 220 ms | 431 ms | 710 ms | 176 MB |
| 1 núcleo a 25% | 15,1 s | 276 / 423 ms | 1,26 s | 1,35 s | 176 MB |

Outros números:

- sync completo de 5 mil produtos: 0,45 s com o núcleo inteiro (atraso máximo da tela de 11 ms); 2,0 s a 40%; 4,9 s a 25%;
- abrir a tela de pagamento: 28 ms com o núcleo inteiro;
- memória estável ao longo das 5 compras (sem crescimento contínuo); 5 mil produtos custam cerca de 9 MB a mais que mil;
- **ocioso:** cerca de 10% de um núcleo de forma constante em todos os perfis (MEL-039);
- a janela ficou em `600×1024` em todas as rodadas, inclusive no carrinho com 30 produtos (nenhum sinal do BUG-066).

## Equivalência estimada com outras placas

Estimativa: o limite de CPU aproxima um núcleo mais lento, mas não reproduz a GPU, o cache nem a banda de memória de outra placa.

| Placa | Perfil equivalente | Avaliação |
|---|---|---|
| Pi 5 | acima de 1 núcleo inteiro | sobra |
| Pi 4, 1 GB | 1 núcleo inteiro | mínimo recomendado, com folga até o perfil de 60% |
| Pi 4, 2 GB | 1 núcleo inteiro | confortável (campo atual) |
| Pi 3B+ (1 GB) | ~40% | no limite: abertura em 8 s, leitura de 130 ms, confirmação lenta |
| Pi Zero 2 W (512 MB) | entre 40% e 25% | não recomendado: lento e memória apertada com o ambiente gráfico |

## Armazenamento

O disco não muda a velocidade da compra: catálogo e banco ficam no cache de memória. Ele pesa em:

- primeira abertura após ligar (lê os 183 MB da release); não medido, porque no teste a release já estava em cache;
- sync do catálogo (gravação SQLite), que roda em segundo plano;
- **queda de energia e desgaste:** o Terminal grava log rotativo, SQLite e pagamento pendente o dia todo. Cartão SD comum corrompe e se desgasta mais; SSD USB é a escolha para quiosque 24/7.

Espaço: release de 183 MB, banco de poucos MB mesmo com 5 mil produtos, logs limitados a cerca de 25 MB (BUG-050).

## Limites do teste

- a abertura a frio (após reboot) não foi medida;
- numa compra do perfil de 60%, o carrinho apareceu vazio e a tela voltou ao Bem-vindo; provável efeito do roteiro trocando de tela rápido demais com CPU lenta, não investigado;
- o roteiro de carga não está no repositório; para repetir, seguir o método acima.
