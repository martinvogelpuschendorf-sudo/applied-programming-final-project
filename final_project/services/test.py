# =====================================================================
# 測試專用區
# =====================================================================
import sys
from PySide6.QtCore import QCoreApplication, QTimer
from TCP_client_service import EMGTCPClient

elapsed_seconds = 0

if __name__ == "__main__":
    # 建立 PySide6 事件循環
    app = QCoreApplication(sys.argv)

    # 1. 初始化非阻塞 Client
    test_client = EMGTCPClient(host='localhost', port=12345)


    # 2. 綁定狀態通知訊號
    def print_status(msg):
        print(f"[GUI Status Notification] -> {msg}")


    test_client.status_updated.connect(print_status)

    # 3. 進行第一次連線嘗試
    test_client.connect()


    # 4. 模擬 30ms 定時器 (驅動網路接收)
    def simulate_gui_timer_loop():
        test_client.receive_data()


    gui_timer = QTimer()
    gui_timer.timeout.connect(simulate_gui_timer_loop)
    gui_timer.start(30)  # 每 30 毫秒刷新一次


    # 5. 建立監控定時器（每 1 秒執行一次）
    def print_every_second_results():
        global elapsed_seconds
        elapsed_seconds += 1

        # 💡 【模擬即時繪圖】：每秒去拿這 1 秒內累積的最新即時數據
        # 呼叫此函式後，Model 內部的 live_pointer 會往前推，實現隨拿隨清
        data = test_client.get_latest_live_data()

        if data.shape[1] > 0:
            print(
                f"\n[Live Monitor - {elapsed_seconds}s/30s] -> Successfully extracted chunk with shape {data.shape} from live buffer.")
            print(f"  - New samples available in this second: {data.shape[1]}")
            print(f"  - First channel first 5 samples values: {data[0, :5]}")
        else:
            print(".", end="", flush=True)

        # 測試 30 秒後自動結束，並觸發離線歷史數據檢查
        if elapsed_seconds >= 30:
            print("\n\n30 seconds test completed. Stopping stream to simulate offline inspection...")

            # 先主動斷線，模擬串流結束
            test_client.disconnect()

            print("-" * 60)
            # 💡 【模擬離線分析】：向Model調閱連線期間「完整的歷史數據」
            print("[Offline Inspection Mode] -> Simulating Student 3 retrieving historical data...")
            try:
                offline_data = test_client.get_all_offline_data()
                print(f"  -> SUCCESS! Retrieved full historical data matrix.")
                print(
                    f"  -> Final Matrix Shape: {offline_data.shape} (Channels: {offline_data.shape[0]}, Total Samples: {offline_data.shape[1]})")
            except Exception as e:
                print(f"  -> ERROR! Could not retrieve offline data: {e}")
            print("-" * 60)

            app.quit()  # 安全結束事件循環


    monitor_timer = QTimer()
    monitor_timer.timeout.connect(print_every_second_results)
    monitor_timer.start(1000)  # 每 1000 毫秒（1秒）執行一次

    print("Test environment initialized. Starting 30-second non-blocking emulation...")
    print("Make sure your TCP_Server is running!")

    sys.exit(app.exec())