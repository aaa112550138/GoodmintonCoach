import google.generativeai as genai
import os
from dotenv import load_dotenv

print("--- API Key 檢查腳本 ---")

# 1. 載入 .env 檔案
print("正在載入 .env 檔案...")
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ 錯誤: 找不到 GEMINI_API_KEY。")
    print("請確認 .env 檔案在同一個資料夾，且內容正確。")
    exit()

if api_key.startswith("sk-"):
    print("❌ 嚴重錯誤: 你的 GEMINI_API_KEY 是 'sk-...' 開頭的！")
    print("這是 OpenAI 的 Key，不是 Google Gemini 的 Key。")
    print("請更換為 Google 的 API Key (通常以 'AIza...' 開頭)。")
    exit()

print(f"✅ 成功載入 API Key (前 4 碼): {api_key[:4]}...")

# 2. 嘗試連線並列出模型
try:
    genai.configure(api_key=api_key)
    print("正在向 Google API 請求模型列表...")
    
    available_models = []
    # 呼叫 ListModels API
    for model in genai.list_models():
        # 我們只關心能 'generateContent' (生成內容) 的模型
        if 'generateContent' in model.supported_generation_methods:
            available_models.append(model.name)
    
    if not available_models:
        print("\n--- 檢查結果 ---")
        print("❌ 失敗！")
        print("API Key 有效，但 Google 回報「沒有任何模型可供使用」。")
        print("這幾乎 100% 是因為：")
        print("1. 你的 Google Cloud Project 尚未啟用 'Generative AI' 或 'Vertex AI' API。")
        print("2. 你的 Project 尚未綁定有效的「計費帳戶 (Billing Account)」。")
    else:
        print("\n--- 檢查結果 ---")
        print("✅ 成功！你的 API Key 可以使用以下模型：")
        for name in available_models:
            print(f"- {name}")
        
except Exception as e:
    print(f"\n❌ 發生連線錯誤: {e}")
    print("這可能是因為：")
    print("1. 你的 API Key 是無效的 (例如：打錯字、已刪除、IP 受限)。")
    print("2. 你的電腦網路無法連線到 Google API。")
