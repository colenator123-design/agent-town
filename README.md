# Agent Town

一個 local-first 的 macOS 桌面夥伴城鎮。Agent Town 像 Finder 一樣管理不同角色；角色只負責 UI，檔案操作、規劃、安全檢查與紀錄都在獨立的 Agent Core。

目前支援：

- 像 Finder 的 Agent Town：分類、搜尋、單擊查看能力、雙擊召喚
- macOS 桌布上的透明動態入口：皮卡丘會在黃色小屋旁活動，點擊進城
- Menu Bar 皮卡丘入口，可隨時打開 Town 或直接召喚
- 皮卡丘右鍵選單可回到 Agent Town
- 多邊獸 Project 專案中心：限定管理 `~/Project`，可建立、瀏覽、重新命名及安全移除檔案
- 快龍通訊助理：透過 macOS Mail 唯讀同步並分類今天的 Gmail
- 美洛耶塔 YouTube Music 助理：搜尋、指定歌曲、播放控制、情境模式、睡眠計時、歌單捷徑與稍後聽
- 妙蛙種子、洛托姆與卡比獸保留為後續助理位置
- 透明、置頂、可拖曳的皮卡丘桌面視窗
- 真正的逐格角色動畫，加上呼吸浮動、電光、狀態光暈與右鍵選單
- 不同 Agent 狀態會改變角色動畫速度
- 點擊角色開啟自然語言輸入框
- 狀態膠囊、快捷操作與圖形化任務預覽
- 將 `workspace/` 內的檔案依類型整理
- 所有移動與建立資料夾操作先預覽、再確認
- SQLite 操作紀錄
- 一鍵復原上一批移動操作
- 最近五筆執行紀錄
- 操作紀錄預設保留 7 天，啟動時自動清除過期紀錄
- 拖放外部檔案到角色，預覽後安全複製至 `workspace/Inbox/`
- 遞迴掃描子資料夾，遇到同名檔案自動使用 `_2`、`_3` 編號
- Planner 與 Executor 在背景執行，處理大量檔案時動畫與 UI 仍保持回應
- 可理解「刪除今天／昨天的截圖」，搜尋 Desktop、Documents、Downloads
- 刪除屬 RED 操作：完整預覽、強制確認，而且只移到 macOS 垃圾桶
- 圖片拖放助理：顯示尺寸、格式與容量，或選擇匯入
- 使用 macOS Vision 在本機進行繁中／英文 OCR，不上傳圖片
- OCR 結果可複製到剪貼簿，或預覽後存成 `workspace/Notes/*.md`
- macOS Vision 本機圖片分類，以及 QR／條碼內容擷取
- 多張拖入圖片以 SHA-256 檢查內容完全相同的重複檔
- 使用 OCR 第一行產生安全檔名，預覽後匯入 `workspace/Images/`
- 嚴格限制檔案工具只能存取專案 `workspace/`

## 啟動

```bash
uv sync --extra dev
uv run pikachu-agent
```

也可執行：

```bash
./run.sh
```

若專案位於 `~/Project/AgentTown`，可以把 `packaging/Agent Town.app` 複製到桌面或 Applications，之後直接雙擊啟動。

啟動後會在桌布黃色小屋旁顯示動態入口。點擊入口打開 Agent Town，單擊皮卡丘查看能力，雙擊或按「召喚」讓它進入工作模式，再點一下皮卡丘輸入例如：

- `幫我整理這些檔案`
- `圖片放 Images，PDF 放 Documents`
- `undo` 或 `復原上一個操作`
- `幫我把今天截圖的檔案刪除`
- `清理昨天的螢幕截圖`

右鍵點皮卡丘可開啟選單或結束程式。

截圖搜尋目錄可用冒號分隔的 `PIKA_SCREENSHOT_DIRS` 自訂。macOS 第一次讀取 Desktop、Documents 或 Downloads 時，可能會要求授權。

OCR helper 已預先編譯；修改 `tools/vision_ocr.swift` 後可執行 `scripts/build_ocr.sh` 重新建置。

可用 `PIKA_LOG_RETENTION_DAYS` 修改操作紀錄保留天數；最短為一天。這不會清除 `workspace/` 內的使用者檔案。

### 快龍與美洛耶塔

- 快龍讀取 macOS Mail 的彙總收件匣，只取得寄件者、主旨、未讀與旗標狀態，不保存郵件本文或附件。
- 美洛耶塔會用 Safari 開啟 YouTube Music。全域媒體控制需先執行 `brew install nowplaying-cli`。
- 美洛耶塔的歌單捷徑與稍後聽存在 `data/music.sqlite3`；此檔案已被 Git 忽略。

## 可選的 AI Planner

預設為完全離線的規則 Planner，不會上傳檔名。若要明確啟用 OpenAI Responses API：

```bash
uv sync --extra dev --extra ai
export OPENAI_API_KEY="你的金鑰"
export PIKA_ENABLE_AI=1
uv run pikachu-agent
```

可用 `PIKA_MODEL` 更換模型，預設為 `gpt-5.2`。AI 只會輸出符合 JSON Schema 的移動計畫，不能直接操作檔案；所有動作仍須經過安全檢查與使用者確認。

先把測試檔案放進 `workspace/`。程式不會碰觸該目錄外的內容。

## 測試

```bash
uv run pytest
```

## 架構

```text
UI -> Interaction -> Agent Core (planner/executor/verifier)
                         |
                    Safety policy
                         |
                  sandboxed file tools
                         |
                   SQLite journal
```

`PikachuWindow` 只接收 `AgentStatus`，不包含任何規劃或檔案操作邏輯。

## 隱私與素材

執行期資料、SQLite 紀錄、`.env`、虛擬環境與 `workspace/` 使用者檔案都不會加入 Git。

公開倉庫不附第三方角色圖片、動畫或角色 App 圖示；缺少素材時會使用文字與程式繪製的替代外觀。個人可在本機依 [`assets/README.md`](assets/README.md) 放入自己有權使用的素材，這些檔案會被 Git 忽略。

Pokémon 及相關角色名稱與權利屬其各自權利人。本專案為非官方、非商業的個人技術作品，未獲 Nintendo、Creatures 或 GAME FREAK 認可或贊助。
