import machine
import time
import random
from machine import Pin, I2C
import ssd1306 # 導入 SSD1306 OLED 函式庫

# --- 引腳定義 ---
# 燈號引腳 (紅、綠、黃)
ledPins = [16, 12, 13]
# 按鈕引腳 (按鈕 A, 按鈕 B)
buttonPins = [5,36]
# 蜂鳴器引腳已移除

# OLED 引腳 (請根據你的實際接線修改)
# 範例: SCL 接 GPIO22, SDA 接 GPIO21
oled_scl = 22
oled_sda = 21
oled_width = 128
oled_height = 64

# --- 遊戲設定 ---
# 遊戲音調已移除
# gameTones = [196, 262, 330]  # G3 (紅), C4 (綠), E4 (黃)

# 定義最大遊戲長度
MAX_GAME_LENGTH = 100

# --- 初始化硬體 ---
leds = [Pin(pin, Pin.OUT) for pin in ledPins]
buttons = [Pin(pin, Pin.IN, Pin.PULL_UP) for pin in buttonPins]
# 蜂鳴器初始化已移除
# speaker = PWM(Pin(speakerPin))

# 確保所有 LED 初始為關閉狀態
for led in leds:
    led.value(0)

# 初始化 OLED
i2c = I2C(scl=Pin(oled_scl), sda=Pin(oled_sda))
oled = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c)

# --- 遊戲變數 ---
gameSequence = [0] * MAX_GAME_LENGTH
gameIndex = 0 # 當前遊戲進行到的關卡 (也是序列長度)
current_selection_index = 0 # 玩家在 OLED 上選擇的當前框框索引 (0, 1, 2)

# --- 自定義字符數據 ---
# 你提供的 CHARACTER_DATA
CHARACTER_DATA = {
    "↑": [0, 0, 1, 0, 3, 128, 3, 128, 5, 64, 9, 32, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
    "□": [0, 0, 0, 0, 63, 254, 32, 2, 32, 2, 32, 2, 32, 2, 32, 2, 32, 2, 32, 2, 32, 2, 32, 2, 32, 2, 32, 2, 32, 2, 63, 254],
    "紅": [0, 0, 8, 0, 16, 0, 18, 254, 100, 16, 60, 16, 26, 16, 18, 16, 63, 16, 125, 16, 9, 144, 42, 16, 107, 16, 73, 16, 72, 16, 9, 255],
    "黃": [0, 0, 4, 32, 63, 252, 4, 32, 7, 224, 0, 0, 255, 254, 31, 248, 17, 8, 17, 8, 31, 248, 17, 8, 31, 248, 4, 48, 56, 76, 64, 6],
    "綠": [0, 0, 16, 64, 48, 252, 44, 136, 200, 248, 56, 136, 53, 254, 44, 32, 247, 38, 16, 188, 84, 240, 82, 104, 83, 172, 211, 38, 16, 224, 0, 0],
    "✓": [0, 0, 0, 0, 0, 0, 0, 128, 0, 192, 1, 128, 3, 0, 2, 0, 4, 0, 12, 0, 8, 0, 136, 0, 208, 0, 80, 0, 112, 0, 32, 0],
}

# 輔助函數：根據 CHARACTER_DATA 繪製自定義字符 (8x16 像素)
# 數據格式：32 bytes, 16 像素高，每行 2 bytes (16 像素寬)
def draw_custom_char(x, y, char_data, color=1):
    for row in range(16): # 16 像素高
        byte1 = char_data[row * 2]
        byte2 = char_data[row * 2 + 1]
        
        # 繪製左 8 像素
        for bit in range(8):
            if (byte1 >> (7 - bit)) & 1: # 從高位到低位讀取
                oled.pixel(x + bit, y + row, color)
        
        # 繪製右 8 像素
        for bit in range(8):
            if (byte2 >> (7 - bit)) & 1: # 從高位到低位讀取
                oled.pixel(x + 8 + bit, y + row, color)

# --- OLED 顯示相關 ---
# OLED 顯示元素的位置和尺寸

# 由於自定義字符是 16x16 像素，重新定義尺寸
char_width = 16
char_height = 16

box_width = 20 # 方框的寬度
box_height = 10 # 方框的高度

# 頂部顏色文字的起始 X 座標，使它們大致居中並有間隔
# 總寬度 128 像素，3 個字符 * 16 像素 = 48 像素
# (128 - 48) / 4 間隔 = 20 像素左右
text_x_coords = [10, 10 + char_width + 20, 10 + 2*(char_width + 20)] 
# 範例： 紅 (10), 黃 (46), 綠 (82) - 這樣應該會比較分散

# 文字的 Y 座標 (頂部)
text_y = 5

# 方框的 Y 座標，在文字下方
box_y = text_y + char_height + 5 

# 方框的 X 座標，與文字對齊並在下方
# 這行是之前出錯的地方，現在 box_width 已經定義了
box_x_coords = [x_coord + (char_width // 2) - (box_width // 2) for x_coord in text_x_coords] # 讓方框在文字下方居中

# 箭頭的 Y 座標，在方框下方
arrow_y = box_y + box_height + 5 

# 在 OLED 上繪製整個遊戲畫面
def draw_game_screen(selected_index=-1, confirmed_index=-1):
    oled.fill(0) # 清除螢幕

    # 顯示頂部的顏色文字
    for i, color_name in enumerate(["紅", "黃", "綠"]): # 直接使用文字字串作為 KEY
        draw_custom_char(text_x_coords[i], text_y, CHARACTER_DATA[color_name])

    # 顯示下方的方框
    for i in range(len(leds)):
        draw_custom_char(box_x_coords[i], box_y, CHARACTER_DATA["□"]) # 繪製方框字符

    # 顯示選擇箭頭
    if selected_index != -1:
        # 箭頭的 X 座標應該在選中框的中心
        arrow_x = box_x_coords[selected_index] + (box_width // 2) - (char_width // 2) 
        draw_custom_char(arrow_x, arrow_y, CHARACTER_DATA["↑"])

    # 顯示確認標誌 (如果確認了某個框框)
    if confirmed_index != -1:
        # 勾號在方框內
        check_x = box_x_coords[confirmed_index] + (box_width // 2) - (char_width // 2)
        check_y = box_y + (box_height // 2) - (char_height // 2) + 2 # 讓勾號在方框內稍微偏上
        draw_custom_char(check_x, check_y, CHARACTER_DATA["✓"]) 

    oled.show()

# --- 遊戲功能函數 (與之前版本相同，但會調用新的 draw_game_screen) ---

# 點亮 LED (蜂鳴器相關已移除)
def light_led(led_index):
    print(f"Lighting LED {led_index} ({['紅', '黃', '綠1'][led_index]})")
    if 0 <= led_index < len(leds):
        leds[led_index].value(1)
        time.sleep(0.5) # 稍微長一點的亮燈時間
        leds[led_index].value(0)
    else:
        print(f"Error: Invalid LED index {led_index}")

# 播放當前遊戲序列
def play_sequence():
    oled.fill(0)
    oled.text("看著我！", 0, 0)
    oled.show()
    time.sleep(1)

    for i in range(gameIndex):
        current_led_index = gameSequence[i]
        light_led(current_led_index) # 呼叫不帶音效的 light_led
        time.sleep(0.1) # 每個燈之間的間隔

# 讀取按鈕輸入，並處理按鈕 A 的選擇移動
def read_buttons_for_selection():
    global current_selection_index
    global current_step # 讓函數可以知道是第幾個步驟

    # 初始顯示選擇狀態
    draw_game_screen(selected_index=current_selection_index)
    oled.text(f"第 {current_step + 1} 個", 0, oled_height - 10) # 顯示當前是第幾個
    oled.show() # 確保文字更新

    while True:
        # 檢查按鈕 A (移動選擇)
        if buttons[0].value() == 0: # 按鈕 A 被按下 (0是按下，1是未按下)
            time.sleep(0.05) # 去抖動
            while buttons[0].value() == 0: # 等待按鈕釋放
                time.sleep(0.01)
            
            current_selection_index = (current_selection_index + 1) % len(leds) # 循環選擇 0, 1, 2
            draw_game_screen(selected_index=current_selection_index) # 更新 OLED 顯示選中的框框
            oled.text(f"第 {current_step + 1} 個", 0, oled_height - 10) # 重新顯示步驟文字
            oled.show()
            print(f"Selected: {['紅', '黃', '綠'][current_selection_index]}")
            time.sleep(0.1) # 避免過快切換
        
        # 檢查按鈕 B (確認選擇)
        if buttons[1].value() == 0: # 按鈕 B 被按下
            time.sleep(0.05) # 去抖動
            while buttons[1].value() == 0: # 等待按鈕釋放
                time.sleep(0.01)
            
            # 顯示確認標誌
            draw_game_screen(selected_index=current_selection_index, confirmed_index=current_selection_index)
            oled.text(f"第 {current_step + 1} 個", 0, oled_height - 10) # 重新顯示步驟文字
            oled.show()
            time.sleep(0.5) # 讓確認標誌顯示一段時間
            return current_selection_index # 返回確認的索引
        
        time.sleep(0.01) # 短暫延遲，避免過度查詢

# 檢查用戶輸入序列
def check_user_sequence():
    global gameIndex, current_selection_index

    # 針對序列中的每一個燈，讓玩家選擇並確認
    for i in range(gameIndex):
        global current_step # 讓 read_buttons_for_selection 知道當前是哪個步驟
        current_step = i
        expected_led_index = gameSequence[i] # 預期的燈號

        # 顯示框框並等待玩家選擇
        current_selection_index = 0 # 重置起始選擇為第一個框框
        
        actual_selected_index = read_buttons_for_selection() # 玩家確認的索引

        print(f"Expected: {['紅', '黃', '綠'][expected_led_index]}, User selected: {['紅', '黃', '綠'][actual_selected_index]}")

        # 判斷是否正確
        if actual_selected_index != expected_led_index:
            return False # 錯誤，遊戲結束

        # 如果正確，給予提示音效 (這裡因為蜂鳴器拔掉，可以考慮讓燈閃爍一下作為替代)
        # 替代音效：讓正確的燈閃爍兩下
        leds[expected_led_index].value(1)
        time.sleep(0.1)
        leds[expected_led_index].value(0)
        time.sleep(0.1)
        leds[expected_led_index].value(1)
        time.sleep(0.1)
        leds[expected_led_index].value(0)
        time.sleep(0.1)


    return True # 所有步驟都正確

# 遊戲結束
def game_over():
    global gameIndex, gameSequence
    score = gameIndex - 1 # 成功完成的關卡數
    print(f"遊戲結束！你的分數: {score}")

    oled.fill(0)
    oled.text("遊戲結束！", 0, 0)
    oled.text(f"分數: {score}", 0, 16)
    oled.show()
    time.sleep(2)

    # 失敗效果：所有燈快速閃爍
    for _ in range(3):
        for led in leds:
            led.value(1)
        time.sleep(0.2)
        for led in leds:
            led.value(0)
        time.sleep(0.2)
    
    # 重置遊戲狀態
    gameIndex = 0
    gameSequence = [0] * MAX_GAME_LENGTH # 重新填充遊戲序列
    
    oled.fill(0)
    oled.text("按任意鍵", 0, 0)
    oled.text("重新開始", 0, 16)
    oled.show()

    # 等待玩家按下按鈕重新開始
    while True:
        for i in range(len(buttons)):
            if buttons[i].value() == 0:
                time.sleep(0.05)
                while buttons[i].value() == 0:
                    time.sleep(0.01)
                return # 返回主迴圈開始新遊戲
        time.sleep(0.01)

# 升級效果 (蜂鳴器移除，改用燈號閃爍)
def play_level_up_effect():
    # 讓所有燈依序閃爍
    for i in range(len(leds)):
        leds[i].value(1)
        time.sleep(0.1)
        leds[i].value(0)
    time.sleep(0.1)
    for i in range(len(leds) - 1, -1, -1): # 反向再閃一次
        leds[i].value(1)
        time.sleep(0.1)
        leds[i].value(0)

# --- 遊戲主迴圈 ---
random.seed(time.ticks_ms()) # 初始化隨機數生成器

oled.fill(0)
oled.text("記憶挑戰", 0, 0)
oled.text("按任意鍵開始", 0, 16)
oled.show()
# 等待玩家按下任意鍵開始第一局遊戲
while True:
    for i in range(len(buttons)):
        if buttons[i].value() == 0:
            time.sleep(0.05)
            while buttons[i].value() == 0:
                time.sleep(0.01)
            break # 跳出等待迴圈
    else:
        time.sleep(0.01)
        continue
    break

while True:
    # 增加新的隨機顏色到序列
    # random.randint(0, len(leds) - 1) 會產生 0, 1, 2 對應紅、綠、黃
    gameSequence[gameIndex] = random.randint(0, len(leds) - 1)
    gameIndex += 1
    
    # 防止序列超出最大長度
    if gameIndex > MAX_GAME_LENGTH:
        gameIndex = MAX_GAME_LENGTH # 或者你可以在這裡宣佈勝利
        oled.fill(0)
        oled.text("恭喜你！", 0, 0)
        oled.text("所有關卡完成！", 0, 16)
        oled.show()
        time.sleep(3)
        game_over() # 重新開始遊戲
        continue

    print(f"\n--- 第 {gameIndex} 關 ---")
    oled.fill(0)
    oled.text(f"第 {gameIndex} 關", 0, 0)
    oled.text("看著我！", 0, 16)
    oled.show()
    time.sleep(1.5) # 給玩家準備時間

    play_sequence() # 播放當前完整的燈光序列

    # 清除 OLED 顯示，準備用戶輸入
    oled.fill(0)
    oled.show()
    time.sleep(0.5)

    # 檢查用戶輸入 (在 read_buttons_for_selection 中會顯示當前步驟)
    if not check_user_sequence(): # 檢查用戶輸入
        game_over() # 遊戲結束
        continue # 從頭開始遊戲主迴圈

    # 如果所有步驟都正確，進入下一關
    play_level_up_effect() # 播放升級效果 (燈號閃爍)
    oled.fill(0)
    oled.text(f"第 {gameIndex} 關", 0, 0)
    oled.text("成功！", 0, 16)
    oled.show()
    time.sleep(1.5)