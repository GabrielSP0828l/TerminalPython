
# FRONT-END TERMINAL INTELIGENTE

Projeto Front-End PyQt5 pronto para:
- Spring Boot
- APIs REST
- Banco de Dados
- Leitor Código Barras
- Balança automática

## Executar

pip install -r requirements.txt

python main.py

## Configurações locais

Na tela de boas-vindas, mantenha o logotipo pressionado por 2 segundos para abrir o menu de configurações.

A opção **Restaurar padrões de fábrica** remove, na próxima inicialização, somente a ativação e o cache operacional local. Antes da remoção, os arquivos são movidos para `db/reset-backups/`. O `.env`, o cadastro no backend e as credenciais Mercado Pago não são alterados.
