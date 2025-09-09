import sys
import json
import time
from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import os


class LipSyncPlayer(QWidget):
    finished = pyqtSignal()

    def __init__(
        self,
        base_image,
        wav_file="",
        avatar_pixmap=None,
        mouth_prefix="./images/hank/hank"
    ):
        super().__init__()

        # QLabel 顯示角色立繪 + 嘴型
        if avatar_pixmap:
            self.label = avatar_pixmap
        else:  # Unittest
            self.setWindowTitle("Lip Sync Demo")
            self.label = QLabel(self)
            self.label.setFixedSize(400, 400)
            self.label.setScaledContents(True)

            layout = QVBoxLayout()
            layout.addWidget(self.label)
            self.setLayout(layout)

        # 嘴型資料
        self.last_shape = "X"  # 初始嘴型可用 X (閉嘴)
        self.lipsync_data = list()

        # 嘴型圖片 cache
        self.mouth_images = {
            shape: QPixmap(
                f"{mouth_prefix}_{shape}.png") for shape in "ABCDEFGHX"
        }

        # 立繪底圖
        self.base_pixmap = QPixmap(base_image)
        self.default_pixmap = self.merge_pixmaps(
            base=QPixmap(base_image),
            overlay=self.mouth_images["X"],  # 初始嘴型 X (閉嘴)
            x=100, y=250
        )
        self.label.setPixmap(self.default_pixmap)

        # 音檔播放器
        wav_file = os.path.abspath(wav_file)
        self.player = QMediaPlayer()
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(wav_file)))
        self.player.setVolume(100)

        # 計時器控制嘴型
        self.start_time = None
        self.timer = QTimer(self)
        self.timer.setInterval(30)  # 每 30ms 更新一次
        self.timer.timeout.connect(self.update_mouth)

        # 嘴型 + 聲音呈現結束
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

    def update_lipsync_data(self, lipsync_data, wav_file):
        print("update_lipsync_data called")
        self.lipsync_data = lipsync_data
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(wav_file)))
        self.last_shape = "X"
        self.start_time = None

    def start(self):
        # print("start called")
        self.start_time = time.time()
        self.player.play()
        self.timer.start()

    def update_mouth(self):
        # print("update_mouth called")
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
            merged = self.merge_pixmaps(
                base=merged,
                overlay=self.mouth_images[shape],
            )
        else:
            print(f"Warning: No image for shape '{shape}'")
            merged = self.merge_pixmaps(
                base=merged,
                overlay=self.mouth_images["X"],  # Default to closed mouth
            )

        self.label.setPixmap(merged)

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.timer.stop()
            self.finished.emit()  # 發出結束訊號

    def merge_pixmaps(self, base, overlay, x=100, y=250):
        """將 overlay 疊加到 base 的 (x, y) 位置"""
        painter = QPainter(base)
        painter.drawPixmap(x, y, overlay)
        painter.end()
        return base


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = LipSyncPlayer(
        wav_file="",
        base_image="images/hank/hank_no_mouth.png",
        mouth_prefix="images/hank/hank"
    )

    lip_data = json.load(
        open("test_code/test_lipsync.json", "r", encoding="utf-8"))

    print(lip_data["mouthCues"])
    window.update_lipsync_data(
        lipsync_data=lip_data["mouthCues"],
        wav_file="test_code/test_audio.wav"
    )
    window.show()
    window.start()

    sys.exit(app.exec_())
