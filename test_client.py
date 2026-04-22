import asyncio
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters

async def run_main_agent_client():
    print("🧠 [測試大腦] 啟動中，準備連線到你的 mcp_report_server...")

    # 1. 告訴程式要去跑哪一個 Server
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_report_server.py"], # 指向你寫好的 Server
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ 成功連線！\n")

            # 2. 呼叫你的分析工具 (從你的截圖看，工具名稱應該是 analyze_badminton_xxx)
            # 假設工具名稱叫 "analyze_badminton_data"，請依據你 server 裡的 @mcp.tool() 函式名稱調整
            tool_name = "analyze_badminton_data" 
            test_question = "請幫我分析一下失誤的狀況。"
            
            print(f"📦 準備呼叫工具：'{tool_name}'")
            print(f"💬 傳入的問題：'{test_question}'")
            print("⏳ 正在讓 LLM 思考與分析數據，請稍等幾秒鐘...\n")
            
            try:
                # 執行呼叫
                result = await session.call_tool(
                    tool_name, 
                    arguments={"query": test_question}
                )
                
                # 3. 印出結果
                print("🎯 ========= 測試大腦收到的回傳結果 =========")
                print(result.content[0].text)
                print("=============================================")
            except Exception as e:
                print(f"❌ 呼叫失敗，發生錯誤：{e}")

if __name__ == "__main__":
    asyncio.run(run_main_agent_client())