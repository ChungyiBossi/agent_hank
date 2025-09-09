
from PyQt5.QtCore import QThread, pyqtSignal

import time
import json
import subprocess
import pyttsx3
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
