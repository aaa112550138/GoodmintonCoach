import os
import io
import platform
import pandas as pd
from dotenv import load_dotenv

# --- 新增：匯入字型管理員 ---
import matplotlib.font_manager as fm

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

# --- 2. 設定模型與 API Key (直接給 Google) ---
DEFAULT_API_MODE = "Gemini"
DEFAULT_MODEL = "gemini-2.5-pro" # 保持使用 1.0 Pro
API_KEY = os.getenv("GEMINI_API_KEY")
print(f"[llm_core DEBUG] 正在使用的模型: {DEFAULT_MODEL}")

if not API_KEY:
    print("="*50)
    print("警告 [llm_core]: 找不到 GEMINI_API_KEY (環境 Variablen)。")
    print("="*50)
else:
    print(f"[llm_core DEBUG] 成功載入 API Key (前 4 碼): {API_KEY[:4]}...")
    try:
        genai.configure(api_key=API_KEY)
        print("[llm_core DEBUG] Google AI SDK 設定成功。")
    except Exception as e:
        print(f"[llm_core DEBUG] Google AI SDK 設定失敗: {e}")

# --- 3. 【全新】自動搜尋中文字型 (v2 - 修正版) ---
def get_chinese_font():
    """在系統中自動搜尋可用的中文字型"""
    print("[llm_core DEBUG] 正在搜尋可用的中文字型...")

    # 1. 建立系統字型快取 (名稱 -> 路徑)
    # 這一步會掃描系統上所有 .ttf 字型
    font_paths = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    font_name_to_path = {}
    for font_path in font_paths:
        try:
            # 從字型檔案路徑獲取字型名稱
            font_name = fm.FontProperties(fname=font_path).get_name()
            font_name_to_path[font_name] = font_path
        except Exception:
            continue # 略過已損壞或無法讀取的字型

    # 2. 優先從常見列表尋找 (Windows, macOS, Linux)
    preferred_font_names = [
        'Microsoft JhengHei', # 微軟正黑體 (Windows)
        'PingFang TC',        # 蘋方-繁 (macOS)
        'Noto Sans CJK TC',   # Google 思源黑體 繁
        'SimHei',             # 黑體 (簡中, 很多系統都有)
        'Arial Unicode MS',   # (舊版 Office 附帶)
    ]
    
    for font_name in preferred_font_names:
        if font_name in font_name_to_path:
             print(f"[llm_core DEBUG] 找到偏好的字型: {font_name}")
             # 直接回傳字型名稱，Matplotlib 應該能根據名稱找到它
             return font_name 

    # 3. 如果都找不到，嘗試尋找系統中第一個支援中文的字型 (fallback)
    print("[llm_core DEBUG] 未找到偏好字型，開始掃描系統字型...")
    for font_path in font_paths: # 重複使用剛剛掃描到的路徑列表
        try:
            font_prop = fm.FontProperties(fname=font_path)
            # 檢查是否能顯示中文「你」
            if fm.get_font(font_prop).get_glyph_name('你'): 
                print(f"[llm_core DEBUG] 找到一個可用的中文字型: {font_path}")
                # 回傳字型檔案的「絕對路徑」
                return font_path 
        except Exception:
            continue # 某些字型檔可能已損壞，跳過
            
    print("[llm_core DEBUG] 警告: 系統中找不到任何可用的中文字型。圖表中文將顯示為方塊。")
    return None

# --- 4. 在程式啟動時，就先找到字型並存起來 ---
GLOBAL_CHINESE_FONT_PATH_OR_NAME = get_chinese_font()


def run_analysis(natural_language_prompt: str) -> dict:
    """
    【修改版】
    直接使用 google.generativeai 呼叫 API，
    並在 system_prompt 中「注射」設定字型的指令。
    """
    
    if df is None:
        return {"text": None, "figure": None, "error": "資料集 'all_dataset.csv' 未載入。"}
    if not API_KEY:
        return {"text": None, "figure": None, "error": "未設定 GEMINI_API_KEY。"}

    try:
        # --- 步驟 0: 初始化 Google AI 模型 ---
        model = genai.GenerativeModel(DEFAULT_MODEL)
        
        # --- 步驟 1: 第一次 AI 呼叫 (生成程式碼) ---
        print(f"[llm_core DEBUG] 正在使用 {DEFAULT_MODEL} 呼叫 Google API (第一次)...")
        
        system_prompt = create_system_prompt(data_schema_info, column_definitions_info)
        
        # --- ▼▼▼ 關鍵修改：注入字體指令 ▼▼▼ ---
        font_prompt_injection = ""
        if GLOBAL_CHINESE_FONT_PATH_OR_NAME:
            # 使用 repr() 確保路徑字串在產生的程式碼中是有效的
            font_path_or_name_str = repr(GLOBAL_CHINESE_FONT_PATH_OR_NAME) 
            
            font_prompt_injection = f"""
            
            *** EXTREMELY IMPORTANT (FONT SETTING) ***
            When generating Python code with matplotlib, you MUST set the font to handle Chinese characters to prevent garbled text (tofu squares).
            The server has a Chinese font available.
            
            You MUST add the following 3 lines of code right after `import matplotlib.pyplot as plt`:
            
            ```python
            import matplotlib.pyplot as plt
            import matplotlib.font_manager as fm
            
            # --- START FONT SETTING ---
            # Use this exact font path or name:
            font_path_or_name = {font_path_or_name_str}
            
            try:
                # Try setting font by path (if it's a path)
                font_prop = fm.FontProperties(fname=font_path_or_name)
                plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
            except Exception:
                # Fallback if it's just a name
                plt.rcParams['font.sans-serif'] = [font_path_or_name]
                
            plt.rcParams['axes.unicode_minus'] = False # Fix for minus sign
            # --- END FONT SETTING ---
            ```
            
            You MUST include this code block. Failure to do so will result in an unusable chart.
            ******************************************
            """
        else:
             font_prompt_injection = """
            *** WARNING (FONT SETTING) ***
            No Chinese font was found on the server. The plot might have garbled text (tofu squares).
            Proceed with chart generation anyway.
            """

        system_prompt += font_prompt_injection
        # --- ▲▲▲ 修改完畢 ▲▲▲ ---
        
        # 組合訊息 (Gemini API 的格式)
        messages_for_api = [
            {'role': 'user', 'parts': [system_prompt]},
            {'role': 'model', 'parts': ["好的，我準備好了。我會依照指示，在 `matplotlib` 程式碼中加入設定中文字型的區塊。請給我使用者的問題。"]}, # 假裝一次對話
            {'role': 'user', 'parts': [natural_language_prompt]}
        ]
        
        response = model.generate_content(messages_for_api)
        ai_response_text = response.text
        print("[llm_core DEBUG] Google API 已回傳程式碼。")

        # --- 步驟 2: 解析並執行程式碼 ---
        code_to_execute = None
        if "```python" in ai_response_text:
            code_start = ai_response_text.find("```python") + len("```python\n")
            code_end = ai_response_text.rfind("```")
            code_to_execute = ai_response_text[code_start:code_end].strip()
            print("--- [llm_core DEBUG] 偵測到 AI 生成的程式碼: ---")
            print(code_to_execute)
            print("-------------------------------------------------")


        final_fig = None
        summary_data = None
        
        if code_to_execute:
            print("[llm_core DEBUG] 正在執行 AI 程式碼 (exec)...")
            exec_globals = {
                "pd": pd, "df": df.copy(),
                "platform": platform, "io": io
                # 注意：我們 "沒有" 傳入 plt，AI 必須自己 `import matplotlib.pyplot as plt`
            }
            exec(code_to_execute, exec_globals)
            print("[llm_core DEBUG] 程式碼執行完畢。")
            
            final_fig = exec_globals.get('fig', None)
            if final_fig:
                print("[llm_core DEBUG] 成功！在 exec_globals 中找到了 'fig' 物件。")
            else:
                print("[llm_core DEBUG] 警告！未在 exec_globals 中找到 'fig' 物件。")
            
            for var_name, var_value in exec_globals.items():
                if isinstance(var_value, (pd.DataFrame, pd.Series)) and var_name != 'df':
                    summary_data = var_value
                    break
        else:
            print("[llm_core DEBUG] 警告: AI 回應中未偵測到 ```python 程式碼區塊。")

        
        # --- 步驟 3: 第二次 AI 呼叫 (生成洞察) ---
        summary_text = ""
        if summary_data is not None:
            print("[llm_core DEBUG] 偵測到摘要資料，正在呼叫 Google API (第二次) 生成洞察...")
            try:
                table_markdown = summary_data.to_markdown()
                insight_prompt = f"""
                這是原始的使用者問題: "{natural_language_prompt}"
                這是根據問題計算出的摘要表格:
                ```markdown
                {table_markdown}
                ```
                請扮演專業數據分析師，根據此表格，用繁體中文撰寫一段簡短精闢的數據洞察。
                直接提供結論，不要複述問題或程式碼。
                """
                insight_model = genai.GenerativeModel(DEFAULT_MODEL)
                insight_response = insight_model.generate_content(insight_prompt)
                summary_text = insight_response.text
                print("[llm_core DEBUG] AI 洞察生成完畢。")
            except Exception as e:
                summary_text = f"\n\n*(無法自動生成數據洞察: {e})*"
        else:
            print("[llm_core DEBUG] 未偵測到摘要資料，跳過 AI 洞察生成。")


        # --- 步驟 4: 組合最終結果 ---
        final_content = ai_response_text
        if summary_text:
            final_content += f"\n\n---\n#### 📊 數據洞察\n{summary_text}"
        
        return {
            "text": final_content, 
            "figure": final_fig, 
            "error": None
        }

    except Exception as e:
        print(f"[llm_core DEBUG] run_analysis 執行時發生嚴重錯誤: {e}")
        return {"text": None, "figure": None, "error": str(e)}


def generate_analysis_from_dashboard(session_id: str, attribute: str, search_query: str) -> dict:
    """
    (保持不變)
    將儀表板的「選項」轉換成「自然語言問題」。
    """
    
    prompt = f"請幫我分析所有場次的數據。"
    
    if search_query:
        prompt += f" 請特別針對學生 '{search_query}' 進行分析。"
    
    if attribute == "ALL (總覽)":
        prompt += " 請提供這個場次的整體數據總覽，並用一個合適的圖表（例如長條圖或圓餅圖）來視覺化關鍵指標。"
    
    elif attribute == "球種":
        prompt += f" 請分析這個場次的「球種」分佈。請使用圓餅圖 (pie chart) 或長條圖 (bar chart) 來呈現不同球種 (例如：殺球, 切球, Tiao, 高遠球) 的使用次數或百分比。"
    
    else:
        prompt += f" 請專注於分析 '{attribute}' 這個指標，並為此生成一個最合適的圖表。"
    
    print(f"[llm_core] 翻譯後的 Prompt: {prompt}")
    
    return run_analysis(prompt)

