def _rgba(color, alpha):
    """Versão translúcida de uma cor ``#RRGGBB`` para QSS (alpha de 0 a 255)."""
    red, green, blue = (int(color[index:index + 2], 16) for index in (1, 3, 5))
    return f"rgba({red}, {green}, {blue}, {alpha})"


class Colors:
    BACKGROUND_PRIMARY = "#08111F"
    BACKGROUND_SECONDARY = "#03111F"
    SURFACE = "#071C33"
    SURFACE_ELEVATED = "#0D253F"
    SURFACE_HOVER = "#102748"

    PRIMARY = "#169DFF"
    PRIMARY_HOVER = "#39B8FF"
    PRIMARY_PRESSED = "#0D8CFF"
    SECONDARY = "#62C8FF"

    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#8DD4FF"
    TEXT_MUTED = "#8B949E"
    TEXT_DISABLED = "#7F97B7"
    TEXT_ON_PRIMARY = "#03111F"

    BORDER = "#17324D"
    DIVIDER = "#30363D"

    SUCCESS = "#00D084"
    SUCCESS_HOVER = "#00E693"
    WARNING = "#E0B54A"
    ERROR = "#FF4D4D"
    ERROR_HOVER = "#F85149"
    INFO = SECONDARY
    # Preço "de" riscado: cinza-azulado com contraste 5,2:1 sobre SURFACE_ELEVATED.
    PRICE_ORIGINAL = TEXT_DISABLED

    # Cores medidas no logotipo oficial (assets/images/logo.png): mediana dos
    # pixels azuis do "24" e dos arcos e dos laranja do "7" e da seta. O
    # laranja é destaque de marca e de feedback; não substitui os estados
    # semânticos acima.
    BRAND_BLUE = "#0073D5"
    BRAND_BLUE_DARK = "#0A5FC4"
    BRAND_ORANGE = "#FF8402"
    BRAND_ORANGE_LIGHT = "#FFB21C"
    BRAND_ORANGE_PRESSED = "#E0650A"
    # Card do carrinho: borda azul discreta e pílula da quantidade.
    CARD_BORDER_BRAND = _rgba(BRAND_BLUE, 70)
    QUANTITY_PILL = _rgba(BRAND_BLUE, 64)

    # Fundos semânticos de estado. Foram escolhidos para manter contraste AA
    # com texto/ícones brancos em uma tela inteira, não apenas em detalhes.
    PAYMENT_SUCCESS_BACKGROUND = "#087A4F"
    PAYMENT_ATTENTION_BACKGROUND = "#C44D0A"
    PAYMENT_ERROR_BACKGROUND = "#D92D20"
    PAYMENT_STATE_FOREGROUND = "#FFFFFF"
    PAYMENT_ACTION_SECONDARY = "#075D3E"
    PAYMENT_ACTION_DANGER = "#7A1F1F"

    LIGHT_SURFACE = "#FFFFFF"
    TEXT_ON_LIGHT = "#10233A"

    INPUT_BACKGROUND = "#FFFFFF"
    INPUT_TEXT = "#17324D"
    INPUT_PLACEHOLDER = "#7F97B7"
    DISABLED_BACKGROUND = "#21262D"
    OVERLAY = "rgba(0, 0, 0, 220)"


class FontFamily:
    PRIMARY = '"Segoe UI", "DejaVu Sans", sans-serif'
    MONOSPACE = '"Consolas", "DejaVu Sans Mono", monospace'


class FontSize:
    DISPLAY = 52
    H1 = 38
    H2 = 30
    H3 = 26
    BODY = 22
    LABEL = 20
    SMALL = 18
    CAPTION = 16
    BUTTON = 22
    PRODUCT_NAME = 26
    PRODUCT_PRICE = 34
    # Piso do preço do card quando o valor não cabe em PRODUCT_PRICE.
    PRODUCT_PRICE_MIN = 22
    PRODUCT_QUANTITY = 22
    TOTAL_LABEL = 28
    CART_TOTAL_VALUE = 46
    TOTAL_VALUE = 48
    CONFIRMATION_PRODUCT_NAME = 26
    CONFIRMATION_PRODUCT_DETAIL = 24
    CONFIRMATION_ACTION = 26
    LOADING_MESSAGE = 32
    STATUS_TITLE = 42


class FontWeight:
    REGULAR = 400
    MEDIUM = 600
    BOLD = 700
    EXTRA_BOLD = 900


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32
    XXXL = 48


class TouchSize:
    MINIMUM = 56
    INPUT = 60
    SECONDARY_BUTTON = 60
    PRIMARY_BUTTON = 72
    ICON = 32
    # Contorno do botão de remover; a área de toque continua em MINIMUM.
    REMOVE_VISUAL = 44
    REMOVE_ICON = 24


class Radius:
    SMALL = 8
    INPUT = 12
    BUTTON = 12
    CARD = 18
    MODAL = 24


class Motion:
    """Durações (ms) das animações; a curva padrão é QEasingCurve.OutCubic."""

    FAST = 150
    BASE = 250
    SLOW = 400
    LOADER_TURN = 1600
    LOGO_PULSE = 2400
    # Borda laranja do card recém-bipado, até sumir.
    CARD_HIGHLIGHT = 600
