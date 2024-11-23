import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QFileDialog,
    QHBoxLayout, QTreeWidget, QTreeWidgetItem, QSplitter, QPushButton
)
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt, pyqtSignal
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Metadata Viewer")
        self.setMinimumSize(900, 600)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        self.metadata = None

        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        self.splitter = splitter

        self.drop_area = DropArea()
        splitter.addWidget(self.drop_area)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

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
        right_layout.addWidget(self.metadata_display)

        self.export_button = QPushButton("Export to JSON")
        self.export_button.setStyleSheet("background-color: #7A4E98; color: #ffffff;")
        self.export_button.clicked.connect(self.export_to_json)
        self.export_button.hide()
        right_layout.addWidget(self.export_button)

        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 0])

        self.drop_area.file_dropped.connect(self.display_metadata)

    def display_metadata(self, filename):
        parser = createParser(filename)
        self.metadata_display.clear()

        if not parser:
            root_item = QTreeWidgetItem(["Unable to parse file"])
            self.metadata_display.addTopLevelItem(root_item)
            self.metadata_display.show()
            self.splitter.setSizes([400, 300])
            return

        with parser:
            try:
                metadata = extractMetadata(parser)
            except Exception as err:
                root_item = QTreeWidgetItem([f"Metadata extraction error: {err}"])
                self.metadata_display.addTopLevelItem(root_item)
                self.metadata_display.show()
                self.splitter.setSizes([400, 300])
                return

        if not metadata:
            root_item = QTreeWidgetItem(["No metadata found."])
            self.metadata_display.addTopLevelItem(root_item)
            self.metadata_display.show()
            self.splitter.setSizes([400, 300])
            return

        data = metadata.exportDictionary(human=True)
        self.metadata = data
        device_info = {}
        device_keywords = [
            'make', 'model', 'device', 'manufacturer', 'camera',
            'phone', 'lens', 'serial', 'software'
        ]

        for category, items in data.items():
            for key, value in items.items():
                for keyword in device_keywords:
                    if keyword in key.lower():
                        device_info[key] = value

        if device_info:
            device_item = QTreeWidgetItem(["Device Information"])
            for key, value in device_info.items():
                child = QTreeWidgetItem([f"{key}: {value}"])
                device_item.addChild(child)

            phone_makes = [
                'Apple', 'Samsung', 'Huawei', 'Xiaomi', 'Google', 'OnePlus', 'Sony',
                'LG', 'Nokia', 'Motorola', 'HTC', 'Oppo', 'Vivo', 'Realme',
                'Lenovo', 'Asus', 'BlackBerry', 'ZTE', 'Alcatel', 'Meizu', 'Tecno'
            ]

            is_phone = False
            for make in phone_makes:
                for value in device_info.values():
                    if make.lower() in str(value).lower():
                        is_phone = True
                        break
                if is_phone:
                    break

            if is_phone:
                child = QTreeWidgetItem(["The device is a phone."])
                device_item.addChild(child)
            else:
                child = QTreeWidgetItem(["The device is not identified as a phone."])
                device_item.addChild(child)
            self.metadata_display.addTopLevelItem(device_item)
        else:
            device_item = QTreeWidgetItem(["No device information found in metadata."])
            self.metadata_display.addTopLevelItem(device_item)

        gps_info = {}

        gps_keywords = ['gps', 'latitude', 'longitude', 'altitude', 'location']

        for category, items in data.items():
            if any(keyword in category.lower() for keyword in gps_keywords):
                gps_info.update(items)
            else:
                for key, value in items.items():
                    if any(keyword in key.lower() for keyword in gps_keywords):
                        gps_info[key] = value

        if gps_info:
            gps_item = QTreeWidgetItem(["GPS Information"])
            for key, value in gps_info.items():
                child = QTreeWidgetItem([f"{key}: {value}"])
                gps_item.addChild(child)
            self.metadata_display.addTopLevelItem(gps_item)
        else:
            gps_item = QTreeWidgetItem(["No GPS information found in metadata."])
            self.metadata_display.addTopLevelItem(gps_item)

        datetime_info = {}

        datetime_keywords = ['date', 'time']

        for category, items in data.items():
            for key, value in items.items():
                for keyword in datetime_keywords:
                    if keyword in key.lower():
                        datetime_info[key] = value

        if datetime_info:
            datetime_item = QTreeWidgetItem(["Date/Time Information"])
            for key, value in datetime_info.items():
                child = QTreeWidgetItem([f"{key}: {value}"])
                datetime_item.addChild(child)
            self.metadata_display.addTopLevelItem(datetime_item)
        else:
            datetime_item = QTreeWidgetItem(["No date/time information found in metadata."])
            self.metadata_display.addTopLevelItem(datetime_item)

        all_metadata_item = QTreeWidgetItem(["All Metadata"])
        for category, items in data.items():
            category_item = QTreeWidgetItem([category])
            for key, value in items.items():
                child = QTreeWidgetItem([f"{key}: {value}"])
                category_item.addChild(child)
            all_metadata_item.addChild(category_item)
        self.metadata_display.addTopLevelItem(all_metadata_item)

        self.metadata_display.expandAll()
        self.metadata_display.show()
        self.export_button.show()
        self.splitter.setSizes([400, 300])

    def export_to_json(self):
        if self.metadata:
            options = QFileDialog.Options()
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save JSON", "", "JSON Files (*.json)", options=options)
            if filename:
                with open(filename, 'w', encoding='utf-8') as file:
                    json.dump(self.metadata, file, indent=4)

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
