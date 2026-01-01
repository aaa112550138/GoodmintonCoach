import os
import io
import platform
import pandas as pd
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import traceback
import json
from contextlib import redirect_stdout # 用於捕獲 print 輸出

# --- 關鍵：從你的 Streamlit 專案中，把這些檔案/資料夾複製過來 ---
try:
    from utils.data_loader import load_all_data
    from config.prompts import create_system_prompt
except ImportError:
    print("="*50)
    print("錯誤：請確保 'utils' 和 'config' 資料夾存在。")
    print("="*50)
    raise

# ▼▼▼ [修改]：只保留 OpenAI 套件 ▼▼▼
try:
    from openai import OpenAI
except ImportError:
    print("="*50)
    print("錯誤：找不到 'openai' 套件。")
    print("請執行： pip install openai")
    print("="*50)
    raise

# --- 初始設定 ---
print("[llm_core DEBUG] 正在載入 .env 檔案...")
load_dotenv()

# --- 1. 載入資料 (保持不變) ---
df, data_schema_info, column_definitions_info = load_all_data()
if df is None:
    print("="*50)
    print("警告 [llm_core]: 'all_dataset.csv' 檔案載入失敗。")
    print("="*50)

# --- 2. [升級] 設定模型與 API Key ---
# --- 全部切換為 OpenAI 模型 ---
ENHANCER_MODEL = "gpt-4o-mini" # 用於快速強化問題
ANALYSIS_MODEL = "gpt-4o"      # 用於寫程式 (建議用 gpt-4o 比較強，若要省錢可用 gpt-4o-mini)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print(f"[llm_core DEBUG] 強化模型: {ENHANCER_MODEL}")
print(f"[llm_core DEBUG] 分析模型: {ANALYSIS_MODEL}")

openai_client = None
if not OPENAI_API_KEY:
    print("="*50)
    print("嚴重錯誤 [llm_core]: 找不到 OPENAI_API_KEY (環境變數)。")
    print("="*50)
else:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print(f"[llm_core DEBUG] OpenAI 設定成功 (Key 前 4 碼: {OPENAI_API_KEY[:4]}...)")
    except Exception as e:
        print(f"OpenAI Client 初始化失敗: {e}")

# --- 3. 自動搜尋中文字型 (保持不變) ---
def get_chinese_font():
    """在系統中自動搜尋可用的中文字型"""
    print("[llm_core DEBUG] 正在搜尋可用的中文字型...")
    font_paths = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    font_name_to_path = {}
    for font_path in font_paths:
        try:
            font_name = fm.FontProperties(fname=font_path).get_name()
            font_name_to_path[font_name] = font_path
        except Exception:
            continue

    preferred_font_names = [
        'Microsoft JhengHei', 'PingFang TC', 'Noto Sans CJK TC', 
        'SimHei', 'Arial Unicode MS',
    ]
    
    for font_name in preferred_font_names:
        if font_name in font_name_to_path:
            print(f"[llm_core DEBUG] 找到偏好的字型: {font_name}")
            return font_name 

    print("[llm_core DEBUG] 未找到偏好字型，開始掃描系統字型...")
    for font_path in font_paths:
        try:
            font_prop = fm.FontProperties(fname=font_path)
            if fm.get_font(font_prop).get_glyph_name('你'): 
                print(f"[llm_core DEBUG] 找到一個可用的中文字型: {font_path}")
                return font_path 
        except Exception:
            continue
            
    print("[llm_core DEBUG] 警告: 系統中找不到任何可用的中文字型。圖表中文將顯示為方塊。")
    return None

GLOBAL_CHINESE_FONT_PATH_OR_NAME = get_chinese_font()


# --- 5. [修改] 提示詞強化邏輯 (OpenAI 版) ---
def enhance_user_prompt(original_prompt: str, schema_info: str) -> str:
    """
    使用 LLM 將模糊的使用者問題轉化為清晰的分析任務。
    """
    if not openai_client:
        return original_prompt

    print(f"[llm_core DEBUG] 正在強化提示詞: {original_prompt}")
    
    system_prompt = f"""
    你是一個輔助系統，你的任務是將使用者的簡短數據分析問題，轉化為一個更清晰、更完整、更具體的數據分析任務描述。
    必須考慮使用者所有方面的可能，及數據中所有欄位的關聯性。
    
    你必須考慮以下的資料庫 schema：
    {schema_info}
    
    你的輸出**只能**包含轉化後的繁體中文問題敘述，不要有任何前言、後語或解釋。
    """
    
    try:
        res = openai_client.chat.completions.create(
            model=ENHANCER_MODEL, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"使用者輸入：{original_prompt}"}
            ],
            temperature=0.2
        )
        return res.choices[0].message.content.strip()
            
    except Exception as e:
        print(f"[llm_core DEBUG] 提示詞強化失敗: {e}。將使用原始提示詞。")
        return original_prompt

# --- 6. 結果格式化 (保持不變) ---
def _format_summary_info_for_prompt(summary_info: dict) -> str:
    """
    將 Python 執行結果的摘要字典，格式化為給 LLM 閱讀的 Markdown 字串。
    """
    if not summary_info:
        return "AI 程式碼未產生任何可供分析的摘要變數。"
        
    analysis_context_str = "程式碼執行後，擷取出以下核心變數與其值：\n\n"
    for name, val in summary_info.items():
        analysis_context_str += f"### 變數 `{name}` (型別: `{type(val).__name__}`)\n"
        
        if isinstance(val, (pd.DataFrame, pd.Series)):
            try:
                md = val.to_markdown()
                if len(md) > 1000:
                    analysis_context_str += f"```\n{str(val)}\n(資料過長，僅顯示部分)\n```\n\n"
                else:
                    analysis_context_str += f"```markdown\n{md}\n```\n\n"
            except Exception:
                analysis_context_str += f"```\n{str(val)}\n```\n\n"
        else:
            analysis_context_str += f"```\n{str(val)}\n```\n\n"
    return analysis_context_str


# --- 4. [獨門技術] 戰術策劃師：拆解多圖表需求 ---
def _plan_analysis_steps(user_prompt: str, schema_info: str) -> str:
    """
    Step 1: 將使用者的模糊指令，拆解成具體的「多圖表」繪圖計畫。
    """
    system_prompt = f"""
    你是一位羽球數據分析的「戰術策劃師」。
    使用者的問題可能很模糊（例如：「分析攻擊數據」）。
    你的任務是將其拆解為 1~3 個具體的視覺化分析步驟，以便 Python 工程師執行。
    
    資料庫 Schema:
    {schema_info}
    
    規定：
    1. 如果問題很簡單，1 個步驟即可。
    2. 如果問題複雜（如「統整分析」），請拆解成多個不同維度的圖表（例如：一張看落點、一張看球種佔比）。
    3. 直接輸出給工程師的指令，不用廢話。
    """
    
    try:
        response = client.chat.completions.create(
            model=ANALYSIS_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"使用者問題: {user_prompt}"}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception:
        return user_prompt # 如果 API 失敗，回傳原始問題


# --- 5. 核心分析函數 (終極整合版) ---
def run_analysis(natural_language_prompt: str, history: list = None) -> dict:
    if df is None: return {"text": None, "figures": [], "error": "資料集未載入"}
    if client is None: return {"text": None, "figures": [], "error": "OpenAI Client 未初始化"}
    if history is None: history = []

    # --- Phase 1: 策劃與優化 (Planning Phase) ---
    print(f"[llm_core] 正在策劃分析路徑: {natural_language_prompt}")
    
    # 呼叫策劃師，把「一句話」變成「詳細的執行計畫」
    # 這就是解決「只會有一張圖」的關鍵：AI 先想好要畫幾張，再去寫 Code
    enhanced_prompt = _plan_analysis_steps(natural_language_prompt, data_schema_info)
    print(f"[llm_core] 優化後的指令: {enhanced_prompt}")

    # --- Phase 2: 建構 System Prompt (整合 front_page.py 的精華) ---
    BADMINTON_MAPPING_PROMPT = """
    **[羽球領域知識 (Domain Knowledge)]**
    - **球種 (type)**: 1:發短球, 2:發長球, 3:長球, 4:殺球, 5:切球, 6:挑球, 7:平球, 8:網前球, 9:推撲球, 10:接殺防守, 11:接不到
    - **場地座標 (landing_area)**: 
        - Row 1 (底線): Area 1-4
        - Row 6 (網前): Area 21-24
    - **戰術邏輯**: 分析時請使用上述術語。
    """

    system_instructions = create_system_prompt(data_schema_info, column_definitions_info)
    system_instructions += "\n" + BADMINTON_MAPPING_PROMPT
    
    # [關鍵] 強制多圖表輸出的 Prompt
    system_instructions += """
    \n**程式碼輸出規定 (Strict Protocol)**:
    1. 你是 Python 程式碼生成器，只輸出 Python Code。
    2. **多圖表支援**: 根據指令，若需要多個角度分析，請生成多個 figure 物件。
    3. **儲存規定**: 務必將所有 figure 物件存入 `figures` list。例: `figures = [fig1, fig2, fig3]`。
    4. **字型**: 務必設定中文字型，避免亂碼。
    5. **錯誤處理**: 繪圖前檢查 df 是否為空 (`if len(df) > 0:`)。
    """

    # 字型注入
    if GLOBAL_CHINESE_FONT_PATH_OR_NAME:
        system_instructions += f"\n(請在 Code 中執行: `plt.rcParams['font.sans-serif'] = ['{GLOBAL_CHINESE_FONT_PATH_OR_NAME}']`)"

    messages = [{"role": "system", "content": system_instructions}]
    messages.extend(history)
    messages.append({"role": "user", "content": f"執行計畫：{enhanced_prompt}"})

    # --- Phase 3: 程式碼生成與自我修正 (Execution Phase) ---
    max_retries = 3
    code_to_execute = ""
    exec_globals = {}
    execution_output = ""
    final_figures = []
    
    for attempt in range(max_retries):
        try:
            print(f"[llm_core] 嘗試生成程式碼 (第 {attempt + 1} 次)...")
            response = client.chat.completions.create(
                model=ANALYSIS_MODEL, messages=messages, temperature=0.1
            )
            ai_content = response.choices[0].message.content
            
            # 解析 Code
            if "```python" in ai_content:
                code_to_execute = ai_content.split("```python")[1].split("```")[0].strip()
            elif "```" in ai_content:
                code_to_execute = ai_content.split("```")[1].split("```")[0].strip()
            else:
                code_to_execute = ai_content

            if not code_to_execute:
                return {"text": ai_content, "figures": [], "error": None}

            # 執行 Code
            print("[llm_core] 正在執行...")
            plt.close('all') 
            exec_globals = {"pd": pd, "df": df.copy(), "plt": plt, "io": io, "platform": platform}
            
            f_capture = io.StringIO()
            with redirect_stdout(f_capture):
                exec(code_to_execute, exec_globals)
            execution_output = f_capture.getvalue()
            
            print("[llm_core] 執行成功！")
            break 
            
        except Exception as e:
            print(f"[llm_core] 錯誤: {e}")
            error_msg = f"Runtime Error: {e}. Please fix the code."
            messages.append({"role": "assistant", "content": ai_content})
            messages.append({"role": "user", "content": error_msg})
            
            if attempt == max_retries - 1:
                return {"text": f"分析失敗: {e}", "figures": [], "error": str(e)}

    # --- Phase 4: 結果擷取 (Retrieval) ---
    final_figures = exec_globals.get("figures", [])
    if not final_figures:
        # 相容性檢查
        single_fig = exec_globals.get("fig", None)
        if single_fig: final_figures = [single_fig]
        elif plt.get_fignums(): final_figures = [plt.gcf()]

    # 擷取變數供 Insight 使用
    summary_info = {}
    for k, v in exec_globals.items():
        if not k.startswith("_") and k not in ["pd", "df", "plt", "io", "figures", "fig"]:
            if isinstance(v, (int, float, str)): summary_info[k] = v
            elif isinstance(v, pd.DataFrame): summary_info[k] = f"DataFrame ({len(v)} rows)"

    # --- Phase 5: 生成教練洞察 (Insight Phase) ---
    print("[llm_core] 正在撰寫教練報告...")
    
    insight_prompt = f"""
    你是一位專業羽球教練。
    
    【使用者原問題】: "{natural_language_prompt}"
    【執行計畫】: "{enhanced_prompt}"
    
    【關鍵數據】: {json.dumps(summary_info, default=str, indent=2, ensure_ascii=False)}
    【程式輸出】: {execution_output}
    【圖表數量】: 已生成 {len(final_figures)} 張圖表。
    
    請撰寫分析報告：
    1. **直接回答**: 針對使用者的問題給出結論。
    2. **圖表解讀**: 依序解釋生成的每一張圖表代表什麼意義（例如：「第一張圖顯示殺球落點集中在...」）。
    3. **戰術建議**: 給予選手具體的改進建議。
    """
    
    try:
        insight_res = client.chat.completions.create(
            model=ANALYSIS_MODEL,
            messages=[
                {"role": "system", "content": "你是由數據驅動的戰術大師。"},
                {"role": "user", "content": insight_prompt}
            ],
            temperature=0.4
        )
        final_text = insight_res.choices[0].message.content
    except Exception:
        final_text = "分析完成，但無法生成文字報告。"

    # --- Phase 6: 回傳 (含向下相容) ---
    full_response_content = f"```python\n{code_to_execute}\n```\n\n{final_text}"
    primary_figure = final_figures[0] if final_figures else None

    return {
        "text": final_text,
        "figures": final_figures,      # 新版 List
        "figure": primary_figure,      # 舊版相容
        "code_executed": code_to_execute,
        "error": None,
        "history_user": {"role": "user", "content": natural_language_prompt},
        "history_model": {"role": "assistant", "content": full_response_content}
    }

# --- 儀表板翻譯器 (保持不變，邏輯通用) ---
def generate_analysis_from_dashboard(session_id: str, attribute: str, search_query: str) -> dict:
    """
    將儀表板的「選項」轉換成「自然語言問題」，並將圖片和文字整合存入同一個 JSON。
    """
    
    prompt = f"請幫我分析所有場次的數據。"
    if search_query:
        prompt += f" 請特別針對學生 '{search_query}' 進行分析。"
    
    if attribute == "ALL (總覽)":
        prompt += " 請提供這個場次的整體數據總覽，並用一個合適的圖表（例如長條圖或圓餅圖）來視覺化關鍵指標。"
    elif attribute == "球種":
        prompt += f" 請分析這個場次的「球種」分佈。請使用圓餅圖 (pie chart) 或長條圖 (bar chart) 來呈現不同球種 (例如：殺球, 切球, Tiao, 高遠球) 的使用次數或百分比。"
    elif attribute == "殺球成功率":
        prompt += (
            f" 請計算 '{search_query}' 的殺球總次數、得分次數和失誤次數，並計算出他的「殺球成功率」（得分/總次數）。"
            f" 請使用一個清晰的長條圖或表格來比較殺球得分與殺球總次數的關係，並分析這個成功率的意涵。"
        )
    elif attribute == "跑動距離":
        prompt += (
            f" 請分析 '{search_query}' 在比賽中的「跑動距離」總數。"
            f" 請使用折線圖 (line chart) 來顯示每一分 (point_id) 的累計跑動距離變化，或使用長條圖來比較不同局數 (game_id) 的跑動距離總和。"
            f" 同時，請計算平均跑動距離並進行總結。"
        )
    else:
        prompt += f" 請專注於分析 '{attribute}' 這個指標，並為此生成一個最合適的圖表。"
    
    print(f"[llm_core] 翻譯後的 Prompt: {prompt}")
    
    # 執行 AI 分析
    result = run_analysis(prompt, history=None)

    save_dir = "report_pics/others" 
    import os
    os.makedirs(save_dir, exist_ok=True)
    base_img_filename = f"{session_id}_{attribute}"
    
    if result["figure"] is not None:
        save_path_img = os.path.join(save_dir, f"{base_img_filename}.png")
        result["figure"].savefig(save_path_img, dpi=150, bbox_inches='tight')
        print(f"圖表已存檔: {save_path_img}")
    
    analysis_text = result.get("text")
    
    if analysis_text:
        try:
            master_json_filename = f"{session_id}_metadata.json"
            master_json_path = os.path.join(save_dir, master_json_filename)
            
            new_card_data = {
                "attribute": attribute,
                "search_query": search_query,
                "analysis_text": analysis_text,
                "image_filename": f"{base_img_filename}.png",
                "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            current_data = {}
            if os.path.exists(master_json_path):
                with open(master_json_path, 'r', encoding='utf-8') as f:
                    try:
                        current_data = json.load(f)
                    except json.JSONDecodeError:
                        current_data = {}

            if "session_id" not in current_data:
                current_data["session_id"] = session_id
            
            if "analysis_cards" not in current_data:
                current_data["analysis_cards"] = []

            cards_list = current_data["analysis_cards"]
            found = False
            for index, card in enumerate(cards_list):
                if card.get("attribute") == attribute:
                    cards_list[index] = new_card_data
                    found = True
                    break
            
            if not found:
                cards_list.append(new_card_data)

            with open(master_json_path, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=4)
                
            print(f"分析文字已更新至總表: {master_json_path}")
            
        except Exception as e:
            print(f"警告: JSON 更新失敗: {e}")
            import traceback
            traceback.print_exc()

    return result


# --- 主程式進入點 (用於測試) ---
if __name__ == "__main__":
    print("\n" + "="*80)
    print(" 🚀 正在啟動 LLM Core 測試 (OpenAI Only)...")
    print("="*80 + "\n")

    conversation_history = []
    
    # --- 第 1 次提問 ---
    print("--- 提問 1: '誰是失誤王？' ---")
    question1 = "誰是失誤王？"
    result1 = run_analysis(question1, history=conversation_history)
    
    if result1["error"]:
        print(f"錯誤: {result1['error']}")
    else:
        print("\n[AI 洞察 1]:")
        print(result1["text"])
        
        # 儲存記憶 (OpenAI 格式)
        conversation_history.append(result1["history_user"])
        conversation_history.append(result1["history_model"])
        
    print("\n" + "="*80 + "\n")

    # --- 第 2 次提問 (利用記憶) ---
    print("--- 提問 2: '那球員 A 的殺球 (smash) 次數呢？' ---")
    question2 = "那球員 A 的殺球 (smash) 次數呢？"
    
    result2 = run_analysis(question2, history=conversation_history)
    
    if result2["error"]:
        print(f"錯誤: {result2['error']}")
    else:
        print("\n[AI 洞察 2]:")
        print(result2["text"])
        
        conversation_history.append(result2["history_user"])
        conversation_history.append(result2["history_model"])

    print("\n" + "="*80 + "\n")
    print("測試完畢。")