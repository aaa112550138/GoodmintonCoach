import sys
import os

# 確保 Python 能正確找到旁邊的 utils, config 和 llm_core
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
import llm_core

# 1. 建立 Report 專屬的 MCP Server
mcp = FastMCP("ReportCoach", host="0.0.0.0", port=8000)

# 2. 把 llm_core 的核心函數包裝成大腦能用的工具
@mcp.tool()
def analyze_badminton_data(query: str) -> str:
    """
    呼叫 Report 子計畫：羽球數據分析與報表生成。
    請傳入具體的自然語言問題 (例如：「分析戴資穎的殺球成功率」或「誰是失誤王？」)。
    工具會讀取歷史比賽數據，並回傳專業教練的戰術分析報告。
    """
    print(f"\n[Report MCP] 收到大腦指令，準備分析: {query}")
    
    try:
        # 直接呼叫你寫好的神級函數！
        result = llm_core.run_analysis(query)
        
        # 檢查是否有錯誤
        if result.get("error"):
            return f"執行分析時發生錯誤：{result['error']}"
            
        # 提取 LLM 總結好的文字報告
        report_text = result.get("text", "分析完成，但未產生文字報告。")
        
        # (進階：你的 run_analysis 其實有回傳 figures，未來如果大腦支援顯示圖片，
        # 我們可以在這裡把圖片轉成 Base64 字串一起回傳。現在 MVP 先回傳純文字報告。)
        
        return report_text
        
    except Exception as e:
        return f"Report Server 發生例外錯誤: {str(e)}"

# 3. 啟動伺服器
if __name__ == "__main__":
    print("🌐 啟動 ReportCoach MCP Server (SSE 網路模式, Port: 8000)...")
    # 將預設的 stdio 改為 sse，並指定 port
    mcp.run(transport="sse")