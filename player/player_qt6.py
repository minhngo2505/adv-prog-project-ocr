"""
player_qt6.py
Myk: Mike Holland, J336025, with Claude, from 11/11/2025

A video player for use by The Blind, with OCR feature to be used with a screen reader.
Player is built using Python, Qt6, VLC.
The embedded VLC player can play both local files, and web URLs.
The player can grab a single frame from a paused video, and send it to a server process for OCR text extraction using Tesseract.

TODO: add support for youtube.

"""

import sys
import json
import platform
from pathlib import Path

from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,QFileDialog, QMessageBox, QFrame, QComboBox, QSlider, QTextEdit, QSpinBox, QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, QTimer
import vlc

class SettingsDialog(QDialog):
    """
    Creates a modal dialog for changing settings. These are persistant in a json config file.
    """
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.config = config

        layout = QVBoxLayout()
        self.setLayout(layout)

        # OCR API URL
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("OCR API URL:"))
        self.api_url_edit = QLineEdit()
        self.api_url_edit.setText(config.get('api_url', 'http://localhost:8000/frame/ocr'))
        api_layout.addWidget(self.api_url_edit)
        layout.addLayout(api_layout)

        # Skip intervals
        skip_layout = QHBoxLayout()
        skip_layout.addWidget(QLabel("Short skip:"))
        self.skip_short_spin = QSpinBox()
        self.skip_short_spin.setRange(1, 60)
        self.skip_short_spin.setValue(config.get('skip_short', 5))
        self.skip_short_spin.setSuffix(" seconds")
        skip_layout.addWidget(self.skip_short_spin)

        skip_layout.addWidget(QLabel("Long skip:"))
        self.skip_long_spin = QSpinBox()
        self.skip_long_spin.setRange(1, 300)
        self.skip_long_spin.setValue(config.get('skip_long', 30))
        self.skip_long_spin.setSuffix(" seconds")
        skip_layout.addWidget(self.skip_long_spin)
        layout.addLayout(skip_layout)

        # Clear history button
        clear_btn = QPushButton("Clear Recent History")
        clear_btn.clicked.connect(self.clear_history)
        clear_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(clear_btn)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def clear_history(self):
        """Clear recent history"""
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to clear recent history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config['recent_items'] = []
            QMessageBox.information(self, "Success", "Recent history cleared")

    def get_settings(self):
        """Return the settings as a dict"""
        return {
            'api_url': self.api_url_edit.text().strip(),
            'skip_short': self.skip_short_spin.value(),
            'skip_long': self.skip_long_spin.value()
        }


class VideoPlayer(QMainWindow):
    """
    Main window for video player app, using Qt6.

    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cyclops Video Player")
        self.setGeometry(100, 100, 900, 700)

        # VLC instance and player
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        # Load config
        self.config_path = self.get_config_path()
        self.config = self.load_config()
        self.recent_items = self.config.get('recent_items', [])
        self.skip_short = self.config.get('skip_short', 5)
        self.skip_long = self.config.get('skip_long', 30)
        self.api_url = self.config.get('api_url', 'http://localhost:8000/frame/ocr')

        # Timer for updating slider
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_slider)
        self.timer.start()

        # Flag to prevent slider update during user drag
        self.slider_pressed = False

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Recent items dropdown
        recent_layout = QHBoxLayout()
        recent_layout.addWidget(QLabel("Recent:"))
        self.recent_combo = QComboBox()
        self.recent_combo.addItem("-- Select recent file or URL --")
        self.recent_combo.addItems(self.recent_items)
        self.recent_combo.currentTextChanged.connect(self.on_recent_selected)
        recent_layout.addWidget(self.recent_combo)

        # Settings button
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self.open_settings)
        settings_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        recent_layout.addWidget(settings_btn)

        layout.addLayout(recent_layout)

        # Top control layout
        control_layout = QHBoxLayout()

        # File selection button
        open_btn = QPushButton("Open Local File")
        open_btn.clicked.connect(self.open_file)
        open_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        control_layout.addWidget(open_btn)

        # URL entry
        control_layout.addWidget(QLabel("URL:"))
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Paste URL here (including YouTube links)")
        self.url_entry.returnPressed.connect(self.load_url)
        control_layout.addWidget(self.url_entry)

        load_url_btn = QPushButton("Load URL")
        load_url_btn.clicked.connect(self.load_url)
        load_url_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        control_layout.addWidget(load_url_btn)

        layout.addLayout(control_layout)

        # Video frame
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setMinimumSize(640, 360)
        layout.addWidget(self.video_frame)

        # Progress slider
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderPressed.connect(self.on_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_slider_released)
        self.position_slider.sliderMoved.connect(self.on_slider_moved)
        layout.addWidget(self.position_slider)

        # Time display and skip controls
        time_control_layout = QHBoxLayout()

        self.time_label = QLabel("00:00.0 / 00:00.0")
        time_control_layout.addWidget(self.time_label)

        time_control_layout.addStretch()

        # Skip controls
        skip_back_long_btn = QPushButton(f"◀◀ {self.skip_long}s")
        skip_back_long_btn.clicked.connect(lambda: self.skip(-self.skip_long))
        skip_back_long_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        time_control_layout.addWidget(skip_back_long_btn)

        skip_back_short_btn = QPushButton(f"◀ {self.skip_short}s")
        skip_back_short_btn.clicked.connect(lambda: self.skip(-self.skip_short))
        skip_back_short_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        time_control_layout.addWidget(skip_back_short_btn)

        skip_forward_short_btn = QPushButton(f"{self.skip_short}s ▶")
        skip_forward_short_btn.clicked.connect(lambda: self.skip(self.skip_short))
        skip_forward_short_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        time_control_layout.addWidget(skip_forward_short_btn)

        skip_forward_long_btn = QPushButton(f"{self.skip_long}s ▶▶")
        skip_forward_long_btn.clicked.connect(lambda: self.skip(self.skip_long))
        skip_forward_long_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        time_control_layout.addWidget(skip_forward_long_btn)

        # skipping to chosen timestamp
        enter_timestamp = QLineEdit()
        skip_to_timestamp_button = QPushButton("Go to timestamp")
        skip_to_timestamp_button.clicked.connect(lambda: self.seek_to_timestamp(enter_timestamp.text()))
        skip_to_timestamp_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        time_control_layout.addWidget(enter_timestamp)
        time_control_layout.addWidget(skip_to_timestamp_button)

        layout.addLayout(time_control_layout)

        # Playback controls and speed
        playback_layout = QHBoxLayout()

        play_btn = QPushButton("▶")
        play_btn.setAccessibleName("play")      # alt text for screen reader
        play_btn.clicked.connect(self.play)
        play_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        playback_layout.addWidget(play_btn)

        pause_btn = QPushButton("⏸")
        pause_btn.setAccessibleName("pause")
        pause_btn.clicked.connect(self.pause)
        pause_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        playback_layout.addWidget(pause_btn)

        stop_btn = QPushButton("■")
        stop_btn.setAccessibleName("stop")
        stop_btn.clicked.connect(self.stop)
        stop_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        playback_layout.addWidget(stop_btn)

        playback_layout.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        speeds = ["0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x", "3x", "4x"]
        self.speed_combo.addItems(speeds)
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        playback_layout.addWidget(self.speed_combo)

        playback_layout.addStretch()
        
        # Volume control
        playback_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)  # VLC volume range = 0–100
        self.volume_slider.setValue(self.player.audio_get_volume())
        self.volume_slider.valueChanged.connect(self.change_volume)
        playback_layout.addWidget(self.volume_slider)

        capture_btn = QPushButton("OCR Frame")
        capture_btn.clicked.connect(self.capture_frame)
        capture_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        playback_layout.addWidget(capture_btn)

        layout.addLayout(playback_layout)

        # Text display area (10 rows visible, scrollable)
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        # Set height for approximately 10 lines of text
        font_metrics = self.text_display.fontMetrics()
        line_height = font_metrics.lineSpacing()
        self.text_display.setMinimumHeight(line_height * 10 + 10)  # 10 lines + padding
        self.text_display.setMaximumHeight(line_height * 10 + 10)
        self.text_display.setPlaceholderText("Captured text will appear here...")
        self.text_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.text_display)

        # Store references to skip buttons for updating labels
        self.skip_back_long_btn = skip_back_long_btn
        self.skip_back_short_btn = skip_back_short_btn
        self.skip_forward_short_btn = skip_forward_short_btn
        self.skip_forward_long_btn = skip_forward_long_btn

        # Set up keyboard shortcuts
        self.setup_shortcuts()

        # Set tab order for better keyboard navigation
        self.setTabOrder(self.recent_combo, settings_btn)
        self.setTabOrder(settings_btn, open_btn)
        self.setTabOrder(open_btn, self.url_entry)
        self.setTabOrder(self.url_entry, load_url_btn)
        self.setTabOrder(load_url_btn, self.position_slider)
        self.setTabOrder(self.position_slider, skip_back_long_btn)
        self.setTabOrder(skip_back_long_btn, skip_back_short_btn)
        self.setTabOrder(skip_back_short_btn, skip_forward_short_btn)
        self.setTabOrder(skip_forward_short_btn, skip_forward_long_btn)
        self.setTabOrder(skip_forward_long_btn, enter_timestamp)
        self.setTabOrder(enter_timestamp, skip_to_timestamp_button)
        self.setTabOrder(skip_to_timestamp_button, play_btn)
        self.setTabOrder(play_btn, pause_btn)
        self.setTabOrder(pause_btn, stop_btn)
        self.setTabOrder(stop_btn, self.speed_combo)
        self.setTabOrder(self.speed_combo, capture_btn)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Playback controls
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_play_pause)
        QShortcut(QKeySequence("K"), self, self.toggle_play_pause)  # YouTube style
        QShortcut(QKeySequence("S"), self, self.stop)

        # Seeking
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.skip(-self.skip_short))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.skip(self.skip_short))
        QShortcut(QKeySequence("J"), self, lambda: self.skip(-self.skip_long))  # YouTube style
        QShortcut(QKeySequence("L"), self, lambda: self.skip(self.skip_long))  # YouTube style

        # Speed controls
        QShortcut(QKeySequence("Shift+,"), self, self.decrease_speed)  # Slower
        QShortcut(QKeySequence("Shift+."), self, self.increase_speed)  # Faster

        # Frame capture
        QShortcut(QKeySequence("C"), self, self.capture_frame)

        # File operations
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_file)
        QShortcut(QKeySequence("Ctrl+,"), self, self.open_settings)  # Standard settings shortcut

    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if self.player.is_playing():
            self.pause()
        else:
            self.play()

    def decrease_speed(self):
        """Decrease playback speed"""
        current_index = self.speed_combo.currentIndex()
        if current_index > 0:
            self.speed_combo.setCurrentIndex(current_index - 1)

    def increase_speed(self):
        """Increase playback speed"""
        current_index = self.speed_combo.currentIndex()
        if current_index < self.speed_combo.count() - 1:
            self.speed_combo.setCurrentIndex(current_index + 1)
            
    def change_volume(self, value):
        """Change VLC player volume"""
        try:
            self.player.audio_set_volume(int(value))
        except Exception as e:
            print(f"Error setting volume: {e}")

    def get_config_path(self):
        """Get platform-appropriate config file path"""
        if platform.system() == "Darwin":  # macOS
            config_dir = Path.home() / "Library" / "Application Support" / "Cyclops"
        elif platform.system() == "Windows":
            import os
            config_dir = Path(os.environ.get('APPDATA', Path.home())) / "Cyclops"
        else:  # Linux
            config_dir = Path.home() / ".config" / "cyclops"

        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    def load_config(self):
        """Load config from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
        return {}

    def save_config(self):
        """Save config to file"""
        try:
            self.config['recent_items'] = self.recent_items
            self.config['skip_short'] = self.skip_short
            self.config['skip_long'] = self.skip_long
            self.config['api_url'] = self.api_url
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def add_to_recent(self, path):
        """Add item to recent list (max 10 items)"""
        if path in self.recent_items:
            self.recent_items.remove(path)

        self.recent_items.insert(0, path)
        self.recent_items = self.recent_items[:10]

        self.recent_combo.clear()
        self.recent_combo.addItem("-- Select recent file or URL --")
        self.recent_combo.addItems(self.recent_items)

        self.save_config()

    def on_recent_selected(self, text):
        """Handle selection from recent items dropdown"""
        if text and text != "-- Select recent file or URL --":
            self.load_media(text)

    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            self.api_url = settings['api_url']
            self.skip_short = settings['skip_short']
            self.skip_long = settings['skip_long']

            # Update button labels
            self.skip_back_long_btn.setText(f"◀◀ {self.skip_long}s")
            self.skip_back_short_btn.setText(f"◀ {self.skip_short}s")
            self.skip_forward_short_btn.setText(f"{self.skip_short}s ▶")
            self.skip_forward_long_btn.setText(f"{self.skip_long}s ▶▶")

            # Update recent items if history was cleared
            self.recent_items = self.config.get('recent_items', [])
            self.recent_combo.clear()
            self.recent_combo.addItem("-- Select recent file or URL --")
            self.recent_combo.addItems(self.recent_items)

            # Save config
            self.save_config()

    def update_slider(self):
        """Update slider position based on video progress"""
        if not self.slider_pressed and self.player.is_playing():
            media = self.player.get_media()
            if media:
                length = self.player.get_length()
                position = self.player.get_time()

                if length > 0:
                    slider_pos = int((position / length) * 1000)
                    self.position_slider.setValue(slider_pos)

                    # Update time label
                    current = self.format_time(position)
                    total = self.format_time(length)
                    self.time_label.setText(f"{current} / {total}")

    def format_time(self, ms):
        """Format milliseconds to mm:ss.d"""
        seconds = ms / 1000
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:04.1f}"

    def on_slider_pressed(self):
        """Handle slider press"""
        self.slider_pressed = True

    def on_slider_released(self):
        """Handle slider release"""
        self.slider_pressed = False
        self.seek_to_slider_position()

    def on_slider_moved(self, position):
        """Handle slider movement"""
        if self.slider_pressed:
            # Update time display during drag
            length = self.player.get_length()
            if length > 0:
                new_time = int((position / 1000) * length)
                current = self.format_time(new_time)
                total = self.format_time(length)
                self.time_label.setText(f"{current} / {total}")

    def seek_to_slider_position(self):
        """Seek video to slider position"""
        position = self.position_slider.value()
        length = self.player.get_length()
        if length > 0:
            new_time = int((position / 1000) * length)
            self.player.set_time(new_time)

    def seek_to_timestamp(self, timestamp):
        """Seek video to chosen timestamp"""
        length = self.player.get_length()
        timestamp = self.format_frames(timestamp)
        if length > 0 and timestamp <= length:
            self.player.set_time(timestamp)

    def format_frames(self, timestamp):
        """Format timestamp to frames"""
        try:
            timestamp.split(":")
            minutes = int(timestamp.split(":")[0])
            seconds = int(timestamp.split(":")[1])
            minutes_to_seconds = minutes * 60
            ms = (seconds + minutes_to_seconds) * 1000
            return ms
        except ValueError:
            return "Incorrect timestamp format"

    def skip(self, seconds):
        """Skip forward or backward by specified seconds"""
        current_time = self.player.get_time()
        new_time = max(0, current_time + (seconds * 1000))
        self.player.set_time(int(new_time))

    def change_speed(self, speed_text):
        """Change playback speed"""
        speed = float(speed_text.replace('x', ''))
        self.player.set_rate(speed)

    def showEvent(self, event):
        """Embed VLC player after window is shown"""
        super().showEvent(event)
        if not hasattr(self, '_embedded'):
            self._embedded = True
            self.embed_video()

    def moveEvent(self, event):
        """Re-embed video when window is moved (fixes macOS multi-display issues)"""
        super().moveEvent(event)
        if hasattr(self, '_embedded') and platform.system() == "Darwin":
            # Force entire window to refresh
            QTimer.singleShot(50, self.refresh_window)

    def resizeEvent(self, event):
        """Re-embed video when window is resized (fixes macOS rendering issues)"""
        super().resizeEvent(event)
        if hasattr(self, '_embedded') and platform.system() == "Darwin":
            QTimer.singleShot(50, self.refresh_window)

    def refresh_window(self):
        """Force entire window to refresh"""
        if platform.system() == "Darwin":
            # Re-embed video
            self.embed_video()
            # Force entire window repaint
            self.update()
            self.repaint()
            # Also force central widget
            self.centralWidget().update()
            self.centralWidget().repaint()

    def embed_video(self):
        """Embed VLC player into the Qt window"""
        if platform.system() == "Darwin":  # macOS
            self.player.set_nsobject(int(self.video_frame.winId()))
        elif platform.system() == "Windows":
            self.player.set_hwnd(int(self.video_frame.winId()))
        elif platform.system() == "Linux":
            self.player.set_xwindow(int(self.video_frame.winId()))

    def open_file(self):
        """Open a local video file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video files (*.mp4 *.avi *.mkv *.mov *.flv *.wmv);;All files (*.*)"
        )
        if file_path:
            self.load_media(file_path)

    def load_url(self):
        """Load video from URL"""
        url = self.url_entry.text().strip()
        if url:
            self.load_media(url)
        else:
            QMessageBox.warning(self, "Warning", "Please enter a URL")

    def load_media(self, path):
        """Load media from file path or URL"""
        try:
            media = self.instance.media_new(path)
            self.player.set_media(media)
            self.add_to_recent(path)
            self.play()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load media: {str(e)}")

    def play(self):
        """Play the video"""
        self.player.play()

    def pause(self):
        """Pause the video"""
        self.player.pause()

    def stop(self):
        """Stop the video"""
        self.player.stop()

    def capture_frame(self):
        """Capture current frame as image and send to OCR"""
        if self.player.is_playing() or self.player.get_state() == vlc.State.Paused:
            # Pause if playing
            was_playing = self.player.is_playing()
            if was_playing:
                self.pause()

            try:
                # Create temporary file for snapshot
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    snapshot_path = tmp.name

                # Take snapshot
                self.player.video_take_snapshot(0, snapshot_path, 0, 0)

                # Wait a moment for snapshot to be written
                import time
                time.sleep(0.2)

                # Send to OCR API
                import requests
                with open(snapshot_path, 'rb') as f:
                    files = {'file': ('frame.png', f, 'image/png')}
                    response = requests.post(
                        self.api_url,
                        files=files,
                        headers={'accept': 'application/json'}
                    )

                # Clean up temp file
                import os
                os.unlink(snapshot_path)

                # Display result
                if response.status_code == 200:
                    # Parse JSON response properly
                    try:
                        # If response is JSON, parse it
                        ocr_data = response.json()
                        # Handle different possible response formats
                        if isinstance(ocr_data, dict):
                            ocr_text = ocr_data.get('text', str(ocr_data))
                        else:
                            ocr_text = str(ocr_data)
                    except json.JSONDecodeError:
                        # If not JSON, treat as plain text
                        ocr_text = response.text

                    self.text_display.append(ocr_text)
                    # Auto-scroll to bottom
                    scrollbar = self.text_display.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())
                else:
                    self.text_display.append(f"OCR Error: {response.status_code} - {response.text}")
                    scrollbar = self.text_display.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())

            except requests.exceptions.ConnectionError:
                QMessageBox.critical(self, "Connection Error",
                                     "Could not connect to OCR service at localhost:8000")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to capture/process frame: {str(e)}")

        else:
            QMessageBox.warning(self, "Warning", "No video playing")

    def closeEvent(self, event):
        """Clean up VLC player on close"""
        self.player.stop()
        self.timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec())