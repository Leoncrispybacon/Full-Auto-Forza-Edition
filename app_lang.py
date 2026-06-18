# ============================================================
#  app_lang.py — GUI string translations for forza_app
#  Separate from lang.py (which serves the terminal scripts)
#  Supports: English (en), Traditional Chinese (zh-tw)
# ============================================================

STRINGS = {

    # ── Window / tabs ─────────────────────────────────────────
    "app_title": {
        "en":    "FAFE",
        "zh-tw": "FAFE",
    },
    "support_thanks": {
        "en":    "If FAFE saves you time, a small tip helps keep it maintained. Thank you!",
        "zh-tw": "如果 FAFE 為你節省了時間，小額贊助能幫助它持續維護。感謝你！",
    },
    "support_jkopay": {
        "en":    "JKOPAY — click to tip",
        "zh-tw": "街口支付（點擊贊助）",
    },
    "support_btn": {
        "en":    "Support Me",
        "zh-tw": "支持我",
    },
    "label_accent_color": {
        "en":    "Accent color",
        "zh-tw": "強調色",
    },
    "tab_race": {
        "en":    "🏁  Race Auto",
        "zh-tw": "🏁  自動掛機刷技術點",
    },
    "race_description": {
        "en":    "AFK-races an EventLab event for skill points — holds W the whole way and restarts each time.\n\nBefore you start:\n•  Be in the car you want to race with.\n•  Make sure your last-played EventLab event is the one you want to grind.\n\nThen either stay on the main menu (FAFE drives to your last event and back) or stop on the Start Race screen yourself. FAFE detects which screen you're on and takes over — it detects the Start Race and race-end screens; the rest is timed.",
        "zh-tw": "在 EventLab 賽事中掛機刷技術點——全程按住 W，每場結束自動重開。\n\n開始前：\n•  先進入你要掛機使用的車輛。\n•  確認你上次遊玩的 EventLab 賽事就是你想刷的地圖。\n\n接著你可以停在主選單（FAFE 會自動前往你上次的賽事並返回），或自行停在開始賽事畫面。FAFE 會偵測你所在的畫面並接手——它偵測開始賽事與賽事結束畫面，其餘以定時操作。",
    },
    "tab_mastery": {
        "en":    "⭐  Auto Unlock 22B",
        "zh-tw": "⭐  自動解鎖22B轉輪",
    },
    "mastery_description": {
        "en":    "Unlocks the mastery tree on every 22B-STi in your garage, one car at a time.\n\nBefore you start:\n•  Be in your My Home garage (not the Horizon Festival map menu).\n•  Make sure the newest 22B in the top-left is brand new.\n\nThe tool snakes downward through the grid, processing each car automatically.",
        "zh-tw": "自動為車庫中每一輛 22B-STi 解鎖熟練度樹，一輛接一輛。\n\n開始前：\n•  停在我的住所裡的車庫（非大世界選單）。\n•  確認左上角最新的 22B 是全新的。\n\n程式會以蛇行方式往下遍歷整個車庫，自動處理每一輛車。",
    },

    "tab_buy": {
        "en":    "🛒  Auto Buy 22B-STi",
        "zh-tw": "🛒  自動購買22B-STi",
    },
    "buy_description": {
        "en":    "Purpose-built to farm the Subaru Impreza 22B-STi.\n\nStay on the main menu and FAFE navigates there on its own:\nCollection Journal → Discover Japan / Master Explorer → Car Collection → Subaru → 22B-STi\nIt buys the set number of times, then returns to the main menu.\n\nYou can also position on the 22B-STi yourself and press Start — the buy macro runs from wherever you are.",
        "zh-tw": "專為刷取 Subaru Impreza 22B-STi 設計。\n\n停在主選單即可，FAFE 會自動前往：\n收藏日記 → 探索大師 → 車輛收藏 → Subaru → 22B-STi\n購買指定次數後返回主選單。\n\n你也可以自行停在 22B-STi 畫面再按開始，購買巨集會在目前畫面執行。",
    },
    "status_starting_buy": {
        "en":    "Starting Auto Buy...",
        "zh-tw": "正在啟動自動購買...",
    },
    "buy_running": {
        "en":    "Auto Buy started.",
        "zh-tw": "自動購買已啟動。",
    },
    "buy_loop": {
        "en":    "Loop",
        "zh-tw": "循環",
    },

    # ── Buy template labels (optional menu-navigation) ─────────
    "buy_tpl_collection_log": {
        "en":    "Collection Log tile (main menu)",
        "zh-tw": "收藏日記圖塊（主選單）",
    },
    "buy_tpl_discover_japan": {
        "en":    "Discover Japan / Master Explorer card",
        "zh-tw": "探索大師卡片",
    },
    "buy_tpl_car_collection": {
        "en":    "Car Collection tile",
        "zh-tw": "車輛收藏圖塊",
    },
    "buy_tpl_subaru": {
        "en":    "Subaru brand tile (brand view)",
        "zh-tw": "Subaru 車廠圖塊（車廠檢視）",
    },
    "buy_tpl_target_car": {
        "en":    "Target car tile (e.g. Impreza 22B-STi)",
        "zh-tw": "目標車輛圖塊（例：Impreza 22B-STi）",
    },
    # ── Buy menu-navigation log messages ──────────────────────
    "log_buy_nav_begin": {
        "en":    "Main menu detected — navigating to the Car Collection…",
        "zh-tw": "偵測到主選單 — 正在前往車輛收藏…",
    },
    "log_buy_nav_skip": {
        "en":    "  (buy navigation templates not captured — running the macro where you are)",
        "zh-tw": "  （未擷取購買導航樣本 — 將直接在目前畫面執行巨集）",
    },
    "log_buy_nav_detected": {
        "en":    "  ✓ {label} ({conf}) — {secs}s",
        "zh-tw": "  ✓ {label}（{conf}）— {secs} 秒",
    },
    "log_buy_nav_click": {
        "en":    "  → click {label}",
        "zh-tw": "  → 點擊 {label}",
    },
    "log_buy_nav_key": {
        "en":    "  → {keys}: {label}",
        "zh-tw": "  → {keys}：{label}",
    },
    "log_buy_nav_fail": {
        "en":    "  ✗ {label} not found in {secs}s — aborting. Are you on the main menu?",
        "zh-tw": "  ✗ {secs} 秒內找不到 {label} — 中止。請確認在主選單。",
    },
    "log_buy_backspace": {
        "en":    "  → Backspace: jump to brand",
        "zh-tw": "  → Backspace：跳至車廠",
    },
    "log_buy_scroll": {
        "en":    "  → scrolling to the bottom of the list ({n} notches)",
        "zh-tw": "  → 捲動至清單底部（{n} 格）",
    },
    "log_buy_scroll_one": {
        "en":    "  → scroll down 1 notch (bring the target car into view)",
        "zh-tw": "  → 向下捲動 1 格（讓目標車輛進入畫面）",
    },
    "log_buy_macro_start": {
        "en":    "Target car focused — starting the buy macro.",
        "zh-tw": "已聚焦目標車輛 — 開始購買巨集。",
    },
    "log_buy_exit_begin": {
        "en":    "Returning to the main menu…",
        "zh-tw": "正在返回主選單…",
    },
    "log_buy_exit_esc": {
        "en":    "  → Esc ({i}/{n})",
        "zh-tw": "  → Esc（{i}/{n}）",
    },
    "log_buy_at_menu": {
        "en":    "  ✓ back at the main menu.",
        "zh-tw": "  ✓ 已返回主選單。",
    },
    "log_buy_exit_fail": {
        "en":    "  ✗ couldn't confirm the main menu in {secs}s — stopping anyway.",
        "zh-tw": "  ✗ {secs} 秒內無法確認主選單 — 仍然停止。",
    },
    "log_buy_stopped": {
        "en":    "Auto Buy stopped.",
        "zh-tw": "自動購買已停止。",
    },

    # ── Delete Cars ───────────────────────────────────────────
    "tab_delete": {
        "en":    "🗑  Delete Used Cars",
        "zh-tw": "🗑  刪除已使用車輛",
    },
    # Main-header page titles (emoji-free; the sidebar nav reuses the tab_* labels)
    "page_title_race": {
        "en":    "AFK Races",
        "zh-tw": "賽事掛機",
    },
    "page_title_mastery": {
        "en":    "Unlock Spin Wheel",
        "zh-tw": "解鎖轉輪",
    },
    "page_title_buy": {
        "en":    "Buy Cars",
        "zh-tw": "購買車輛",
    },
    "page_title_delete": {
        "en":    "Delete Cars",
        "zh-tw": "刪除車輛",
    },
    "page_title_spin": {
        "en":    "Auto Spin Wheel",
        "zh-tw": "自動轉輪",
    },
    # Sidebar nav labels (emoji-free, short — the header shows the full page title)
    "nav_race": {
        "en":    "AFK Races",
        "zh-tw": "賽事掛機",
    },
    "nav_mastery": {
        "en":    "Unlock Spin Wheel",
        "zh-tw": "解鎖轉輪",
    },
    "nav_buy": {
        "en":    "Buy Cars",
        "zh-tw": "購買車輛",
    },
    "nav_delete": {
        "en":    "Delete Cars",
        "zh-tw": "刪除車輛",
    },
    "nav_spin": {
        "en":    "Auto Spin Wheel",
        "zh-tw": "自動轉輪",
    },
    "nav_full_auto": {
        "en":    "Full Auto",
        "zh-tw": "全自動",
    },
    "page_title_full_auto": {
        "en":    "Full Auto",
        "zh-tw": "全自動",
    },
    # ── Full Auto (chained orchestrator) ──────────────────────
    "full_auto_description": {
        "en":    "Chains everything into one farm loop:\nAFK race (for mastery points) → buy 33 cars → unlock their mastery trees → sell them → repeat.\n\nSet the races per cycle and whether to spin wheels each cycle. Each step needs its own templates captured (race nav, buy nav). Runs until you press Stop / F9.",
        "zh-tw": "將所有功能串成一個循環：\n賽事掛機（賺取熟練點數）→ 購買 33 輛車 → 解鎖熟練樹 → 賣出 → 重複。\n\n設定每循環的賽事數，以及是否每循環轉輪。各步驟需先擷取各自的樣本（賽事導航、購買導航）。會持續執行直到你按下停止／F9。",
    },
    "full_auto_count_label": {
        "en":    "Races per cycle (mastery points):",
        "zh-tw": "每循環賽事數（熟練點數）：",
    },
    "full_auto_car_count_label": {
        "en":    "Cars to buy / unlock / sell per cycle:",
        "zh-tw": "每循環購買／解鎖／賣出車輛數：",
    },
    "full_auto_start_label": {
        "en":    "Start cycle from:",
        "zh-tw": "循環起始於：",
    },
    "full_auto_start_race": {
        "en":    "Race (full cycle)",
        "zh-tw": "賽事（完整循環）",
    },
    "full_auto_start_buy": {
        "en":    "Buy cars",
        "zh-tw": "購買車輛",
    },
    "full_auto_start_mastery": {
        "en":    "Unlock mastery",
        "zh-tw": "解鎖熟練",
    },
    "full_auto_start_sell": {
        "en":    "Sell cars",
        "zh-tw": "賣出車輛",
    },
    "full_auto_start_spin": {
        "en":    "Spin Wheel",
        "zh-tw": "轉輪",
    },
    "full_auto_branch_label": {
        "en":    "After selling:",
        "zh-tw": "賣出後：",
    },
    "full_auto_branch_wheelspin": {
        "en":    "Spin wheels",
        "zh-tw": "轉動輪盤",
    },
    "full_auto_branch_racing": {
        "en":    "Back to racing",
        "zh-tw": "回到賽事",
    },
    "status_starting_full_auto": {
        "en":    "Starting Full Auto...",
        "zh-tw": "正在啟動全自動...",
    },
    # Full Auto pre-flight checklist (Start gated until all are ticked)
    "fa_check_title": {
        "en":    "Before you start — confirm all of these:",
        "zh-tw": "開始前 — 請確認以下所有項目：",
    },
    "fa_check_driving": {
        "en":    "I'm driving the car I want to grind with.",
        "zh-tw": "我正在駕駛要用來刷的車。",
    },
    "fa_check_map": {
        "en":    "The map I want to AFK on is my last-played event.",
        "zh-tw": "我要掛機的地圖是上次遊玩的賽事。",
    },
    "fa_check_neighbor": {
        "en":    "Once in Garage, the car to the right of my current car is not new. (one-time setup)",
        "zh-tw": "進入車庫後，我目前車輛右側的那輛車不是全新車。（一次性設定）",
    },
    "fa_check_favorite": {
        "en":    "Only ONE Subaru 22B-STI is marked as Favorite. (one-time setup — more than one breaks grind-car selection)",
        "zh-tw": "只有「一輛」Subaru 22B-STI 被標記為我的最愛。（一次性設定 — 超過一輛會導致練車選取失敗）",
    },
    "fa_check_stock_paint": {
        "en":    "The car I'm using to AFK is a 22B-STI with a stock paint job. (one-time setup — a custom livery breaks grind-car detection)",
        "zh-tw": "我用來掛機的車是「原廠塗裝」的 22B-STI。（一次性設定 — 自訂塗裝會導致練車偵測失敗）",
    },

    "status_fa_checklist": {
        "en":    "Full Auto: tick all the checklist items first.",
        "zh-tw": "全自動：請先勾選所有檢查清單項目。",
    },
    "log_fa_checklist_block": {
        "en":    "Can't start Full Auto — tick every box in the pre-flight checklist first.",
        "zh-tw": "無法啟動全自動 — 請先勾選檢查清單中的每一項。",
    },
    "status_delete_confirm": {
        "en":    "Delete Cars: tick the confirmation box first.",
        "zh-tw": "刪除車輛：請先勾選確認框。",
    },
    "log_delete_confirm_block": {
        "en":    "Can't start — tick the box confirming all cars between the first and last will be deleted.",
        "zh-tw": "無法啟動 — 請先勾選確認框，確認第一輛與最後一輛之間的所有車輛都會被刪除。",
    },
    "log_fa_started": {
        "en":    "Full Auto started.",
        "zh-tw": "全自動已啟動。",
    },
    "log_fa_muted": {
        "en":    "🔇 Game muted for the Full Auto session (unmutes on stop).",
        "zh-tw": "🔇 全自動期間靜音遊戲（停止時取消靜音）。",
    },
    "log_fa_race_count_warn": {
        "en":    "  ⚠ Races per cycle is 0 (unlimited) — the cycle can't advance past racing. Set a positive number.",
        "zh-tw": "  ⚠ 每循環賽事數為 0（無限）— 循環將卡在賽事無法繼續。請設定正整數。",
    },
    "log_fa_cycle": {
        "en":    "==== Full Auto — cycle #{n} ====",
        "zh-tw": "==== 全自動 — 第 {n} 循環 ====",
    },
    "log_fa_step_race": {
        "en":    "[1/5] AFK race…",
        "zh-tw": "[1/5] 賽事掛機…",
    },
    "log_fa_step_buy": {
        "en":    "[2/5] Buy {n} cars…",
        "zh-tw": "[2/5] 購買 {n} 輛車…",
    },
    "log_fa_step_mastery_todo": {
        "en":    "[3/5] Mastery {n} cars — NOT YET WIRED (skipped).",
        "zh-tw": "[3/5] 熟練 {n} 輛車 — 尚未接入（略過）。",
    },
    "log_fa_step_sell_todo": {
        "en":    "[4/5] Sell {n} cars — NOT YET WIRED (skipped).",
        "zh-tw": "[4/5] 賣出 {n} 輛車 — 尚未接入（略過）。",
    },
    "log_fa_step_sell": {
        "en":    "[4/5] Sell {n} cars…",
        "zh-tw": "[4/5] 賣出 {n} 輛車…",
    },
    "log_fa_step_spin_todo": {
        "en":    "[5/5] Wheelspin branch — NOT YET WIRED (skipped).",
        "zh-tw": "[5/5] 轉輪分支 — 尚未接入（略過）。",
    },
    "log_fa_step_spin": {
        "en":    "[5/5] Wheelspin ×{n}…",
        "zh-tw": "[5/5] 轉輪 ×{n}…",
    },
    "log_fa_step_mastery": {
        "en":    "[3/5] Mastery {n} cars…",
        "zh-tw": "[3/5] 熟練 {n} 輛車…",
    },
    # Full Auto — mastery positioning nav (main menu → My Cars → newest car)
    "log_fa_mastery_nav_begin": {
        "en":    "  Mastery: navigating main menu → My Cars…",
        "zh-tw": "  熟練：從主選單導航至車庫…",
    },
    "log_fa_mastery_nav_detected": {
        "en":    "  ✓ {label} detected ({conf}) — {secs}s",
        "zh-tw": "  ✓ 偵測到 {label}（{conf}）— {secs}s",
    },
    "log_fa_mastery_nav_click": {
        "en":    "  → click {label}",
        "zh-tw": "  → 點擊 {label}",
    },
    "log_fa_mastery_tab_right": {
        "en":    "  → switch to CARS tab (D ×2)",
        "zh-tw": "  → 切換到 車輛 分頁（D ×2）",
    },
    "log_fa_mastery_mycars": {
        "en":    "  → Enter → My Cars grid",
        "zh-tw": "  → Enter → 我的車輛 列表",
    },
    "log_fa_mastery_sort": {
        "en":    "  → X → open sort menu",
        "zh-tw": "  → X → 開啟排序選單",
    },
    "log_fa_mastery_nav_fail": {
        "en":    "  ✗ {label} not found in {secs}s — aborting mastery nav.",
        "zh-tw": "  ✗ {secs}s 內找不到 {label} — 中止熟練導航。",
    },
    "log_fa_mastery_at_grid": {
        "en":    "  ✓ at My Cars, positioned on the newest car.",
        "zh-tw": "  ✓ 已在車庫，定位至最新車輛。",
    },
    "log_fa_mastery_nav_skip": {
        "en":    "  Mastery nav templates not captured — skipping mastery step.",
        "zh-tw": "  熟練導航模板尚未擷取 — 略過熟練步驟。",
    },
    # Full Auto — sell step (ride non-target → re-sort → walk to Nth car → sell)
    "log_fa_sell_begin": {
        "en":    "  Sell: preparing to sell {n} cars…",
        "zh-tw": "  賣車：準備賣出 {n} 輛車…",
    },
    "log_fa_sell_ride": {
        "en":    "  → ride a non-target car (Right → Enter → Enter) so it's excluded from the sale",
        "zh-tw": "  → 騎乘一輛非目標車（Right → Enter → Enter），使其排除於賣出之外",
    },
    "log_fa_sell_find_car": {
        "en":    "  → re-select grind car: Y → Favorites → Backspace → brand → car (excludes it from the sale + drives it next race)",
        "zh-tw": "  → 重新選擇練車：Y → 我的最愛 → Backspace → 品牌 → 車輛（排除於賣出之外，並作為下一場比賽用車）",
    },
    "log_fa_sell_wait_grid": {
        "en":    "  → waiting for the My Cars grid to load (header)…",
        "zh-tw": "  → 等待我的車輛列表載入（標題）…",
    },
    "log_fa_sell_get_in": {
        "en":    "  → Select An Action menu detected — Get In Car (Enter)",
        "zh-tw": "  → 偵測到「選擇動作」選單 — 進入車輛（Enter）",
    },
    "log_fa_sell_car_retry": {
        "en":    "  ! Select An Action didn't open — re-clicking grind car (retry #{n})",
        "zh-tw": "  ! 「選擇動作」未開啟 — 重新點擊練車（重試 #{n}）",
    },
    "log_fa_sell_sort": {
        "en":    "  → X → Recently Added → Backspace → Enter (jump to newest car)",
        "zh-tw": "  → X → 最近新增 → Backspace → Enter（跳至最新車輛）",
    },
    "log_fa_sell_position": {
        "en":    "  → position on car #{n}: Right ×{r}, Down ×{d}",
        "zh-tw": "  → 定位至第 {n} 輛車：Right ×{r}，Down ×{d}",
    },
    "log_fa_sell_macro": {
        "en":    "  → selling {n} cars (Enter → Down×4 → Enter → Down → Enter each)…",
        "zh-tw": "  → 賣出 {n} 輛車（每輛 Enter → Down×4 → Enter → Down → Enter）…",
    },
    "log_fa_sell_car": {
        "en":    "    ✓ sold {i}/{n}",
        "zh-tw": "    ✓ 已賣 {i}/{n}",
    },
    "log_fa_sell_exit": {
        "en":    "  → exiting to main menu: ESC → home → ESC → open world → ESC → main",
        "zh-tw": "  → 返回主選單：ESC → 住宅 → ESC → 開放世界 → ESC → 主選單",
    },
    "log_fa_sell_wait_world": {
        "en":    "  → waiting for open world (home icon)…",
        "zh-tw": "  → 等待開放世界（住宅圖示）…",
    },
    "log_fa_sell_at_menu": {
        "en":    "  ✓ cars sold, back at the main menu.",
        "zh-tw": "  ✓ 已賣出車輛，返回主選單。",
    },
    "log_fa_sell_fail": {
        "en":    "  ✗ {label} not found in {secs}s — aborting sell.",
        "zh-tw": "  ✗ {secs}s 內找不到 {label} — 中止賣車。",
    },
    "log_fa_sell_skip": {
        "en":    "  Sell templates not captured — skipping sell step.",
        "zh-tw": "  賣車模板尚未擷取 — 略過賣車步驟。",
    },
    # Full Auto template setup — categories + labels
    "fa_cat_mastery": {
        "en":    "Mastery (main menu → My Cars)",
        "zh-tw": "熟練（主選單 → 車庫）",
    },
    "fa_cat_sell": {
        "en":    "Sell (My Cars → sell block)",
        "zh-tw": "賣車（車庫 → 賣出區塊）",
    },
    "fa_tpl_my_cars": {
        "en":    "My Cars (after riding)",
        "zh-tw": "我的車輛（騎乘後）",
    },
    "fa_tpl_my_cars_header": {
        "en":    "My Cars header (top-left)",
        "zh-tw": "我的車輛 標題（左上角）",
    },
    "fa_tpl_anna": {
        "en":    "Home icon (appears when leaving the home menu)",
        "zh-tw": "住宅圖示（離開住宅選單時出現）",
    },
    "fa_tpl_grind_brand": {
        "en":    "Grind car brand (Manufacturer menu)",
        "zh-tw": "練車品牌（製造商選單）",
    },
    "fa_tpl_grind_car": {
        "en":    "Grind car tile (brand list)",
        "zh-tw": "練車車輛（品牌列表）",
    },
    "fa_tpl_select_action": {
        "en":    "\"Select An Action\" menu (after clicking the car)",
        "zh-tw": "「選擇動作」選單（點擊車輛後）",
    },
    "fa_tpl_return_home": {
        "en":    "Return Home tile",
        "zh-tw": "返回住宅 圖塊",
    },
    "fa_tpl_cars_tab": {
        "en":    "CARS tab",
        "zh-tw": "車輛 分頁",
    },
    "fa_tpl_recently_added": {
        "en":    "Recently Added (sort)",
        "zh-tw": "最近新增（排序）",
    },
    "log_fa_stopped": {
        "en":    "Full Auto stopped.",
        "zh-tw": "全自動已停止。",
    },
    "log_fa_aborted": {
        "en":    "Full Auto stopped — a step could not proceed (not advancing to the next cycle).",
        "zh-tw": "全自動已停止 — 某步驟無法繼續（不進入下一循環）。",
    },
    "label_activity": {
        "en":    "Activity",
        "zh-tw": "活動記錄",
    },
    "delete_description": {
        "en":    "Deletes cars one by one, from oldest to newest.\n\nBefore you start:\n•  Go to your garage and stop on the oldest car you want to start from (bottom-right of the grid).\n•  Make sure the deletion path holds only cars you want gone — it can't skip any.\n\nFor each car it presses: action menu → Down ×4 → confirm → Down ×1 → confirm. If a car you want to keep is in the path, press Stop to cancel.",
        "zh-tw": "由舊到新逐一刪除車輛。\n\n開始前：\n•  停在車庫，選取你想開始刪除中最舊的那台（網格最右下角）。\n•  確認刪除路徑上只有你想刪掉的車——途中無法跳過任何一台。\n\n每輛車的操作：開啟動作選單 → 下鍵 ×4 → 確認 → 下鍵 ×1 → 確認刪除。若路徑上有想保留的車，請按停止取消。",
    },
    "status_starting_delete": {
        "en":    "Starting Delete Used Cars...",
        "zh-tw": "正在啟動刪除車輛...",
    },
    "log_delete_started": {
        "en":    "Auto Delete started.",
        "zh-tw": "自動刪除已啟動。",
    },
    "log_delete_started_count": {
        "en":    "Auto Delete started — will delete {n} cars.",
        "zh-tw": "自動刪除已啟動 — 將刪除 {n} 輛車。",
    },
    "log_delete_limit_reached": {
        "en":    "Reached target of {n} cars deleted. Stopping.",
        "zh-tw": "已完成目標 {n} 輛，自動停止。",
    },
    "delete_count_label": {
        "en":    "Number of cars to delete:",
        "zh-tw": "要刪除的車輛數量：",
    },
    "delete_count_hint": {
        "en":    "(0 = unlimited)",
        "zh-tw": "（0 = 無限循環）",
    },
    "buy_count_label": {
        "en":    "Number of cars to buy:",
        "zh-tw": "要購買的車輛數量：",
    },
    "log_buy_limit_reached": {
        "en":    "Reached target of {n} purchases. Stopping.",
        "zh-tw": "已完成目標 {n} 次購買，自動停止。",
    },
    # ── Auto Spin Wheel ───────────────────────────────────────
    "spin_description": {
        "en":    "Spins the Super Wheelspin over and over. From the My Horizon menu it selects Super Wheelspin, then each spin waits for the on-screen prompt: skip-forward → collect all 3 prizes. Duplicate-reward menus are handled per the mode below.\n\nBefore you start:\n•  Open the My Horizon menu with the Super Wheelspin tile visible.\n\n⚠  Sell mode sells duplicate cars automatically and UNATTENDED — once started it sells every duplicate it sees, with no confirmation. Use Add to Garage if unsure.",
        "zh-tw": "連續轉動超級輪盤。從「我的 HORIZON」選單選擇超級輪盤後，每次轉動都會等待畫面提示：快轉 → 一次領取全部 3 個獎勵。重複獎勵選單會依下方模式處理。\n\n開始前：\n•  開啟「我的 HORIZON」選單，並確保看得到超級輪盤圖示。\n\n⚠  賣出模式會自動且無人看管地賣掉重複車輛——一旦啟動，看到任何重複車輛都會直接賣出、不會再次確認。不確定請選「加入車庫」。",
    },
    "spin_count_label": {
        "en":    "Number of spins to run:",
        "zh-tw": "要轉動的次數：",
    },
    "spin_type_label": {
        "en":    "Wheel:",
        "zh-tw": "輪盤：",
    },
    "spin_type_super": {
        "en":    "Super (3 prizes)",
        "zh-tw": "超級（3 獎）",
    },
    "spin_type_normal": {
        "en":    "Normal (1 prize)",
        "zh-tw": "一般（1 獎）",
    },
    "spin_mode_label": {
        "en":    "Duplicate handling:",
        "zh-tw": "重複獎勵處理：",
    },
    "spin_mode_garage": {
        "en":    "Add to Garage",
        "zh-tw": "加入車庫",
    },
    "spin_mode_sell": {
        "en":    "Sell Car",
        "zh-tw": "賣出車輛",
    },
    "spin_mode_hint": {
        "en":    "Sell mode sells duplicates automatically — see the warning above.",
        "zh-tw": "賣出模式會自動賣掉重複車輛 — 請見上方警告。",
    },
    "spin_tpl_my_horizon": {
        "en":    "My Horizon tab (top nav)",
        "zh-tw": "我的 HORIZON 分頁（頂部導覽）",
    },
    "spin_tpl_super": {
        "en":    "Super Wheelspin tile",
        "zh-tw": "超級輪盤圖示",
    },
    "spin_tpl_normal": {
        "en":    "Wheelspin tile (normal)",
        "zh-tw": "一般輪盤圖示",
    },
    "spin_tpl_skip": {
        "en":    "Skip-forward prompt (bottom-left)",
        "zh-tw": "快轉提示（左下角）",
    },
    "spin_tpl_collect": {
        "en":    "Collect prompt (bottom-left)",
        "zh-tw": "領取提示（左下角）",
    },
    "spin_tpl_collect_final": {
        "en":    "Final-spin Collect Prize prompt (no spins left)",
        "zh-tw": "最後一轉的領取獎勵提示（已無轉盤）",
    },
    "spin_tpl_duplicate": {
        "en":    "Duplicate-reward menu",
        "zh-tw": "重複獎勵選單",
    },
    "spin_loop": {
        "en":    "Spin",
        "zh-tw": "轉動",
    },
    "status_starting_spin": {
        "en":    "Starting Auto Spin Wheel...",
        "zh-tw": "正在啟動自動轉輪...",
    },
    "log_spin_started": {
        "en":    "Auto Spin Wheel started.",
        "zh-tw": "自動轉輪已啟動。",
    },
    "log_spin_started_count": {
        "en":    "Auto Spin Wheel started — will run {n} spins.",
        "zh-tw": "自動轉輪已啟動 — 將轉動 {n} 次。",
    },
    "log_spin_sell_warn": {
        "en":    "SELL mode: duplicate cars will be sold automatically and unattended.",
        "zh-tw": "賣出模式：重複車輛將被自動且無人看管地賣出。",
    },
    "log_spin_select_mh_tab": {
        "en":    "Selecting the My Horizon tab (starting from the main menu)...",
        "zh-tw": "選擇「我的 HORIZON」分頁（從主選單開始）…",
    },
    "log_spin_mh_tab_off": {
        "en":    "  (no My Horizon tab template — assuming you're already on the My Horizon menu)",
        "zh-tw": "  （無「我的 HORIZON」分頁樣本 — 假設已在「我的 HORIZON」選單）",
    },
    "log_spin_on_my_horizon": {
        "en":    "  Already on the My Horizon menu ({label} visible) — clicking the wheel, skipping the tab.",
        "zh-tw": "  已在「我的 HORIZON」選單（可見{label}）— 直接點擊輪盤，略過分頁。",
    },
    "log_spin_select_super": {
        "en":    "Selecting Super Wheelspin...",
        "zh-tw": "選擇超級輪盤…",
    },
    "log_spin_super_not_found": {
        "en":    "Super Wheelspin tile not found — start on the My Horizon menu with it visible, then try again.",
        "zh-tw": "找不到超級輪盤圖示 — 請在「我的 HORIZON」選單（可看到超級輪盤）開始後再試一次。",
    },
    "log_spin_select_tile": {
        "en":    "Selecting {label}...",
        "zh-tw": "選擇{label}…",
    },
    "log_spin_tile_not_found": {
        "en":    "{label} not found — start on the My Horizon menu with it visible, then try again.",
        "zh-tw": "找不到{label} — 請在「我的 HORIZON」選單（可看到該圖示）開始後再試一次。",
    },
    "log_spin_spin": {
        "en":    "Spinning...",
        "zh-tw": "轉動中…",
    },
    "log_spin_wait_skip": {
        "en":    "  → waiting for skip or collect prompt",
        "zh-tw": "  → 等待快轉或領取提示",
    },
    "log_spin_skip": {
        "en":    "  → skip: Enter (fast-forward the reveal)",
        "zh-tw": "  → 快轉：Enter（跳過開獎動畫）",
    },
    "log_spin_skip_off": {
        "en":    "  (no skip template — skip-forward disabled, will wait for the reveal)",
        "zh-tw": "  （無快轉樣本 — 已停用快轉，將等待開獎動畫）",
    },
    "log_spin_collect_cleared": {
        "en":    "  · collect prompt cleared in {secs}s (collecting animation)",
        "zh-tw": "  · 領取提示於 {secs} 秒後消失（領取動畫）",
    },
    "log_spin_wait_collect": {
        "en":    "  → waiting for collect prompt",
        "zh-tw": "  → 等待領取提示出現",
    },
    "log_spin_stage_slow": {
        "en":    "Still waiting for the wheelspin screen — recheck the template/threshold if this persists.",
        "zh-tw": "仍在等待轉輪畫面 — 若持續發生，請重新檢查樣本／門檻。",
    },
    "log_spin_collect": {
        "en":    "  → collect: Enter (takes all 3 prizes)",
        "zh-tw": "  → 領取：Enter（一次領取全部 3 個獎勵）",
    },
    "log_spin_end_esc": {
        "en":    "  → final spin — collect: Esc (takes all 3 prizes, then exits to the menu)",
        "zh-tw": "  → 最後一轉 — 領取：Esc（領取全部 3 個獎勵後返回選單）",
    },
    "log_spin_end_enter": {
        "en":    "  → final spin (out of spins) — Collect Prize: Enter (collects and leaves)",
        "zh-tw": "  → 最後一轉（已無轉盤）— 領取獎勵：Enter（領取後離開）",
    },
    "log_spin_detected": {
        "en":    "  ✓ {label} detected ({conf}) — {secs}s",
        "zh-tw": "  ✓ 偵測到{label}（{conf}）— {secs} 秒",
    },
    "log_spin_wait_dup": {
        "en":    "  → waiting for duplicate menu or next spin",
        "zh-tw": "  → 等待重複選單或下一次轉動",
    },
    "log_spin_no_dup": {
        "en":    "  ✓ no more duplicates — next spin ({secs}s)",
        "zh-tw": "  ✓ 沒有更多重複 — 下一次轉動（{secs} 秒）",
    },
    "log_spin_back_menu": {
        "en":    "  ✓ no more duplicates — back at the My Horizon menu ({secs}s)",
        "zh-tw": "  ✓ 沒有更多重複 — 已返回「我的 HORIZON」選單（{secs} 秒）",
    },
    "log_spin_dup_garage": {
        "en":    "  → duplicate #{n}: Add to Garage (Enter)",
        "zh-tw": "  → 重複 #{n}：加入車庫（Enter）",
    },
    "log_spin_dup_sell": {
        "en":    "  → duplicate #{n}: Sell (Down×2 → Enter)",
        "zh-tw": "  → 重複 #{n}：賣出（Down×2 → Enter）",
    },
    "log_spin_limit_reached": {
        "en":    "Reached target of {n} spins. Stopping.",
        "zh-tw": "已完成目標 {n} 次轉動，自動停止。",
    },
    "log_spin_stopped": {
        "en":    "Auto Spin Wheel stopped.",
        "zh-tw": "自動轉輪已停止。",
    },
    "mastery_count_label": {
        "en":    "Number of cars to process:",
        "zh-tw": "要處理的車輛數量：",
    },
    "race_count_label": {
        "en":    "Number of races to run:",
        "zh-tw": "要跑的場數：",
    },
    "log_mastery_started_count": {
        "en":    "Auto Mastery started — will process {n} cars.",
        "zh-tw": "自動熟練度已啟動 — 將處理 {n} 輛車。",
    },
    "log_mastery_limit_reached": {
        "en":    "Reached target of {n} cars. Stopping.",
        "zh-tw": "已完成目標 {n} 輛，自動停止。",
    },
    "log_race_started_count": {
        "en":    "Race Auto started — will run {n} races.",
        "zh-tw": "自動跑圖已啟動 — 將跑 {n} 場。",
    },
    "log_race_limit_reached": {
        "en":    "Reached target of {n} races. Stopping.",
        "zh-tw": "已完成目標 {n} 場，自動停止。",
    },
    # ── Race menu navigation (main menu → Start screen) ──
    "log_race_nav_begin": {
        "en":    "Main menu detected — navigating to your last EventLab event…",
        "zh-tw": "偵測到主選單 — 正在前往你上次的 EventLab 賽事…",
    },
    "log_race_at_start": {
        "en":    "Start screen detected — skipping menu navigation.",
        "zh-tw": "偵測到開始畫面 — 略過選單導航。",
    },
    "log_race_nav_detected": {
        "en":    "  ✓ {label} ({conf}) — {secs}s",
        "zh-tw": "  ✓ {label}（{conf}）— {secs} 秒",
    },
    "log_race_nav_click": {
        "en":    "  → click {label}",
        "zh-tw": "  → 點擊 {label}",
    },
    "log_race_nav_enter": {
        "en":    "  → Enter: {label}",
        "zh-tw": "  → Enter：{label}",
    },
    "log_race_nav_retry": {
        "en":    "  ↻ {label} not detected yet (load in progress) — pressing Enter again",
        "zh-tw": "  ↻ 尚未偵測到{label}（載入中）— 再按一次 Enter",
    },
    "log_race_nav_fail": {
        "en":    "  ✗ {label} not found in {secs}s — aborting navigation. Are you on the main menu and connected?",
        "zh-tw": "  ✗ {secs} 秒內找不到 {label} — 中止導航。請確認在主選單且已連線。",
    },
    "log_race_nav_done": {
        "en":    "  ✓ navigation complete — at the Start screen.",
        "zh-tw": "  ✓ 導航完成 — 已到達開始畫面。",
    },
    # ── Race exit (results → main menu) ──
    "log_race_exit_begin": {
        "en":    "Returning to the main menu…",
        "zh-tw": "正在返回主選單…",
    },
    "log_race_exit_continue": {
        "en":    "  → Enter: Continue (leaving the race)",
        "zh-tw": "  → Enter：繼續（離開賽事）",
    },
    "log_race_exit_menu_detected": {
        "en":    "  ✓ \"What's Next\" menu ({conf}) — {secs}s",
        "zh-tw": "  ✓「接下來做什麼」選單（{conf}）— {secs} 秒",
    },
    "log_race_exit_esc_menu": {
        "en":    "  → Esc: close the \"What's Next\" menu",
        "zh-tw": "  → Esc：關閉「接下來做什麼」選單",
    },
    "log_race_exit_esc_world": {
        "en":    "  → Esc: open the main menu",
        "zh-tw": "  → Esc：開啟主選單",
    },
    "log_race_at_menu": {
        "en":    "  ✓ back at the main menu.",
        "zh-tw": "  ✓ 已返回主選單。",
    },
    "log_race_exit_fail": {
        "en":    "  ✗ couldn't confirm the main menu in {secs}s — stopping anyway.",
        "zh-tw": "  ✗ {secs} 秒內無法確認主選單 — 仍然停止。",
    },
    "log_delete_stopped": {
        "en":    "Auto Delete stopped.",
        "zh-tw": "自動刪除已停止。",
    },
    "delete_loop": {
        "en":    "Car",
        "zh-tw": "車輛",
    },

    # ── Updater ───────────────────────────────────────────────
    "update_title": {
        "en":    "Update Available",
        "zh-tw": "有新版本",
    },
    "update_available": {
        "en":    "A new version is available: {tag}",
        "zh-tw": "發現新版本：{tag}",
    },
    "update_prompt": {
        "en":    "Open the download page to get the latest version?",
        "zh-tw": "是否開啟下載頁面取得最新版本？",
    },
    "update_yes": {
        "en":    "Open download page",
        "zh-tw": "開啟下載頁面",
    },
    "update_no": {
        "en":    "Later",
        "zh-tw": "稍後再說",
    },

    # ── Top bar ───────────────────────────────────────────────
    "settings_window_title": {
        "en":    "Settings",
        "zh-tw": "設定",
    },
    "settings_back": {
        "en":    "Back",
        "zh-tw": "返回",
    },
    "settings_race_section": {
        "en":    "Race Auto",
        "zh-tw": "自動掛機刷技術點",
    },
    "settings_mastery_section": {
        "en":    "Auto Unlock 22B",
        "zh-tw": "自動解鎖22B轉輪",
    },
    "settings_buy_section": {
        "en":    "Auto Buy 22B-STi",
        "zh-tw": "自動購買22B-STi",
    },
    "settings_delete_section": {
        "en":    "Delete Used Cars",
        "zh-tw": "刪除已使用車輛",
    },
    "settings_wheelspin_section": {
        "en":    "Auto Spin Wheel",
        "zh-tw": "自動轉輪",
    },
    "settings_appearance_section": {
        "en":    "Appearance",
        "zh-tw": "外觀",
    },
    "settings_system_section": {
        "en":    "System",
        "zh-tw": "系統",
    },
    "settings_shortcuts_section": {
        "en":    "Shortcuts",
        "zh-tw": "快捷鍵",
    },
    "label_theme": {
        "en":    "Theme:",
        "zh-tw": "主題：",
    },
    "label_theme_preset": {
        "en":    "Theme",
        "zh-tw": "主題",
    },
    "label_language": {
        "en":    "Language:",
        "zh-tw": "語言：",
    },
    "label_ui_scale": {
        "en":    "UI scale:",
        "zh-tw": "介面縮放：",
    },
    "setting_game_lang": {
        "en":    "Game menu language:",
        "zh-tw": "遊戲選單語言：",
    },
    "game_lang_auto": {
        "en":    "Auto (follow app)",
        "zh-tw": "自動（跟隨介面）",
    },
    "setting_overlay": {
        "en":    "Game status overlay:",
        "zh-tw": "遊戲狀態浮層：",
    },
    "setting_mute": {
        "en":    "Mute game while running:",
        "zh-tw": "執行時將遊戲靜音：",
    },
    "setting_ocr": {
        "en":    "OCR text detection:",
        "zh-tw": "OCR 文字偵測：",
    },
    "setting_ocr_hint": {
        "en":    "off = lighter on CPU (fixes game stutter)",
        "zh-tw": "關閉 = 較省 CPU（修正遊戲卡頓）",
    },
    "overlay_indicator": {
        "en":    "Overlay",
        "zh-tw": "浮層",
    },
    "ov_func_race": {
        "en": "Race", "zh-tw": "賽事",
    },
    "ov_func_mastery": {
        "en": "Mastery", "zh-tw": "熟練度",
    },
    "ov_func_buy": {
        "en": "Buy", "zh-tw": "購買",
    },
    "ov_func_delete": {
        "en": "Delete", "zh-tw": "刪除",
    },
    "ov_func_spin": {
        "en": "Spin", "zh-tw": "轉輪",
    },
    "overlay_hint_stop": {
        "en":    "■  Press {key} to stop",
        "zh-tw": "■  按 {key} 停止",
    },
    "overlay_hint_start": {
        "en":    "▶  Press {key} to start",
        "zh-tw": "▶  按 {key} 開始",
    },
    "scale_auto": {
        "en":    "Auto",
        "zh-tw": "自動",
    },
    "theme_system": {
        "en":    "System",
        "zh-tw": "系統",
    },
    "theme_light": {
        "en":    "Light",
        "zh-tw": "淺色",
    },
    "theme_dark": {
        "en":    "Dark",
        "zh-tw": "深色",
    },

    # ── Setup panel ───────────────────────────────────────────
    "setup_header": {
        "en":    "▶  Setup & Templates",
        "zh-tw": "▶  設定與樣本",
    },
    "setup_header_open": {
        "en":    "▼  Setup & Templates",
        "zh-tw": "▼  設定與樣本",
    },
    "label_threshold": {
        "en":    "Minimum required similarity:",
        "zh-tw": "最低所需相似度：",
    },
    "label_monitor": {
        "en":    "Game monitor:",
        "zh-tw": "遊戲螢幕：",
    },
    "monitor_primary_tag": {
        "en":    "(Primary)",
        "zh-tw": "（主螢幕）",
    },
    "label_templates": {
        "en":    "Templates (press CAPS LOCK to capture each):",
        "zh-tw": "樣本（按 CAPS LOCK 逐一擷取）：",
    },
    "label_nodes": {
        "en":    "Node positions (6 mastery nodes)",
        "zh-tw": "節點位置（6 個熟練度節點）",
    },
    "btn_start_capture": {
        "en":    "Start Capture Session",
        "zh-tw": "開始擷取作業",
    },
    "btn_stop_capture": {
        "en":    "Stop Session",
        "zh-tw": "停止作業",
    },
    "btn_recapture": {
        "en":    "Retake",
        "zh-tw": "重新擷取",
    },
    "capture_instruction": {
        "en":    "Navigate your game to the same screen, then press CAPS LOCK to capture. Drag to select the area, then press ENTER to confirm. Press ESC at any time to cancel. If the selection window doesn't appear, Alt-Tab to find it.",
        "zh-tw": "請將遊戲切換至相同畫面，然後按 CAPS LOCK 擷取。拖曳框選範圍後按 ENTER 確認。隨時按 ESC 可取消。若視窗未出現，請按 Alt-Tab 查看是否在背景。",
    },
    "capture_nodes_instruction": {
        "en":    "Get to the Mastery screen, press CAPS LOCK to screenshot then click 6 nodes.",
        "zh-tw": "進入熟練度畫面，按 CAPS LOCK 截圖後點擊 6 個節點。",
    },
    "capture_cancelled": {
        "en":    "Capture {reason} — press CAPS LOCK to retry.",
        "zh-tw": "擷取{reason} — 按 CAPS LOCK 重試。",
    },
    "setup_complete": {
        "en":    "Setup complete.",
        "zh-tw": "設定完成。",
    },
    "setup_in_progress": {
        "en":    "Setup in progress.",
        "zh-tw": "設定進行中。",
    },
    "all_templates_done": {
        "en":    "All templates already captured.",
        "zh-tw": "所有樣本已擷取完成。",
    },
    "capturing_label": {
        "en":    "Capturing: {label}",
        "zh-tw": "擷取中：{label}",
    },
    "template_saved": {
        "en":    "  Template '{key}' saved.",
        "zh-tw": "  樣本 '{key}' 已儲存。",
    },
    "set_roi_instruction": {
        "en":    "Set DETECTION AREA for {label}: drag the region the template should be searched in (saves no image)",
        "zh-tw": "為 {label} 設定偵測範圍：框選樣本要被搜尋的區域（不會儲存影像）",
    },
    "roi_saved": {
        "en":    "  Detection area for '{key}' saved.",
        "zh-tw": "  '{key}' 的偵測範圍已儲存。",
    },
    "btn_set_roi_tip": {
        "en":    "Set detection area",
        "zh-tw": "設定偵測範圍",
    },
    "nodes_saved": {
        "en":    "  Node positions saved.",
        "zh-tw": "  節點位置已儲存。",
    },

    # ── Advanced settings ─────────────────────────────────────
    "settings_header": {
        "en":    "▶  Advanced Settings",
        "zh-tw": "▶  進階設定",
    },
    "settings_header_open": {
        "en":    "▼  Advanced Settings",
        "zh-tw": "▼  進階設定",
    },
    "setting_race_threshold": {
        "en":    "Minimum required similarity",
        "zh-tw": "最低所需相似度",
    },
    "setting_race_check_interval": {
        "en":    "Check interval (s)",
        "zh-tw": "檢測間隔（秒）",
    },
    "setting_race_post_key_wait": {
        "en":    "Trigger to input delay (s)",
        "zh-tw": "觸發與開始輸入之間的間隔（秒）",
    },
    "setting_mastery_threshold": {
        "en":    "Minimum required similarity",
        "zh-tw": "最低所需相似度",
    },
    "setting_mastery_cutscene_wait": {
        "en":    "Cutscene wait (s)",
        "zh-tw": "過場動畫等待（秒）",
    },
    "setting_mastery_grid_unlock_wait": {
        "en":    "Node unlock delay (s)",
        "zh-tw": "節點解鎖延遲（秒）",
    },
    "setting_menu_tap_wait": {
        "en":    "Menu tap delay (s)",
        "zh-tw": "選單點按延遲（秒）",
    },
    "setting_buy_post_key_wait": {
        "en":    "Key interval (s)",
        "zh-tw": "按鍵間隔（秒）",
    },
    "setting_delete_post_key_wait": {
        "en":    "Key interval (s)",
        "zh-tw": "按鍵間隔（秒）",
    },
    "setting_wheelspin_post_key_wait": {
        "en":    "Key interval (s)",
        "zh-tw": "按鍵間隔（秒）",
    },

    # ── Run controls ──────────────────────────────────────────
    "btn_start": {
        "en":    "Start",
        "zh-tw": "開始",
    },
    "btn_stop": {
        "en":    "Stop",
        "zh-tw": "停止",
    },

    # ── Status messages ───────────────────────────────────────
    "shortcut_toggle": {
        "en":    "{key} to start / stop",
        "zh-tw": "{key} 啟動 / 停止",
    },
    "shortcut_capture": {
        "en":    "Press {key} to capture | Y = save | N = redo",
        "zh-tw": "按 {key} 擷取 | Y = 儲存 | N = 重拍",
    },
    "setting_toggle_key": {
        "en":    "Start / Stop key",
        "zh-tw": "啟動 / 停止鍵",
    },
    "setting_capture_key": {
        "en":    "Capture key",
        "zh-tw": "擷取鍵",
    },
    "setting_report_key": {
        "en":    "Bug report key",
        "zh-tw": "錯誤回報鍵",
    },
    "setting_overlay_key": {
        "en":    "Overlay toggle key",
        "zh-tw": "浮層切換鍵",
    },
    "report_started": {
        "en":    "🐞 Bug report started — capturing screenshot, logs & system info...",
        "zh-tw": "🐞 已開始產生錯誤回報 — 擷取截圖、日誌與系統資訊中…",
    },
    "report_generating": {
        "en":    "Generating bug report — capturing screenshot & log...",
        "zh-tw": "正在產生錯誤回報 — 擷取截圖與日誌中…",
    },
    "report_saved": {
        "en":    "✅ Bug report complete — saved to: {path}",
        "zh-tw": "✅ 錯誤回報已完成 — 儲存於：{path}",
    },
    "report_privacy": {
        "en":    "Note: this bundle includes your settings and basic system info. Fine to share for support; review before posting publicly.",
        "zh-tw": "注意：此回報包含你的設定與基本系統資訊。提供給支援沒問題，公開分享前請先檢視。",
    },
    "report_help_btn": {
        "en":    "Report a Bug",
        "zh-tw": "回報錯誤",
    },
    "report_help_title": {
        "en":    "How to Report a Bug",
        "zh-tw": "如何回報錯誤",
    },
    "report_help_intro": {
        "en":    "Found a problem? Send us a one-click diagnostic report — just follow these steps:",
        "zh-tw": "遇到問題嗎？只要依照以下步驟，就能一鍵傳送診斷回報：",
    },
    "report_help_step1": {
        "en":    "Run the script (Race / Mastery / etc.) and let it run until the problem happens — i.e. it gets stuck or stops working.",
        "zh-tw": "執行腳本（賽事／熟練度等），讓它持續運作直到發生問題（卡住或停止運作）。",
    },
    "report_help_step2": {
        "en":    "When it fails, STAY on that exact game screen — don't alt-tab, click away, or close anything.",
        "zh-tw": "發生問題時，請停留在當下的遊戲畫面 — 不要切換視窗、點擊其他地方或關閉任何東西。",
    },
    "report_help_step3": {
        "en":    "With that failing screen still showing, press {key}.",
        "zh-tw": "在問題畫面仍顯示的狀態下，按下 {key}。",
    },
    "report_help_step4": {
        "en":    "FAFE saves a report (screenshot of that screen + log + system info) and opens the folder automatically.",
        "zh-tw": "FAFE 會自動儲存回報（該畫面的截圖＋日誌＋系統資訊）並開啟資料夾。",
    },
    "report_help_step5": {
        "en":    "Upload the FAFE_report_….zip to our Discord, and tell us your screen resolution and which tab failed.",
        "zh-tw": "將 FAFE_report_….zip 上傳到我們的 Discord，並告訴我們你的螢幕解析度與發生問題的分頁。",
    },
    "report_help_discord": {
        "en":    "Join our Discord",
        "zh-tw": "加入我們的 Discord",
    },
    "shortcut_press_any_key": {
        "en":    "Press any key...",
        "zh-tw": "請按下任意鍵...",
    },
    "startup_game_not_focused": {
        "en":    "  WARNING: Forza Horizon 6 is not the active window.\n  Please switch to the game before the countdown ends.",
        "zh-tw": "  警告：Forza Horizon 6 並非目前使用中的視窗。\n  請在倒數結束前切換至遊戲。",
    },
    "startup_game_focused": {
        "en":    "  Forza Horizon 6 detected.",
        "zh-tw": "  已偵測到 Forza Horizon 6。",
    },
    "startup_switch_to_game": {
        "en":    "  Switch to your game now!",
        "zh-tw": "  請立即切換至遊戲！",
    },
    "startup_countdown": {
        "en":    "  Starting in {i}...",
        "zh-tw": "  {i} 秒後開始...",
    },
    "startup_running": {
        "en":    "  Running!",
        "zh-tw": "  開始執行！",
    },
    "log_placeholder": {

        "en":    "Automation log will appear here when running...",
        "zh-tw": "執行後，自動化紀錄將顯示於此...",
    },
    "status_ready": {
        "en":    "Ready",
        "zh-tw": "就緒",
    },
    "status_starting_race": {
        "en":    "Starting race automation...",
        "zh-tw": "正在啟動自動競速...",
    },
    "status_starting_mastery": {
        "en":    "Starting Mastery Lite...",
        "zh-tw": "正在啟動熟練度精簡版...",
    },
    "status_stopping": {
        "en":    "Stopping...",
        "zh-tw": "停止中...",
    },
    "status_stopped": {
        "en":    "Stopped",
        "zh-tw": "已停止",
    },
    "status_setup_incomplete": {
        "en":    "Setup incomplete — missing templates",
        "zh-tw": "設定未完成 — 缺少樣本",
    },

    # ── Race template labels ──────────────────────────────────
    "race_tpl_start_menu": {
        "en":    "Start Race menu",
        "zh-tw": "開始比賽選單",
    },
    "race_tpl_racing": {
        "en":    "Race active (HUD / speedometer)",
        "zh-tw": "比賽進行中（HUD / 速度表）",
    },
    "race_tpl_restart_menu": {
        "en":    "Restart Race menu",
        "zh-tw": "重新開始比賽選單",
    },
    "race_tpl_creative_hub": {
        "en":    "Creative Hub button (top nav)",
        "zh-tw": "創意中心按鈕（上方導覽列）",
    },
    "race_tpl_eventlab": {
        "en":    "EventLab tile",
        "zh-tw": "EventLab 圖塊",
    },
    "race_tpl_play_event": {
        "en":    "Play Event tile",
        "zh-tw": "遊玩賽事（Play Event）圖塊",
    },
    "race_tpl_events_arrow": {
        "en":    "Events ◀ tab arrow (top-left)",
        "zh-tw": "賽事 ◀ 分頁箭頭（左上角）",
    },
    "race_tpl_my_history": {
        "en":    "MY HISTORY screen",
        "zh-tw": "我的歷史（MY HISTORY）畫面",
    },
    "race_tpl_choose_race_type": {
        "en":    "Choose Race Type screen",
        "zh-tw": "選擇比賽類型畫面",
    },
    "race_tpl_car_select": {
        "en":    "Car-selection screen",
        "zh-tw": "車輛選擇畫面",
    },
    "race_tpl_next_activity": {
        "en":    "\"What's Next\" menu (after a race)",
        "zh-tw": "賽後「接下來做什麼」選單",
    },
    "race_tpl_confirm": {
        "en":    "Confirmation dialog",
        "zh-tw": "確認對話框",
    },

    # ── Mastery template labels ───────────────────────────────

    # ── Automation log messages ───────────────────────────────
    "log_template_loaded": {
        "en":    "  Template '{key}' loaded.",
        "zh-tw": "  樣本 '{key}' 已載入。",
    },
    "log_nodes_loaded": {
        "en":    "  {n} node positions loaded.",
        "zh-tw": "  已載入 {n} 個節點位置。",
    },
    "log_template_missing": {
        "en":    "  ERROR: Template '{key}' not found. Run setup first.",
        "zh-tw": "  錯誤：找不到樣本 '{key}'。請先執行設定。",
    },
    "log_nodes_missing": {
        "en":    "  ERROR: Node positions not found. Run setup first.",
        "zh-tw": "  錯誤：找不到節點位置。請先執行設定。",
    },
    "log_race_started": {
        "en":    "Race automation started.",
        "zh-tw": "自動競速已啟動。",
    },
    "log_bg_input_on": {
        "en":    "⚙ Background input ON (experimental) — sending to the game window without focus. Note: driving (held W) may not register this way.",
        "zh-tw": "⚙ 背景輸入已開啟（實驗性）— 不需切到遊戲也能送出輸入。注意：駕駛（按住 W）可能無法以此方式生效。",
    },
    "log_bg_input_not_found": {
        "en":    "⚠ Background input ON but no window titled '{title}' was found — using normal (focused) input instead.",
        "zh-tw": "⚠ 已開啟背景輸入，但找不到標題含「{title}」的視窗 — 改用一般（需聚焦）輸入。",
    },
    "log_bg_window_size": {
        "en":    "  Detecting against game window: {w}×{h} (don't move/resize it while running).",
        "zh-tw": "  以遊戲視窗為偵測範圍：{w}×{h}（執行期間請勿移動或縮放視窗）。",
    },
    "log_bg_letterbox": {
        "en":    "  Black bars detected — cropping to game content {w}×{h} (window aspect ≠ game aspect).",
        "zh-tw": "  偵測到黑邊 — 裁切至遊戲畫面內容 {w}×{h}（視窗比例與遊戲比例不符）。",
    },
    "log_bg_keep_active": {
        "en":    "  Keep-alive ON — telling the game it's active so it won't auto-pause (experimental; only works if the game trusts it).",
        "zh-tw": "  保持作用中已開啟 — 持續告知遊戲它仍為作用中視窗以避免自動暫停（實驗性；僅在遊戲採信時有效）。",
    },
    "log_bg_capture_window": {
        "en":    "  Window capture ON (PrintWindow) — sees the game even when covered by another window. NOTE: may be black for DirectX games; if detection fails, set background_capture back to 'region'.",
        "zh-tw": "  視窗擷取已開啟（PrintWindow）— 即使被其他視窗遮住也能擷取遊戲畫面。注意：DirectX 遊戲可能擷取到全黑；若偵測失敗，請將 background_capture 改回 'region'。",
    },
    "log_game_muted": {
        "en":    "  Game muted for this run (other apps unaffected).",
        "zh-tw": "  本次執行已將遊戲靜音（不影響其他程式）。",
    },
    "log_game_unmuted": {
        "en":    "  Game unmuted.",
        "zh-tw": "  已取消遊戲靜音。",
    },
    "log_race_stopped": {
        "en":    "Race automation stopped.",
        "zh-tw": "自動競速已停止。",
    },
    "log_mastery_started": {
        "en":    "Auto Unlock 22B started.",
        "zh-tw": "自動解鎖22B轉輪已啟動。",
    },
    "log_mastery_stopped": {
        "en":    "Auto Unlock 22B stopped.",
        "zh-tw": "自動解鎖22B轉輪已停止。",
    },
    "log_loop": {
        "en":    "\n-- Loop #{n} --",
        "zh-tw": "\n-- 第 {n} 圈 --",
    },
    "log_car": {
        "en":    "\n-- Car #{n} --",
        "zh-tw": "\n-- 第 {n} 輛 --",
    },
    "log_detected": {
        "en":    "  {label} detected ({conf})",
        "zh-tw": "  偵測到 {label}（{conf}）",
    },
    "log_timed_out": {
        "en":    "  {label} timed out after {t}s",
        "zh-tw": "  {label} 於 {t} 秒後逾時",
    },
    "log_warn_not_detected": {
        "en":    "⚠ WARNING: '{label}' not detected after 10s. If not detecting, try dragging the threshold slider to the left. You may also need to recapture this template. If the game ignores all input (car won't move / clicks do nothing), run FAFE as administrator.",
        "zh-tw": "⚠ 警告：'{label}' 超過 10 秒未偵測到。若持續無法偵測，請將閾值滑桿向左拖動。也可以嘗試重新擷取此樣本。若遊戲完全不接受輸入（車子不動／點擊無效），請以系統管理員身分執行 FAFE。",
    },
    "log_timed_out_retry": {
        "en":    "  Timed out — retrying.",
        "zh-tw": "  逾時 — 重試中。",
    },
    "log_pressing": {
        "en":    "  Pressing {key} [{label}]",
        "zh-tw": "  按下 {key}【{label}】",
    },
    "log_race_wait_start": {
        "en":    "  Race starting — waiting before holding W...",
        "zh-tw": "  賽事開始中 — 按住 W 前先等待...",
    },
    "log_holding_w": {
        "en":    "  Holding W — waiting for race to end...",
        "zh-tw": "  按住 W — 等待比賽結束...",
    },
    "log_released_w": {
        "en":    "  Released W — race over.",
        "zh-tw": "  釋放 W — 比賽結束。",
    },
    "log_race_end_timeout": {
        "en":    "  Race end not detected after 1h — releasing W.",
        "zh-tw": "  1 小時後仍未偵測到比賽結束 — 釋放 W。",
    },
    "log_not_found_retry": {
        "en":    "  {label} not found — retrying loop.",
        "zh-tw": "  找不到 {label} — 重試循環。",
    },
    "log_esc_x2": {
        "en":    "  Pressing ESC x2 to return...",
        "zh-tw": "  按下 ESC 兩次返回...",
    },
    "log_clicking_nodes": {
        "en":    "  Clicking {n} mastery nodes...",
        "zh-tw": "  點擊 {n} 個熟練度節點...",
    },
    "log_node": {
        "en":    "    Node {i}/{n} at ({x},{y})",
        "zh-tw": "    節點 {i}/{n} 位於 ({x},{y})",
    },
    # Keyboard grid navigation of the mastery tree (replaces node clicking)
    "log_grid_unlock": {
        "en":    "  Unlocking {n} nodes via keyboard (WASD + Enter)...",
        "zh-tw": "  以鍵盤解鎖 {n} 個節點（WASD + Enter）...",
    },
    "log_grid_step": {
        "en":    "    Node {i}/{n}: {keys}",
        "zh-tw": "    節點 {i}/{n}：{keys}",
    },
    "log_grid_missing": {
        "en":    "  Mastery tree path not set — open Setup and pick the nodes on the grid.",
        "zh-tw": "  尚未設定熟練度路徑 — 請開啟設定並在格子上選取節點。",
    },
    # Mastery grid picker widget
    "grid_title": {
        "en":    "Mastery tree — unlock path",
        "zh-tw": "熟練度樹 — 解鎖路徑",
    },
    "grid_hint": {
        "en":    "Click nodes in unlock order (S = start, bottom-left). Click the last one again to undo. The bot navigates them with WASD + Enter.",
        "zh-tw": "依解鎖順序點擊節點（S = 起點，左下角）。再次點擊最後一個可取消。程式會以 WASD + Enter 導航。",
    },
    "grid_clear": {
        "en":    "Clear",
        "zh-tw": "清除",
    },
    # Standalone mastery garage-block picker
    "carblock_title": {
        "en":    "Cars to unlock — garage block",
        "zh-tw": "要解鎖的車輛 — 車庫區塊",
    },
    "carblock_hint": {
        "en":    "The garage fills top→bottom by column. Click your FIRST car's row (left) and your LAST car's row (right), and enter how many FULL columns sit between them (0 = the last car is in the very next column).",
        "zh-tw": "車庫依欄由上而下排列。點選第一輛車的列（左）與最後一輛車的列（右），並輸入兩者之間有幾個「整欄」（0 = 最後一輛車就在下一欄）。",
    },
    "carblock_first": {
        "en":    "First car",
        "zh-tw": "第一輛車",
    },
    "carblock_middle": {
        "en":    "Full columns\nbetween",
        "zh-tw": "中間\n整欄數",
    },
    "carblock_last": {
        "en":    "Last car",
        "zh-tw": "最後一輛車",
    },
    "carblock_total": {
        "en":    "Total: {n} cars",
        "zh-tw": "共 {n} 輛車",
    },
    "delete_block_title": {
        "en":    "Cars to delete — garage block",
        "zh-tw": "要刪除的車輛 — 車庫區塊",
    },
    "delete_block_hint": {
        "en":    "The garage fills top→bottom by column. Click your FIRST car's row (left) and your LAST car's row (right), and enter how many FULL columns sit between them (0 = the last car is in the very next column). Every car in this block is deleted.",
        "zh-tw": "車庫依欄由上而下排列。點選第一輛車的列（左）與最後一輛車的列（右），並輸入兩者之間有幾個「整欄」（0 = 最後一輛車就在下一欄）。此區塊內的所有車輛都會被刪除。",
    },
    "delete_confirm": {
        "en":    "I understand all cars in between the first and last car will be deleted.",
        "zh-tw": "我了解第一輛車與最後一輛車之間的所有車輛都會被刪除。",
    },
    "log_loop": {
        "en":    "Loop",
        "zh-tw": "循環",
    },
    "log_navigating": {
        "en":    "  Navigating: {keys}",
        "zh-tw": "  導航中：{keys}",
    },
    "log_loop1_start": {
        "en":    "  Starting at row {row} — no navigation needed.",
        "zh-tw": "  從第 {row} 排開始 — 無需移動。",
    },
    "log_open_action_menu": {
        "en":    "  Pressing Enter to open action menu...",
        "zh-tw": "  按下 Enter 開啟動作選單...",
    },
    "log_esc_back": {
        "en":    "  Pressing ESC ×2 to exit...",
        "zh-tw": "  按下 ESC ×2 返回...",
    },
    "log_buy_key": {
        "en":    "  Pressing [{key}]",
        "zh-tw": "  按下 [{key}]",
    },
    "status_user_select": {
        "en":    "Please select a new 22B-STI and open the action menu.",
        "zh-tw": "請選擇一輛新的 22B-STI 並開啟動作選單。",
    },
    "status_waiting_action_menu": {
        "en":    "Waiting for action menu (Ride This Car)...",
        "zh-tw": "等待動作選單（駕駛車輛）...",
    },
    "status_racing": {
        "en":    "Racing — holding W...",
        "zh-tw": "比賽中 — 按住 W...",
    },
    "status_waiting_for": {
        "en":    "Waiting for {label}...",
        "zh-tw": "等待 {label}...",
    },
    # ── Setting tooltips ─────────────────────────────────────────
    "tip_race_threshold": {
        "en":    "How closely the screen must match the template to count as detected.\nHigher = stricter. Lower = more lenient but may cause false detections.",
        "zh-tw": "畫面與樣本的相符程度，達到此值才視為偵測成功。\n數值越高越嚴格，越低則越寬鬆但可能誤判。",
    },
    "tip_race_check_interval": {
        "en":    "How often the screen is checked for each state (in seconds).\nLower = faster response but uses more CPU.",
        "zh-tw": "每次偵測畫面狀態的間隔時間（秒）。\n數值越低反應越快，但 CPU 使用率越高。",
    },
    "tip_race_post_key_wait": {
        "en":    "How long to wait after pressing a key before the next action (in seconds).\nIncrease if the game misses key presses.",
        "zh-tw": "按下按鍵後，等待下一個動作的時間（秒）。\n若遊戲漏接按鍵，請增加此數值。",
    },
    "tip_mastery_threshold": {
        "en":    "How closely the screen must match the template to count as detected.\nHigher = stricter. Lower = more lenient but may cause false detections.",
        "zh-tw": "畫面與樣本的相符程度，達到此值才視為偵測成功。\n數值越高越嚴格，越低則越寬鬆但可能誤判。",
    },
    "tip_mastery_cutscene_wait": {
        "en":    "How long to wait for the 'Ride This Car' cutscene before pressing ESC (in seconds).\nDefault 11. Increase if the cutscene runs longer on your machine.",
        "zh-tw": "按下 ESC 前等待「乘坐這輛車」過場動畫的時間（秒）。\n預設 11。若你的電腦過場動畫較長，請增加此數值。",
    },
    "tip_mastery_grid_unlock_wait": {
        "en":    "How long to wait after unlocking each mastery-tree node before moving to the next (in seconds).\nDefault 1.25. Increase on weaker hardware if nodes don't register before the cursor moves on.",
        "zh-tw": "解鎖每個熟練度樹節點後、移動到下一個之前的等待時間（秒）。\n預設 1.25。若硬體較弱、節點尚未生效游標就移動，請調高。",
    },
    "tip_menu_tap_wait": {
        "en":    "Delay after each menu cursor tap (Up/Down arrows) in Mastery and Delete Cars (in seconds).\nDefault 0.25. Increase on weaker hardware if menu taps don't register before the next press.",
        "zh-tw": "熟練度與刪除車輛中，每次選單游標點按（上/下方向鍵）後的延遲（秒）。\n預設 0.25。若硬體較弱、點按尚未生效就按下一鍵，請調高。",
    },
    "tip_buy_post_key_wait": {
        "en":    "How long to wait between each key press during purchase (in seconds).",
        "zh-tw": "每次購買按鍵之間的等待時間（秒）。",
    },
    "tip_delete_post_key_wait": {
        "en":    "How long to wait between each key press during deletion (in seconds).",
        "zh-tw": "每次刪除按鍵之間的等待時間（秒）。",
    },
    "tip_wheelspin_post_key_wait": {
        "en":    "How long to wait between each key press during a spin (in seconds).",
        "zh-tw": "轉輪每次按鍵之間的等待時間（秒）。",
    },

    "mastery_start_row_label": {
        "en":    "Start from row",
        "zh-tw": "從第幾排開始",
    },
    "mastery_start_row_hint": {
        "en":    "(which row is your first car on?)",
        "zh-tw": "（你的第一台車在哪一排？）",
    },

    # ── Mastery mode toggle (detect / keys) ───────────────────
    "log_mkeys_ride": {
        "en":    "Pressing Enter — Ride This Car",
        "zh-tw": "按下 Enter — 駕駛這輛車",
    },
    "log_mkeys_cutscene": {
        "en":    "Waiting for the cutscene, then pressing ESC...",
        "zh-tw": "等待過場動畫後按 ESC…",
    },
    "log_mkeys_upgrade": {
        "en":    "Pressing Down + Enter — Upgrade & Tuning",
        "zh-tw": "按下 ↓ + Enter — 升級與調校",
    },
    "log_mkeys_mastery": {
        "en":    "Pressing Down ×7 + Enter — Car Mastery",
        "zh-tw": "按下 ↓ ×7 + Enter — 車輛熟練度",
    },
    "log_mkeys_wait_mastery": {
        "en":    "Waiting for the Mastery screen...",
        "zh-tw": "等待熟練度畫面…",
    },
    "log_mkeys_mycars": {
        "en":    "Pressing Up + Enter — My Cars",
        "zh-tw": "按下 ↑ + Enter — 我的車輛",
    },
    "log_mkeys_sort": {
        "en":    "Pressing X + Down ×6 + Enter — sort by Recently Added",
        "zh-tw": "按下 X + ↓ ×6 + Enter — 依最近新增排序",
    },
}


def t(string_key: str, lang: str, **kwargs) -> str:

    """Get a translated string. Falls back to English if missing."""
    entry = STRINGS.get(string_key, {})
    text  = entry.get(lang) or entry.get("en", f"[{string_key}]")
    if kwargs:
        text = text.format(**kwargs)
    return text
