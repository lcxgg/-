import json
import math
import random
import sys
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtMultimedia, QtWidgets


APP_DIR = Path(__file__).resolve().parent
LEADERBOARD_FILE = APP_DIR / "点小球排行榜.json"
TOTAL_ROUNDS = 20
START_BALL_RADIUS = 30
MIN_BALL_RADIUS = 16
COUNTDOWN_SECONDS = 30
HIT_SOUND_FILE = APP_DIR / "点小球_hit.wav"
MISS_SOUND_FILE = APP_DIR / "点小球_miss.wav"


APP_STYLE = """
QWidget {
    color: #eef4ff;
    font-family: "Microsoft YaHei", "Segoe UI", Arial;
    font-size: 14px;
}
QMainWindow, QWidget#root {
    background: #0f1720;
}
QFrame#panel {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
}
QLabel#title {
    color: #ffffff;
    font-size: 26px;
    font-weight: 700;
}
QLabel#metricValue {
    color: #ffffff;
    font-size: 22px;
    font-weight: 700;
}
QLabel#metricLabel {
    color: #9fb0c7;
    font-size: 12px;
}
QLineEdit, QComboBox, QSpinBox {
    min-height: 34px;
    padding: 0 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.06);
    color: #eef4ff;
}
QCheckBox {
    spacing: 8px;
}
QPushButton {
    min-height: 38px;
    padding: 0 16px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(46, 196, 182, 0.18);
    color: #ffffff;
    font-weight: 600;
}
QPushButton:hover {
    background: rgba(46, 196, 182, 0.28);
    border: 1px solid rgba(46, 196, 182, 0.75);
}
QPushButton:pressed {
    background: rgba(46, 196, 182, 0.38);
}
QTableWidget {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    gridline-color: rgba(255, 255, 255, 0.08);
}
QHeaderView::section {
    background: rgba(255, 255, 255, 0.08);
    color: #dce7f7;
    border: none;
    padding: 8px;
}
QTableWidget::item {
    padding: 6px;
}
QMessageBox {
    background: #18222d;
}
QMessageBox QLabel {
    color: #eef4ff;
    min-width: 220px;
}
QMessageBox QPushButton {
    min-width: 72px;
    min-height: 34px;
    background: rgba(46, 196, 182, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.16);
    color: #ffffff;
}
QMessageBox QPushButton:hover {
    background: rgba(46, 196, 182, 0.28);
    border: 1px solid rgba(46, 196, 182, 0.75);
}
"""


@dataclass
class ScoreEntry:
    player: str
    accuracy: float
    correct: int
    wrong: int
    played_at: str


class GameCanvas(QtWidgets.QWidget):
    hit = QtCore.pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(620, 420)
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        self.ball_center = QtCore.QPointF(0, 0)
        self.ball_radius = START_BALL_RADIUS
        self.ripple_radius = 0.0
        self.ripple_opacity = 0
        self.active = False
        self.move_timer = QtCore.QTimer(self)
        self.move_timer.timeout.connect(self.randomize_ball)
        self.animation_timer = QtCore.QTimer(self)
        self.animation_timer.timeout.connect(self.advance_animation)

    def start(self, radius: int, move_interval_ms: int):
        self.active = True
        self.ball_radius = radius
        self.move_timer.start(move_interval_ms)
        self.randomize_ball()
        self.update()

    def stop(self):
        self.active = False
        self.move_timer.stop()
        self.update()

    def set_difficulty(self, radius: int, move_interval_ms: int):
        self.ball_radius = radius
        if self.active:
            self.move_timer.start(move_interval_ms)
        self.update()

    def randomize_ball(self):
        margin = self.ball_radius + 12
        width = max(self.width(), margin * 2 + 1)
        height = max(self.height(), margin * 2 + 1)
        x = random.randint(margin, width - margin)
        y = random.randint(margin, height - margin)
        self.ball_center = QtCore.QPointF(x, y)
        self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if not self.active or event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        delta = event.position() - self.ball_center
        is_hit = delta.x() ** 2 + delta.y() ** 2 <= self.ball_radius ** 2
        if is_hit:
            self.start_hit_animation()
        self.hit.emit(is_hit)
        if is_hit:
            self.randomize_ball()
        self.update()

    def start_hit_animation(self):
        self.ripple_radius = float(self.ball_radius)
        self.ripple_opacity = 180
        self.animation_timer.start(16)

    def advance_animation(self):
        self.ripple_radius += 2.8
        self.ripple_opacity -= 12
        if self.ripple_opacity <= 0:
            self.animation_timer.stop()
            self.ripple_opacity = 0
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        gradient = QtGui.QLinearGradient(
            QtCore.QPointF(rect.left(), rect.top()),
            QtCore.QPointF(rect.right(), rect.bottom()),
        )
        gradient.setColorAt(0, QtGui.QColor("#152230"))
        gradient.setColorAt(1, QtGui.QColor("#101820"))
        painter.fillRect(rect, gradient)

        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 18), 1))
        step = 40
        for x in range(0, rect.width(), step):
            painter.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), step):
            painter.drawLine(0, y, rect.width(), y)

        if self.active:
            glow = QtGui.QRadialGradient(self.ball_center, self.ball_radius * 2.2)
            glow.setColorAt(0, QtGui.QColor(46, 196, 182, 120))
            glow.setColorAt(1, QtGui.QColor(46, 196, 182, 0))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(self.ball_center, self.ball_radius * 2.2, self.ball_radius * 2.2)

            ball_gradient = QtGui.QRadialGradient(
                self.ball_center - QtCore.QPointF(self.ball_radius * 0.3, self.ball_radius * 0.3),
                self.ball_radius * 1.3,
            )
            ball_gradient.setColorAt(0, QtGui.QColor("#8ff7ea"))
            ball_gradient.setColorAt(1, QtGui.QColor("#2ec4b6"))
            painter.setBrush(ball_gradient)
            painter.setPen(QtGui.QPen(QtGui.QColor("#d8fff9"), 2))
            painter.drawEllipse(self.ball_center, self.ball_radius, self.ball_radius)

            if self.ripple_opacity > 0:
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.setPen(QtGui.QPen(QtGui.QColor(143, 247, 234, self.ripple_opacity), 3))
                painter.drawEllipse(self.ball_center, self.ripple_radius, self.ripple_radius)
        else:
            painter.setPen(QtGui.QColor("#9fb0c7"))
            painter.setFont(QtGui.QFont("Microsoft YaHei", 18, QtGui.QFont.Weight.Medium))
            painter.drawText(
                QtCore.QRectF(rect),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "点击“开始游戏”",
            )


class MetricCard(QtWidgets.QFrame):
    def __init__(self, label: str, value: str):
        super().__init__()
        self.setObjectName("panel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.value_label = QtWidgets.QLabel(value)
        self.value_label.setObjectName("metricValue")
        label_widget = QtWidgets.QLabel(label)
        label_widget.setObjectName("metricLabel")
        layout.addWidget(self.value_label)
        layout.addWidget(label_widget)

    def set_value(self, value: str):
        self.value_label.setText(value)


class BallClickGame(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.correct = 0
        self.wrong = 0
        self.remaining = TOTAL_ROUNDS
        self.seconds_left = COUNTDOWN_SECONDS
        self.game_running = False
        self.entries = self.load_leaderboard()
        self.countdown_timer = QtCore.QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.ensure_sound_files()
        self.hit_sound = self.build_sound(HIT_SOUND_FILE)
        self.miss_sound = self.build_sound(MISS_SOUND_FILE)
        self.setup_ui()
        self.refresh_metrics()
        self.refresh_leaderboard()

    def setup_ui(self):
        self.setWindowTitle("点小球")
        self.resize(1040, 720)

        root = QtWidgets.QWidget()
        root.setObjectName("root")
        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        top_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("点小球")
        title.setObjectName("title")
        self.player_input = QtWidgets.QLineEdit()
        self.player_input.setPlaceholderText("玩家姓名")
        self.player_input.setMaximumWidth(160)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["固定次数", "倒计时"])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        self.duration_spin = QtWidgets.QSpinBox()
        self.duration_spin.setRange(10, 180)
        self.duration_spin.setValue(COUNTDOWN_SECONDS)
        self.duration_spin.setSuffix(" 秒")
        self.duration_spin.setVisible(False)
        self.start_button = QtWidgets.QPushButton("开始游戏")
        self.start_button.clicked.connect(self.start_game)
        top_row.addWidget(title)
        top_row.addStretch(1)
        top_row.addWidget(self.player_input)
        top_row.addWidget(self.mode_combo)
        top_row.addWidget(self.duration_spin)
        top_row.addWidget(self.start_button)
        root_layout.addLayout(top_row)

        metrics_row = QtWidgets.QHBoxLayout()
        self.correct_card = MetricCard("正确", "0")
        self.wrong_card = MetricCard("错误", "0")
        self.remaining_card = MetricCard("剩余次数", str(TOTAL_ROUNDS))
        self.time_card = MetricCard("剩余时间", "--")
        self.accuracy_card = MetricCard("准确率", "0.00%")
        for card in [self.correct_card, self.wrong_card, self.remaining_card, self.time_card, self.accuracy_card]:
            metrics_row.addWidget(card)
        root_layout.addLayout(metrics_row)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(16)

        self.canvas = GameCanvas()
        self.canvas.hit.connect(self.handle_click)
        body.addWidget(self.canvas, 3)

        leaderboard_panel = QtWidgets.QFrame()
        leaderboard_panel.setObjectName("panel")
        leaderboard_layout = QtWidgets.QVBoxLayout(leaderboard_panel)
        leaderboard_layout.setContentsMargins(14, 14, 14, 14)
        leaderboard_layout.setSpacing(12)

        leaderboard_header = QtWidgets.QHBoxLayout()
        leaderboard_title = QtWidgets.QLabel("排行榜")
        leaderboard_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.clear_button = QtWidgets.QPushButton("清空")
        self.clear_button.clicked.connect(self.clear_leaderboard)
        leaderboard_header.addWidget(leaderboard_title)
        leaderboard_header.addStretch(1)
        leaderboard_header.addWidget(self.clear_button)
        leaderboard_layout.addLayout(leaderboard_header)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["排名", "玩家", "准确率", "成绩", "时间"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        leaderboard_layout.addWidget(self.table)
        body.addWidget(leaderboard_panel, 2)

        root_layout.addLayout(body, 1)
        self.setCentralWidget(root)

    def start_game(self):
        player = self.player_input.text().strip()
        if not player:
            QtWidgets.QMessageBox.warning(self, "提示", "请先输入玩家姓名")
            return
        self.countdown_timer.stop()
        self.correct = 0
        self.wrong = 0
        self.remaining = TOTAL_ROUNDS
        self.seconds_left = self.duration_spin.value()
        self.game_running = True
        self.start_button.setText("重新开始")
        self.apply_difficulty()
        self.canvas.start(self.current_ball_radius(), self.current_move_interval())
        if self.is_countdown_mode():
            self.countdown_timer.start(1000)
        else:
            self.countdown_timer.stop()
        self.refresh_metrics()

    def handle_click(self, is_hit: bool):
        if not self.game_running:
            return
        if is_hit:
            self.correct += 1
            self.hit_sound.play()
        else:
            self.wrong += 1
            self.miss_sound.play()
        if not self.is_countdown_mode():
            self.remaining -= 1
        self.apply_difficulty()
        self.refresh_metrics()
        if not self.is_countdown_mode() and self.remaining == 0:
            self.finish_game()

    def finish_game(self):
        if not self.game_running:
            return
        self.game_running = False
        self.canvas.stop()
        self.countdown_timer.stop()
        accuracy = self.current_accuracy()
        played_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.entries.append(
            ScoreEntry(
                player=self.player_input.text().strip(),
                accuracy=accuracy,
                correct=self.correct,
                wrong=self.wrong,
                played_at=played_at,
            )
        )
        self.entries.sort(key=lambda item: (-item.accuracy, -item.correct, item.wrong, item.played_at))
        self.entries = self.entries[:10]
        self.save_leaderboard()
        self.refresh_leaderboard()
        QtWidgets.QMessageBox.information(
            self,
            "游戏结束",
            f"正确：{self.correct}\n错误：{self.wrong}\n准确率：{accuracy:.2%}",
        )

    def current_accuracy(self) -> float:
        total = self.correct + self.wrong
        return self.correct / total if total else 0.0

    def refresh_metrics(self):
        self.correct_card.set_value(str(self.correct))
        self.wrong_card.set_value(str(self.wrong))
        self.remaining_card.set_value("--" if self.is_countdown_mode() else str(self.remaining))
        self.time_card.set_value(f"{self.seconds_left}s" if self.is_countdown_mode() else "--")
        self.accuracy_card.set_value(f"{self.current_accuracy():.2%}")

    def load_leaderboard(self) -> list[ScoreEntry]:
        if not LEADERBOARD_FILE.exists():
            return []
        try:
            raw_entries = json.loads(LEADERBOARD_FILE.read_text(encoding="utf-8"))
            return [
                ScoreEntry(
                    player=entry.get("player", "匿名"),
                    accuracy=entry["accuracy"],
                    correct=entry["correct"],
                    wrong=entry["wrong"],
                    played_at=entry["played_at"],
                )
                for entry in raw_entries
            ]
        except Exception:
            return []

    def save_leaderboard(self):
        data = [
            {
                "accuracy": entry.accuracy,
                "player": entry.player,
                "correct": entry.correct,
                "wrong": entry.wrong,
                "played_at": entry.played_at,
            }
            for entry in self.entries
        ]
        LEADERBOARD_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def refresh_leaderboard(self):
        self.table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            values = [
                str(row + 1),
                entry.player,
                f"{entry.accuracy:.2%}",
                f"{entry.correct} / {entry.correct + entry.wrong}",
                entry.played_at,
            ]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def on_mode_changed(self, mode: str):
        self.duration_spin.setVisible(mode == "倒计时")
        self.refresh_metrics()

    def is_countdown_mode(self) -> bool:
        return self.mode_combo.currentText() == "倒计时"

    def update_countdown(self):
        self.seconds_left -= 1
        self.refresh_metrics()
        if self.seconds_left <= 0:
            self.finish_game()

    def progress_ratio(self) -> float:
        if self.is_countdown_mode():
            total = max(1, self.duration_spin.value())
            return 1.0 - max(0, self.seconds_left) / total
        played = self.correct + self.wrong
        return min(1.0, played / TOTAL_ROUNDS)

    def current_ball_radius(self) -> int:
        ratio = self.progress_ratio()
        return round(START_BALL_RADIUS - (START_BALL_RADIUS - MIN_BALL_RADIUS) * ratio)

    def current_move_interval(self) -> int:
        ratio = self.progress_ratio()
        return round(1600 - 900 * ratio)

    def apply_difficulty(self):
        self.canvas.set_difficulty(self.current_ball_radius(), self.current_move_interval())

    def clear_leaderboard(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            "清空排行榜",
            "确定清空全部排行榜记录吗？",
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.entries.clear()
        self.save_leaderboard()
        self.refresh_leaderboard()

    def ensure_sound_files(self):
        self.write_tone(HIT_SOUND_FILE, 880, 0.08, 0.28)
        self.write_tone(MISS_SOUND_FILE, 220, 0.12, 0.22)

    def write_tone(self, path: Path, frequency: int, duration: float, volume: float):
        if path.exists():
            return
        sample_rate = 44100
        total_samples = int(sample_rate * duration)
        frames = bytearray()
        for i in range(total_samples):
            envelope = 1.0 - i / total_samples
            sample = int(
                32767
                * volume
                * envelope
                * math.sin(2 * math.pi * frequency * i / sample_rate)
            )
            frames += sample.to_bytes(2, byteorder="little", signed=True)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(frames)

    def build_sound(self, path: Path) -> QtMultimedia.QSoundEffect:
        sound = QtMultimedia.QSoundEffect(self)
        sound.setSource(QtCore.QUrl.fromLocalFile(str(path)))
        sound.setVolume(0.35)
        return sound


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    window = BallClickGame()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
