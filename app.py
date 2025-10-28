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
        {"id": "S001", "name": "週一 18:00 - 20:00 (A 場地)"},
        {"id": "S002", "name": "週三 19:00 - 21:00 (B 場地)"},
        {"id": "S003", "name": "週五 17:00 - 19:00 (A 場地)"},
        {"id": "S004", "name": "週六 10:00 - 12:00 (C 場地)"},
    ]

# --- ▼▼▼ 唯一修改的地方 ▼▼▼ ---
def get_attributes_list():
    """定義可以分析的屬性"""
    # 在列表中加入 "球種"
    return ["ALL (總覽)", "勝率", "失誤率", "出席率", "得分率", "球種"]
# --- ▲▲▲ 唯一修改的地方 ▲▲▲ ---

# --- 模擬比賽報告連結 (來自你的 HTML) ---
def get_report_links():
    """模擬 HTML 中的 links"""
    return [
        {"route": "report_view", "param": "R001", "name": "2024 夏季聯賽 - 總報告"},
        {"route": "report_view", "param": "R002", "name": "2024 秋季訓練 - 總報告"},
    ]

@app.route('/report/<report_id>')
def report_view(report_id):
    """一個假的路由，用來讓 url_for('report_view') 能運作"""
    return f"這是報告 {report_id} 的頁面"
# --------------------


# --- 路由 1: 儀表板首頁 (只處理 GET 請求) ---
@app.route('/', methods=['GET'])
def dashboard():
    
    sessions = get_sessions_from_db()
    attributes = get_attributes_list() # <-- 這裡會自動抓到新的列表
    links = get_report_links()
    
    # 傳遞預設值給模板
    return render_template(
        'index.html',
        sessions=sessions,
        attributes=attributes,
        links=links,
        chart_data=None, 
        current_session=None,
        current_attribute=None,
        current_search=""
    )

# --- 路由 2: 【全新】處理分析請求的 API ---
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    if llm_core is None:
        return jsonify({"error": "AI 核心模組 (llm_core.py) 載入失敗。"}), 500

    try:
        # 1. 從前端的 fetch 請求中獲取 JSON 資料
        data = request.get_json()
        search_query = data.get('search_query')
        session_id = data.get('session_id')
        attribute = data.get('attribute_name')

        if not session_id or not attribute:
            return jsonify({"error": "缺少 'session_id' 或 'attribute_name'"}), 400
        
        print(f"--- 收到 API 請求 ---")
        print(f"搜尋: {search_query}, 場次: {session_id}, 屬性: {attribute}")
        
        # 2. 呼叫「大腦」核心
        result = llm_core.generate_analysis_from_dashboard(
            session_id=session_id,
            attribute=attribute,
            search_query=search_query
        )
        
        # 3. 檢查 AI 執行是否出錯
        if result["error"]:
            print(f"AI 執行錯誤: {result['error']}")
            return jsonify({"error": f"AI 分析失敗: {result['error']}"}), 500
        
        # 4. 【關鍵】將 Matplotlib 圖表轉換為 Base64 圖片字串
        image_base64 = None
        if result["figure"]:
            buf = io.BytesIO()
            result["figure"].savefig(buf, format='png', dpi=150, bbox_inches='tight')
            image_bytes = buf.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            buf.close()

        # 5. 將所有結果包裝成 JSON 回傳給前端
        return jsonify({
            "status": "success",
            "analysis_text": result["text"],        # AI 生成的文字
            "chart_image_base64": image_base64  # AI 生成的圖表 (Base64)
        })

    except Exception as e:
        print(f"Error in /api/analyze: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)

