## PyQt

1. 安裝pyQt套件工具
    > pip install pyqt5 pyqt5-tools
2. 尋找Qt Designer
   ![](images/find_designer.png)
3. 執行版面編輯工具，並匯出xxx.ui檔案
    * 利用layout管理自適應規則。
    * QDialog本身包含layout，對應視窗大小的縮放。
4. 撰寫Python腳本，設計互動邏輯。


## Agent Work Flow

主體為 **Agent App** 負責UI呈現與訊息更新
1. 輸入user_message並送出
2. 透過 **ChatWorker** 從LLM取得串流回應
    * 累積至多一句的token。
    * 將累積成一句的內容轉送給**TTSWorker**。
    * 負責更新歷史訊息。
3. **TTSWorker** 負責生成聲音檔
    * 聲音檔依句子等級生成
    * 生成後提交完成訊息丟還給**Agent App**