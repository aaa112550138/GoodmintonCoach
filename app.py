# ▼▼▼ 修改 1: 匯入 os 和 send_from_directory ▼▼▼
from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
import io
import base64 
import os # <-- 需要 os 模組來組合路徑

try:
    import llm_core
except ImportError:
    llm_core = None
    print("="*50)
    print("錯誤: 找不到 llm_core.py。")
    print("="*50)

#init
app = Flask(__name__)

# ▼▼▼ 修改 2: (Part 1) 定義 report_pics 資料夾的絕對路徑 ▼▼▼
# app.root_path 指的是 app.py 所在的資料夾
REPORT_PICS_DIR = os.path.join(app.root_path, 'report_pics')
# 
# 你的資料夾結構現在應該是:
# badminton_app/
# ├── app.py              <-- (app.root_path)
# ├── report_pics/        <-- (REPORT_PICS_DIR)
# │   └── chao_vs_tao/
# │       ├── win_rate.png
# │       └── error_rate.png
# ├── static/
# └── templates/
#

#fake db
# --- 模擬資料庫  ---
def get_sessions_from_db():
    """模擬抓取場次"""
    return [
        {"id": "S001", "name": "場次1"},
    ]

def get_attributes_list():
    """定義可以分析的屬性"""
    return ["ALL (總覽)", "勝率", "失誤率", "出席率", "球落點分布", "球種"]

def get_report_links():
    """模擬 HTML 中的 links"""
    return [
        {"route": "report_view", "param": "R001", "name": "R001: 趙 vs 陶 (chao_vs_tao)"},
    ]

def get_main_text(report_id):
    """ 模擬你要放的主要文字 (根據 ID) """
    return f"""
    這裡是報告 {report_id} 的主要文字區塊。
    周天成的主要得分手段為「落地致勝」，主要失分原因為「出界」、「掛網」和「未過網」。

    關鍵發現：

    得分手段集中： 周天成的得分手段主要依賴於「落地致勝」（80次），遠高於其他得分方式。這顯示其進攻具備一定威脅性，能直接得分。
    數據來源：player_win_reasons
    非受迫性失誤為主： 周天成的失分主要來自於「出界」（74次）、「掛網」（60次）和「未過網」（24次），這些都屬於非受迫性失誤。這暗示周天成在比賽中可能存在穩定性問題，需要減少自身失誤。
    數據來源：player_lose_reasons
    
    總結：

    周天成具備強勁的進攻能力，但需要透過減少非受迫性失誤來提升比賽穩定性。
    """

# ▼▼▼ 修改 3: 調整 get_chart_card_data ▼▼▼
def get_chart_card_data(report_id):
    """
    模擬圖表的資料 (根據 ID)
    """
    image_folder_name = ""
    if report_id == "R001":
        # 這裡對應到你說的資料夾
        image_folder_name = "chao_vs_tao" 
    elif report_id == "R002":
        image_folder_name = "other" # 假設有另一個
    else:
        # 給一個預設值，以防萬一
        image_folder_name = "default" 

    # *** 請確保你的 'report_pics/chao_vs_tao/' 資料夾中
    # *** 真的有 'win_rate.png' 和 'error_rate.png' 這兩個檔案
    
    mock_data = [
        {
            # 這是關鍵修改：
            # 網址 (URL) 指向我們即將建立的新路由 /report-images/
            # Flask 會把這個請求轉發給 serve_report_image() 函式
            "image_url": f"/report-images/{image_folder_name}/diff_balls.png", 
            "title": f"{image_folder_name} - 不同球種",
            "description": "這是從 report_pics 動態載入的球種圖。"
        },
        {
            "image_url": f"/report-images/{image_folder_name}/different_places_score.png",
            "title": f"{image_folder_name} - 得分分布圖",
            "description": "這是從 report_pics 動態載入的得分分布圖。"
        },
        {
            "image_url": f"/report-images/{image_folder_name}/opp_lose_reasons.png",
            "title": f"{image_folder_name} - 得分分析圖",
            "description": "這是從 report_pics 動態載入的得分分析圖。"
        },
        {
            "image_url": f"/report-images/{image_folder_name}/running.png",
            "title": f"{image_folder_name} - 得分分析圖",
            "description": "這是從 report_pics 動態載入的得分分析圖。"
        },
        {
            "image_url": f"/report-images/{image_folder_name}/score_reason.png",
            "title": f"{image_folder_name} - 得分分析圖",
            "description": "這是從 report_pics 動態載入的得分分析圖。"
        },
        {
            "image_url": f"/report-images/{image_folder_name}/smash.png",
            "title": f"{image_folder_name} - 得分分析圖",
            "description": "這是從 report_pics 動態載入的得分分析圖。"
        },
        {
            "image_url": f"/report-images/{image_folder_name}/time_error.png",
            "title": f"{image_folder_name} - 得分分析圖",
            "description": "這是從 report_pics 動態載入的得分分析圖。"
        },
    ]
    
    # 附註: 更保險的寫法是使用 url_for
    # path = f'{image_folder_name}/win_rate.png'
    # mock_data[0]["image_url"] = url_for('serve_report_image', path_to_image=path)
    # 這樣如果未來你改了 @app.route 的網址，這裡會自動更新。
    # 不過目前 f-string 的寫法是最直觀的。
    
    return mock_data
# --- ▲▲▲ 修改 3 完畢 ▲▲▲ ---


# --- 路由 1: 儀表板首頁 (保持不變) ---
@app.route('/', methods=['GET'])
def dashboard():
    sessions = get_sessions_from_db()
    attributes = get_attributes_list()
    links = get_report_links() 
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

# --- 路由 2: API (保持不變) ---
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    if llm_core is None:
        return jsonify({"error": "AI 核心模組 (llm_core.py) 載入失敗。"}), 500

    try:
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

# --- 路由 3: 報告頁面 (保持不變) ---
@app.route('/report/<report_id>')
def report_view(report_id):
    """
    動態報告頁面
    """
    print(f"正在為 {report_id} 生成報告頁面...")
    main_text = get_main_text(report_id)
    chart_items = get_chart_card_data(report_id) # <-- 這裡會抓到新的 URL
    
    return render_template(
        'report.html', 
        report_title=f"報告 {report_id} 分析", 
        main_introduction_text=main_text,
        chart_data_list=chart_items
    )

# ▼▼▼ 修改 2: (Part 2) 新增 "圖片傳送路由" ▼▼▼
#
@app.route('/report-images/<path:path_to_image>')
def serve_report_image(path_to_image):
    """
    這個路由會攔截所有 /report-images/ 開頭的請求
    並從 REPORT_PICS_DIR (也就是 'report_pics' 資料夾)
    安全地傳送 'path_to_image' (例如 "chao_vs_tao/win_rate.png")
    """
    print(f"正在從 {REPORT_PICS_DIR} 傳送圖片: {path_to_image}")
    return send_from_directory(REPORT_PICS_DIR, path_to_image)
# --- ▲▲▲ 修改 2 完畢 ▲▲▲ ---


if __name__ == '__main__':
    app.run(debug=True, port=5000)