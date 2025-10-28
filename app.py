# 檔名: app.py
from flask import Flask, render_template, request

app = Flask(__name__)

# --- 模擬資料庫 ---
def get_sessions_from_db():
    """模擬抓取場次"""
    return [
        {"id": "S001", "name": "週一 18:00 - 20:00 (A 場地)"},
        {"id": "S002", "name": "週三 19:00 - 21:00 (B 場地)"},
        {"id": "S003", "name": "週五 17:00 - 19:00 (A 場地)"},
        {"id": "S004", "name": "週六 10:00 - 12:00 (C 場地)"},
    ]

def get_attributes_list():
    """定義可以分析的屬性"""
    # 就像你說的 "all 勝率 失誤率"
    return ["ALL (總覽)", "勝率", "失誤率", "出席率", "得分率"]
# --------------------


# 讓首頁同時支援 GET (載入) 和 POST (提交)
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    
    # --- 1. 準備下拉選單的資料 (無論 GET 或 POST 都需要) ---
    sessions = get_sessions_from_db()
    attributes = get_attributes_list()
    
    # --- 2. 準備傳回網頁的變數 (先設定預設值) ---
    chart_placeholder_text = None  # 用來放圖表區的提示文字
    selected_session_id = None     # 用來記住使用者選了哪個場次
    selected_attribute = None      # 用來記住使用者選了哪個屬性
    search_query = None            # 用來記住搜尋關鍵字

    # --- 3. 處理表單提交 (如果是 POST 請求) ---
    if request.method == 'POST':
        # 從表單接收資料
        search_query = request.form.get('search_query')
        selected_session_id = request.form.get('session_id')
        selected_attribute = request.form.get('attribute_name')
        
        # (示範) 在 Python 終端機印出收到的資料
        print(f"--- 收到生成圖表請求 ---")
        print(f"搜尋關鍵字: {search_query}")
        print(f"選擇的場次: {selected_session_id}")
        print(f"選擇的屬性: {selected_attribute}")
        
        # 
        # 在這裡，你可以呼叫你的 Python 函式去「開始做事」
        # 例如: data = your_function(selected_session_id, selected_attribute)
        #
        
        # 準備一個文字，傳回網頁的「圖表區」
        chart_placeholder_text = f"成功! Python 正在為您分析：\n場次 [{selected_session_id}] 的 [{selected_attribute}] 資料"

    # --- 4. 渲染網頁 ---
    # 把所有資料一次傳遞給 index.html
    return render_template(
        'index.html',
        sessions=sessions,
        attributes=attributes,
        chart_data=chart_placeholder_text,  # 傳遞圖表區的文字
        # 把使用者剛選的值再傳回去，讓下拉選單 "記住" 選擇
        current_session=selected_session_id,
        current_attribute=selected_attribute,
        current_search=search_query
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)