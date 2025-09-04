import sys
import json
import time
from PyQt5.QtCore import QTimer, QUrl
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import os


class LipSyncPlayer(QWidget):
    def __init__(
        self,
        wav_file,
        lipsync_json,
        base_image,
        mouth_prefix="./images/hank/hank"
    ):
        super().__init__()
        self.setWindowTitle("Lip Sync Demo")

        # QLabel 顯示角色立繪 + 嘴型
        self.label = QLabel()
        self.label.setFixedSize(400, 400)
        self.label.setScaledContents(True)
        self.last_shape = "X"  # 初始嘴型可用 X (閉嘴)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        # 立繪底圖
        self.base_pixmap = QPixmap(base_image)

        # 嘴型資料
        with open(lipsync_json, "r", encoding="utf-8") as f:
            self.lipsync_data = json.load(f)["mouthCues"]

        # 嘴型圖片 cache
        self.mouth_images = {shape: QPixmap(
            f"{mouth_prefix}_{shape}.png") for shape in "ABCDEFGHX"}

        # 音檔播放器
        wav_file = os.path.abspath(wav_file)
        self.player = QMediaPlayer()
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(wav_file)))
        self.player.setVolume(100)

        # 計時器控制嘴型
        self.start_time = None
        self.timer = QTimer(self)
        self.timer.setInterval(10)  # 每 10ms 更新一次
        self.timer.timeout.connect(self.update_mouth)

    def start(self):
        self.start_time = time.time()
        self.player.play()
        self.timer.start()

    def update_mouth(self):
        if not self.start_time:
            return

        current_time = time.time() - self.start_time
        shape = self.last_shape
        for cue in self.lipsync_data:
            if cue["start"] <= current_time < cue["end"]:
                shape = cue["value"]
                break
        self.last_shape = shape

        print(f"Time: {current_time:.2f}, Shape: {shape}")
        # 疊圖
        merged = QPixmap(self.base_pixmap)  # 複製底圖
        if shape in self.mouth_images:
            painter = QPainter(merged)
            # 調整嘴巴位置 (x, y)
            painter.drawPixmap(100, 250, self.mouth_images[shape])
            painter.end()

        self.label.setPixmap(merged)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = LipSyncPlayer(
        wav_file="test_code/test_audio.wav",
        lipsync_json="test_code/test_lipsync.json",
        base_image="images/hank/hank_no_mouth.png",
        mouth_prefix="images/hank/hank"
    )
    window.show()
    window.start()

    sys.exit(app.exec_())
