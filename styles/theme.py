from styles.tokens import (
    Colors,
    FontFamily,
    FontSize,
    FontWeight,
    Radius,
    Spacing,
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
                min-height: 24px;
                padding: {Spacing.MD}px {Spacing.XL}px;
                border-radius: {Radius.BUTTON}px;
                border: 1px solid transparent;
                font-size: {FontSize.BUTTON}px;
                font-weight: {FontWeight.BOLD};
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
                min-height: 24px;
                padding: {Spacing.MD}px {Spacing.LG}px;
                background-color: {Colors.INPUT_BACKGROUND};
                color: {Colors.INPUT_TEXT};
                placeholder-text-color: {Colors.INPUT_PLACEHOLDER};
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
                font-size: {FontSize.LABEL}px;
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
                font-size: {FontSize.CAPTION}px;
            }}

            QLabel#activationStatus {{
                color: {Colors.INFO};
                background-color: {Colors.SURFACE_ELEVATED};
                border: 1px solid {Colors.PRIMARY};
                border-radius: {Radius.INPUT}px;
                font-size: {FontSize.SMALL}px;
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
            QFrame#paymentCard {{
                max-width: 820px;
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
            }}
            QLabel#paymentTitle {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.H1}px;
                font-weight: {FontWeight.BOLD}; letter-spacing: 2px;
            }}
            QLabel#paymentTotal {{
                color: {Colors.SUCCESS}; font-size: {FontSize.DISPLAY}px;
                font-weight: {FontWeight.BOLD};
            }}
            QLabel#paymentLoading {{
                color: {Colors.INFO}; font-size: {FontSize.H3}px;
                font-weight: {FontWeight.MEDIUM};
            }}
            QLabel#paymentLoading[state="error"] {{ color: {Colors.ERROR}; }}
            QLabel#paymentInstructions {{
                color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.BODY}px;
                padding: {Spacing.LG}px;
            }}
            QLabel#paymentTimer {{
                color: {Colors.WARNING}; font-size: {FontSize.H2}px;
                font-weight: {FontWeight.BOLD};
            }}
        """

    @classmethod
    def confirmation_stylesheet(cls):
        return cls.component_stylesheet() + f"""
            QWidget#confirmationScreen {{ background-color: {Colors.BACKGROUND_PRIMARY}; }}
            QFrame#confirmationCard {{
                background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER};
                border-radius: {Radius.MODAL}px;
            }}
            QLabel#confirmationIcon {{ color: {Colors.SUCCESS}; font-size: 96px; }}
            QLabel#confirmationTitle {{
                color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.H1}px;
                font-weight: {FontWeight.BOLD}; letter-spacing: 2px;
            }}
            QLabel#confirmationSubtitle {{ color: {Colors.TEXT_SECONDARY}; font-size: {FontSize.BODY}px; }}
            QLabel#confirmationTimer {{ color: {Colors.INFO}; font-size: {FontSize.SMALL}px; }}
            QProgressBar {{ background-color: {Colors.DISABLED_BACKGROUND}; border: none; max-height: 6px; }}
            QProgressBar::chunk {{ background-color: {Colors.SUCCESS}; }}
        """
