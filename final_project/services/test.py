# =====================================================================
# 測試專用區：直接單獨執行此檔案時會跑這裡
# =====================================================================
import sys
from PySide6.QtCore import QCoreApplication, QTimer
from TCP_client_service import EMGTCPClient  # 請確保檔名與你的 Client 檔名一致

# 全域變數，用來紀錄模擬 GUI 測試的時間
elapsed_seconds = 0

if __name__ == "__main__":
    # 建立 PySide6 事件循環（這是 QTimer 能運作的核心基礎）
    app = QCoreApplication(sys.argv)

    # 1. 初始化你的新版非阻塞 Client
    test_client = EMGTCPClient(host='localhost', port=12345)


    # 2. 綁定狀態通知訊號
    def print_status(msg):
        print(f"[GUI Status Notification] -> {msg}")


    test_client.status_updated.connect(print_status)

    # 3. 進行第一次連線嘗試
    test_client.connect()


    # 4. 模擬QTimer
    def simulate_gui_timer_loop():
        # ❶ 呼叫非阻塞接收。當目前狀態為斷線時，此函式內部會直接 return，不會像之前一樣自作聰明地去重連。
        test_client.receive_data()


    gui_timer = QTimer()
    gui_timer.timeout.connect(simulate_gui_timer_loop)
    gui_timer.start(30)  # 精準模擬組員要求的 30 毫秒刷新率


    # 5. 建立第二個定時器：每隔 1 秒鐘把資料印出來，測試 30 秒後自動結束
    def print_every_second_results():
        global elapsed_seconds
        elapsed_seconds += 1

        # 模擬組員每秒去拿這 1 秒內累積的所有數據
        data = test_client.get_latest_data()

        # 透過 data.shape[1] 檢查這 1 秒內是否有成功重組出新的取樣點
        if data.shape[1] > 0:
            print(
                f"\n[GUI 1s Monitor - {elapsed_seconds}s/30s] -> Successfully extracted chunk with shape {data.shape} from buffer.")
            print(f"  - Total samples available in this chunk: {data.shape[1]}")
            print(f"  - First channel first 5 samples values: {data[0, :5]}")
        else:
            # 如果 Server 播放完畢，接下來的秒數因為已經徹底斷線且不自動重連，會持續印出點點，提示目前已經沒有新資料
            print(".", end="", flush=True)

        # 測試 30 秒後自動關閉測試程式
        if elapsed_seconds >= 30:
            print("\n\n30 seconds test completed. Disconnecting client and exiting...")
            test_client.disconnect()
            app.quit()  # 安全結束 PySide6 事件循環


    monitor_timer = QTimer()
    monitor_timer.timeout.connect(print_every_second_results)
    monitor_timer.start(1000)  # 每 1000 毫秒（1秒）執行一次

    print("Test environment initialized. Starting 30-second non-blocking emulation...")
    print("Behavior style: Exercise standard (Halts permanently when server playback finishes).")
    print("Make sure your TCP_Server is running!")

    # 讓 PySide6 保持運作，並啟動所有的 QTimer
    sys.exit(app.exec())