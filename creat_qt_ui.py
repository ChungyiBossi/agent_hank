from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QDialog, QListWidgetItem,
    QWidget, QLabel, QHBoxLayout
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5 import uic

import sys
from openai import OpenAI
from lipsync_player import LipSyncPlayer
from cloud_keys import OPENAI_API_KEY
import pyttsx3

import time
import json
import subprocess

# -----------------------
# 背景 Worker：
# ChatWorker: Get AI Streaming Response
# TTS Worker: AI response to speech
# LipSync Worker: wav to lipsync.json
# LipSyncPlayer: play wav + lipsync
# -----------------------


class LipSyncWorker(QThread):
    # 當分析完成後，發出嘴型資料
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, wav_file, parent=None, lipsync_data=None):
        super().__init__(parent)
        self.wav_file = wav_file
        self.lipsync_data = lipsync_data

    def run(self):
        try:
            # 呼叫 rhubarb CLI
            json_name = self.wav_file.replace(".wav", "_lipsync.json")
            result = subprocess.run(
                [
                    ".\\Rhubarb-Lip-Sync\\rhubarb.exe",
                    "-f", "json",               # 輸出格式 JSON
                    self.wav_file,              # 音檔路徑
                    "-o", json_name        # 輸出檔案
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                self.error.emit(result.stderr)
                return

            # 讀取 lipsync.json
            print(f"[Lipsync] Reading {json_name}.")
            with open(json_name, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 把結果傳回主執行緒
            self.finished.emit(data["mouthCues"])

        except Exception as e:
            self.error.emit(str(e))


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
