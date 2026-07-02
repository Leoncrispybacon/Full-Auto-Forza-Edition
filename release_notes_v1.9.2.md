**FAFE v1.9.2**

**Improved**
- F9 / F10 / F12 hotkeys are more reliable while the game is focused or running borderless. Custom hotkey bindings still work.
- OCR is off by default again to avoid game stutter. If you turn OCR on, FAFE now auto-tunes OCR settings based on your CPU, with a lighter preset for Intel 12th / 13th / 14th gen and Core Ultra CPUs.
- Unlock / Delete: the middle-column car amount can now be typed directly, not only changed with +/-.
- Race, Buy, and Wheelspin count fields now persist between launches.
- Update checking is restored. FAFE only checks the GitHub release version and opens the releases page; it does not download or install updates itself.

**Fixes**
- Unlock Spin Wheel now starts correctly again. A stale unused dependency could stop the Unlock module from loading.
- Unlock / Delete setup panels no longer appear empty after editing the car amount selector.
- Auto Wheelspin now checks the final-collect prompt only on the last requested spin, avoiding false matches on earlier spins.
- Background keep-alive now sends a smaller fake-active signal and skips it while the game is already foreground, reducing the chance of tiny repeated stutters.
- Letterbox / pillarbox cropping is now enabled only for functions where it is safe, so dark garage or menu screens are less likely to be mistaken for black bars.

**Build**
- This is the public teaser build. Full Auto remains in preview / coming-soon state here.
- The installer version is now `1.9.2`.

Download: `FAFE_Setup.exe` below. Close FAFE before installing over an older version.

---

**FAFE v1.9.2**

**改善**
- F9 / F10 / F12 全域快捷鍵在遊戲前景或無邊框模式下更穩定。使用者自訂快捷鍵仍會正常套用。
- OCR 預設再次關閉，以避免遊戲卡頓。若手動開啟 OCR，FAFE 會依 CPU 自動套用設定；Intel 12 / 13 / 14 代與 Core Ultra 會使用較低負載的預設。
- 解鎖 / 刪除：中間欄車輛數量現在可直接輸入，不再只能用 +/- 調整。
- 賽車、購買、轉輪的數量設定現在會在重新啟動後保留。
- 更新檢查已恢復。FAFE 只會檢查 GitHub 最新版本並開啟 releases 頁面，不會自行下載或安裝更新。

**修正**
- 修正「解鎖轉輪」可能無法開始的問題。舊的未使用依賴會讓解鎖模組載入失敗。
- 修正調整車輛數量選擇器後，解鎖 / 刪除設定面板可能變空白的問題。
- 自動轉輪現在只會在最後一次轉輪時檢查 final collect 提示，避免前面的轉輪被誤判。
- 背景 keep-alive 現在只送出更小的假啟用訊號，且遊戲已在前景時會跳過，降低固定間隔小卡頓的機率。
- 黑邊裁切現在只在安全的功能中啟用，減少車庫或深色選單被誤判為黑邊的情況。

**建置**
- 這是公開 teaser 版本。Full Auto 在此版本仍為預覽 / coming soon 狀態。
- 安裝程式版本已更新為 `1.9.2`。

下載：下方的 `FAFE_Setup.exe`。更新前請先關閉 FAFE，再安裝覆蓋舊版本。
