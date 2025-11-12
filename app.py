from flask import Flask, render_template, request, jsonify, url_for
import io
import base64 

try:
    import llm_core
except ImportError:
    llm_core = None
    print("="*50)
    print("錯誤: 找不到 llm_core.py。")
    print("="*50)


app = Flask(__name__)

# --- 模擬資料庫 (保持不變) ---
def get_sessions_from_db():
    """模擬抓取場次"""
    return [
        {"id": "S001", "name": "場次1"}
    ]

def get_attributes_list():
    """定義可以分析的屬性"""
    return ["ALL (總覽)", "勝率", "失誤率", "出席率", "球落點分布", "球種"]

# --- 模擬比賽報告連結 (來自你的 HTML) ---
def get_report_links():
    """
    模擬 HTML 中的 links。
    "route" 欄位必須對應到 @app.route 函式的名稱 (report_view)
    "param" 欄位會被傳遞給 <report_id>
    """
    return [
        {"route": "report_view", "param": "R001", "name": "R001: 場次1"}
    ]

# --- (從上個範例) 模擬報告資料 (已修改為動態) ---
def get_main_text(report_id):
    """ 模擬你要放的主要文字 (根據 ID) """
    # 未來你可以用 report_id 去資料庫查詢
    return f"""
    這裡是報告 {report_id} 的主要文字區塊。
    這份報告總結了「週三 19:00 - 21:00 (B 場地)」的學員表現。
    整體而言，學員的殺球成功率顯著提升，但在網前小球的處理上失誤率偏高...
    """

def get_chart_card_data(report_id):
    """
    模擬圖表的資料 (根據 ID)
    (未來這裡會用 report_id 去資料庫查)
    """
    # 假設 R001 和 R002 用了不同的圖表標題
    if report_id == "R001":
        titles = ["R001-勝率分析", "R001-失誤分佈"]
    else:
        titles = ["R002-出席狀況", "R002-得分手段"]
        
    mock_data = [
        {
            "image_url": "/static/chart1.png", # 假設你有這些圖在 static 資料夾
            "title": titles[0],
            "description": "這是一兩行的文字，用來說明這張圖的重點。"
        },
        {
            "image_url": "/static/chart2.png",
            "title": titles[1],
            "description": "分析反手拍與正手拍的失誤比例。"
        },
    ]
    return mock_data
# --------------------


# --- 路由 1: 儀表板首頁 (只處理 GET 請求) ---
@app.route('/', methods=['GET'])
def dashboard():
    
    sessions = get_sessions_from_db()
    attributes = get_attributes_list()
    links = get_report_links() # <-- 取得要生成的連結
    
    # 傳遞預設值給模板
    return render_template(
        'index.html',
        sessions=sessions,
        attributes=attributes,
        links=links, # <-- 傳給 index.html
        chart_data=None, 
        current_session=None,
        current_attribute=None,
        current_search=""
    )

# --- 路由 2: 處理分析請求的 API (保持不變) ---
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    if llm_core is None:
        return jsonify({"error": "AI 核心模組 (llm_core.py) 載入失敗。"}), 500

    try:
        # ... (你提供的程式碼都很好，保持不變) ...
        data = request.get_json()
        search_query = data.get('search_query')
        session_id = data.get('session_id')
        attribute = data.get('attribute_name')

        if not session_id or not attribute:
            return jsonify({"error": "缺少 'session_id' 或 'attribute_name'"}), 400
        
        print(f"--- 收到 API 請求 ---")
        print(f"搜尋: {search_query}, 場次: {session_id}, 屬性: {attribute}")
        
        result = llm_core.generate_analysis_from_dashboard(
            session_id=session_id,
            attribute=attribute,
            search_query=search_query
        )
        
        if result["error"]:
            print(f"AI 執行錯誤: {result['error']}")
            return jsonify({"error": f"AI 分析失敗: {result['error']}"}), 500
        
        image_base64 = None
        if result["figure"]:
            buf = io.BytesIO()
            result["figure"].savefig(buf, format='png', dpi=150, bbox_inches='tight')
            image_bytes = buf.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            buf.close()

        return jsonify({
            "status": "success",
            "analysis_text": result["text"], 
            "chart_image_base64": image_base64 
        })

    except Exception as e:
        print(f"Error in /api/analyze: {e}")
        return jsonify({"error": str(e)}), 500


# --- ▼▼▼ 這是你要求的修改 ▼▼▼ ---
#
# 原本的: @app.route('/templates/report.html') 
# 原本的: def report_view(report_id):
#
# 修正為：
# 1. 路由 (Route) 應該是描述性的，例如 /report/
# 2. 路由中用 <report_id> 來接收變數
# 3. 函式名稱 report_view 必須和 get_report_links() 裡的 "route" 欄位一致
# 4. 函式 render_template('report.html', ...) 會去 'templates' 資料夾找 'report.html'
#
@app.route('/report/<report_id>')
def report_view(report_id):
    """
    這才是正確的「報告頁面」路由
    """
    print(f"正在為 {report_id} 生成報告頁面...")
    
    # 1. 根據傳入的 report_id 獲取專屬資料
    main_text = get_main_text(report_id)
    chart_items = get_chart_card_data(report_id)
    
    # 2. 渲染 'templates/report.html' 
    #    (Flask 會自動去 'templates' 資料夾找)
    return render_template(
        'report.html', 
        report_title=f"報告 {report_id} 分析", # 傳一個動態標題
        main_introduction_text=main_text,
        chart_data_list=chart_items
    )
# --- ▲▲▲ 修改完畢 ▲▲▲ ---


if __name__ == '__main__':
    app.run(debug=True, port=5000)