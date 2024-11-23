import sys
import json
import re
import os
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QFileDialog,
    QHBoxLayout, QTreeWidget, QTreeWidgetItem, QSplitter, QPushButton
)
from PyQt5.QtGui import QPalette, QColor, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Metadata Viewer")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        self.metadata = None
        self.address = None
        self.current_image_filename = None
        self.map_label = None
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        self.splitter = splitter

        self.drop_area = DropArea()
        splitter.addWidget(self.drop_area)

        right_panel = QWidget()
        self.right_layout = QVBoxLayout(right_panel)

        self.metadata_display = QTreeWidget()
        self.metadata_display.setHeaderHidden(True)
        self.metadata_display.setStyleSheet("""
            QTreeWidget {
                background-color: #252526;
                color: #d4d4d4;
                font-size: 14px;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background-color: #7A4E98;
                color: #ffffff;
            }
        """)
        self.metadata_display.hide()
        self.right_layout.addWidget(self.metadata_display)

        self.export_button = QPushButton("Export to JSON")
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #7A4E98; 
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #5F3B78;
            }
        """)
        self.export_button.clicked.connect(self.export_to_json)
        self.export_button.hide()
        self.right_layout.addWidget(self.export_button)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 0])

        self.drop_area.file_dropped.connect(self.display_metadata)

    def parse_lat_lon(self, coord_str):
        coord_str = coord_str.strip()
        direction = coord_str[-1] if coord_str[-1] in 'NSEW' else None
        coord_str = coord_str[:-1].strip() if direction else coord_str
        try:
            value = float(coord_str)
        except ValueError:
            match = re.match(r'(\d+)[°\s]+(\d+)[\'\s]+([\d\.]+)["\s]*', coord_str)
            if not match:
                return None
            degrees, minutes, seconds = match.groups()
            value = float(degrees) + float(minutes)/60 + float(seconds)/3600
        if direction in ['S', 'W']:
            value = -value
        return value

    def extract_info(self, data, keywords):
        info = {}
        for category, items in data.items():
            if any(keyword in category.lower() for keyword in keywords):
                info.update(items)
            else:
                for key, value in items.items():
                    if any(keyword in key.lower() for keyword in keywords):
                        info[key] = value
        return info

    def extract_gps_info(self, data):
        gps_keywords = ['gps', 'latitude', 'longitude', 'altitude', 'location']
        gps_info = self.extract_info(data, gps_keywords)
        latitude_str = gps_info.get('GPS Latitude') or gps_info.get('Latitude')
        longitude_str = gps_info.get('GPS Longitude') or gps_info.get('Longitude')
        if not (latitude_str and longitude_str) and 'GPS Position' in gps_info:
            position_str = gps_info['GPS Position']
            parts = position_str.replace(',', ' ').split()
            if len(parts) >= 4:
                latitude_str = parts[0] + parts[1]
                longitude_str = parts[2] + parts[3]
        latitude = self.parse_lat_lon(latitude_str) if latitude_str else None
        longitude = self.parse_lat_lon(longitude_str) if longitude_str else None
        return gps_info, latitude, longitude

    def reverse_geocode(self, latitude, longitude):
        try:
            geocode_url = f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=jsonv2"
            headers = {'User-Agent': 'MetadataViewer/1.0'}
            geocode_response = requests.get(geocode_url, headers=headers)
            if geocode_response.status_code == 200:
                geocode_data = geocode_response.json()
                address = geocode_data.get('display_name', 'Address not found.')
            else:
                address = 'Address not found (HTTP error).'
        except Exception as e:
            address = f'Address not found (Exception: {e})'
        return address

    def get_map_image(self, latitude, longitude):
        map_url = (
            f"https://static-maps.yandex.ru/1.x/?ll={longitude},{latitude}"
            f"&size=550,200&z=10&l=map&pt={longitude},{latitude},pm2rdm&lang=en_US"
        )
        response = requests.get(map_url)
        if response.status_code == 200:
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            return pixmap
        return None

    def show_error(self, message):
        self.metadata_display.clear()
        self.metadata_display.addTopLevelItem(QTreeWidgetItem([message]))
        self.metadata_display.show()
        self.splitter.setSizes([400, 600])

    def add_info_to_tree(self, parent_item, info_dict):
        for key, value in info_dict.items():
            parent_item.addChild(QTreeWidgetItem([f"{key}: {value}"]))

    def build_metadata_tree(self, device_info, gps_info, datetime_info, data, address):
        if device_info:
            device_item = QTreeWidgetItem(["Device Information"])
            self.add_info_to_tree(device_item, device_info)
            phone_makes = [
                'Apple', 'Samsung', 'Huawei', 'Xiaomi', 'Google', 'OnePlus', 'Sony',
                'LG', 'Nokia', 'Motorola', 'HTC', 'Oppo', 'Vivo', 'Realme',
                'Lenovo', 'Asus', 'BlackBerry', 'ZTE', 'Alcatel', 'Meizu', 'Tecno'
            ]
            is_phone = any(
                make.lower() in str(value).lower()
                for make in phone_makes
                for value in device_info.values()
            )
            phone_item_text = "The device is a phone." if is_phone else "The device is not identified as a phone."
            device_item.addChild(QTreeWidgetItem([phone_item_text]))
            self.metadata_display.addTopLevelItem(device_item)
        else:
            self.metadata_display.addTopLevelItem(QTreeWidgetItem(["No device information found in metadata."]))

        if gps_info:
            gps_item = QTreeWidgetItem(["GPS Information"])
            self.add_info_to_tree(gps_item, gps_info)
            if address:
                gps_item.addChild(QTreeWidgetItem([f"Address: {address}"]))
            self.metadata_display.addTopLevelItem(gps_item)
        else:
            self.metadata_display.addTopLevelItem(QTreeWidgetItem(["No GPS information found in metadata."]))

        if datetime_info:
            datetime_item = QTreeWidgetItem(["Date/Time Information"])
            self.add_info_to_tree(datetime_item, datetime_info)
            self.metadata_display.addTopLevelItem(datetime_item)
        else:
            self.metadata_display.addTopLevelItem(QTreeWidgetItem(["No date/time information found in metadata."]))

        all_metadata_item = QTreeWidgetItem(["All Metadata"])
        for category, items in data.items():
            category_item = QTreeWidgetItem([category])
            self.add_info_to_tree(category_item, items)
            all_metadata_item.addChild(category_item)
        self.metadata_display.addTopLevelItem(all_metadata_item)

    def display_metadata(self, filename):
        parser = createParser(filename)
        self.metadata_display.clear()
        if self.map_label:
            self.right_layout.removeWidget(self.map_label)
            self.map_label.deleteLater()
            self.map_label = None

        if not parser:
            self.show_error("Unable to parse file")
            return

        with parser:
            try:
                metadata = extractMetadata(parser)
            except Exception as err:
                self.show_error(f"Metadata extraction error: {err}")
                return

        if not metadata:
            self.show_error("No metadata found.")
            return

        data = metadata.exportDictionary(human=True)
        self.metadata = data

        device_keywords = ['make', 'model', 'device', 'manufacturer', 'camera', 'phone', 'lens', 'serial', 'software']
        datetime_keywords = ['date', 'time']

        device_info = self.extract_info(data, device_keywords)
        datetime_info = self.extract_info(data, datetime_keywords)
        gps_info, latitude, longitude = self.extract_gps_info(data)

        self.address = self.reverse_geocode(latitude, longitude) if latitude and longitude else None

        if latitude and longitude:
            map_pixmap = self.get_map_image(latitude, longitude)
            if map_pixmap:
                self.map_label = QLabel()
                self.map_label.setPixmap(map_pixmap)
                self.right_layout.insertWidget(0, self.map_label)
                self.map_label.show()

        self.build_metadata_tree(device_info, gps_info, datetime_info, data, self.address)

        self.metadata_display.expandAll()
        self.metadata_display.show()
        self.export_button.show()
        self.splitter.setSizes([400, 600])

        self.current_image_filename = filename

    def export_to_json(self):
        if self.metadata:
            options = QFileDialog.Options()
            if self.current_image_filename:
                base_name = os.path.splitext(os.path.basename(self.current_image_filename))[0]
                default_filename = f"{base_name}.json"
            else:
                default_filename = "metadata.json"

            filename, _ = QFileDialog.getSaveFileName(
                self, "Save JSON", default_filename, "JSON Files (*.json)", options=options)
            if filename:
                export_data = self.metadata.copy()
                if self.address:
                    export_data['Address'] = self.address
                try:
                    with open(filename, 'w', encoding='utf-8') as file:
                        json.dump(export_data, file, indent=4)
                except Exception as e:
                    self.show_error(f"Failed to export JSON: {e}")

class DropArea(QLabel):
    file_dropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #555;
                border-radius: 5px;
                background-color: #2d2d30;
                color: #aaaaaa;
                font-size: 18px;
            }
            QLabel:hover {
                border-color: #b298dc;
            }
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Drag and drop an image here\nor click to browse")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
            urls = event.mimeData().urls()
            if urls:
                filepath = urls[0].toLocalFile()
                self.file_dropped.emit(filepath)
        else:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            options = QFileDialog.Options()
            options |= QFileDialog.ReadOnly
            filename, _ = QFileDialog.getOpenFileName(
                self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)", options=options)
            if filename:
                self.file_dropped.emit(filename)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(45, 45, 48))
    palette.setColor(QPalette.AlternateBase, QColor(30, 30, 30))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(45, 45, 48))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Highlight, QColor("#7A4E98"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
