import sys
import json
import platform
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLineEdit, QLabel,
                             QFileDialog, QMessageBox, QFrame, QComboBox,
                             QSlider, QTextEdit, QSpinBox)
from PyQt6.QtCore import Qt, QTimer
import vlc


class VideoPlayer(QMainWindow):
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
        layout.addLayout(recent_layout)

        # Top control layout
        control_layout = QHBoxLayout()

        # File selection button
        open_btn = QPushButton("Open Local File")
        open_btn.clicked.connect(self.open_file)
        control_layout.addWidget(open_btn)

        # URL entry
        control_layout.addWidget(QLabel("URL:"))
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Paste URL here (including YouTube links)")
        self.url_entry.returnPressed.connect(self.load_url)
        control_layout.addWidget(self.url_entry)

        load_url_btn = QPushButton("Load URL")
        load_url_btn.clicked.connect(self.load_url)
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
        time_control_layout.addWidget(skip_back_long_btn)

        skip_back_short_btn = QPushButton(f"◀ {self.skip_short}s")
        skip_back_short_btn.clicked.connect(lambda: self.skip(-self.skip_short))
        time_control_layout.addWidget(skip_back_short_btn)

        skip_forward_short_btn = QPushButton(f"{self.skip_short}s ▶")
        skip_forward_short_btn.clicked.connect(lambda: self.skip(self.skip_short))
        time_control_layout.addWidget(skip_forward_short_btn)

        skip_forward_long_btn = QPushButton(f"{self.skip_long}s ▶▶")
        skip_forward_long_btn.clicked.connect(lambda: self.skip(self.skip_long))
        time_control_layout.addWidget(skip_forward_long_btn)

        # Skip interval settings
        time_control_layout.addWidget(QLabel("Short:"))
        self.skip_short_spin = QSpinBox()
        self.skip_short_spin.setRange(1, 60)
        self.skip_short_spin.setValue(self.skip_short)
        self.skip_short_spin.setSuffix("s")
        self.skip_short_spin.valueChanged.connect(self.update_skip_buttons)
        time_control_layout.addWidget(self.skip_short_spin)

        time_control_layout.addWidget(QLabel("Long:"))
        self.skip_long_spin = QSpinBox()
        self.skip_long_spin.setRange(1, 300)
        self.skip_long_spin.setValue(self.skip_long)
        self.skip_long_spin.setSuffix("s")
        self.skip_long_spin.valueChanged.connect(self.update_skip_buttons)
        time_control_layout.addWidget(self.skip_long_spin)

        layout.addLayout(time_control_layout)

        # Playback controls and speed
        playback_layout = QHBoxLayout()

        play_btn = QPushButton("Play")
        play_btn.clicked.connect(self.play)
        playback_layout.addWidget(play_btn)

        pause_btn = QPushButton("Pause")
        pause_btn.clicked.connect(self.pause)
        playback_layout.addWidget(pause_btn)

        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self.stop)
        playback_layout.addWidget(stop_btn)

        playback_layout.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        speeds = ["0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x", "3x", "4x"]
        self.speed_combo.addItems(speeds)
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        playback_layout.addWidget(self.speed_combo)

        playback_layout.addStretch()

        capture_btn = QPushButton("Capture Frame")
        capture_btn.clicked.connect(self.capture_frame)
        playback_layout.addWidget(capture_btn)

        layout.addLayout(playback_layout)

        # Text display area (4 rows visible, scrollable)
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setMaximumHeight(100)
        self.text_display.setPlaceholderText("Captured text will appear here...")
        layout.addWidget(self.text_display)

        # Store references to skip buttons for updating labels
        self.skip_back_long_btn = skip_back_long_btn
        self.skip_back_short_btn = skip_back_short_btn
        self.skip_forward_short_btn = skip_forward_short_btn
        self.skip_forward_long_btn = skip_forward_long_btn

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
            self.config['skip_short'] = self.skip_short_spin.value()
            self.config['skip_long'] = self.skip_long_spin.value()
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

    def skip(self, seconds):
        """Skip forward or backward by specified seconds"""
        current_time = self.player.get_time()
        new_time = max(0, current_time + (seconds * 1000))
        self.player.set_time(int(new_time))

    def update_skip_buttons(self):
        """Update skip button labels when values change"""
        self.skip_short = self.skip_short_spin.value()
        self.skip_long = self.skip_long_spin.value()

        self.skip_back_long_btn.setText(f"◀◀ {self.skip_long}s")
        self.skip_back_short_btn.setText(f"◀ {self.skip_short}s")
        self.skip_forward_short_btn.setText(f"{self.skip_short}s ▶")
        self.skip_forward_long_btn.setText(f"{self.skip_long}s ▶▶")

        self.save_config()

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
        """Capture current frame as image"""
        if self.player.is_playing() or self.player.get_state() == vlc.State.Paused:
            # Pause if playing
            was_playing = self.player.is_playing()
            if was_playing:
                self.pause()

            # Take snapshot
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Frame",
                "",
                "PNG files (*.png);;JPEG files (*.jpg)"
            )
            if file_path:
                # video_take_snapshot(num, path, width, height)
                # 0 for default size
                self.player.video_take_snapshot(0, file_path, 0, 0)

                # Add your OCR code here
                # Example: send file_path to your OCR API
                # result = your_ocr_function(file_path)
                # self.text_display.append(result)

                # Placeholder text for demonstration
                self.text_display.append(f"Frame captured: {file_path}")
                self.text_display.append("Add your OCR processing code here...")

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