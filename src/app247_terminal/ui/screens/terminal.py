import logging
from decimal import ROUND_FLOOR, Decimal

from PyQt5.QtCore import QRectF, QSize, Qt, QTimer, QVariantAnimation
from PyQt5.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QBoxLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app247_terminal.services.payment_listener import PaymentListener
from app247_terminal.models.cart import Carrinho
from app247_terminal.models.item import Item
from app247_terminal.models.product import Produtos
from app247_terminal.ui import texts
from app247_terminal.ui.brand import BrandLogo, animations_enabled, flash
from app247_terminal.ui.inactivity import InactivityPrompt
from app247_terminal.ui.responsive import follow_layout_profile
from app247_terminal.ui.styles.svg_icons import ColoredSvgLabel, render_colored_svg
from app247_terminal.ui.styles.theme import Theme
from app247_terminal.ui.styles.tokens import Colors, FontSize, Motion, Radius, Spacing, TouchSize
from app247_terminal.utils.resources import icon_path
from app247_terminal.ui.screens.session_timer import SessionTimerLabel
from app247_terminal.models.money import format_brl, persisted
from app247_terminal.services.scanner_router import ScannerRouter, ScanType
from app247_terminal.services.purchase_api import CustomerLinkWorker
from app247_terminal.services.catalog_service import CatalogService
from app247_terminal.services.customer_link_service import CustomerLinkStateService


logger = logging.getLogger(__name__)


class ProductCard(QFrame):
    """Card touchscreen que apresenta somente dados úteis ao consumidor.

    Hierarquia: nome (até três linhas) no topo, preço como elemento dominante
    e, no rodapé, quantidade em pílula à esquerda e remover à direita. Em
    promoção, o selo com o desconto ocupa o canto superior direito e a
    primeira linha do nome desconta a largura dele.

    Identidade: filete no topo, azul que termina em laranja como as setas do
    logotipo. O card recém-bipado ganha uma borda laranja que some em
    ``Motion.CARD_HIGHLIGHT`` ms, desenhada no próprio card.
    """

    HEIGHT = 280
    # Distância visual uniforme entre a borda e o conteúdo, nos quatro lados.
    PADDING = Spacing.LG
    # Folga entre a área de toque (56 px) e o contorno visível (44 px).
    REMOVE_INSET = (TouchSize.MINIMUM - TouchSize.REMOVE_VISUAL) // 2
    # Borda de 2 px desenhada pelo tema, em cada lado.
    BORDER = 2
    # Selo com nome de promoção ocupa no máximo esta fração da largura útil.
    BADGE_MAX_RATIO = 0.4
    MAX_NAME_LINES = 3
    # Altura do nome com duas linhas; a terceira cresce sobre o espaço livre.
    NAME_HEIGHT = 68
    # Filete de marca no topo: altura e fração azul (o resto é laranja).
    ACCENT_HEIGHT = 3
    ACCENT_BLUE_SHARE = 0.72

    def __init__(self, item, remove_callback, parent=None):
        super().__init__(parent)
        self.item = item
        self._highlight = 0.0
        self._highlight_fade = QVariantAnimation(self)
        self._highlight_fade.setDuration(Motion.CARD_HIGHLIGHT)
        self._highlight_fade.setStartValue(1.0)
        self._highlight_fade.setEndValue(0.0)
        self._highlight_fade.valueChanged.connect(self._set_highlight)
        self.setObjectName("productRow")
        self.setFixedHeight(self.HEIGHT)

        layout = QVBoxLayout(self)
        # À direita e embaixo o botão traz a própria folga até o contorno.
        layout.setContentsMargins(
            self.PADDING,
            self.PADDING,
            self.PADDING - self.REMOVE_INSET,
            self.PADDING - self.REMOVE_INSET,
        )
        layout.setSpacing(Spacing.XS)

        self.name = QLabel()
        self.name.setProperty("role", "productCardName")
        # As linhas são montadas em _update_display_name; com quebra
        # automática o QLabel criaria linhas extras e cortaria o texto.
        self.name.setWordWrap(False)
        self.name.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.name.setFixedHeight(self.NAME_HEIGHT)
        self.original_price = QLabel()
        self.original_price.setProperty("role", "productCardOriginalPrice")
        self.original_price.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.price = QLabel()
        self.price.setProperty("role", "productCardPrice")
        self.price.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.unit_price = QLabel()
        self.unit_price.setProperty("role", "productCardUnitPrice")
        self.unit_price.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # Fora do layout: posicionado no canto em _place_badge.
        self.promotion_badge = QLabel(texts.CART_PROMOTION_BADGE, self)
        self.promotion_badge.setProperty("role", "promotionBadge")
        self.promotion_badge.setAlignment(Qt.AlignCenter)
        self.promotion_badge.hide()
        self.quantity = QLabel()
        self.quantity.setProperty("role", "productCardQuantity")
        self.quantity.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        remove = QPushButton()
        remove.setProperty("variant", "remove")
        remove.setIcon(QIcon(render_colored_svg(
            icon_path("trash.svg"), Colors.ERROR, (48, 48)
        )))
        remove.setIconSize(QSize(TouchSize.REMOVE_ICON, TouchSize.REMOVE_ICON))
        remove.setFixedSize(TouchSize.MINIMUM, TouchSize.MINIMUM)
        remove.setAccessibleName(
            texts.CART_REMOVE_ACCESSIBLE.format(name=item.produto.nome)
        )
        self.remove_button = remove
        remove.clicked.connect(remove_callback)

        bottom = QHBoxLayout()
        bottom.setSpacing(Spacing.MD)
        # A pílula ocupa só a largura do texto.
        bottom.addWidget(self.quantity, 0, Qt.AlignLeft | Qt.AlignVCenter)
        bottom.addStretch(1)
        bottom.addWidget(remove, 0, Qt.AlignVCenter)
        layout.addWidget(self.name)
        layout.addStretch(1)
        layout.addWidget(self.original_price)
        layout.addWidget(self.price)
        layout.addWidget(self.unit_price)
        layout.addStretch(1)
        layout.addLayout(bottom)
        self.update_item(item)

    def update_item(self, item):
        self.item = item
        self.full_name = str(item.produto.nome or "Produto")
        self.name.setToolTip(self.full_name)
        self.name.setAccessibleName(self.full_name)
        promotion = bool(item.produto.em_promocao)
        if promotion:
            original_subtotal = item.produto.preco_original * item.quantidade
            self.original_price.setText(format_brl(original_subtotal))
            self.original_price.show()
            self.promotion_badge.show()
        else:
            self.original_price.hide()
            self.promotion_badge.hide()
        self.price.setText(format_brl(item.subtotal()))
        self.price.setProperty("promotion", promotion)
        self.price.style().unpolish(self.price)
        self.price.style().polish(self.price)
        if item.quantidade > 1:
            self.unit_price.setText(texts.CART_UNIT_PRICE.format(
                quantity=item.quantidade, price=format_brl(item.produto.preco)
            ))
            self.unit_price.show()
        else:
            self.unit_price.hide()
        self.quantity.setText(f"Qtd: {item.quantidade}")
        self._update_badge()
        self._update_display_name()
        self._fit_price()

    @staticmethod
    def discount_percent(original, current):
        """Desconto inteiro arredondado para baixo, ou ``None`` se não calculável.

        Para baixo, o selo nunca anuncia mais desconto do que o real.
        """
        try:
            original = Decimal(str(original))
            current = Decimal(str(current))
        except (ArithmeticError, TypeError, ValueError):
            return None
        if original <= 0 or current < 0 or current >= original:
            return None
        percent = ((original - current) * 100 / original).quantize(
            Decimal("1"), rounding=ROUND_FLOOR
        )
        return int(percent) if percent >= 1 else None

    def _content_width(self):
        """Largura útil para texto, igual à distância visual do botão."""
        return max(1, self.width() - 2 * (self.BORDER + self.PADDING))

    def _update_badge(self):
        if not self.item.produto.em_promocao:
            return
        produto = self.item.produto
        percent = self.discount_percent(produto.preco_original, produto.preco)
        if percent is not None:
            text = texts.CART_DISCOUNT_BADGE.format(percent=percent)
        else:
            self.promotion_badge.ensurePolished()
            metrics = QFontMetrics(self.promotion_badge.font())
            limit = int(self._content_width() * self.BADGE_MAX_RATIO)
            name = str(produto.promocao_nome or texts.CART_PROMOTION_BADGE).upper()
            text = metrics.elidedText(name, Qt.ElideRight, limit)
        self.promotion_badge.setText(text)
        self.promotion_badge.adjustSize()
        self._place_badge()

    def _place_badge(self):
        badge = self.promotion_badge
        badge.move(
            self.width() - self.BORDER - self.PADDING - badge.width(),
            self.BORDER + self.PADDING,
        )
        badge.raise_()

    def set_card_width(self, width):
        self.setFixedWidth(width)
        self._update_badge()
        self._update_display_name()
        self._fit_price()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # A largura final só é conhecida aqui; medir antes disso deixava a
        # primeira linha larga demais e o QLabel a quebrava em uma terceira.
        self._update_badge()
        self._update_display_name()
        self._fit_price()

    def _update_display_name(self):
        """Limita o nome a três linhas sem reduzir a fonte.

        A primeira linha divide espaço com o selo de promoção; as demais usam
        a largura inteira e a última recebe reticências.
        """
        self.name.ensurePolished()
        metrics = QFontMetrics(self.name.font())
        full_width = self._content_width()
        widths = [full_width] * self.MAX_NAME_LINES
        if not self.promotion_badge.isHidden():
            widths[0] = max(1, full_width - self.promotion_badge.width() - Spacing.SM)
        words = self.full_name.split() or ["Produto"]
        lines = []
        for index, width in enumerate(widths):
            if not words:
                break
            if index == len(widths) - 1:
                line = " ".join(words)
                words = []
            else:
                line = words.pop(0)
                while words and metrics.horizontalAdvance(f"{line} {words[0]}") <= width:
                    line = f"{line} {words.pop(0)}"
            lines.append(metrics.elidedText(line, Qt.ElideRight, width))
        self.name.setText("\n".join(lines))
        self.name.setFixedHeight(
            max(self.NAME_HEIGHT, len(lines) * metrics.lineSpacing() + 4)
        )

    def _fit_price(self):
        """Reduz a fonte do preço só quando o valor não cabe na largura útil.

        Começa em ``PRODUCT_PRICE`` e desce até ``PRODUCT_PRICE_MIN``; preços
        que cabem nunca mudam de tamanho.
        """
        self.price.setStyleSheet("")
        self.price.ensurePolished()
        font = self.price.font()
        width = self._content_width()
        size = FontSize.PRODUCT_PRICE
        while size > FontSize.PRODUCT_PRICE_MIN:
            font.setPixelSize(size)
            if QFontMetrics(font).horizontalAdvance(self.price.text()) <= width:
                break
            size -= 1
        if size != FontSize.PRODUCT_PRICE:
            self.price.setStyleSheet(f"font-size: {size}px;")

    def highlight(self):
        """Borda laranja que some em Motion.CARD_HIGHLIGHT ms (leitura do item)."""
        if not animations_enabled():
            return
        self._highlight_fade.stop()
        self._highlight_fade.start()

    def _set_highlight(self, value):
        self._highlight = float(value)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(
            QRectF(self.rect()).adjusted(1, 1, -1, -1), Radius.CARD, Radius.CARD
        )
        painter.setClipPath(clip)
        split = self.width() * self.ACCENT_BLUE_SHARE
        painter.fillRect(QRectF(0, 0, split, self.ACCENT_HEIGHT), QColor(Colors.BRAND_BLUE))
        painter.fillRect(
            QRectF(split, 0, self.width() - split, self.ACCENT_HEIGHT),
            QColor(Colors.BRAND_ORANGE),
        )
        painter.restore()
        if self._highlight > 0:
            color = QColor(Colors.BRAND_ORANGE)
            color.setAlphaF(self._highlight)
            painter.setPen(QPen(color, 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5),
                Radius.CARD, Radius.CARD,
            )
        painter.end()

class TerminalScreen(QWidget):
    """Carrinho visual; o objeto ``carrinho`` é a fonte única da compra atual."""

    GRID_MIN_CARD_WIDTH = 250
    GRID_MAX_CARD_WIDTH = 292
    GRID_MAX_COLUMNS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.parent = parent
        self.db = CatalogService()
        self.carrinho = Carrinho()
        self.linhas = {}
        self.total = Decimal("0")
        self.id_contador = 1
        self.peso_total_venda = 0.0
        self._grid_columns = 3
        self._grid_card_width = self.GRID_MAX_CARD_WIDTH
        self._checkout_interactions_enabled = True
        self.scanner_router = ScannerRouter()
        self.customer_link_store = CustomerLinkStateService()
        self.customer_link_worker = None
        self.customer_link_generation = None
        self.customer_display_name = None

        self.listener = PaymentListener(self)
        self.listener.payment_status_signal.connect(
            self.processar_evento_pagamento, Qt.QueuedConnection
        )
        self.listener.product_sync_required.connect(
            self.processar_evento_produto, Qt.QueuedConnection
        )
        self.listener.sync_requested.connect(
            self.solicitar_sync_produtos, Qt.QueuedConnection
        )
        self.listener.connected.connect(
            self.verificar_pagamento_apos_reconexao, Qt.QueuedConnection
        )
        self.listener.start()

        self.setProperty("role", "page")
        self.setObjectName("cartScreen")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(Theme.cart_stylesheet())
        self._montar_interface()
        # Os itens só existem em memória: depois de reiniciar não há compra para
        # continuar, e um vínculo antigo iria para o próximo cliente.
        self.customer_link_store.clear()
        session = getattr(parent, "compra_session", None)
        if session is not None:
            session.state_changed.connect(self._compra_state_changed)

        self.timer_foco = QTimer(self)
        self.timer_foco.timeout.connect(self.garantir_foco)
        self.timer_foco.start(1000)

    def _montar_interface(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        root.setSpacing(Spacing.MD)

        self.header_card = QFrame(self)
        self.header_card.setObjectName("cartHeader")
        header = QHBoxLayout(self.header_card)
        header.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        header.setSpacing(Spacing.MD)

        title = QLabel("SUA COMPRA")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.session_timer = SessionTimerLabel(self.parent_app.compra_session, self)
        header_logo = BrandLogo(parent=self.header_card)
        header_logo.setFixedSize(70, TouchSize.MINIMUM)
        header.addWidget(header_logo)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.session_timer)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.productsContainer = QWidget()
        self.productsLayout = QGridLayout(self.productsContainer)
        self.productsLayout.setContentsMargins(0, 0, 0, 0)
        self.productsLayout.setSpacing(Spacing.MD)
        self.productsLayout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.scroll.setWidget(self.productsContainer)

        self.empty_label = None
        self._show_empty_state()

        scanner_layout = QHBoxLayout()
        scanner_layout.setSpacing(Spacing.MD)
        self.codigo_barras = QLineEdit()
        self.codigo_barras.setProperty("role", "input")
        self.codigo_barras.setPlaceholderText("Aguardando leitura do produto...")
        self.codigo_barras.returnPressed.connect(self.readProduct)

        self.peso_display = QLineEdit("0.000 KG")
        self.peso_display.setProperty("role", "input")
        self.peso_display.setReadOnly(True)
        self.peso_display.setMaximumWidth(190)
        self.peso_display.setAlignment(Qt.AlignCenter)
        scanner_layout.addWidget(self.codigo_barras, 3)
        scanner_layout.addWidget(self.peso_display, 1)

        self.customer_status = QLabel(texts.CART_CUSTOMER_PROMPT)
        self.customer_status.setProperty("role", "pageSubtitle")
        self.customer_status.setAlignment(Qt.AlignCenter)
        self.customer_icon = ColoredSvgLabel("qr.svg", Colors.TEXT_SECONDARY, "", self)
        self.customer_icon.setFixedSize(28, 28)
        customer_row = QHBoxLayout()
        customer_row.setSpacing(Spacing.SM)
        customer_row.addStretch(1)
        customer_row.addWidget(self.customer_icon)
        customer_row.addWidget(self.customer_status)
        customer_row.addStretch(1)

        self.footer_card = QFrame(self)
        self.footer_card.setObjectName("cartFooter")
        footer = QBoxLayout(QBoxLayout.LeftToRight, self.footer_card)
        self.footer_layout = footer
        footer.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.MD)
        footer.setSpacing(Spacing.MD)

        total_label = QLabel("TOTAL")
        total_label.setObjectName("cartTotalLabel")
        self.totalBox = QLabel("R$ 0,00")
        self.totalBox.setObjectName("cartTotal")
        self.totalBox.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        actions = QHBoxLayout()
        actions.setSpacing(Spacing.MD)
        self.btn_cancelar = QPushButton("CANCELAR COMPRA")
        self.btn_cancelar.setProperty("variant", "ghost")
        self.btn_cancelar.clicked.connect(self.cancelar_venda)

        self.btn_finalizar = QPushButton("FINALIZAR")
        self.btn_finalizar.setProperty("variant", "primary")
        self.btn_finalizar.setProperty("primaryAction", True)
        self.btn_finalizar.setMinimumHeight(TouchSize.PRIMARY_BUTTON)
        self.btn_finalizar.clicked.connect(self.ir_para_pagamento)
        # Alias interno para compatibilidade com integrações/testes antigos.
        self.btn_pagar = self.btn_finalizar

        actions.addWidget(self.btn_cancelar, 1)
        actions.addWidget(self.btn_finalizar, 2)
        total_row = QHBoxLayout()
        total_row.setSpacing(Spacing.MD)
        total_row.addWidget(total_label)
        total_row.addWidget(self.totalBox)
        total_row.addStretch(1)
        footer.addLayout(total_row, 1)
        footer.addLayout(actions, 2)
        follow_layout_profile(self._apply_compact_footer)

        root.addWidget(self.header_card)
        root.addWidget(self.scroll, 1)
        root.addLayout(customer_row)
        root.addLayout(scanner_layout)
        root.addWidget(self.footer_card)
        self.session_timer.follow_orientation(header, root, 1)
        # Sobre a lista: cabeçalho (relógio) e rodapé (ações) ficam livres.
        self.inactivity_prompt = InactivityPrompt(self.scroll, self)

    def _apply_compact_footer(self, compact):
        """Em pé (600 px) o total fica acima das ações em vez de ao lado."""
        self.footer_layout.setDirection(
            QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight
        )

    def atualizar_interface(self):
        self.totalBox.setText(self.carrinho.total_formatado())
        self.peso_display.setText(f"{self.peso_total_venda:.3f} KG")

    def atualizar_linha(self, codigo, label):
        item = self.carrinho.buscar_item(codigo)
        if not item or codigo not in self.linhas:
            return
        _, card, _ = self.linhas[codigo]
        card.update_item(item)

    def _show_empty_state(self):
        self.productsContainer.setMinimumHeight(0)
        self.empty_label = QLabel(texts.CART_EMPTY)
        self.empty_label.setProperty("role", "pageSubtitle")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setMinimumHeight(120)
        self.productsLayout.addWidget(self.empty_label, 0, 0, 1, self._grid_columns)

    def _relayout_product_cards(self):
        cards = [entry[0] for entry in self.linhas.values()]
        for card in cards:
            self.productsLayout.removeWidget(card)
        for index, card in enumerate(cards):
            row, column = divmod(index, self._grid_columns)
            card.set_card_width(self._grid_card_width)
            self.productsLayout.addWidget(card, row, column)
        row_count = (len(cards) + self._grid_columns - 1) // self._grid_columns
        content_height = (
            row_count * ProductCard.HEIGHT
            + max(0, row_count - 1) * self.productsLayout.verticalSpacing()
        )
        self.productsContainer.setMinimumHeight(content_height)

    def _update_grid_geometry(self):
        """Dimensiona o catálogo pelo viewport, já descontada a barra vertical."""
        available_width = self.scroll.viewport().width()
        if available_width <= 0:
            available_width = max(0, self.width() - (2 * Spacing.LG) - 14)

        spacing = self.productsLayout.horizontalSpacing()
        possible_columns = max(
            1,
            (available_width + spacing) // (self.GRID_MIN_CARD_WIDTH + spacing),
        )
        columns = min(self.GRID_MAX_COLUMNS, possible_columns)
        card_width = min(
            self.GRID_MAX_CARD_WIDTH,
            max(
                1,
                (available_width - (spacing * (columns - 1))) // columns,
            ),
        )

        geometry_changed = (
            columns != self._grid_columns or card_width != self._grid_card_width
        )
        self._grid_columns = columns
        self._grid_card_width = card_width

        if self.empty_label is not None:
            self.productsLayout.removeWidget(self.empty_label)
            self.productsLayout.addWidget(
                self.empty_label, 0, 0, 1, self._grid_columns
            )
        elif geometry_changed:
            self._relayout_product_cards()

    def processar_evento_pagamento(self, data):
        if self.parent_app:
            self.parent_app.pagamento.processar_evento(data)

    def processar_evento_produto(self, event):
        self.solicitar_sync_produtos("WEBSOCKET_EVENT")

    def solicitar_sync_produtos(self, origin):
        sync_service = getattr(self.parent_app, "sync_service", None)
        if sync_service is not None:
            sync_service.request_sync(origin)

    def reconciliar_pagamento(self):
        if self.parent_app and self.parent_app.compra_session.payment_in_flight:
            self.parent_app.pagamento.reconciliar_estado()

    def verificar_pagamento_apos_reconexao(self):
        if self.parent_app:
            self.parent_app.pagamento.verificar_apos_reconexao()

    def liberar_tela(self):
        self._desvincular_cliente()
        if self.parent_app is not None:
            self.parent_app.compra_session.cart_id = None
        self.carrinho = Carrinho()
        self.linhas.clear()
        while self.productsLayout.count():
            layout_item = self.productsLayout.takeAt(0)
            widget = layout_item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.empty_label = None
        self._show_empty_state()
        self.total = Decimal("0")
        self.id_contador = 1
        self.peso_total_venda = 0.0
        self.atualizar_interface()

    def set_checkout_interactions_enabled(self, enabled):
        self._checkout_interactions_enabled = bool(enabled)
        self.codigo_barras.setEnabled(enabled)
        self.btn_finalizar.setEnabled(enabled)
        self.btn_cancelar.setEnabled(enabled)
        for card, _, _ in self.linhas.values():
            card.setEnabled(enabled)

    def _can_accept_checkout_action(self):
        if not self._checkout_interactions_enabled:
            return False
        if self.parent_app.stacked_widget.currentWidget() is not self:
            return False
        return self.parent_app.compra_session.can_accept_checkout_actions()

    def garantir_foco(self):
        if self.parent and self.parent.stacked_widget.currentWidget() == self:
            if not self.codigo_barras.hasFocus():
                self.codigo_barras.setFocus()

    def ir_para_pagamento(self):
        """Abre o resumo; nenhuma chamada remota é iniciada neste toque."""
        if self.parent_app.compra_session.payment_in_flight:
            logger.warning(
                "[PAYMENT-UI] acesso à confirmação bloqueado: pagamento ativo orderId=%s attemptId=%s status=%s",
                self.parent_app.compra_session.order_id,
                self.parent_app.compra_session.payment_attempt_id,
                self.parent_app.compra_session.last_status,
            )
            self.parent_app.pagamento.mostrar_reconciliacao_pendente(
                origin="CART_ACTION"
            )
            return
        if not self._can_accept_checkout_action():
            return
        if not self.linhas:
            self.mostrar_aviso(
                "Carrinho vazio", "Adicione pelo menos um produto antes de continuar."
            )
            return
        if self.parent_app:
            self.parent_app.confirmacao_compra.mostrar_resumo()
            self.parent_app.setCurrentWidget(self.parent_app.confirmacao_compra)

    def iniciar_pagamento_confirmado(self):
        """Único ponto visual que encaminha o carrinho atual ao fluxo Point."""
        if self.parent_app is None:
            logger.error("[PAYMENT-UI] início recusado: parent ausente")
            return False
        if not self._checkout_interactions_enabled:
            logger.warning("[PAYMENT-UI] início recusado: interações bloqueadas")
            return False
        if self.parent_app.stacked_widget.currentWidget() is not self.parent_app.confirmacao_compra:
            logger.warning("[PAYMENT-UI] início recusado: tela atual não é confirmação")
            return False
        if self.parent_app.compra_session.payment_in_flight:
            logger.warning(
                "[PAYMENT-UI] início recusado: pagamento ativo orderId=%s attemptId=%s status=%s",
                self.parent_app.compra_session.order_id,
                self.parent_app.compra_session.payment_attempt_id,
                self.parent_app.compra_session.last_status,
            )
            self.parent_app.pagamento.mostrar_reconciliacao_pendente(
                origin="CONFIRM_BUTTON"
            )
            return False
        if not self.parent_app.compra_session.can_accept_checkout_actions():
            logger.warning("[PAYMENT-UI] início recusado: sessão indisponível")
            return False
        if self.carrinho.vazio():
            logger.warning("[PAYMENT-UI] início recusado: carrinho vazio")
            return False

        logger.info("[PAYMENT-UI] navegando para preparação do pagamento")
        cart_payload = self.carrinho.to_dict()
        if (self.customer_display_name is not None
                and self.parent_app.compra_session.charge_changes_cart(cart_payload)):
            generation = self.parent_app.compra_session.generation
            self._desvincular_cliente()
            self.mostrar_aviso(
                "Cliente desvinculado",
                "Você alterou os itens depois do pagamento não aprovado, então esta "
                "compra seguirá sem vínculo com o seu App247.",
            )
            # O aviso é modal: inatividade ou teto podem encerrar a compra
            # enquanto ele está aberto, e então não há o que cobrar.
            if (generation != self.parent_app.compra_session.generation
                    or not self.parent_app.compra_session.can_accept_checkout_actions()):
                logger.warning("[PAYMENT-UI] início recusado: compra encerrada no aviso")
                return False
        return self.parent_app.pagamento.iniciar_pagamento(
            cart_payload, self.totalBox.text()
        )

    def cancelar_venda(self):
        if self.parent_app and self._can_accept_checkout_action():
            self.parent_app.reset_compra()
            self.parent_app.setCurrentWidget(self.parent_app.welcome)

    def remover_produto(self, codigo_produto, widget_linha):
        if not self._can_accept_checkout_action():
            return
        item = self.carrinho.buscar_item(codigo_produto)
        if not item:
            return
        self.carrinho.remover_item(codigo_produto)
        self.linhas.pop(codigo_produto, None)
        widget_linha.deleteLater()
        self._relayout_product_cards()
        self.atualizar_interface()
        if self.carrinho.vazio():
            had_customer = (self.customer_display_name is not None
                            or self.customer_link_worker is not None)
            self.parent_app.compra_session.cancel()
            self._show_empty_state()
            if had_customer:
                self.mostrar_aviso(
                    "Cliente desvinculado",
                    "Você removeu todos os itens, então esta compra não está mais "
                    "vinculada ao seu App247.\n\nPara vincular, escaneie um novo QR "
                    "do aplicativo.",
                )

    def readProduct(self):
        self._registrar_atividade()
        scan = self.scanner_router.parse(self.codigo_barras.text())
        self.codigo_barras.clear()
        if scan.type == ScanType.UNKNOWN:
            if scan.value:
                self.mostrar_aviso("QR não reconhecido", "Use um QR de identificação do App247.")
            return
        if scan.type == ScanType.CUSTOMER_LINK_TOKEN:
            self._link_customer(scan.value)
            return
        if not self._can_accept_checkout_action():
            return
        barcode = scan.value
        try:
            product_tuple = self.db.buscar_por_codigo(barcode)
            if not product_tuple:
                self.mostrar_aviso(
                    "Produto não encontrado", "O produto informado não está cadastrado."
                )
                self.codigo_barras.clear()
                return

            produto = Produtos.from_tuple(product_tuple)
            codigo = produto.codigo
            if not self.parent_app.compra_session.start_if_needed():
                self.codigo_barras.clear()
                return

            item_existente = self.carrinho.buscar_item(produto.id)
            if item_existente is not None:
                codigo_existente = item_existente.produto.codigo
                item = item_existente
                item.quantidade += 1
                _, label, _ = self.linhas[codigo_existente]
                self.atualizar_interface()
                self.atualizar_linha(codigo_existente, label)
                self._destacar_leitura(label)
                self.codigo_barras.clear()
                self.codigo_barras.setFocus()
                return

            if self.empty_label is not None:
                self.empty_label.setParent(None)
                self.empty_label.deleteLater()
                self.empty_label = None

            novo_item = Item(produto=produto, quantidade=1, received_weight=None)
            self.carrinho.adicionar_item(novo_item)
            item = self.carrinho.buscar_item(codigo)
            id_linha = self.id_contador

            linha_widget = ProductCard(
                item,
                lambda _, c=codigo: self.remover_produto(
                    c, self.linhas[c][0]
                ),
                self.productsContainer,
            )
            self.linhas[codigo] = (linha_widget, linha_widget, id_linha)
            self._relayout_product_cards()

            self.atualizar_interface()
            self._destacar_leitura(linha_widget)
            self.id_contador += 1
            self.codigo_barras.clear()
            self.codigo_barras.setFocus()
        except Exception:
            logger.exception("Erro ao processar leitura do produto")
            self.mostrar_aviso(
                "Não foi possível ler o produto",
                "Tente escanear novamente. Se o problema continuar, chame o responsável.",
            )

    def _registrar_atividade(self):
        """Leitura do leitor conta como presença, mesmo vinda da tela inicial."""
        monitor = getattr(self.parent_app, "inactivity_monitor", None)
        if monitor is not None:
            monitor.register_activity()

    def _destacar_leitura(self, card):
        """Confirma a leitura: traz o card para a área visível e o destaca."""
        # A geometria do card novo só existe depois que o layout é ativado.
        self.productsLayout.activate()
        self.scroll.ensureWidgetVisible(card, 0, Spacing.MD)
        if isinstance(card, ProductCard):
            card.highlight()
        else:
            flash(card)
        flash(self.footer_card)

    def _link_customer(self, opaque_token):
        if self.parent_app.compra_session.payment_in_flight:
            self.mostrar_aviso(
                "Pagamento em andamento",
                "Não é possível alterar o cliente enquanto há um pagamento em andamento.",
            )
            return
        if self.customer_link_worker is not None and self.customer_link_worker.isRunning():
            return
        if not self.parent_app.compra_session.start_if_needed():
            return
        self.customer_link_generation = self.parent_app.compra_session.generation
        self.customer_status.setText("Identificando cliente...")
        self.codigo_barras.setEnabled(False)
        self.customer_link_worker = CustomerLinkWorker(
            opaque_token,
            self.carrinho.to_dict(),
            cart_id=self.parent_app.compra_session.cart_id,
            parent=self,
        )
        self.customer_link_worker.succeeded.connect(self._customer_linked)
        self.customer_link_worker.failed.connect(self._customer_link_failed)
        self.customer_link_worker.finished.connect(self._customer_worker_finished)
        self.customer_link_worker.start()

    def _customer_link_is_stale(self):
        """Resposta de uma compra que já acabou não pode tocar a compra seguinte."""
        session = self.parent_app.compra_session
        if (self.customer_link_generation is not None
                and self.customer_link_generation == session.generation
                and not session.payment_in_flight):
            return False
        logger.info("[CUSTOMER-LINK] resposta descartada; compra de origem encerrada")
        self.customer_link_generation = None
        return True

    def _customer_linked(self, payload):
        if self._customer_link_is_stale():
            self._show_customer_prompt()
            return
        cart_id = str(payload.get("cartId") or "")
        if not cart_id:
            self._customer_link_failed("CUSTOMER_LINK_FAILED", "Resposta inválida")
            return
        self.parent_app.compra_session.set_remote_ids(cart_id=cart_id)
        self.customer_display_name = str(payload.get("displayName") or "Cliente")
        self.customer_status.setText(
            f"✓ Compra vinculada a {self.customer_display_name}"
        )

    def _customer_link_failed(self, code, _message):
        if self._customer_link_is_stale():
            self._show_customer_prompt()
            return
        messages = {
            "CUSTOMER_LINK_TOKEN_EXPIRED": "QR expirado. Gere um novo QR no aplicativo.",
            "CUSTOMER_LINK_TOKEN_ALREADY_USED": "Este QR já foi utilizado. Gere um novo QR no aplicativo.",
            "CUSTOMER_LINK_TENANT_MISMATCH": "Este QR não pode ser usado neste Terminal.",
            "CUSTOMER_ALREADY_LINKED": "Esta compra já está vinculada a outro cliente.",
            "CUSTOMER_LINK_PAYMENT_ALREADY_STARTED": "Não é possível alterar o cliente enquanto há um pagamento em andamento.",
            "CUSTOMER_LINK_RATE_LIMITED": "Aguarde um momento antes de tentar novamente.",
        }
        friendly = messages.get(code, "Não foi possível identificar o cliente. Tente novamente.")
        self._show_customer_prompt()
        self.mostrar_aviso("Identificação do cliente", friendly)

    def _customer_worker_finished(self):
        worker = self.customer_link_worker
        self.customer_link_worker = None
        if worker is not None:
            worker.deleteLater()
        if self._checkout_interactions_enabled:
            self.codigo_barras.setEnabled(True)
            self.codigo_barras.setFocus()

    def _show_customer_prompt(self):
        self.customer_status.setText(texts.CART_CUSTOMER_PROMPT)

    def _desvincular_cliente(self):
        self.customer_link_generation = None
        self.customer_display_name = None
        self._show_customer_prompt()

    def _compra_state_changed(self, state):
        # O vínculo vale só para a compra atual; toda compra encerrada passa por IDLE.
        if state == "IDLE":
            self._desvincular_cliente()

    def aplicar_precos_atualizados(self, payload):
        for change in (payload or {}).get("items", []):
            product_id = str(change.get("produtoId") or "")
            for item in self.carrinho.listar_itens():
                if str(item.produto.id) != product_id:
                    continue
                item.produto.preco_original = persisted(change.get("precoOriginal"))
                item.produto.preco = persisted(change.get("precoAtual"))
                item.produto.em_promocao = bool(change.get("emPromocao"))
                item.produto.promocao_id = change.get("promocaoId")
                item.produto.promocao_nome = change.get("promocaoNome")
                self.atualizar_linha(item.produto.codigo, None)
        self.atualizar_interface()

    def mostrar_aviso(self, titulo, mensagem):
        QMessageBox.warning(self, titulo, mensagem, QMessageBox.Ok)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_grid_geometry()
        # O viewport recebe sua largura final depois que o layout raiz conclui o
        # resize; recalcular no próximo ciclo evita usar a largura provisória.
        QTimer.singleShot(0, self._update_grid_geometry)
