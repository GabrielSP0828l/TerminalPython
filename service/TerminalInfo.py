import socket
import uuid
from pathlib import Path


class TerminalInfo:

    @staticmethod
    def get_serial_number():

        # Raspberry Pi
        caminhos = [
            "/sys/firmware/devicetree/base/serial-number",
            "/proc/device-tree/serial-number"
        ]

        for caminho in caminhos:

            try:

                if Path(caminho).exists():

                    serial = Path(
                        caminho
                    ).read_text().strip("\x00").strip()

                    if serial:
                        return serial

            except Exception:
                pass

        # Ubuntu / Debian / Linux em geral
        try:

            machine_id = Path(
                "/etc/machine-id"
            ).read_text().strip()

            if machine_id:
                return machine_id

        except Exception:
            pass

        return "UNKNOWN"
    @staticmethod
    def get_mac_address():

        mac = uuid.getnode()

        return ':'.join(
            f'{(mac >> ele) & 0xff:02x}'
            for ele in range(40, -1, -8)
        )

    @staticmethod
    def get_ip_address():

        s = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        try:

            s.connect(
                ("8.8.8.8", 80)
            )

            return s.getsockname()[0]

        except Exception:

            return "0.0.0.0"

        finally:

            s.close()

    @classmethod
    def to_dict(cls):

        return {
            "serialNumber": cls.get_serial_number(),
            "macAddress": cls.get_mac_address(),
            "ipAddress": cls.get_ip_address()
        }
