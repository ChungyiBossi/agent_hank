from PyQt5.QtWidgets import (
    QApplication, QDialog, QListWidgetItem,
    QWidget, QLabel, QHBoxLayout
)
from PyQt5.QtGui import QFont, QColor
from PyQt5 import uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import sys
from openai import OpenAI
from cloud_keys import OPENAI_API_KEY


# -----------------------
# 背景 Worker：收 AI stream
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
        self.chatbot_client = OpenAI(api_key=OPENAI_API_KEY)
        self.chat_history = []

        # AI 回覆 item（暫存）
        self.ai_item = None

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
            self.chatbot_client, self.chat_history, user_message)
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
        """動態更新 AI 回覆到泡泡 QLabel"""
        if self.ai_label:
            # 1. 文字追加到 QLabel
            self.ai_label.setText(self.ai_label.text() + token)

            # 2. 強制重新計算尺寸
            self.ai_label.adjustSize()

            # 3. 根據尺寸更新 QListWidgetItem 高度
            self.ai_item.setSizeHint(self.ai_label.sizeHint())

            # 4. 自動捲動到底
            self.history_widget.scrollToBottom()

    def finish_ai_item(self, full_text):
        """stream 結束"""
        print("完整回覆：", full_text)
        print(f"Update History Size:{len(self.chat_history)}")
        # list不需要更新，初始化用的chat_history會直接被reference


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AgentApp()
    window.show()
    sys.exit(app.exec_())
