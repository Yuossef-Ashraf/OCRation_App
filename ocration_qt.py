# ================================
# OCRATION - Modern GUI (PyQt6)
# ================================
import sys
import os
import cv2
import logging
from typing import List, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QFileDialog,
    QTextEdit, QLineEdit, QComboBox, QListWidget, QGroupBox,
    QMessageBox, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel,
    QProgressBar, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QAction

# Backend
from image_ocr import extract_text_from_path
from llm_model import organize_entities, summarize_text, is_llm_available

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# ================================
# STYLESHEET (Modern Dark Theme)
# ================================
DARK_THEME_CSS = """
QMainWindow {
    background-color: #0f172a;
}
QWidget {
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    font-size: 14px;
}
QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 1.2em;
    font-weight: bold;
    color: #94a3b8;
    background-color: #1e293b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
}
QPushButton {
    background-color: #6366f1;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #4f46e5;
}
QPushButton:pressed {
    background-color: #4338ca;
}
QPushButton#SecondaryBtn {
    background-color: #334155;
    border: 1px solid #475569;
}
QPushButton#SecondaryBtn:hover {
    background-color: #475569;
}
QPushButton#DestructiveBtn {
    background-color: #ef4444;
}
QPushButton#DestructiveBtn:hover {
    background-color: #dc2626;
}
QLineEdit, QTextEdit, QListWidget, QComboBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px;
    color: #f8fafc;
}
QLineEdit:focus, QTextEdit:focus, QListWidget:focus {
    border: 1px solid #6366f1;
}
QListWidget::item:selected {
    background-color: #334155;
    border-radius: 4px;
}
QLabel#HeaderTitle {
    font-size: 24px;
    font-weight: bold;
    color: #6366f1;
}
QLabel#SubHeader {
    color: #94a3b8;
    font-size: 13px;
}
"""

# ================================
# WORKER THREAD (Non-blocking UI)
# ================================
class OCRWorker(QThread):
    finished = pyqtSignal(str, str)  # result_text, error_message
    progress = pyqtSignal(str)

    def __init__(self, files: List[str], ocr_mode: str, use_llm: bool, summarize: bool):
        super().__init__()
        self.files = files
        self.ocr_mode = ocr_mode
        self.use_llm = use_llm
        self.summarize = summarize

    def run(self):
        full_text = []
        try:
            for idx, path in enumerate(self.files):
                self.progress.emit(f"Processing ({idx+1}/{len(self.files)}): {os.path.basename(path)}...")
                
                # Call Improved OCR Engine
                result = extract_text_from_path(path, mode=self.ocr_mode)
                
                if result.get("error"):
                    full_text.append(f"--- ERROR: {os.path.basename(path)} ---\n{result['error']}\n")
                    continue
                
                text = result.get("text", "").strip()
                if text:
                    full_text.append(f"--- {os.path.basename(path)} ---\n{text}\n")
            
            combined = "\n".join(full_text)

            # LLM Post-processing
            if combined and self.use_llm and is_llm_available():
                self.progress.emit("Improving text with AI...")
                combined = improve_text(combined)
                
                if self.summarize:
                    self.progress.emit("Summarizing...")
                    summary = summarize_text(combined)
                    combined = f"--- SUMMARY ---\n{summary}\n\n--- ORIGINAL TEXT ---\n{combined}"

            self.finished.emit(combined, "")
            
        except Exception as e:
            logging.exception("Worker Error")
            self.finished.emit("", str(e))


# ================================
# MAIN WINDOW
# ================================
class OCRATION(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCRATION - Modern OCR & Text Processing")
        self.resize(1200, 800)
        self.setStyleSheet(DARK_THEME_CSS)

        self.selected_files = []
        self.is_processing = False

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Grid Layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ====================
        # LEFT PANEL (Controls)
        # ====================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        left_panel.setFixedWidth(380)

        # Header
        header_layout = QHBoxLayout()
        logo_label = QLabel("🤖 OCRATION")
        logo_label.setObjectName("HeaderTitle")
        header_layout.addWidget(logo_label)
        header_layout.addStretch()
        left_layout.addLayout(header_layout)

        left_layout.addWidget(QLabel("Modern AI-Powered Text Extraction", objectName="SubHeader"))

        # Camera Section
        cam_group = QGroupBox("Camera Index")
        cam_layout = QVBoxLayout()
        self.cam_combo = QComboBox()
        self.cam_combo.addItems(["0 - Auto Detect", "1", "2"])
        cam_layout.addWidget(self.cam_combo)
        cam_group.setLayout(cam_layout)
        left_layout.addWidget(cam_group)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_select = QPushButton("📂 Select Files")
        self.btn_select.setMinimumHeight(45)
        self.btn_select.clicked.connect(self.select_files)
        
        self.btn_capture = QPushButton("📷 Capture")
        self.btn_capture.setMinimumHeight(45)
        self.btn_capture.clicked.connect(self.capture_image)
        
        btn_layout.addWidget(self.btn_select)
        btn_layout.addWidget(self.btn_capture)
        left_layout.addLayout(btn_layout)

        # File List
        list_group = QGroupBox("Selected Files")
        list_layout = QVBoxLayout()
        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        list_layout.addWidget(self.file_list_widget)
        
        # Select All / Remove
        file_actions = QHBoxLayout()
        self.btn_clear_list = QPushButton("Clear List")
        self.btn_clear_list.setObjectName("SecondaryBtn")
        self.btn_clear_list.clicked.connect(self.clear_files)
        file_actions.addWidget(self.btn_clear_list)
        list_layout.addLayout(file_actions)
        
        list_group.setLayout(list_layout)
        left_layout.addWidget(list_group)

        # Processing Settings
        settings_group = QGroupBox("⚙ Processing Settings")
        settings_layout = QVBoxLayout()
        
        # Mode
        mode_layout = QHBoxLayout()
        mode_label = QLabel("OCR Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Standard (Fast)", "High (Handwriting/Tables)", "Auto (Smart)"])
        self.mode_combo.setCurrentIndex(2) # Default Auto
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo)
        settings_layout.addLayout(mode_layout)

        # Options
        self.chk_llm_improve = QCheckBox("Enhance with AI (Fix errors)")
        self.chk_llm_improve.setChecked(True)
        self.chk_summarize = QCheckBox("Summarize Content")
        
        settings_layout.addWidget(self.chk_llm_improve)
        settings_layout.addWidget(self.chk_summarize)

        # Process Buttons
        proc_btn_layout = QHBoxLayout()
        self.btn_process = QPushButton("▶ Process")
        self.btn_process.setMinimumHeight(45)
        self.btn_process.clicked.connect(self.start_processing)
        
        self.btn_clear_all = QPushButton("🗑 Reset")
        self.btn_clear_all.setObjectName("DestructiveBtn")
        self.btn_clear_all.setMinimumHeight(45)
        self.btn_clear_all.clicked.connect(self.reset_all)
        
        proc_btn_layout.addWidget(self.btn_process)
        proc_btn_layout.addWidget(self.btn_clear_all)
        settings_layout.addLayout(proc_btn_layout)

        settings_group.setLayout(settings_layout)
        left_layout.addWidget(settings_group)
        
        # Status Bar / Progress within panel
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #94a3b8; font-style: italic;")
        left_layout.addWidget(self.status_label)

        left_layout.addStretch() # Push everything up

        # ====================
        # RIGHT PANEL (Output)
        # ====================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15)

        # Search Bar
        search_group = QGroupBox("🔍 Search")
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find inside text...")
        self.search_input.returnPressed.connect(self.search_text)
        
        self.btn_search = QPushButton("Go")
        self.btn_search.setFixedWidth(50)
        self.btn_search.clicked.connect(self.search_text)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.btn_search)
        search_group.setLayout(search_layout)
        right_layout.addWidget(search_group)

        # Output Area
        out_group = QGroupBox("📄 Extracted Text (Editable)")
        out_layout = QVBoxLayout()
        self.text_output = QTextEdit()
        self.text_output.setPlaceholderText("Results will appear here...")
        self.text_output.setStyleSheet("font-family: Consolas, monospace; font-size: 13px; line-height: 1.4;")
        out_layout.addWidget(self.text_output)
        
        # Save Controls
        save_layout = QHBoxLayout()
        self.file_name_input = QLineEdit()
        self.file_name_input.setPlaceholderText("filename")
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["TXT", "JSON"])
        self.format_combo.setFixedWidth(80)
        
        self.btn_save = QPushButton("💾 Save")
        self.btn_save.clicked.connect(self.save_file)
        
        save_layout.addWidget(self.btn_save)
        save_layout.addWidget(self.format_combo)
        save_layout.addWidget(self.file_name_input)
        
        out_layout.addLayout(save_layout)
        out_group.setLayout(out_layout)
        right_layout.addWidget(out_group)

        # Add Panels to Main Layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

    # ====================
    # LOGIC
    # ====================
    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", "", "Images (*.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        if files:
            self.selected_files.extend(files)
            self.refresh_file_list()

    def refresh_file_list(self):
        self.file_list_widget.clear()
        for f in self.selected_files:
            self.file_list_widget.addItem(os.path.basename(f))
        
        self.status_label.setText(f"{len(self.selected_files)} files selected.")

    def clear_files(self):
        self.selected_files = []
        self.refresh_file_list()

    def capture_image(self):
        try:
            cam_idx = 0
            if self.cam_combo.currentIndex() > 0:
                cam_idx = int(self.cam_combo.currentText())
            
            cap = cv2.VideoCapture(cam_idx)
            if not cap.isOpened():
                QMessageBox.warning(self, "Camera Error", "Could not open camera.")
                return
            
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                path = os.path.abspath("captured_image.png")
                cv2.imwrite(path, frame)
                self.selected_files.append(path)
                self.refresh_file_list()
                QMessageBox.information(self, "Success", "Image captured successfully!")
            else:
                QMessageBox.warning(self, "Capture Failed", "Could not read frame.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def start_processing(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No Files", "Please select or capture images first.")
            return

        if self.is_processing:
            return

        self.is_processing = True
        self.btn_process.setText("Processing...")
        self.btn_process.setEnabled(False)
        self.text_output.clear()

        # Parse Settings
        mode_map = {0: "standard", 1: "high", 2: "auto"}
        ocr_mode = mode_map.get(self.mode_combo.currentIndex(), "standard")
        
        # Start Worker
        self.worker = OCRWorker(
            self.selected_files,
            ocr_mode=ocr_mode,
            use_llm=self.chk_llm_improve.isChecked(),
            summarize=self.chk_summarize.isChecked()
        )
        self.worker.progress.connect(self.update_status)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.start()

    def update_status(self, msg):
        self.status_label.setText(msg)

    def on_processing_finished(self, text, error):
        self.is_processing = False
        self.btn_process.setText("▶ Process")
        self.btn_process.setEnabled(True)
        
        if error:
            QMessageBox.critical(self, "Processing Error", error)
            self.status_label.setText("Error occurred.")
        else:
            self.text_output.setPlainText(text)
            self.status_label.setText("Processing complete.")

    def reset_all(self):
        self.clear_files()
        self.text_output.clear()
        self.search_input.clear()
        self.status_label.setText("Ready")

    def search_text(self):
        query = self.search_input.text()
        if not query:
            return
            
        cursor = self.text_output.textCursor()
        doc = self.text_output.document()
        
        # Simple highlight logic
        cursor.setPosition(0) 
        self.text_output.setTextCursor(cursor)
        
        found = self.text_output.find(query)
        if not found:
            self.status_label.setText(f"'{query}' not found.")
        else:
            self.status_label.setText(f"Found '{query}'.")

    def save_file(self):
        text = self.text_output.toPlainText()
        if not text:
            QMessageBox.warning(self, "Empty", "No text to save.")
            return

        fname = self.file_name_input.text().strip() or "output"
        fmt = self.format_combo.currentText().lower()
        
        path, _ = QFileDialog.getSaveFileName(self, "Save File", f"{fname}.{fmt}")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    if fmt == "json":
                        import json
                        json.dump({"content": text}, f, indent=2, ensure_ascii=False)
                    else:
                        f.write(text)
                QMessageBox.information(self, "Saved", f"File saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Global Font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = OCRATION()
    window.show()
    sys.exit(app.exec())
