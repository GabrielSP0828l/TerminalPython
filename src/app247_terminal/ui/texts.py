"""Textos de interface do Terminal, reunidos para ajuste sem caçar no código.

Regra das telas do cliente: um título e uma ação. Detalhe técnico fica em
telas de administrador ou no log. Não há tradução; são apenas constantes.
"""

# --- Espera ---------------------------------------------------------------
WELCOME_CLOCK_FORMAT = "%H:%M:%S"

# --- Carrinho -------------------------------------------------------------
CART_CUSTOMER_PROMPT = "App247: leia o QR do aplicativo"
CART_EMPTY = "Nenhum produto escaneado"
CART_REMOVE_ACCESSIBLE = "Remover {name}"
CART_DISCOUNT_BADGE = "-{percent}%"
# Preço unitário, abaixo do total da linha quando Qtd > 1.
CART_UNIT_PRICE = "{quantity} × {price}"
# Selo quando o percentual não pode ser calculado e a promoção não tem nome.
CART_PROMOTION_BADGE = "PROMOÇÃO"

# --- Sessão de compra -----------------------------------------------------
SESSION_ENDING = "Sessão prestes a encerrar"
INACTIVITY_TITLE = "Ainda está aí?"
INACTIVITY_COUNTDOWN = "A compra será cancelada em {seconds} s"
INACTIVITY_CONTINUE = "CONTINUAR"

# --- Pagamento: loading ---------------------------------------------------
PAYMENT_SENDING_TITLE = "ENVIANDO PAGAMENTO"

PAYMENT_CONFIRMING_TITLE = "CONFIRMANDO PAGAMENTO"
PAYMENT_CHECK_SENT = "Verificando se a cobrança foi enviada..."
PAYMENT_CHECK_SENT_HINT = (
    "A conexão oscilou. Não tente pagar novamente enquanto confirmamos o estado."
)
PAYMENT_CHECK_CREATED = "Verificando se a cobrança foi criada..."
PAYMENT_CHECK_CREATED_HINT = "O tempo terminou. Não inicie outra compra."
PAYMENT_SAFE_CONCLUSION = "Aguardando a conclusão segura da operação..."
PAYMENT_SAFE_CONCLUSION_HINT = (
    "Não inicie outra compra enquanto verificamos se houve cobrança."
)

PAYMENT_VERIFYING_TITLE = "VERIFICANDO PAGAMENTO"
PAYMENT_RECONNECTED = "Conexão restaurada. Confirmando o envio da cobrança..."
PAYMENT_RECONNECTED_HINT = (
    "Não tente pagar novamente enquanto consultamos o servidor."
)

PAYMENT_WAITING_TITLE = "AGUARDANDO PAGAMENTO"
PAYMENT_WAITING = "Estamos verificando a cobrança atual."
PAYMENT_WAITING_HINT = (
    "Verifique se a maquininha está ligada e conectada. "
    "Não inicie outro pagamento."
)
PAYMENT_CHECK_AGAIN = "VERIFICAR NOVAMENTE"

PAYMENT_NOT_CONCLUDED_TITLE = "PAGAMENTO NÃO CONCLUÍDO"
PAYMENT_NOT_CONCLUDED_HINT = "Os produtos continuam na lista da compra."
PAYMENT_BACK_TO_CART = "VOLTAR À COMPRA"

# --- Pagamento: maquininha ------------------------------------------------
PAYMENT_MACHINE_TITLE = "Use a maquininha"
PAYMENT_MACHINE_MESSAGE = "Aperte o botão verde e escolha a forma de pagamento"
PAYMENT_PENDING_TITLE = "PAGAMENTO AINDA NÃO CONCLUÍDO"
# Só aparece em PAYMENT_PENDING_TITLE: é quando o cliente pode ter cancelado
# a forma de pagamento na maquininha.
PAYMENT_PENDING_SUPPORT = (
    "Se cancelar Débito, Crédito ou outra opção, pressione o botão "
    "verde novamente para escolher outra."
)
PAYMENT_CANCELLING_TITLE = "CANCELANDO COMPRA"
PAYMENT_CANCELLING_MESSAGE = "Estamos confirmando o encerramento da cobrança."
PAYMENT_CANCELLING_SUPPORT = (
    "Se a maquininha ainda mostrar a cobrança, cancele a operação nela. "
    "O terminal continuará verificando o resultado."
)
PAYMENT_CANCEL = "CANCELAR COMPRA"
PAYMENT_CANCEL_REQUESTED = "CANCELAMENTO SOLICITADO"

# --- Pagamento: recusa ----------------------------------------------------
PAYMENT_ERROR_TITLE = "PAGAMENTO NÃO APROVADO"
PAYMENT_ERROR_SUPPORT = "Seus produtos continuam na compra."
PAYMENT_RETRY = "TENTAR NOVAMENTE"
# Motivo exibido sob o título. Recusa e falha genérica não acrescentam nada
# ao título, por isso ficam vazias e a linha é ocultada.
PAYMENT_FAILURE_REASONS = {
    "REJECTED": "",
    "FAILED": "",
    "CANCELED": "Pagamento cancelado",
    "CANCELLED": "Pagamento cancelado",
    "EXPIRED": "O tempo para pagamento terminou",
    "REFUNDED": "Pagamento estornado",
}

# --- Pagamento aprovado e comprovante -------------------------------------
POST_PAYMENT_COUNTDOWN = "Finalizando em {minutes:02}:{seconds:02}"
RECEIPT_INPUT_TITLE = "ENVIAR COMPROVANTE"
RECEIPT_PHONE_LABEL = "Número com DDD"
RECEIPT_PHONE_PLACEHOLDER = "(99) 99999-9999"
RECEIPT_SENT_TITLE = "COMPROVANTE ENVIADO"
RECEIPT_FAILED_TITLE = "ENVIO NÃO CONCLUÍDO"
RECEIPT_FAILED_SUFFIX = " O pagamento continua aprovado."

# --- Bloqueio e recuperação (vistas pelo cliente) --------------------------
RECOVERY_CONFIRMING_TITLE = "Confirmando seu pagamento"
RECOVERY_CONFIRMING_MESSAGE = "Aguarde um momento."
UNAVAILABLE_TITLE = "Terminal indisponível"
UNAVAILABLE_MESSAGE = "Chame um atendente."

# --- Offline ----------------------------------------------------------------
OFFLINE_TITLE = "SEM CONEXÃO"
OFFLINE_RETRYING = "Tentando reconectar..."

# --- Ativação (administrador) ------------------------------------------------
ACTIVATION_WAITING = "Aguardando ativação..."
ACTIVATION_BLOCKED = (
    "Operação bloqueada. O Terminal volta sozinho assim que o "
    "backend confirmar a autorização."
)
ACTIVATION_CREDENTIAL_REVOKED = (
    "Credencial revogada ou inválida. Solicite reprovisionamento."
)
ACTIVATION_NO_PERMISSION = (
    "Terminal sem permissão operacional. Contate o administrador."
)

# --- Wi-Fi (administrador) ---------------------------------------------------
WIFI_CHECKING = "Verificando Wi-Fi..."
WIFI_CONNECTING_TITLE = "CONECTANDO AO WI-FI..."
WIFI_DISCONNECTING_TITLE = "DESCONECTANDO WI-FI..."
WIFI_ENABLING_TITLE = "ATIVANDO WI-FI..."
