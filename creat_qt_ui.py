from PyQt5.QtWidgets import (
    QApplication, QDialog, QListWidgetItem,
    QWidget, QLabel, QHBoxLayout
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QUrl, QThread, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5 import uic

import sys
from openai import OpenAI
from cloud_keys import OPENAI_API_KEY
import pyttsx3

import time
import os
# -----------------------
# 背景 Worker：
# ChatWorker: Get AI Streaming Response
# TTS Worker: AI response to speech
# -----------------------


class ChatWorker(QThread):
    # 兩組Signal渠道
    new_token = pyqtSignal(str)   # 每次收到 token 就丟給 UI
    finished = pyqtSignal(str)    # stream 結束後丟完整文字

    def __init__(self, client, history, new_sentence):
        super().__init__()
        self.client = client
        self.history = history
        self.new_sentence = new_sentence

    def run(self):
        # 紀錄問句
        self.history.append({"role": "user", "content": self.new_sentence})
        stream = self.client.chat.completions.create(
            model="gpt-4",
            messages=self.history,
            stream=True,
        )

        response = []
        for chunk in stream:
            new_word = chunk.choices[0].delta.content
            if new_word:
                response.append(new_word)
                self.new_token.emit(new_word)  # 丟給 UI 更新
        full_reply = "".join(response)
        self.history.append({"role": "assistant", "content": full_reply})
        self.finished.emit(full_reply)


class TTSWorker(QThread):
    done = pyqtSignal(str)   # 音檔生成完後，把句子送回去顯示

    def __init__(self, text):
        super().__init__()
        self.text = text
        self.engine = pyttsx3.init()

    def run(self):

        timestamp = int(time.time() * 1000)  # 毫秒級時間戳
        filename = f"tts_files/temp_{timestamp}.wav"
        self.engine.save_to_file(self.text, filename)
        self.engine.runAndWait()   # 執行音訊檔案生成
        self.done.emit(filename)   # 音檔生成完成


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
        self.player = QMediaPlayer()
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

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
        self.worker.new_token.connect(self.update_ai_response)   # 即時更新
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
        label.setFont(QFont("Arial", 12))

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

    def update_ai_response(self, token):
        # 累積文字
        self.partial_sentence += token

        # 判斷是否一句結束
        if token in ["。", "，", "！", "？", ".", "!", "?"]:
            sentence = self.partial_sentence.strip()
            self.partial_sentence = ""
            self.send_sentence_to_tts(sentence)   # 丟去生成音檔

    def finish_ai_item(self, full_text):
        """stream 結束"""
        print("完整回覆：", full_text)
        print(f"Update History Size:{len(self.chat_history)}")
        # list不需要更新，初始化用的chat_history會直接被reference

    def send_sentence_to_tts(self, sentence):
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
        # 如果 player 沒在播，就開始播放
        if self.player.state() != QMediaPlayer.PlayingState:
            self.play_next_in_queue()

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.play_next_in_queue()

    def play_next_in_queue(self):
        if not self.tts_queue:
            return
        filename, sentence = self.tts_queue.pop(0)

        # 1. 顯示句子（與聲音同步）
        self.ai_label.setText(self.ai_label.text() + sentence)
        # 2. 強制重新計算尺寸
        self.ai_label.adjustSize()
        # 3. 根據尺寸更新 QListWidgetItem 高度
        self.ai_item.setSizeHint(self.ai_label.sizeHint())
        # 4. 自動捲動到底
        self.history_widget.scrollToBottom()
        # 播音檔
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(filename)))
        self.player.play()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AgentApp()
    window.show()
    sys.exit(app.exec_())
