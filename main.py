import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import QTimer
from bleak import discover
from asyncio import new_event_loop, set_event_loop
from time import sleep, time_ns
from binascii import hexlify
from json import dumps
from datetime import datetime
import json
import asyncio
from PyQt5.QtWidgets import QHBoxLayout, QSpacerItem, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

# Configure update duration (update after n seconds)
UPDATE_DURATION = 1
MIN_RSSI = -60
AIRPODS_MANUFACTURER = 76
AIRPODS_DATA_LENGTH = 54
RECENT_BEACONS_MAX_T_NS = 10000000000  # 10 Seconds

recent_beacons = []

def get_best_result(device):
    recent_beacons.append({
        "time": time_ns(),
        "device": device
    })
    strongest_beacon = None
    i = 0
    while i < len(recent_beacons):
        if(time_ns() - recent_beacons[i]["time"] > RECENT_BEACONS_MAX_T_NS):
            recent_beacons.pop(i)
            continue
        if strongest_beacon is None or strongest_beacon.rssi < recent_beacons[i]["device"].rssi:
            strongest_beacon = recent_beacons[i]["device"]
        i += 1

    if strongest_beacon is not None and strongest_beacon.address == device.address:
        strongest_beacon = device

    return strongest_beacon

# Getting data with hex format
async def get_device():
    # Scanning for devices
    devices = await discover()
    for d in devices:
        # Checking for AirPods
        d = get_best_result(d)
        if d.rssi >= MIN_RSSI and AIRPODS_MANUFACTURER in d.metadata['manufacturer_data']:
            data_hex = hexlify(bytearray(d.metadata['manufacturer_data'][AIRPODS_MANUFACTURER]))
            data_length = len(hexlify(bytearray(d.metadata['manufacturer_data'][AIRPODS_MANUFACTURER])))
            if data_length == AIRPODS_DATA_LENGTH:
                return data_hex
    return False

# Getting data from hex string and converting it to dict(json)
async def get_data():
    raw = await get_device()

    # Return blank data if airpods not found
    if not raw:
        return dict(status=0, model="AirPods not found")

    flip: bool = is_flipped(raw)

    # On 7th position we can get AirPods model, gen1, gen2, Pro or Max
    if chr(raw[7]) == 'e':
        model = "AirPodsPro"
    elif chr(raw[7]) == '3':
        model = "AirPods3"
    elif chr(raw[7]) == 'f':
        model = "AirPods2"
    elif chr(raw[7]) == '2':
        model = "AirPods1"
    elif chr(raw[7]) == 'a':
        model = "AirPodsMax"
    else:
        model = "unknown"

    # Checking left AirPod for availability and storing charge in variable
    status_tmp = int("" + chr(raw[12 if flip else 13]), 16)
    left_status = (100 if status_tmp == 10 else (status_tmp * 10 + 5 if status_tmp <= 10 else -1))

    # Checking right AirPod for availability and storing charge in variable
    status_tmp = int("" + chr(raw[13 if flip else 12]), 16)
    right_status = (100 if status_tmp == 10 else (status_tmp * 10 + 5 if status_tmp <= 10 else -1))

    # Checking AirPods case for availability and storing charge in variable
    status_tmp = int("" + chr(raw[15]), 16)
    case_status = (100 if status_tmp == 10 else (status_tmp * 10 + 5 if status_tmp <= 10 else -1))

    # On 14th position we can get charge status of AirPods
    charging_status = int("" + chr(raw[14]), 16)
    charging_left: bool = (charging_status & (0b00000010 if flip else 0b00000001)) != 0
    charging_right: bool = (charging_status & (0b00000001 if flip else 0b00000010)) != 0
    charging_case: bool = (charging_status & 0b00000100) != 0

    # Return result info in dict format
    return dict(
        status=1,
        charge=dict(
            left=left_status,
            right=right_status,
            case=case_status
        ),
        charging_left=charging_left,
        charging_right=charging_right,
        charging_case=charging_case,
        model=model,
        date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        raw=raw.decode("utf-8")
    )

# Return if left and right is flipped in the data
def is_flipped(raw):
    return (int("" + chr(raw[10]), 16) & 0x02) == 0

async def run():
    output_file = "output_json.txt"

    while True:
        data = await get_data()

        if data["status"] == 1:
            json_data = dumps(data)
            with open(output_file, "w") as f:
                f.write(json_data + "\n")
        else:
            json_data = json.dumps(data)

        yield json_data
        sleep(UPDATE_DURATION)

class FileWatcherApp(QWidget):
    def __init__(self, app):
        super().__init__()

        self.setWindowTitle("AIRJOOOS")
        self.setGeometry(100, 100, 600, 400)  # (x, y, width, height)

        main_layout = QVBoxLayout()

        # Horizontal layout for AirPods images
        airpods_layout = QHBoxLayout()
        airpods_layout.addSpacerItem(QSpacerItem(167, 5, QSizePolicy.Minimum, QSizePolicy.Minimum))
        # Create labels for displaying left and right AirPods images
        l_airpod_label = QLabel(self)
        l_airpod_pixmap = QPixmap("/home/arnav/Downloads/AirStatus/pictures/l_airpod_removebg.png")
        l_airpod_label.setPixmap(l_airpod_pixmap)
        l_airpod_label.resize(l_airpod_pixmap.width(), l_airpod_pixmap.height())
        airpods_layout.addWidget(l_airpod_label)

        # Adding space between the images
        airpods_layout.addSpacerItem(QSpacerItem(10, 5, QSizePolicy.Minimum, QSizePolicy.Minimum))

        r_airpod_label = QLabel(self)
        r_airpod_pixmap = QPixmap("/home/arnav/Downloads/AirStatus/pictures/r_airpod_removebg.png")
        r_airpod_label.setPixmap(r_airpod_pixmap)
        r_airpod_label.resize(r_airpod_pixmap.width(), r_airpod_pixmap.height())
        airpods_layout.addWidget(r_airpod_label)

        main_layout.addLayout(airpods_layout)

        # Adding a stretchable space to ensure the case image is centered
        main_layout.addSpacerItem(QSpacerItem(20, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))

        # Create label for displaying case image
        case_label = QLabel(self)
        case_pixmap = QPixmap("/home/arnav/Downloads/AirStatus/pictures/case_open_removebg.png")
        case_label.setPixmap(case_pixmap)
        case_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(case_label, alignment=Qt.AlignCenter)

        # Adding a stretchable space to push the text to the bottom
        main_layout.addSpacerItem(QSpacerItem(20, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))

        # Create a label for displaying the file content
        self.file_label = QLabel(self)
        self.file_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.file_label)

        self.setLayout(main_layout)

        # Create a QTimer to check the file content periodically
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_file_content)
        self.timer.start(1000)  # Update every 1000 milliseconds (1 second)

    def update_file_content(self):
        try:
            with open("output_json.txt", "r") as f:
                content = f.read()
                data = json.loads(content)

                # Extract information from the JSON data
                charge_info = data.get("charge", {})
                charging_left = data.get("charging_left", False)
                charging_right = data.get("charging_right", False)
                charging_case = data.get("charging_case", False)
                model = data.get("model", "Unknown")

                # Construct the display text
                text = (
                    f"Charge: {charge_info}\n"
                    f"Charging Left: {charging_left}\n"
                    f"Charging Right: {charging_right}\n"
                    f"Charging Case: {charging_case}\n"
                    f"Model: {model}"
                )

                # Update the file_label text
                self.file_label.setText(text)
        except FileNotFoundError:
            self.file_label.setText("File not found.")
        except json.JSONDecodeError:
            self.file_label.setText("Error decoding JSON.")

async def main():
    app = QApplication(sys.argv)
    window = FileWatcherApp(app)

    async for item in run():
        print("SUCCESS FROM INSIDE MAIN FUNCTION", item)
        await asyncio.sleep(0.1)  # Short delay to allow UI to update
        window.show()
        sys.exit(app.exec_())

if __name__ == '__main__':
    loop = new_event_loop()
    set_event_loop(loop)
    loop.run_until_complete(main())
