from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
import io
import base64 
import os 
import time
import json
import uuid  # [新增] 用於產生模版 ID
import matplotlib.pyplot as plt # [新增] 用於處理圖表

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
TEMPLATES_FILE = os.path.join(app.root_path, 'user_templates.json') # [新增] 模版存檔路徑

# ==========================================
#  [新功能] 模版管理系統 (Prompt Templates)
# ==========================================
def load_user_templates():
    """讀取使用者儲存的模版"""
    if not os.path.exists(TEMPLATES_FILE):
        return []
    try:
        with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_new_template(name, prompt):
    """儲存新模版"""
    templates = load_user_templates()
    new_template = {
        "id": str(uuid.uuid4()),
        "name": name,
        "prompt": prompt,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    # 新的放前面
    templates.insert(0, new_template) 
    with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(templates, f, ensure_ascii=False, indent=4)
    return new_template

def delete_user_template(template_id):
    """刪除模版"""
    templates = load_user_templates()
    templates = [t for t in templates if t['id'] != template_id]
    with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(templates, f, ensure_ascii=False, indent=4)

# ==========================================
#  輔助函式 (Helpers)
# ==========================================
def get_sessions_from_db():
    return [{"id": "S001", "name": "場次1"}]

def get_attributes_list():
    return ["ALL (總覽)", "勝率", "失誤率", "出席率", "球落點分布", "球種", "不同擊球位置", "跑動距離"]

def get_report_links():
    return [
        {"route": "report_view", "param": "R001", "name": "R001: 趙 vs 陶 (chao_vs_tao)"},
        {"route": "view_template_1", "param": None, "name": "🏸 進攻效益專項報告 "},
        {"route": "view_template_2", "param": None, "name": "🏸 防守評估專項報告 "},
        {"route": "view_template_3", "param": None, "name": "🏸 綜合評估專項報告 "},
        {"route": "view_template_4", "param": None, "name": "🏸 關鍵球分析報告 "}
    ]

def get_main_text(report_id):
    if report_id == "R001":
        return """### (摘要內容省略...)"""
    return f"這裡是報告 {report_id} 的文字摘要..."

def get_session_id_from_report_id(report_id):
    if report_id == "R001": return "S001"
    return None 

def get_chart_card_data(report_id):
    # (讀取靜態 JSON 的舊邏輯)
    session_id = get_session_id_from_report_id(report_id)
    if not session_id: return []
    metadata_filename = f"{session_id}_metadata.json"
    metadata_path = os.path.join(REPORT_PICS_DIR, "others", metadata_filename)
    if not os.path.exists(metadata_path):
        return [{"image_url": "/report-images/chao_vs_tao/win_rate.png", "title": "範例", "description": "無資料"}]
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []
    chart_data_list = []
    image_base_url = f"/report-images/others/" 
    for card in data.get("analysis_cards", []):
        chart_data_list.append({
            "image_url": f"{image_base_url}{card['image_filename']}", 
            "title": f"{card['attribute']} 分析",
            "description": card['analysis_text'],
        })
    return chart_data_list

# [新增] 圖片轉 Base64 輔助函式
def fig_to_base64(fig):
    """將 matplotlib figure 轉換為 base64 字串"""
    try:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        buf.close()
        plt.close(fig) # 記得關閉 figure 釋放記憶體
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"圖片轉換失敗: {e}")
        return ""

# ==========================================
#  路由區塊 (Routes)
# ==========================================

# --- 首頁 ---
@app.route('/', methods=['GET'])
def dashboard():
    # [新功能] 讀取模版傳給前端
    my_templates = load_user_templates()
    
    return render_template('index.html',
        sessions=get_sessions_from_db(),
        attributes=get_attributes_list(),
        links=get_report_links(),
        my_templates=my_templates, # 傳遞模版列表
        chart_data=None, current_session=None, current_attribute=None, current_search=""
    )

# --- API: 儲存模版 ---
@app.route('/api/save-template', methods=['POST'])
def api_save_template():
    try:
        data = request.get_json()
        name = data.get('name')
        prompt = data.get('prompt')
        
        if not name or not prompt:
            return jsonify({"success": False, "message": "名稱或指令不能為空"}), 400
            
        save_new_template(name, prompt)
        return jsonify({"success": True, "message": "模版儲存成功！"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- API: 刪除模版 ---
@app.route('/api/delete-template/<template_id>', methods=['POST'])
def api_delete_template(template_id):
    try:
        delete_user_template(template_id)
        return jsonify({"success": True, "message": "刪除成功"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# --- PART 1: 舊版單選 API (AJAX) ---
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    if llm_core is None:
        return jsonify({"error": "AI 核心模組未載入。"}), 500
    try:
        data = request.get_json()
        search_query = data.get('search_query')
        session_id = data.get('session_id')
        attribute = data.get('attribute_name')

        if not session_id or not attribute:
            return jsonify({"error": "缺少必要參數"}), 400

        result = llm_core.generate_analysis_from_dashboard(
            session_id=session_id, attribute=attribute, search_query=search_query
        )
        
        if result["error"]:
            return jsonify({"error": f"AI 分析失敗: {result['error']}"}), 500
        
        # [修正] 處理多圖，這裡只回傳第一張做預覽
        image_base64 = None
        figures = result.get("figures", [])
        if not figures and result.get("figure"):
            figures = [result.get("figure")]
            
        if figures:
            image_base64 = fig_to_base64(figures[0]).replace("data:image/png;base64,", "")

        return jsonify({
            "status": "success",
            "analysis_text": result["text"], 
            "chart_image_base64": image_base64 
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- PART 2: 多選 LLM 生成 -> 跳轉 report.html ---
@app.route('/ai-report', methods=['POST'])
def generate_ai_report_page():
    try:
        selected_items = request.form.getlist('selected_items')
        if not selected_items: return "錯誤：未選擇任何項目。", 400

        print(f"收到生成報告請求，項目清單: {selected_items}")
        chart_data_list = []
        main_summary = f"本報告針對選手的「{'、'.join(selected_items)}」進行了深入的專項分析。"

        # [新增] 合成一個「總指令」，讓這個多選操作也能被存成文字模版
        # 因為我們的 LLM Core 現在有「戰術策劃師」，它看得懂這句指令並能還原成多張圖
        synthetic_prompt = f"請詳細分析選手的以下項目：{'、'.join(selected_items)}，並生成相關圖表與戰術建議。"

        for item in selected_items:
            print(f"正在分析單一項目: {item} ...")
            # 這裡針對單項微調 Prompt
            prompt = f"請專注分析羽球選手的「{item}」表現，並生成相關圖表與戰術建議。"
            
            if llm_core:
                try:
                    res = llm_core.run_analysis(prompt)
                    if not res.get("error"):
                        figures = res.get("figures", [])
                        if not figures and res.get("figure"): figures = [res["figure"]]
                        
                        if figures:
                            for i, fig in enumerate(figures):
                                img_url = fig_to_base64(fig)
                                chart_data_list.append({
                                    "title": f"{item} - 分析圖表 {i+1}",
                                    "description": res["text"] if i == 0 else "(續上圖分析)",
                                    "image_url": img_url
                                })
                        else:
                            chart_data_list.append({
                                "title": f"{item} - 文字分析",
                                "description": res["text"],
                                "image_url": "/report-images/chao_vs_tao/win_rate.png"
                            })
                    else:
                        print(f"分析錯誤: {res['error']}")
                except Exception as e:
                    print(f"分析 {item} 時發生例外: {e}")
            else:
                # 模擬模式
                chart_data_list.append({
                    "title": f"{item} (模擬)",
                    "description": "模擬數據...",
                    "image_url": "/report-images/chao_vs_tao/win_rate.png"
                })

        return render_template('report.html',
            report_title=f"AI 專項分析報告 ({len(selected_items)}項指標)",
            main_introduction_text=main_summary,
            chart_data_list=chart_data_list,
            # [關鍵修復]：把合成的指令傳給前端，這樣「存為最愛」按鈕就會出現了！
            original_prompt=synthetic_prompt
        )
    except Exception as e:
        return f"系統錯誤: {str(e)}", 500


# --- PART 3: 教練自定義輸入 -> 跳轉 report.html ---
@app.route('/ai-report-text', methods=['POST'])
def generate_ai_report_text():
    try:
        user_input = request.form.get('user_input', '').strip()
        if not user_input: return "錯誤：請輸入分析內容。", 400

        print(f"收到教練自定義請求: {user_input}")
        chart_data_list = []
        
        if llm_core:
            try:
                # 1. 呼叫 LLM (會回傳 List)
                res = llm_core.run_analysis(user_input)
                
                if not res.get("error"):
                    text_content = res["text"]
                    
                    # 2. 取得圖表列表
                    figures = res.get("figures", [])
                    if not figures and res.get("figure"): figures = [res["figure"]]
                    
                    # 3. 處理圖表
                    if figures:
                        for i, fig in enumerate(figures):
                            img_url = fig_to_base64(fig)
                            chart_data_list.append({
                                "title": f"戰術圖解 {i+1}",
                                "description": text_content if i == 0 else "...", 
                                "image_url": img_url
                            })
                    else:
                        chart_data_list.append({
                            "title": "戰術分析結果",
                            "description": text_content,
                            "image_url": "/report-images/chao_vs_tao/win_rate.png"
                        })
                else:
                    return f"AI 分析錯誤: {res['error']}", 500
                    
            except Exception as e:
                print(f"LLM 執行例外: {e}")
                return f"LLM 執行例外: {e}", 500
        else:
            # 模擬模式
            time.sleep(1.0)
            chart_data_list = [{
                "title": "教練自定義分析 (模擬)",
                "description": f"針對「{user_input}」的模擬分析結果...",
                "image_url": "/report-images/chao_vs_tao/win_rate.png"
            }]

        return render_template('report.html',
            report_title="AI 客製化教練報告",
            main_introduction_text=f"教練指令：\n「{user_input}」",
            chart_data_list=chart_data_list,
            # [關鍵] 傳回使用者輸入的 prompt，供前端儲存模版使用
            original_prompt=user_input
        )

    except Exception as e:
        return f"系統發生錯誤: {str(e)}", 500


# --- PART 4: JSON 範本預覽 ---
@app.route('/view-report-1')
def view_template_1():
    json_path = os.path.join(app.root_path, 'report_pics', 'others', 'template_1.json')
    if not os.path.exists(json_path): return f"找不到 JSON: {json_path}", 404
    try:
        with open(json_path, 'r', encoding='utf-8') as f: data = json.load(f)
        if "analysis_cards" in data:
            for card in data["analysis_cards"]:
                if not card["image_filename"].startswith("others/"):
                    card["image_filename"] = f"others/{card['image_filename']}"
        return render_template('report_view.html', report=data)
    except Exception as e: return f"JSON Error: {str(e)}", 500

@app.route('/view-report-2')
def view_template_2():
    json_path = os.path.join(app.root_path, 'report_pics', 'defense', 'defense.json')
    if not os.path.exists(json_path): return f"找不到 JSON: {json_path}", 404
    try:
        with open(json_path, 'r', encoding='utf-8') as f: data = json.load(f)
        if "analysis_cards" in data:
            for card in data["analysis_cards"]:
                if not card["image_filename"].startswith("defense/"):
                    card["image_filename"] = f"defense/{card['image_filename']}"
        return render_template('report_view.html', report=data)
    except Exception as e: return f"JSON Error: {str(e)}", 500

@app.route('/view-report-3')
def view_template_3():
    json_path = os.path.join(app.root_path, 'report_pics', 'overall', 'overall.json')
    if not os.path.exists(json_path): return f"找不到 JSON: {json_path}", 404
    try:
        with open(json_path, 'r', encoding='utf-8') as f: data = json.load(f)
        if "analysis_cards" in data:
            for card in data["analysis_cards"]:
                if not card["image_filename"].startswith("overall/"):
                    card["image_filename"] = f"overall/{card['image_filename']}"
        return render_template('report_view.html', report=data)
    except Exception as e: return f"JSON Error: {str(e)}", 500

@app.route('/view-report-4')
def view_template_4():
    json_path = os.path.join(app.root_path, 'report_pics', 'keyPoint', 'keyPoint.json')
    if not os.path.exists(json_path): return f"找不到 JSON: {json_path}", 404
    try:
        with open(json_path, 'r', encoding='utf-8') as f: data = json.load(f)
        if "analysis_cards" in data:
            for card in data["analysis_cards"]:
                if not card["image_filename"].startswith("keyPoint/"):
                    card["image_filename"] = f"keyPoint/{card['image_filename']}"
        return render_template('report_view.html', report=data)
    except Exception as e: return f"JSON Error: {str(e)}", 500


# --- 圖片路由 & 舊版路由 ---
@app.route('/report-images/<path:path_to_image>')
def serve_report_image(path_to_image):
    return send_from_directory(REPORT_PICS_DIR, path_to_image)

@app.route('/report/<report_id>')
def report_view(report_id):
    return render_template('report.html', 
        report_title=f"報告 {report_id} 分析", 
        main_introduction_text=get_main_text(report_id),
        chart_data_list=get_chart_card_data(report_id)
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)