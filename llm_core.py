import os
import io
import platform
import pandas as pd
from dotenv import load_dotenv
import matplotlib.font_manager as fm
import traceback # --- [新增]：用於印出詳細錯誤 ---

# --- 關鍵：從你的 Streamlit 專案中，把這些檔案/資料夾複製過來 ---
try:
    from utils.data_loader import load_all_data
    from config.prompts import create_system_prompt
except ImportError:
    print("="*50)
    print("錯誤：請確保 'utils' 和 'config' 資料夾存在。")
    print("="*50)
    raise

# --- 關鍵：我們「直接」匯入 Google 官方套件 ---
try:
    import google.generativeai as genai
except ImportError:
    print("="*50)
    print("錯誤：找不到 'google-generativeai' 套件。")
    print("請執行： pip install google-generativeai")
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
# --- 使用不同的模型來執行不同任務，更具成本效益 ---
ENHANCER_MODEL = "gemini-2.0-flash" # 用於快速、便宜的問題強化
ANALYSIS_MODEL = "gemini-2.0-flash"   # 用於複雜的程式碼生成與洞察
API_KEY = os.getenv("GEMINI_API_KEY")

print(f"[llm_core DEBUG] 強化模型: {ENHANCER_MODEL}")
print(f"[llm_core DEBUG] 分析模型: {ANALYSIS_MODEL}")

if not API_KEY:
    print("="*50)
    print("警告 [llm_core]: 找不到 GEMINI_API_KEY (環境變數)。")
    print("="*50)
else:
    print(f"[llm_core DEBUG] 成功載入 API Key (前 4 碼): {API_KEY[:4]}...")
    try:
        genai.configure(api_key=API_KEY)
        print("[llm_core DEBUG] Google AI SDK 設定成功。")
    except Exception as e:
        print(f"[llm_core DEBUG] Google AI SDK 設定失敗: {e}")

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

# --- 4. 在程式啟動時，就先找到字型並存起來 (保持不變) ---
GLOBAL_CHINESE_FONT_PATH_OR_NAME = get_chinese_font()


# --- 5. [新增] 移植自 Streamlit 的「提示詞強化」邏輯 ---
def enhance_user_prompt(original_prompt: str, schema_info: str) -> str:
    """
    使用 LLM 將模糊的使用者問題轉化為清晰的分析任務。
    """
    print(f"[llm_core DEBUG] 正在強化提示詞: {original_prompt}")
    
    enhancement_system_prompt = f"""
    你是一個輔助系統，你的任務是將使用者的簡短數據分析問題，轉化為一個更清晰、更完整、更具體的數據分析任務描述，必須考慮使用者所有方面的可能，及數據中所有欄位的關聯性。
    這個描述將被交給另一個 AI (Python 程式碼生成器) 來執行。
    
    你必須考慮以下的資料庫 schema：
    {schema_info}
    
    你的輸出**只能**包含轉化後的繁體中文問題敘述，不要有任何前言、後語或解釋。

    範例 1:
    使用者輸入：誰是失誤王？
    你輸出：請統計 'player' 欄位中 'type' 為 'error' (失誤) 的次數，並找出誰的失誤次數最高，將結果儲存在一個變數 (例如 'error_king_name' 和 'error_king_count') 中。
    
    範例 2:
    使用者輸入：球員 A 的圓餅圖
    你輸出：請分析 'player' 欄位為 'A' 的所有擊球，並使用圓餅圖顯示 'type' (球種) 的分佈比例。
    """
    
    try:
        model = genai.GenerativeModel(ENHANCER_MODEL)
        # --- [關鍵] 使用低溫 (temperature=0.2) 確保轉譯的準確性與一致性 ---
        response = model.generate_content(
            [
                {'role': 'user', 'parts': [enhancement_system_prompt]},
                {'role': 'model', 'parts': ["好的，我會將使用者的問題轉化為清晰的任務。請給我使用者的問題。"]},
                {'role': 'user', 'parts': [original_prompt]}
            ],
            generation_config={"temperature": 0.2} 
        )
        enhanced_prompt = response.text.strip()
        print(f"[llm_core DEBUG] 強化後的提示詞: {enhanced_prompt}")
        return enhanced_prompt
    except Exception as e:
        print(f"[llm_core DEBUG] 提示詞強化失敗: {e}。將使用原始提示詞。")
        return original_prompt

# --- 6. [新增] 移植自 Streamlit 的「結果格式化」邏輯 ---
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
                # 嘗試轉換為 Markdown，如果太大或失敗則用 str
                md = val.to_markdown()
                if len(md) > 1000: # 限制長度
                    analysis_context_str += f"```\n{str(val)}\n(資料過長，僅顯示部分)\n```\n\n"
                else:
                    analysis_context_str += f"```markdown\n{md}\n```\n\n"
            except Exception:
                analysis_context_str += f"```\n{str(val)}\n```\n\n"
        else:
            analysis_context_str += f"```\n{str(val)}\n```\n\n"
    return analysis_context_str


# --- 7. [重大升級] 核心分析函數 ---
def run_analysis(natural_language_prompt: str, history: list = None, max_retries: int = 2) -> dict:
    """
    【重大升級版】
    - 支援交談記憶 (history)
    - 支援提示詞強化 (enhance_user_prompt)
    - 支援程式碼自我修正 (self-correction loop)
    - 支援更強大的結果擷取 (summary_info)
    - 策略性使用 temperature
    """
    
    if df is None:
        return {"text": None, "figure": None, "error": "資料集 'all_dataset.csv' 未載入。"}
    if not API_KEY:
        return {"text": None, "figure": None, "error": "未設定 GEMINI_API_KEY。"}

    if history is None:
        history = []

    try:
        # --- 步驟 0: 初始化分析模型 ---
        analysis_model = genai.GenerativeModel(ANALYSIS_MODEL)
        
        # --- 步驟 1: 【新】強化提示詞 ---
        # (此步驟使用 ENHANCER_MODEL，已在函數內)
        enhanced_prompt = enhance_user_prompt(natural_language_prompt, data_schema_info)

        # --- 步驟 2: 【修改】生成程式碼 (加入記憶與字型) ---
        print(f"[llm_core DEBUG] 正在使用 {ANALYSIS_MODEL} 呼叫 Google API (生成程式碼)...")
        
        system_prompt = create_system_prompt(data_schema_info, column_definitions_info)
        
        # --- ▼ 注入字體指令 (保持不變) ▼ ---
        font_prompt_injection = ""
        if GLOBAL_CHINESE_FONT_PATH_OR_NAME:
            font_path_or_name_str = repr(GLOBAL_CHINESE_FONT_PATH_OR_NAME)
            font_prompt_injection = f"""
            *** EXTREMELY IMPORTANT (FONT SETTING) ***
            You MUST add the following 3 lines of code right after `import matplotlib.pyplot as plt` to set the Chinese font:
            ```python
            import matplotlib.pyplot as plt
            import matplotlib.font_manager as fm
            
            # --- START FONT SETTING ---
            font_path_or_name = {font_path_or_name_str}
            try:
                font_prop = fm.FontProperties(fname=font_path_or_name)
                plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
            except Exception:
                plt.rcParams['font.sans-serif'] = [font_path_or_name]
            plt.rcParams['axes.unicode_minus'] = False # Fix for minus sign
            # --- END FONT SETTING ---
            ```
            ******************************************
            """
        system_prompt += font_prompt_injection
        # --- ▲ 修改完畢 ▲ ---
        
        # --- 【修改】組合訊息 (加入 history) ---
        messages_for_api = [
            {'role': 'user', 'parts': [system_prompt]},
            {'role': 'model', 'parts': ["好的，我準備好了。我會依照指示，在 `matplotlib` 程式碼中加入設定中文字型的區塊。請給我使用者的問題。"]},
        ]
        
        # 加入歷史對話
        messages_for_api.extend(history)
        
        # 加入本次強化後的問題
        messages_for_api.append({'role': 'user', 'parts': [enhanced_prompt]})
        
        # --- 步驟 3: 【新】程式碼生成與自我修正迴圈 ---
        code_to_execute = None
        ai_response_text = ""
        
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"[llm_core DEBUG] 偵測到錯誤，正在進行第 {attempt + 1} 次修正嘗試...")
            
            # --- [關鍵] 使用低溫 (temperature=0.1) 確保程式碼的精確性 ---
            response = analysis_model.generate_content(
                messages_for_api,
                generation_config={"temperature": 0.1}
            )
            ai_response_text = response.text
            
            # (1) 解析程式碼
            if "```python" in ai_response_text:
                code_start = ai_response_text.find("```python") + len("```python\n")
                code_end = ai_response_text.rfind("```")
                code_to_execute = ai_response_text[code_start:code_end].strip()
            else:
                # AI 沒有回傳程式碼，可能只是純文字回答
                if not code_to_execute:
                    print("[llm_core DEBUG] AI 回應中未偵測到程式碼。")
                    # 如果是第一次嘗試就沒程式碼，可能
                    return {"text": ai_response_text, "figure": None, "error": None}


            print("--- [llm_core DEBUG] 偵測到 AI 生成的程式碼 (嘗試 {}): ---".format(attempt + 1))
            print(code_to_execute)
            print("-------------------------------------------------")
            
            # (2) 執行程式碼
            final_fig = None
            summary_info = {} # --- [升級] 使用字典擷取結果 ---
            
            try:
                print("[llm_core DEBUG] 正在執行 AI 程式碼 (exec)...")
                exec_globals = {
                    "pd": pd, "df": df.copy(),
                    "platform": platform, "io": io
                }
                exec(code_to_execute, exec_globals)
                print("[llm_core DEBUG] 程式碼執行完畢。")
                
                # --- [升級] 移植自 Streamlit 的「結果擷取」邏輯 ---
                ignore_list = ['df', 'pd', 'platform', 'io', 'fig', 'np', 'plt', 'sns', 'fm']
                for name, val in exec_globals.items():
                    if name.startswith('_') or name in ignore_list:
                        continue
                    if isinstance(val, (int, float, str, bool)):
                        summary_info[name] = val
                    elif hasattr(val, '__len__') and not isinstance(val, str) and len(val) < 20:
                        summary_info[name] = val
                
                final_fig = exec_globals.get('fig', None)
                print(f"[llm_core DEBUG] 成功！擷取到 {len(summary_info)} 個變數。")
                
                # 執行成功，跳出修正迴圈
                break 
                
            except Exception as e:
                print(f"[llm_core DEBUG] 程式碼執行失敗: {e}")
                traceback.print_exc() # 印出更詳細的錯誤
                error_message = f"程式碼執行失敗: {type(e).__name__}: {e}"
                
                if attempt == max_retries - 1:
                    # 達到最大重試次數，宣告失敗
                    print("[llm_core DEBUG] 達到最大重試次數，宣告失敗。")
                    return {"text": None, "figure": None, "error": error_message}
                
                # --- [關鍵] 建立修正提示 ---
                # 告訴 AI 錯在哪，並要求修正
                fix_prompt = f"""
                你之前生成的 Python 程式碼在執行時發生了以下錯誤：
                
                錯誤類型: {type(e).__name__}
                錯誤訊息: {e}

                這是你之前生成的 (錯誤的) 程式碼：
                ```python
                {code_to_execute}
                ```
                
                請修正這個錯誤，並**只**提供修正後的完整 Python 程式碼區塊 (```python ... ```)。
                """
                # 將修正請求加入到對話歷史中，準備下一次迴圈
                messages_for_api.append({'role': 'model', 'parts': [ai_response_text]}) # AI 的錯誤回答
                messages_for_api.append({'role': 'user', 'parts': [fix_prompt]})      # 我們的修正請求
        
        # --- 步驟 4: 【升級】第二次 AI 呼叫 (生成洞察) ---
        print("[llm_core DEBUG] 正在呼叫 Google API (生成洞察)...")
        
        # (1) 格式化 summary_info
        analysis_context_str = _format_summary_info_for_prompt(summary_info)
        
        # (2) 建立洞察提示
        # --- [升級] 移植自 Streamlit 的「洞察提示」邏輯 ---
        insight_prompt = f"""
        你是一位專業的羽球數據分析師。
        使用者的原始問題是：「{natural_language_prompt}」
        
        根據這個問題，AI 產生並執行了一段 Python 程式碼，程式碼執行後產生的核心數據變數如下。

        --- 核心數據變數 ---
        {analysis_context_str}
        --- 核心數據變數結束 ---

        請你基於「使用者問題」和上述所有「核心數據變數」，用繁體中文撰寫一份精簡、條理分明的數據洞察報告。
        報告應包含以下部分：
        1.  **直接回答**：直接且明確地回答使用者的問題。
        2.  **關鍵發現**：從數據中提煉出 1 到 3 個最關鍵的觀察或趨勢。
        3.  **總結**：用一句話總結分析結果。
        
        請避免重複描述數據內容，專注於提供有價值的見解。
        """

        try:
            # --- [關鍵] 使用中低溫 (temperature=0.4) 確保洞察的專業性與可讀性 ---
            insight_response = analysis_model.generate_content(
                insight_prompt,
                generation_config={"temperature": 0.4}
            )
            summary_text = insight_response.text
            print("[llm_core DEBUG] AI 洞察生成完畢。")
        except Exception as e:
            summary_text = f"*(無法自動生成數據洞察: {e})*"
            print(f"[llm_core DEBUG] AI 洞察生成失敗: {e}")


        # --- 步驟 5: 【修改】組合最終結果 (支援歷史) ---
        
        # 這是 AI 第一次的回應 (包含程式碼)
        code_block_for_history = ai_response_text
        
        # 這是 AI 第二次的回應 (洞察)
        # 我們將兩者組合起來，儲存到 history 中
        final_content_for_history = (
            f"{code_block_for_history}\n\n"
            f"---\n"
            f"### 📊 數據洞察\n"
            f"{summary_text}"
        )
        
        return {
            "text": summary_text,  # 最終的洞察文字
            "figure": final_fig,           # 最終的圖表物件
            "code_executed": code_to_execute, # 最終 (或修正後) 執行的程式碼
            "error": None,
            
            # --- [關鍵] 回傳這兩項，用於建立下一次呼叫的 history ---
            "history_user": {"role": "user", "parts": [natural_language_prompt]}, # 儲存「原始」問題
            "history_model": {"role": "model", "parts": [final_content_for_history.strip()]}
        }

    except Exception as e:
        print(f"[llm_core DEBUG] run_analysis 執行時發生嚴重錯誤: {e}")
        traceback.print_exc()
        return {"text": None, "figure": None, "error": str(e)}


# --- (保持不變) 儀表板翻譯器 ---
# llm_core.py

# ... (省略前面的程式碼和匯入)
import json # 確保有這行

# ... (省略 run_analysis 等其他函式)

# --- 儀表板翻譯器 (修改後) ---
def generate_analysis_from_dashboard(session_id: str, attribute: str, search_query: str) -> dict:
    """
    將儀表板的「選項」轉換成「自然語言問題」，並將圖片和文字整合存入同一個 JSON。
    """
    
    # --- 1. 定義 Prompt (保持不變) ---
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
    
    # --- 2. 執行 AI 分析 ---
    result = run_analysis(prompt, history=None)

    # --- 3. 定義路徑 ---
    # 建議：每個 session 最好有一個獨立資料夾，或是像你現在這樣放在 others
    # 這裡假設你想把同一個 session 的資料整合在一起
    save_dir = "report_pics/others" 
    import os
    os.makedirs(save_dir, exist_ok=True)

    # 圖片的檔名還是需要區分 attribute
    base_img_filename = f"{session_id}_{attribute}"
    
    # --- 4. 圖片儲存 (保持不變) ---
    if result["figure"] is not None:
        save_path_img = os.path.join(save_dir, f"{base_img_filename}.png")
        result["figure"].savefig(save_path_img, dpi=150, bbox_inches='tight')
        print(f"圖表已存檔: {save_path_img}")
    
    # --- 5. 文字儲存 (修改：整合進單一 JSON) ---
    analysis_text = result.get("text")
    
    if analysis_text:
        try:
            # 定義這個 Session 的總表檔名
            # 例如: report_pics/others/S001_metadata.json
            master_json_filename = f"{session_id}_metadata.json"
            master_json_path = os.path.join(save_dir, master_json_filename)
            
            # (A) 準備這一次分析的資料物件
            new_card_data = {
                "attribute": attribute,             # 關鍵字：例如 "殺球成功率"
                "search_query": search_query,
                "analysis_text": analysis_text,     # AI 文字
                "image_filename": f"{base_img_filename}.png", # 對應圖片檔名
                "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # (B) 讀取現有的 JSON (如果有的話)
            current_data = {}
            if os.path.exists(master_json_path):
                with open(master_json_path, 'r', encoding='utf-8') as f:
                    try:
                        current_data = json.load(f)
                    except json.JSONDecodeError:
                        print("JSON 格式錯誤，將重新建立。")
                        current_data = {}

            # (C) 初始化結構
            if "session_id" not in current_data:
                current_data["session_id"] = session_id
            
            # 使用 list 來儲存不同 attribute 的卡片
            if "analysis_cards" not in current_data:
                current_data["analysis_cards"] = []

            # (D) 更新邏輯：檢查這個 attribute 是否已經存在
            # 如果存在就更新，不存在就 Append
            cards_list = current_data["analysis_cards"]
            found = False
            for index, card in enumerate(cards_list):
                if card.get("attribute") == attribute:
                    # 找到了！更新它
                    cards_list[index] = new_card_data
                    found = True
                    break
            
            if not found:
                # 沒找到，新增它
                cards_list.append(new_card_data)

            # (E) 寫回檔案
            with open(master_json_path, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=4)
                
            print(f"分析文字已更新至總表: {master_json_path}")
            
        except Exception as e:
            print(f"警告: JSON 更新失敗: {e}")
            import traceback
            traceback.print_exc()

    return result


# --- [新增] 主程式進入點 (用於測試) ---
if __name__ == "__main__":
    # 這是一個範例，展示如何使用「交談記憶」
    
    print("\n" + "="*80)
    print(" 🚀 正在啟動 LLM Core 測試 (支援記憶)...")
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
        if result1["figure"]:
            print("(已生成圖表 1)")
        
        # 儲存記憶
        conversation_history.append(result1["history_user"])
        conversation_history.append(result1["history_model"])
        
    print("\n" + "="*80 + "\n")

    # --- 第 2 次提問 (利用記憶) ---
    print("--- 提問 2: '那球員 A 的殺球 (smash) 次數呢？' ---")
    question2 = "那球員 A 的殺球 (smash) 次數呢？"
    
    # --- [關鍵] 傳入更新後的 conversation_history ---
    result2 = run_analysis(question2, history=conversation_history)
    
    if result2["error"]:
        print(f"錯誤: {result2['error']}")
    else:
        print("\n[AI 洞察 2]:")
        print(result2["text"])
        if result2["figure"]:
            print("(已生成圖表 2)")
            
        # 再次儲存記憶
        conversation_history.append(result2["history_user"])
        conversation_history.append(result2["history_model"])

    print("\n" + "="*80 + "\n")
    print("測試完畢。")