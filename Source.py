#!/usr/bin/env python3
"""
GForms Submission Nuker – PySide6 GUI
"""

import json
import os
import random
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ============================================================
# CONFIGURATION
# ============================================================

APP_NAME = "GForms Submission Nuker"
MAX_SUBMISSIONS_PER_RUN = 5000
MIN_DELAY = 0.5
MAX_DELAY = 60.0
DEFAULT_DELAY = 1.0


def get_config_path() -> Path:
    """
    Returns a responsible location for the config file.
    - Compiled (frozen): uses AppData (Windows) or ~/.config (Linux)
    - Normal script: next to the .py file
    """
    if getattr(sys, "frozen", False):
        # Running as a compiled executable
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            # Linux / macOS
            base = Path.home() / ".config"
        config_dir = base / "GFormsSubmissionNuker"
    else:
        # Running as a normal Python script
        config_dir = Path(__file__).parent

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "gforms_submission_nuker_config.json"


CONFIG_PATH = get_config_path()


# ============================================================
# WORKER
# ============================================================

class SubmissionWorker(QObject):
    progress = Signal(int, int)
    log = Signal(str)
    success = Signal(int, int)
    failure = Signal(int, str)
    finished = Signal(int, int, list)
    stopped = Signal()

    def __init__(self, form_url: str, entries: list, total: int, delay: float):
        super().__init__()
        self.form_url = form_url
        self.entries = entries
        self.total = total
        self.delay = delay
        self.running = True

    def stop(self):
        self.running = False

    def _randomize_entry(self, entry: dict) -> dict:
        result = {}
        for key, value in entry.items():
            if "|" in value:
                options = [v.strip() for v in value.split("|") if v.strip()]
                result[key] = random.choice(options) if options else value
            else:
                result[key] = value
        return result

    def run(self):
        successful = 0
        failed = 0
        failed_entries = []

        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": self.form_url.replace("/formResponse", "/viewform"),
        })

        self.log.emit(f"Total submissions: {self.total}")
        self.log.emit(f"Answer sets: {len(self.entries)}")
        if self.delay <= 0:
            self.log.emit("Delay: NONE (maximum speed)")
        else:
            self.log.emit(f"Delay: {self.delay:.2f} s between submissions")
        self.log.emit("Randomization: values containing '|' will be randomly chosen each time")

        for i in range(1, self.total + 1):
            if not self.running:
                self.log.emit("Stopped by user.")
                self.stopped.emit()
                break

            base_entry = self.entries[(i - 1) % len(self.entries)]
            data = self._randomize_entry(base_entry)

            try:
                response = session.post(
                    self.form_url,
                    data=data,
                    timeout=20,
                    allow_redirects=True,
                )
                status = response.status_code

                if 200 <= status < 400:
                    successful += 1
                    self.success.emit(i, status)
                    self.log.emit(f"SUCCESS | {i}/{self.total} | HTTP {status}")
                else:
                    failed += 1
                    failed_entries.append(base_entry)
                    self.failure.emit(i, f"HTTP {status}")
                    self.log.emit(f"FAILED  | {i}/{self.total} | HTTP {status}")

            except requests.RequestException as error:
                failed += 1
                failed_entries.append(base_entry)
                self.failure.emit(i, str(error))
                self.log.emit(f"ERROR   | {i}/{self.total} | {error}")

            self.progress.emit(i, self.total)

            if self.delay > 0 and i < self.total and self.running:
                remaining = self.delay
                while remaining > 0 and self.running:
                    time.sleep(min(0.1, remaining))
                    remaining -= 0.1

        session.close()
        self.finished.emit(successful, failed, failed_entries)


# ============================================================
# FIELD ROW
# ============================================================

class FieldRow(QWidget):
    def __init__(self, field="", value=""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.field_input = QLineEdit()
        self.field_input.setPlaceholderText("entry.123456789")
        self.field_input.setText(field)

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Value or Value1 | Value2 | Value3")
        self.value_input.setText(value)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setFixedWidth(80)

        layout.addWidget(self.field_input, 2)
        layout.addWidget(self.value_input, 3)
        layout.addWidget(self.remove_button)
        self.remove_button.clicked.connect(self.deleteLater)

    def get_data(self):
        return self.field_input.text().strip(), self.value_input.text().strip()


# ============================================================
# ANSWER SET
# ============================================================

class SubmissionEntry(QFrame):
    def __init__(self, number):
        super().__init__()
        self.number = number
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(6)

        header = QHBoxLayout()
        self.title = QLabel(f"Answer Set {number}")
        self.title.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.duplicate_button = QPushButton("Duplicate")
        self.delete_button = QPushButton("Delete")
        self.duplicate_button.setFixedWidth(90)
        self.delete_button.setFixedWidth(80)

        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.duplicate_button)
        header.addWidget(self.delete_button)
        self.layout.addLayout(header)

        labels = QHBoxLayout()
        labels.addWidget(QLabel("Form Field"), 2)
        labels.addWidget(QLabel("Value (use | to randomize)"), 3)
        labels.addWidget(QLabel(""), 0)
        self.layout.addLayout(labels)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        self.layout.addWidget(self.rows_container)

        self.add_field_button = QPushButton("+ Add Field")
        self.layout.addWidget(self.add_field_button)
        self.add_field_button.clicked.connect(self.add_field)
        self.add_field()

    def add_field(self, field="", value=""):
        self.rows_layout.addWidget(FieldRow(field, value))

    def get_data(self):
        data = {}
        for i in range(self.rows_layout.count()):
            widget = self.rows_layout.itemAt(i).widget()
            if isinstance(widget, FieldRow):
                field, value = widget.get_data()
                if field:
                    data[field] = value
        return data

    def load_data(self, data):
        self.clear_fields()
        for field, value in data.items():
            self.add_field(field, value)

    def clear_fields(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.entries = []
        self.failed_entries = []
        self.thread = None
        self.worker = None

        self.setWindowTitle(APP_NAME)
        self.resize(960, 840)
        self.setMinimumSize(720, 620)

        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Title
        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        subtitle = QLabel("For educational purposes only. Use responsibly.")
        subtitle.setStyleSheet("color: gray;")
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        # Form URL
        url_group = QGroupBox("Google Form")
        url_layout = QVBoxLayout(url_group)

        instruction = QLabel(
            "Paste a <b>formResponse</b> URL "
            "(or a viewform URL – it will be converted automatically).<br>"
            "Example ending: <code>.../formResponse</code>"
        )
        instruction.setWordWrap(True)
        instruction.setStyleSheet("color: #e3e3e3; margin-bottom: 4px;")
        url_layout.addWidget(instruction)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "https://docs.google.com/forms/d/e/.../formResponse"
        )
        self.validate_button = QPushButton("Validate")
        self.clear_url_button = QPushButton("Clear")
        self.validate_button.setFixedWidth(90)
        self.clear_url_button.setFixedWidth(70)

        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.validate_button)
        url_row.addWidget(self.clear_url_button)

        self.url_status = QLabel('Tip: Copy the link from the form\'s "Your response has been recorded" page.')
        self.url_status.setStyleSheet("color: #e3e3e3;")

        url_layout.addLayout(url_row)
        url_layout.addWidget(self.url_status)
        main_layout.addWidget(url_group)

        self.validate_button.clicked.connect(self.validate_url)
        self.clear_url_button.clicked.connect(self.url_input.clear)

        # Number of submissions
        count_group = QGroupBox("Number of Submissions")
        count_layout = QHBoxLayout(count_group)
        count_layout.addWidget(QLabel("Total submissions to send:"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, MAX_SUBMISSIONS_PER_RUN)
        self.count_spin.setValue(10)
        self.count_spin.setFixedWidth(110)
        count_layout.addWidget(self.count_spin)
        count_layout.addStretch()
        hint = QLabel("(up to 5000 • multiple Answer Sets are cycled)")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        count_layout.addWidget(hint)
        main_layout.addWidget(count_group)

        # Answer Sets
        entries_group = QGroupBox("Answer Sets")
        entries_layout = QVBoxLayout(entries_group)

        random_hint = QLabel(
            "Tip: In any Value field you can write multiple options separated by <b>|</b><br>"
            "Example: <code>Yes | No | Maybe</code> → a random choice is made for every submission"
        )
        random_hint.setWordWrap(True)
        random_hint.setStyleSheet("color: #e3e3e3; margin-bottom: 6px;")
        entries_layout.addWidget(random_hint)

        self.entries_scroll = QScrollArea()
        self.entries_scroll.setWidgetResizable(True)
        self.entries_scroll.setMinimumHeight(160)

        self.entries_widget = QWidget()
        self.entries_layout = QVBoxLayout(self.entries_widget)
        self.entries_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.entries_layout.setSpacing(8)
        self.entries_scroll.setWidget(self.entries_widget)
        entries_layout.addWidget(self.entries_scroll)

        buttons_row = QHBoxLayout()
        self.add_entry_button = QPushButton("+ Add Answer Set")
        self.clear_entries_button = QPushButton("Clear All")
        buttons_row.addWidget(self.add_entry_button)
        buttons_row.addWidget(self.clear_entries_button)
        buttons_row.addStretch()
        entries_layout.addLayout(buttons_row)

        main_layout.addWidget(entries_group, 1)

        self.add_entry_button.clicked.connect(self.add_entry)
        self.clear_entries_button.clicked.connect(self.clear_entries)

        # Speed
        speed_group = QGroupBox("Submission Speed")
        speed_layout = QVBoxLayout(speed_group)

        self.no_delay_checkbox = QCheckBox("No delay (maximum speed)")
        self.no_delay_checkbox.setToolTip(
            "When enabled, submissions are sent as fast as the network allows."
        )
        speed_layout.addWidget(self.no_delay_checkbox)

        self.delay_label = QLabel()
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(int(MIN_DELAY * 10))
        self.speed_slider.setMaximum(int(MAX_DELAY * 10))
        self.speed_slider.setValue(int(DEFAULT_DELAY * 10))

        speed_layout.addWidget(self.delay_label)
        speed_layout.addWidget(self.speed_slider)
        main_layout.addWidget(speed_group)

        self.speed_slider.valueChanged.connect(self.update_delay_label)
        self.no_delay_checkbox.toggled.connect(self._on_no_delay_toggled)
        self.update_delay_label()

        # Progress
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.count_label = QLabel("Successful: 0 | Failed: 0")
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.count_label)
        main_layout.addWidget(progress_group)

        # Controls
        controls = QHBoxLayout()
        self.start_button = QPushButton("START")
        self.stop_button = QPushButton("STOP")
        self.stop_button.setEnabled(False)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        main_layout.addLayout(controls)

        self.start_button.clicked.connect(self.start_submission)
        self.stop_button.clicked.connect(self.stop_submission)

        # Output
        output_group = QGroupBox("Output / Errors")
        output_layout = QVBoxLayout(output_group)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(140)
        output_layout.addWidget(self.output)
        main_layout.addWidget(output_group)

        # Safety note
        safety = QLabel(
            "Developed by 43Grim in relation with Artificial Intelligence"
        )
        safety.setWordWrap(True)
        safety.setStyleSheet("color: gray; font-size: 11px;")
        main_layout.addWidget(safety)

    def _on_no_delay_toggled(self, checked: bool):
        self.speed_slider.setEnabled(not checked)
        self.update_delay_label()

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    def get_submission_url(self):
        url = self.url_input.text().strip().rstrip("/")
        if not url:
            return None
        if url.endswith("/viewform"):
            url = url[:-9] + "/formResponse"
        return url

    def validate_url(self):
        url = self.get_submission_url()
        if not url:
            self.url_status.setText("Invalid: URL cannot be empty.")
            self.url_status.setStyleSheet("color: #c0392b;")
            return False

        parsed = urlparse(url)
        if not (
            parsed.scheme == "https"
            and parsed.netloc == "docs.google.com"
            and "/forms/" in parsed.path
        ):
            self.url_status.setText("Invalid Google Forms URL.")
            self.url_status.setStyleSheet("color: #c0392b;")
            return False

        if not url.endswith("/formResponse"):
            self.url_status.setText("Warning: URL does not appear to be a formResponse endpoint.")
            self.url_status.setStyleSheet("color: #e67e22;")
            return False

        self.url_status.setText("Valid submission endpoint.")
        self.url_status.setStyleSheet("color: #27ae60;")
        return True

    # --------------------------------------------------------
    # ANSWER SETS
    # --------------------------------------------------------

    def add_entry(self, data=None):
        number = len(self.entries) + 1
        entry = SubmissionEntry(number)
        if data:
            entry.load_data(data)

        entry.delete_button.clicked.connect(
            lambda checked=False, e=entry: self.remove_entry(e)
        )
        entry.duplicate_button.clicked.connect(
            lambda checked=False, e=entry: self.duplicate_entry(e)
        )

        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def remove_entry(self, entry):
        if entry in self.entries:
            self.entries.remove(entry)
            entry.deleteLater()
            self.renumber_entries()

    def duplicate_entry(self, entry):
        self.add_entry(entry.get_data())

    def clear_entries(self):
        for entry in self.entries:
            entry.deleteLater()
        self.entries.clear()

    def renumber_entries(self):
        for i, entry in enumerate(self.entries, 1):
            entry.number = i
            entry.title.setText(f"Answer Set {i}")

    def get_entries_data(self):
        entries = []
        for entry in self.entries:
            data = entry.get_data()
            if not data:
                raise ValueError(f"Answer Set {entry.number} contains no fields.")
            for field, value in data.items():
                if not field.startswith("entry."):
                    raise ValueError(
                        f"Answer Set {entry.number}: '{field}' must start with 'entry.'"
                    )
                if not field[6:].isdigit():
                    raise ValueError(
                        f"Answer Set {entry.number}: '{field}' needs a numeric ID."
                    )
                if value == "":
                    raise ValueError(
                        f"Answer Set {entry.number}: '{field}' has an empty value."
                    )
            entries.append(data)
        return entries

    # --------------------------------------------------------
    # SPEED
    # --------------------------------------------------------

    def get_delay(self):
        if self.no_delay_checkbox.isChecked():
            return 0.0
        return self.speed_slider.value() / 10

    def update_delay_label(self):
        if self.no_delay_checkbox.isChecked():
            self.delay_label.setText("Delay: NONE (maximum speed)")
        else:
            delay = self.get_delay()
            rate = 60 / delay if delay > 0 else 0
            self.delay_label.setText(
                f"Delay: {delay:.1f} seconds between submissions "
                f"(approx. {rate:.0f} submissions/minute)"
            )

    # --------------------------------------------------------
    # SUBMISSION
    # --------------------------------------------------------

    def start_submission(self):
        if not self.validate_url():
            QMessageBox.warning(
                self, "Invalid URL",
                "Please enter a valid Google Forms formResponse URL."
            )
            return

        try:
            entries = self.get_entries_data()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid Answer Set", str(error))
            return

        if not entries:
            QMessageBox.warning(
                self, "No Answer Sets",
                "Add at least one Answer Set before starting."
            )
            return

        total = self.count_spin.value()
        delay = self.get_delay()

        self.failed_entries = []
        self.output.clear()
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting…")
        self.count_label.setText("Successful: 0 | Failed: 0")

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.thread = QThread()
        self.worker = SubmissionWorker(
            form_url=self.get_submission_url(),
            entries=entries,
            total=total,
            delay=delay,
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.add_log)
        self.worker.success.connect(self.handle_success)
        self.worker.failure.connect(self.handle_failure)
        self.worker.finished.connect(self.handle_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def stop_submission(self):
        if self.worker:
            self.worker.stop()
            self.progress_label.setText("Stopping…")
            self.stop_button.setEnabled(False)

    def update_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Processing {current} of {total}")

    def add_log(self, message):
        self.output.append(message)

    def handle_success(self, index, status):
        successful, failed = self.get_current_counts()
        self.count_label.setText(f"Successful: {successful + 1} | Failed: {failed}")

    def handle_failure(self, index, message):
        successful, failed = self.get_current_counts()
        self.count_label.setText(f"Successful: {successful} | Failed: {failed + 1}")

    def get_current_counts(self):
        try:
            parts = (
                self.count_label.text()
                .replace("Successful:", "")
                .replace("Failed:", "")
                .split("|")
            )
            return int(parts[0].strip()), int(parts[1].strip())
        except Exception:
            return 0, 0

    def handle_finished(self, successful, failed, failed_entries):
        self.failed_entries = failed_entries
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_label.setText("Finished")
        self.output.append(
            "\n========================================\n"
            "RUN COMPLETE\n"
            f"Successful: {successful}\n"
            f"Failed:     {failed}\n"
            "========================================"
        )

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    def save_config(self):
        try:
            config = {
                "form_url": self.url_input.text(),
                "delay": self.speed_slider.value() / 10,
                "no_delay": self.no_delay_checkbox.isChecked(),
                "total_submissions": self.count_spin.value(),
                "entries": [e.get_data() for e in self.entries if e.get_data()],
            }
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def load_config(self):
        if not CONFIG_PATH.exists():
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)

            self.url_input.setText(config.get("form_url", ""))

            delay = max(MIN_DELAY, min(MAX_DELAY, float(config.get("delay", DEFAULT_DELAY))))
            self.speed_slider.setValue(int(delay * 10))

            self.no_delay_checkbox.setChecked(config.get("no_delay", False))

            total = config.get("total_submissions", 10)
            self.count_spin.setValue(max(1, min(MAX_SUBMISSIONS_PER_RUN, total)))

            for data in config.get("entries", []):
                self.add_entry(data)

            self._on_no_delay_toggled(self.no_delay_checkbox.isChecked())
        except Exception as error:
            self.output.append(f"Could not load configuration: {error}")

    def closeEvent(self, event):
        self.save_config()
        if self.thread and self.thread.isRunning():
            if self.worker:
                self.worker.stop()
            self.thread.quit()
            self.thread.wait(3000)
        event.accept()


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
