from styles.tokens import (
    Colors,
    FontFamily,
    FontSize,
    FontWeight,
    Radius,
    Spacing,
    TouchSize,
)


class Theme:
    @classmethod
    def component_stylesheet(cls):
        return f"""
            QWidget {{
                font-family: {FontFamily.PRIMARY};
                font-size: {FontSize.BODY}px;
                color: {Colors.TEXT_PRIMARY};
            }}

            QWidget[role="page"] {{
                background-color: {Colors.BACKGROUND_PRIMARY};
            }}

            QLabel[role="pageTitle"] {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {FontSize.H1}px;
                font-weight: {FontWeight.BOLD};
            }}

            QLabel[role="pageSubtitle"] {{
                color: {Colors.TEXT_SECONDARY};
                font-size: {FontSize.BODY}px;
            }}

            QLabel[role="sectionTitle"] {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {FontSize.H2}px;
                font-weight: {FontWeight.BOLD};
            }}

            QFrame[role="card"] {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}

            QFrame[role="information"] {{
                background-color: {Colors.SURFACE_ELEVATED};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.INPUT}px;
            }}

            QPushButton {{
                min-height: {TouchSize.SECONDARY_BUTTON}px;
                padding: 0 {Spacing.XL}px;
                border-radius: {Radius.BUTTON}px;
                border: 1px solid transparent;
                font-size: {FontSize.BUTTON}px;
                font-weight: {FontWeight.BOLD};
            }}

            QPushButton[primaryAction="true"] {{
                min-height: {TouchSize.PRIMARY_BUTTON}px;
                font-size: {FontSize.H3}px;
            }}

            QPushButton[variant="primary"] {{
                background-color: {Colors.PRIMARY};
                color: {Colors.TEXT_ON_PRIMARY};
            }}
            QPushButton[variant="primary"]:hover {{
                background-color: {Colors.PRIMARY_HOVER};
            }}
            QPushButton[variant="primary"]:pressed {{
                background-color: {Colors.PRIMARY_PRESSED};
            }}

            QPushButton[variant="secondary"] {{
                background-color: {Colors.SURFACE_ELEVATED};
                color: {Colors.TEXT_SECONDARY};
                border-color: {Colors.PRIMARY};
            }}
            QPushButton[variant="secondary"]:hover {{
                background-color: {Colors.SURFACE_HOVER};
            }}
            QPushButton[variant="secondary"]:pressed {{
                background-color: {Colors.BACKGROUND_SECONDARY};
            }}

            QPushButton[variant="danger"] {{
                background-color: {Colors.ERROR};
                color: {Colors.TEXT_PRIMARY};
            }}
            QPushButton[variant="danger"]:hover {{
                background-color: {Colors.ERROR_HOVER};
            }}
            QPushButton[variant="danger"]:pressed {{
                background-color: {Colors.BACKGROUND_SECONDARY};
            }}

            QPushButton[variant="ghost"] {{
                background-color: transparent;
                color: {Colors.TEXT_SECONDARY};
                border-color: {Colors.BORDER};
            }}
            QPushButton[variant="ghost"]:hover {{
                background-color: {Colors.SURFACE_HOVER};
            }}

            QPushButton:disabled {{
                background-color: {Colors.DISABLED_BACKGROUND};
                color: {Colors.TEXT_DISABLED};
                border-color: {Colors.DIVIDER};
            }}

            QLineEdit[role="input"] {{
                min-height: {TouchSize.INPUT}px;
                padding: 0 {Spacing.LG}px;
                background-color: {Colors.INPUT_BACKGROUND};
                color: {Colors.INPUT_TEXT};
                border: 2px solid transparent;
                border-radius: {Radius.INPUT}px;
                selection-background-color: {Colors.PRIMARY};
            }}
            QLineEdit[role="input"]:focus {{
                border-color: {Colors.PRIMARY};
            }}
            QLineEdit[role="input"][state="error"] {{
                border-color: {Colors.ERROR};
            }}
            QLineEdit[role="input"]:disabled,
            QLineEdit[role="input"]:read-only {{
                background-color: {Colors.DISABLED_BACKGROUND};
                color: {Colors.TEXT_DISABLED};
                border-color: {Colors.DIVIDER};
            }}

            QLabel[state="success"] {{ color: {Colors.SUCCESS}; }}
            QLabel[state="warning"] {{ color: {Colors.WARNING}; }}
            QLabel[state="error"] {{ color: {Colors.ERROR}; }}
            QLabel[state="info"],
            QLabel[state="loading"] {{ color: {Colors.INFO}; }}

            QLabel[role="sessionTimer"] {{
                min-height: 38px;
                padding: 0 {Spacing.MD}px;
                color: {Colors.TEXT_SECONDARY};
                background-color: {Colors.SURFACE_ELEVATED};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.SMALL}px;
                font-size: {FontSize.LABEL}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel[role="sessionTimer"][state="warning"] {{
                color: {Colors.WARNING};
                border-color: {Colors.WARNING};
            }}
            QLabel[role="sessionTimer"][state="critical"] {{
                color: {Colors.PAYMENT_STATE_FOREGROUND};
                background-color: {Colors.PAYMENT_ATTENTION_BACKGROUND};
                border-color: {Colors.PAYMENT_STATE_FOREGROUND};
            }}

            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
            QScrollBar:vertical {{
                width: 14px;
                background: {Colors.BACKGROUND_PRIMARY};
                border: none;
            }}
            QScrollBar::handle:vertical {{
                min-height: {TouchSize.MINIMUM}px;
                background: {Colors.PRIMARY};
                border-radius: 7px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
        """

    @classmethod
    def page_stylesheet(cls):
        return cls.component_stylesheet() + f"""
            QWidget[role="page"] {{ background-color: {Colors.BACKGROUND_PRIMARY}; }}
        """

    @classmethod
    def cart_stylesheet(cls):
        return cls.page_stylesheet() + f"""
            QWidget#cartScreen {{
                background-color: {Colors.BACKGROUND_PRIMARY};
            }}
            QFrame#cartHeader, QFrame#cartFooter {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}
            QLabel#cartTotalLabel {{
                color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.LABEL}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel#cartTotal {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.CART_TOTAL_VALUE}px;
                font-weight: {FontWeight.BOLD};
            }}
            QFrame#productRow {{
                background-color: {Colors.SURFACE_ELEVATED};
                border: 2px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}
            QLabel[role="productCardName"] {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.PRODUCT_NAME}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel[role="productCardPrice"] {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.PRODUCT_PRICE}px;
                font-weight: {FontWeight.EXTRA_BOLD};
            }}
            QLabel[role="productCardOriginalPrice"] {{
                color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.SMALL}px;
                text-decoration: line-through;
            }}
            QLabel[role="promotionBadge"] {{
                color: {Colors.PAYMENT_STATE_FOREGROUND};
                background-color: {Colors.SUCCESS};
                border-radius: {Radius.SMALL}px;
                padding: 3px {Spacing.SM}px;
                font-size: {FontSize.CAPTION}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel[role="productCardQuantity"] {{
                color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.PRODUCT_QUANTITY}px;
                font-weight: {FontWeight.BOLD};
            }}
            QPushButton[variant="remove"] {{
                min-width: 108px;
                min-height: {TouchSize.MINIMUM}px;
                padding: 0 {Spacing.MD}px; background-color: {Colors.ERROR};
                color: {Colors.PAYMENT_STATE_FOREGROUND}; border: 2px solid {Colors.ERROR};
                font-size: {FontSize.SMALL}px;
            }}
        """

    @classmethod
    def purchase_confirmation_stylesheet(cls):
        return cls.page_stylesheet() + f"""
            QWidget#purchaseConfirmationScreen {{
                background-color: {Colors.BACKGROUND_PRIMARY};
            }}
            QFrame#purchaseConfirmationCard {{
                background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}
            QLabel#purchaseConfirmationTitle {{
                color: {Colors.TEXT_PRIMARY}; font-size: 40px;
                font-weight: {FontWeight.EXTRA_BOLD};
            }}
            QLabel#confirmationItemCount {{
                color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.H3}px;
                font-weight: {FontWeight.MEDIUM};
            }}
            QFrame#confirmationTotalCard {{
                background-color: {Colors.LIGHT_SURFACE};
                border: 3px solid {Colors.PRIMARY};
                border-radius: {Radius.INPUT}px;
            }}
            QLabel#confirmationTotalCaption {{
                color: {Colors.TEXT_ON_LIGHT}; font-size: {FontSize.TOTAL_LABEL}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel#confirmationTotal {{
                color: {Colors.TEXT_ON_LIGHT}; font-size: {FontSize.TOTAL_VALUE}px;
                font-weight: {FontWeight.EXTRA_BOLD};
            }}
            QLabel[role="confirmationProductName"] {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.CONFIRMATION_PRODUCT_NAME}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel[role="confirmationProductQuantity"] {{
                color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.CONFIRMATION_PRODUCT_DETAIL}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel[role="confirmationProductPrice"] {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.CONFIRMATION_PRODUCT_DETAIL}px;
                font-weight: {FontWeight.EXTRA_BOLD};
            }}
            QPushButton[confirmationAction="true"] {{
                min-height: {TouchSize.PRIMARY_BUTTON}px;
                font-size: {FontSize.CONFIRMATION_ACTION}px;
            }}
        """

    @classmethod
    def welcome_stylesheet(cls):
        return cls.page_stylesheet() + f"""
            QFrame#centralCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Colors.SURFACE}, stop:1 {Colors.BACKGROUND_SECONDARY});
                border: 1px solid {Colors.BORDER}; border-radius: {Radius.CARD}px;
            }}
            QLabel#welcomeTitle {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.DISPLAY}px;
                font-weight: {FontWeight.EXTRA_BOLD};
            }}
            QLabel#welcomeSubtitle {{
                color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.H3}px;
                font-weight: {FontWeight.MEDIUM}; letter-spacing: 4px;
            }}
            QLabel#welcomeClock {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.DISPLAY}px;
                font-weight: {FontWeight.MEDIUM};
            }}
        """

    @classmethod
    def settings_stylesheet(cls):
        return cls.page_stylesheet() + f"""
            QFrame#settingsCard {{
                background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}
        """

    @classmethod
    def wifi_stylesheet(cls):
        return cls.keyboard_stylesheet() + f"""
            QFrame#wifiStatusCard {{
                background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}
            QLabel#wifiCurrentSsid {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.H3}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel#wifiCurrentDetails {{
                color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.SMALL}px;
            }}
            QPushButton[wifiNetwork="true"] {{
                min-height: 76px; padding: {Spacing.SM}px {Spacing.LG}px;
                text-align: left; background-color: {Colors.SURFACE_ELEVATED};
                color: {Colors.TEXT_PRIMARY}; border: 2px solid {Colors.BORDER};
                font-size: {FontSize.LABEL}px;
            }}
            QPushButton[wifiNetwork="true"][connected="true"] {{
                border-color: {Colors.SUCCESS}; color: {Colors.SUCCESS};
            }}
            QLabel#wifiFeedbackMessage {{
                color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.H3}px;
                font-weight: {FontWeight.MEDIUM};
            }}
        """

    @classmethod
    def display_stylesheet(cls):
        return cls.settings_stylesheet() + f"""
            QFrame#displayStatusCard {{
                background-color: {Colors.SURFACE_ELEVATED};
                border: 2px solid {Colors.BORDER}; border-radius: {Radius.CARD}px;
            }}
            QLabel#displayCurrentOrientation {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.H2}px;
                font-weight: {FontWeight.BOLD};
            }}
        """

    @classmethod
    def admin_stylesheet(cls):
        return cls.keyboard_stylesheet() + f"""
            QFrame#adminAuthCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}
            QLabel#adminAuthStatus {{
                min-height: {TouchSize.MINIMUM}px;
                color: {Colors.TEXT_SECONDARY};
                font-size: {FontSize.BODY}px;
                font-weight: {FontWeight.MEDIUM};
            }}
            QLabel#adminAuthStatus[state="error"] {{ color: {Colors.ERROR}; }}
        """

    @classmethod
    def keyboard_stylesheet(cls):
        return cls.page_stylesheet() + f"""
            QFrame#inputContainer {{
                background-color: {Colors.SURFACE}; border: 2px solid {Colors.PRIMARY};
                border-radius: {Radius.CARD}px;
            }}
            QPushButton[key="true"] {{
                min-height: 64px; min-width: 56px; padding: 0 {Spacing.SM}px;
                background-color: {Colors.SURFACE_ELEVATED}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER}; font-size: {FontSize.BODY}px;
            }}
            QPushButton[key="true"]:pressed {{ background-color: {Colors.PRIMARY_PRESSED}; }}
            QPushButton[keyType="special"] {{ color: {Colors.TEXT_SECONDARY}; border-color: {Colors.PRIMARY}; }}
        """

    @classmethod
    def app_payment_stylesheet(cls):
        return cls.page_stylesheet() + f"""
            QFrame#appPaymentCard {{
                background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}
            QLabel#appPaymentTotal {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.DISPLAY}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel#appPaymentTimer {{ color: {Colors.WARNING}; font-size: {FontSize.H2}px; font-weight: {FontWeight.BOLD}; }}
        """

    @classmethod
    def offline_stylesheet(cls):
        return cls.component_stylesheet() + f"""
            QWidget#offlineOverlay {{ background-color: {Colors.OVERLAY}; }}
            QFrame#offlineCard {{
                background-color: {Colors.SURFACE_ELEVATED};
                border: 2px solid {Colors.ERROR}; border-radius: {Radius.MODAL}px;
            }}
            QLabel#offlineIcon {{ color: {Colors.ERROR}; font-size: 84px; }}
        """

    @classmethod
    def activation_stylesheet(cls):
        return cls.component_stylesheet() + f"""
            QWidget#activationScreen {{
                background-color: {Colors.BACKGROUND_PRIMARY};
            }}

            QFrame#activationCard {{
                background: qlineargradient(
                    spread: pad,
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {Colors.SURFACE},
                    stop: 1 {Colors.BACKGROUND_SECONDARY}
                );
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}

            QWidget#activationBody,
            QWidget#activationDetails {{
                background-color: transparent;
            }}

            QLabel#activationTitle {{
                color: {Colors.TEXT_PRIMARY};
                background-color: transparent;
                font-size: {FontSize.H1}px;
                font-weight: {FontWeight.BOLD};
                letter-spacing: 2px;
            }}

            QLabel#activationSubtitle {{
                color: {Colors.TEXT_SECONDARY};
                background-color: transparent;
                font-size: {FontSize.BODY}px;
            }}

            QLabel#activationQrCode {{
                background-color: {Colors.INPUT_BACKGROUND};
                border: 6px solid {Colors.INPUT_BACKGROUND};
                border-radius: {Radius.INPUT}px;
                padding: {Spacing.XS}px;
            }}

            QLabel#activationDeviceInfo {{
                color: {Colors.TEXT_SECONDARY};
                background-color: transparent;
                font-family: {FontFamily.MONOSPACE};
                font-size: {FontSize.SMALL}px;
            }}

            QLabel#activationStatus {{
                color: {Colors.INFO};
                background-color: {Colors.SURFACE_ELEVATED};
                border: 1px solid {Colors.PRIMARY};
                border-radius: {Radius.INPUT}px;
                font-size: {FontSize.BODY}px;
                font-weight: {FontWeight.MEDIUM};
                padding: {Spacing.MD}px;
            }}

            QLabel#activationStatus[state="success"] {{
                color: {Colors.SUCCESS};
                border-color: {Colors.SUCCESS};
            }}

            QLabel#activationStatus[state="error"] {{
                color: {Colors.TEXT_PRIMARY};
                background-color: {Colors.ERROR};
                border-color: {Colors.ERROR_HOVER};
            }}

            QLabel#activationStatus[state="loading"] {{
                color: {Colors.TEXT_SECONDARY};
                border-color: {Colors.INFO};
            }}
        """

    @classmethod
    def payment_stylesheet(cls):
        return cls.component_stylesheet() + f"""
            QWidget#pointPaymentScreen {{ background-color: {Colors.BACKGROUND_PRIMARY}; }}
            QWidget[paymentState="error"] {{
                background-color: {Colors.PAYMENT_ERROR_BACKGROUND};
            }}
            QWidget[paymentState="attention"] {{
                background-color: {Colors.PAYMENT_ATTENTION_BACKGROUND};
            }}
            QWidget[paymentState="success"] {{
                background-color: {Colors.PAYMENT_SUCCESS_BACKGROUND};
            }}
            QWidget[paymentState] QLabel {{
                color: {Colors.PAYMENT_STATE_FOREGROUND};
                background-color: transparent;
            }}
            QLabel#paymentStateTitle {{
                font-size: {FontSize.STATUS_TITLE}px;
                font-weight: {FontWeight.EXTRA_BOLD};
                letter-spacing: 1px;
            }}
            QLabel#paymentStateMessage {{
                font-size: {FontSize.H2}px;
                font-weight: {FontWeight.MEDIUM};
            }}
            QLabel#paymentStateSupporting {{
                color: {Colors.PAYMENT_STATE_FOREGROUND};
                font-size: 24px;
                font-weight: {FontWeight.MEDIUM};
            }}
            QLabel#paymentStateTotal {{
                color: {Colors.PAYMENT_STATE_FOREGROUND};
                font-size: {FontSize.DISPLAY}px;
                font-weight: {FontWeight.EXTRA_BOLD};
            }}
            QWidget[paymentState] QPushButton[variant="statePrimary"] {{
                min-height: {TouchSize.PRIMARY_BUTTON}px;
                background-color: {Colors.PAYMENT_STATE_FOREGROUND};
                color: {Colors.BACKGROUND_SECONDARY};
                border: 2px solid {Colors.PAYMENT_STATE_FOREGROUND};
                font-size: {FontSize.H3}px;
                font-weight: {FontWeight.EXTRA_BOLD};
            }}
            QWidget[paymentState] QPushButton[variant="statePrimary"]:pressed {{
                background-color: {Colors.SURFACE_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
            }}
            QWidget[paymentState] QPushButton[variant="stateSecondary"] {{
                min-height: {TouchSize.SECONDARY_BUTTON}px;
                background-color: {Colors.PAYMENT_ACTION_SECONDARY};
                color: {Colors.PAYMENT_STATE_FOREGROUND};
                border: 2px solid {Colors.PAYMENT_STATE_FOREGROUND};
            }}
            QWidget[paymentState] QPushButton[variant="stateSecondary"]:pressed {{
                background-color: {Colors.BACKGROUND_SECONDARY};
            }}
            QWidget#paymentLoadingPage {{
                background-color: {Colors.BACKGROUND_PRIMARY};
            }}
            QLabel#paymentTitle {{
                color: {Colors.TEXT_PRIMARY}; font-size: 36px;
                font-weight: {FontWeight.BOLD}; letter-spacing: 2px;
            }}
            QLabel#paymentLoading {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.LOADING_MESSAGE}px;
                font-weight: {FontWeight.MEDIUM};
            }}
            QLabel#paymentLoading[state="error"] {{ color: {Colors.ERROR}; }}
            QLabel#paymentInstructions {{
                color: {Colors.TEXT_SECONDARY}; font-size: 24px;
            }}
        """

    @classmethod
    def confirmation_stylesheet(cls):
        return cls.payment_stylesheet() + f"""
            QLabel#postPaymentNoticeTitle {{
                color: {Colors.PAYMENT_STATE_FOREGROUND};
                font-size: {FontSize.H1}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel#postPaymentNoticeMessage {{
                color: {Colors.PAYMENT_STATE_FOREGROUND};
                font-size: {FontSize.BODY}px;
            }}
        """
