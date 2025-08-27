from PyQt5.QtWidgets import QApplication, QDialog, QListWidgetItem
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
        self.setFixedSize(935, 472)

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
        user_item = QListWidgetItem(f"你說: {message}")
        user_item.setFont(QFont("Arial", 12))
        user_item.setBackground(QColor("#CDE7CD"))
        user_item.setTextAlignment(Qt.AlignLeft)
        self.history_widget.addItem(user_item)

    def record_agent_response(self, user_message):
        # 預留一個空 item
        self.ai_item = QListWidgetItem("")
        self.ai_item.setFont(QFont("Arial", 12))
        self.ai_item.setBackground(QColor("#FFFFFF"))
        self.ai_item.setTextAlignment(Qt.AlignLeft)
        self.history_widget.addItem(self.ai_item)

        # 啟動背景 thread
        self.worker = ChatWorker(
            self.chatbot_client, self.chat_history, user_message)
        self.worker.new_token.connect(self.update_ai_item)   # 即時更新
        self.worker.finished.connect(self.finish_ai_item)    # stream 結束
        self.worker.start()

    def update_ai_item(self, token):
        """動態更新 AI 回覆"""
        if self.ai_item:
            self.ai_item.setText(self.ai_item.text() + token)
            if self.ai_item.text():  # 有東西
                self.ai_item.setBackground(QColor("#FFEACF"))
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
