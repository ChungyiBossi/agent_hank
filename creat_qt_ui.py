from PyQt5.QtWidgets import QApplication, QDialog, QListWidgetItem
from PyQt5.QtGui import QFont, QColor, QIcon
from PyQt5 import uic
from PyQt5.QtCore import Qt
import sys
# from resources_rc import *  # qrc 資源檔，包含 agent.png 與 user.png


class MyApp(QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("agent.ui", self)

        # 連接送出按鈕
        self.send_btn.clicked.connect(self.send_message)

        # 調整每個聊天項目間距
        self.history_widget.setSpacing(5)

    def send_message(self):
        text = self.user_input.text().strip()
        if text:
            # -------------------------
            # 使用者訊息（右邊，綠色，帶頭像）
            # -------------------------
            user_item = QListWidgetItem(f"你說  '{text}' ")
            # user_item.setBackground(QColor("#52C252"))
            user_item.setFont(QFont("Arial", 12))
            user_item.setIcon(QIcon(":/images/user.png"))
            user_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.history_widget.addItem(user_item)

            # -------------------------
            # AI 回覆（左邊，白色，帶頭像）
            # -------------------------
            ai_text = f"Agent: '{text}' "
            ai_item = QListWidgetItem(f"  {ai_text}  ")
            # ai_item.setBackground(QColor("#E48787"))
            ai_item.setFont(QFont("Arial", 12))
            ai_item.setIcon(QIcon(":/images/agent.png"))
            ai_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)
            self.history_widget.addItem(ai_item)

            # 自動捲動到底
            self.history_widget.scrollToBottom()

            # 清空輸入框
            self.user_input.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())
