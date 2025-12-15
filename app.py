from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
import io
import base64 
import os 
import time
import json
# --- 嘗試匯入 llm_core ---
try:
    import llm_core
except ImportError:
    llm_core = None
    print("="*50)
    print("警告: 找不到 llm_core.py，AI 功能將使用模擬模式。")
    print("="*50)

app = Flask(__name__)
REPORT_PICS_DIR = os.path.join(app.root_path, 'report_pics')

# ... (保留原有的 get_sessions_from_db 等輔助函式，這裡省略以節省篇幅) ...
def get_sessions_from_db():
    return [{"id": "S001", "name": "場次1"}]

def get_attributes_list():
    return ["ALL (總覽)", "勝率", "失誤率", "出席率", "球落點分布", "球種","不同擊球位置","跑動距離"]

def get_report_links():
    return [{"route": "report_view", "param": "R001", "name": "R001: 趙 vs 陶 (chao_vs_tao)"}]

def get_main_text(report_id):
    """
    根據 report_id 返回報告的主要摘要文字。
    
    由於這個文字是總結性的，我們假設它是專門為 R001 撰寫的。
    未來可以從專門的 `report_summary.json` 中讀取。
    """
    if report_id == "R001":
        # 使用 Markdown 或 HTML 格式來呈現文字
        return """
### 周天成得分/失分分析摘要

**得分手段集中：**
周天成的主要得分手段依賴於「落地致勝」(80次)，遠高於其他得分方式。這顯示其進攻具備一定威脅性，能直接得分。

**非受迫性失誤為主：**
周天成的失分主要來自於「出界」(74次)、「掛網」(60次) 和「未過網」(24次)，這些都屬於非受迫性失誤。這暗示周天成在比賽中可能存在穩定性問題，需要減少自身失誤。

---

**總結：**

周天成具備強勁的進攻能力，但需要透過減少非受迫性失誤來提升比賽穩定性。
"""
    # 預設情況
    return f"這裡是報告 {report_id} 的文字摘要..."

def get_session_id_from_report_id(report_id):
    """
    輔助函式：根據報告ID獲取對應的Session ID。
    這裡需要根據您的實際數據庫或命名規則進行調整。
    
    由於您的 JSON 檔名是 S001_metadata.json，我們假設 R001 對應 S001。
    """
    if report_id == "R001":
        return "S001"
    # 如果未來有更多報告，可以在這裡擴展
    # elif report_id == "R002":
    #     return "S002"
    return None # 如果找不到，返回 None

def get_chart_card_data(report_id):
    # 1. 獲取 Session ID
    session_id = get_session_id_from_report_id(report_id)
    if not session_id:
        return []

    # 2. 構造 metadata.json 的路徑
    # 根據您在 llm_core.py 中設定的路徑: report_pics/others/S001_metadata.json
    metadata_filename = f"{session_id}_metadata.json"
    metadata_path = os.path.join(REPORT_PICS_DIR, "others", metadata_filename)

    if not os.path.exists(metadata_path):
        print(f"警告: 找不到報告元數據檔案: {metadata_path}")
        return [{
            "image_url": None, 
            "title": "報告載入失敗",
            "description": f"找不到 {session_id} 的分析資料，請先執行 AI 分析。"
        }]

    # 3. 讀取並解析 JSON
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"錯誤: 無法解析報告 JSON 檔案: {e}")
        return []

    # 4. 轉換數據格式 (將 analysis_cards 轉換為 chart_data_list)
    chart_data_list = []
    
    # 預期的圖片路徑前綴 (例如: /report-images/others/)
    image_base_url = f"/report-images/others/" 

    for card in data.get("analysis_cards", []):
        chart_data_list.append({
            # 這是 report.html 用來顯示圖表的 URL
            "image_url": f"{image_base_url}{card['image_filename']}", 
            
            # 使用 attribute 作為卡片標題
            "title": f"{card['attribute']} 分析",
            
            # 使用 analysis_text 作為卡片描述 (這是你要求帶入的文字)
            "description": card['analysis_text'],
            
            # 可選：將 markdown 格式的文字轉換為 HTML (如果您的前端支援 Markdown 則不需要)
            # "description_html": markdown_to_html(card['analysis_text']) 
        })
        
    # 5. 返回結果
    return chart_data_list


# ==========================================
#  路由區塊
# ==========================================

@app.route('/', methods=['GET'])
def dashboard():
    # 首頁
    return render_template('index.html',
        sessions=get_sessions_from_db(),
        attributes=get_attributes_list(),
        links=get_report_links(), 
        chart_data=None, current_session=None, current_attribute=None, current_search=""
    )

# --- 舊版 API (保留給舊按鈕用) ---
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    if llm_core is None:
        return jsonify({"error": "AI 核心模組 (llm_core.py) 未載入。"}), 500

    try:
        data = request.get_json()
        search_query = data.get('search_query')
        session_id = data.get('session_id')
        attribute = data.get('attribute_name')

        if not session_id or not attribute:
            return jsonify({"error": "缺少必要參數"}), 400

        result = llm_core.generate_analysis_from_dashboard(
            session_id=session_id,
            attribute=attribute,
            search_query=search_query
        )
        
        if result["error"]:
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
        return jsonify({"error": str(e)}), 500


# =========================================================
# ▼▼▼ 【關鍵修改】新路由：直接生成並跳轉到 report.html ▼▼▼
# =========================================================
@app.route('/ai-report', methods=['POST'])
def generate_ai_report_page():
    try:
        # 1. 獲取使用者選擇的項目清單
        selected_items = request.form.getlist('selected_items')
        
        if not selected_items:
            return "錯誤：未選擇任何項目，請回上一頁重新選擇。", 400

        print(f"收到生成報告請求，項目清單: {selected_items}")

        # 這是要傳給 report.html 的資料清單
        chart_data_list = []
        
        # 總結文字 (可以先給一個簡單的開場白，或是再呼叫一次 LLM 做總結)
        items_str = "、".join(selected_items)
        main_summary = f"本報告針對選手的「{items_str}」進行了深入的專項分析。以下為各項目的詳細數據圖表與戰術建議。"

        # 2. 【關鍵】迴圈處理每個屬性
        for item in selected_items:
            print(f"正在分析單一項目: {item} ...")
            
            # 針對單一項目的 Prompt
            prompt = f"請專注分析羽球選手的「{item}」表現。請根據數據生成一張關於 {item} 的圖表，並提供該項目的具體優缺點分析與訓練建議。"
            
            item_text = ""
            item_image_url = ""
            success = False

            if llm_core:
                try:
                    # 呼叫 LLM
                    result = llm_core.run_analysis(prompt)
                    
                    if not result.get("error"):
                        item_text = result["text"]
                        
                        # 處理圖片
                        if result["figure"]:
                            buf = io.BytesIO()
                            result["figure"].savefig(buf, format='png', dpi=150, bbox_inches='tight')
                            buf.seek(0)
                            img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                            item_image_url = f"data:image/png;base64,{img_b64}"
                            buf.close()
                            # 重要：關閉圖表以釋放記憶體，避免下一張圖疊在一起
                            import matplotlib.pyplot as plt
                            plt.close(result["figure"]) 
                        else:
                            # 沒生成圖片時的預設圖
                            item_image_url = "/report-images/chao_vs_tao/win_rate.png"
                        
                        success = True
                except Exception as e:
                    print(f"分析 {item} 時發生錯誤: {e}")

            # Fallback (如果 LLM 失敗或沒開啟)
            if not success:
                # 為了避免每個項目都要等 1.5秒，模擬模式可以快一點
                # time.sleep(0.5) 
                item_text = f"""**{item} 分析 (模擬)**：\n數據顯示選手在{item}的穩定性上有待加強。建議針對該項目進行多球訓練。"""
                item_image_url = "/report-images/chao_vs_tao/win_rate.png"

            # 將這個項目的結果加入清單
            chart_data_list.append({
                "title": f"{item} - 深度分析",
                "description": item_text,  # 這裡放 LLM 針對該項目的分析文字
                "image_url": item_image_url
            })

        # 3. 渲染 report.html
        return render_template(
            'report.html',
            report_title=f"AI 專項分析報告 ({len(selected_items)}項指標)",
            main_introduction_text=main_summary,
            chart_data_list=chart_data_list
        )

    except Exception as e:
        print(f"系統錯誤: {e}")
        return f"系統發生錯誤: {str(e)}", 500

# --- 報告頁面路由 (舊有連結用) ---
@app.route('/report/<report_id>')
def report_view(report_id):
    return render_template('report.html', 
        report_title=f"報告 {report_id} 分析", 
        main_introduction_text=get_main_text(report_id),
        chart_data_list=get_chart_card_data(report_id)
    )

# --- 圖片路由 ---
@app.route('/report-images/<path:path_to_image>')
def serve_report_image(path_to_image):
    return send_from_directory(REPORT_PICS_DIR, path_to_image)

if __name__ == '__main__':
    app.run(debug=True, port=5000)