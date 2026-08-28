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

    # Fundos semânticos de estado. Foram escolhidos para manter contraste AA
    # com texto/ícones brancos em uma tela inteira, não apenas em detalhes.
    PAYMENT_SUCCESS_BACKGROUND = "#087A4F"
    PAYMENT_ATTENTION_BACKGROUND = "#C44D0A"
    PAYMENT_ERROR_BACKGROUND = "#D92D20"
    PAYMENT_STATE_FOREGROUND = "#FFFFFF"

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


class Radius:
    SMALL = 8
    INPUT = 12
    BUTTON = 12
    CARD = 18
    MODAL = 24
