from PyQt5.QtWidgets import QApplication, QLabel, QWidget
from PyQt5.QtWidgets import (
    QApplication, QDialog, QListWidgetItem,
    QWidget, QLabel, QHBoxLayout
)
from PyQt5 import uic

import sys
from openai import OpenAI
from lipsync_player import LipSyncPlayer
from workers import ChatWorker, TTSWorker, LipSyncWorker
from cloud_keys import OPENAI_API_KEY

# -----------------------
# 主程式 UI
# -----------------------


class AgentApp(QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("agent.ui", self)
        self.send_btn.clicked.connect(self.record_conversation)
        self.clear_btn.clicked.connect(self.clear_input)
        self.history_widget.setSpacing(5)

        # OpenAI Client
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        self.chat_history = []
        self.partial_sentence = ""  # 暫時存放成句前的tokens

        # TTS
        # self.tts_engine = pyttsx3.init()
        self.tts_workers = []  # 存所有活著的 worker
        self.tts_queue = []      # 句子 + 音檔檔名

        # LipSync cues
        self.lipsync_workers = []
        self.lipsync_data_queue = []  # 存放待處理的音檔

        # LipSync Player
        self.lip_player = LipSyncPlayer(
            avatar_pixmap=self.agent_pixmap,
            base_image="images/hank/hank_no_mouth.png",
            mouth_prefix="images/hank/hank"
        )
        self.lip_player.finished.connect(self.play_next_in_queue)  # 播完一個接著播下一個

    def clear_input(self):
        self.user_input.clear()
        self.history_widget.clear()
        self.chat_history.clear()

    def record_conversation(self):
        text = self.user_input.text().strip()
        if text:
            self.record_user_message(text)
            self.record_agent_response(text)
            self.user_input.clear()
            self.history_widget.scrollToBottom()

    def record_user_message(self, message):
        self.add_message(f"你說: {message}", sender="user")

    def record_agent_response(self, user_message):
        self.ai_item = self.add_message("", sender="agent")

        # 啟動背景 thread
        self.worker = ChatWorker(
            self.openai_client, self.chat_history, user_message)
        self.worker.new_token.connect(self.collect_response_tokens)   # 即時更新
        self.worker.finished.connect(self.finish_ai_item)    # stream 結束
        self.worker.start()

    def add_message(self, message, sender="user"):
        """
        sender: "user" → 綠色泡泡
                "agent" → 白色泡泡
        """
        item = QListWidgetItem(self.history_widget)
        widget = QWidget()
        layout = QHBoxLayout()

        # 文字泡泡
        label = QLabel(message)
        label.setWordWrap(True)
        label.setMinimumHeight(25)

        # 顏色依 sender 區分
        if sender == "user":
            label.setStyleSheet("background-color: #CDE7CD;")
        else:
            label.setStyleSheet("background-color: #FFFFFF;")
            self.ai_label = label  # 暫存 AI 的 QLabel

        layout.addWidget(label)
        widget.setLayout(layout)

        item.setSizeHint(widget.sizeHint())
        self.history_widget.addItem(item)
        self.history_widget.setItemWidget(item, widget)
        self.history_widget.scrollToBottom()
        return item

    def collect_response_tokens(self, token):
        # 累積文字
        self.partial_sentence += token

        # 判斷是否一句結束
        if token in ["。", "，", "！", "？", ".", "!", "?"]:
            sentence = self.partial_sentence.strip()
            self.partial_sentence = ""
            self.generate_sentence_speech(sentence)   # 丟去生成音檔

    def finish_ai_item(self, full_text):
        """stream 結束"""
        print("完整回覆：", full_text)
        print(f"Update History Size:{len(self.chat_history)}")
        # list不需要更新，初始化用的chat_history會直接被reference

    def generate_sentence_speech(self, sentence):
        tts_worker = TTSWorker(sentence)
        tts_worker.done.connect(
            lambda filename, w=tts_worker, s=sentence:
            self.on_tts_done(filename, s, w))
        tts_worker.start()
        self.tts_workers.append(tts_worker)

    def on_tts_done(self, filename, sentence, worker):
        # 加入播放佇列
        self.tts_queue.append((filename, sentence))
        self.tts_workers.remove(worker)
        worker.deleteLater()

        # 接著丟給 LipSyncWorker
        lipsync_worker = LipSyncWorker(filename)
        lipsync_worker.finished.connect(
            lambda lipsync_data,  w=lipsync_worker:
            self.on_lipsync_done(lipsync_data, w)
        )
        lipsync_worker.start()
        self.lipsync_workers.append(lipsync_worker)

    def on_lipsync_done(self, lipsync_data, worker):
        self.lipsync_data_queue.append(lipsync_data)  # 放入嘴型佇列
        self.lipsync_workers.remove(worker)  # 移除 worker
        worker.deleteLater()
        self.play_next_in_queue()  # 嘗試播放下一個

    def play_next_in_queue(self):
        # 如果正在撥放就不觸發
        is_player_idle = self.lip_player.is_player_idle()
        if not is_player_idle:
            print("Player is busy, wait for next signal.")
            return

        if not self.tts_queue:  # 無聲音檔時離開
            print("No TTS data!")
            return
        if not self.lipsync_data_queue:  # 無嘴形時離開
            print("No lipsync data!")
            return

        # 播音檔
        filename, sentence = self.tts_queue.pop(0)
        lipsync_data = self.lipsync_data_queue.pop(0)
        self.update_ai_ui(sentence)  # 顯示句子
        self.lip_player.update_lipsync_data(
            lipsync_data=lipsync_data,
            wav_file=filename
        )
        self.lip_player.start()
        print(f"[Play] {filename}")

    def update_ai_ui(self, next_sentence):
        # 1. 顯示句子（與聲音同步）
        self.ai_label.setText(self.ai_label.text() + next_sentence)
        # 2. 強制重新計算尺寸
        self.ai_label.adjustSize()
        # 3. 根據尺寸更新 QListWidgetItem 高度
        self.ai_item.setSizeHint(self.ai_label.sizeHint())
        # 4. 自動捲動到底
        self.history_widget.scrollToBottom()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AgentApp()
    window.show()
    sys.exit(app.exec_())
