# =====================================================================
# 測試專用區：直接單獨執行此檔案時會跑這裡
# =====================================================================
import threading
import socket
import time

from emg_client_service import EMGTCPClient
if __name__ == "__main__":
    import time
    import sys
    from PySide6.QtCore import QCoreApplication

    # 建立一個基礎的 PySide6 事件循環，否則 Signal 機制會無法運作
    app = QCoreApplication(sys.argv)

    # 1. 宣告你的 Client，連線到剛剛開好的 localhost:12345
    test_client = EMGTCPClient(host='localhost', port=12345)


    # 2. 定義一個簡單的接收函式，用來把你的廣播訊號印在螢幕上
    def print_status(msg):
        print(f"[GUI Status Notification] -> {msg}")


    # 3. 綁定訊號
    test_client.status_updated.connect(print_status)

    # 4. 啟動連線與接收
    test_client.start()


    # 5. 每隔 1 秒鐘，模擬 GUI 來呼叫 get_latest_data()，看看有沒有成功抓到資料
    def simulate_gui_polling():
        for _ in range(10):  # 測試抓取 10 次
            time.sleep(1)
            data = test_client.get_latest_data()
            if data:
                print(f"\n[GUI Timer Triggereded] Extracted {len(data)} frames from buffer.")
                print(f"Latest frame shape: {data[-1].shape}")  # 檢查是不是 (32, 18)
                print(f"First channel sample values: {data[-1][0, :5]}")  # 印出第1通道前5個點驗證
            else:
                print(".", end="", flush=True)

        print("\nTesting complete. Stopping client...")
        test_client.stop()
        sys.exit()


    # 開啟另一個執行緒來模擬 GUI 抓資料，避免卡死
    threading.Thread(target=simulate_gui_polling, daemon=True).start()

    # 讓 PySide6 保持運作
    sys.exit(app.exec())