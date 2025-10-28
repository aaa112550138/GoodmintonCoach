// 確保 DOM 載入完成後才執行
document.addEventListener("DOMContentLoaded", function() {
    
    // --- 1. 【全新】AI 分析表單的邏輯 ---
    const analysisForm = document.getElementById("analysis-form");
    const resultArea = document.getElementById("analysis-result-area");
    const generateButton = document.getElementById("generate-button");

    // 檢查元素是否存在，避免錯誤
    if (analysisForm) {
        analysisForm.addEventListener("submit", function(event) {
            // 1. 阻止表單的預設提交行為 (防止頁面重新整理)
            event.preventDefault(); 

            // 2. 獲取表單中的值 (使用你新的 ID)
            const search_query = document.getElementById("search_input").value;
            const session_id = document.getElementById("session_select").value;
            const attribute_name = document.getElementById("attribute_select").value;

            // 簡單的前端驗證
            if (!session_id || !attribute_name) {
                resultArea.innerHTML = `<p class="error-message">錯誤：\n請務必選擇「場次」和「屬性」。</p>`;
                return;
            }

            // 3. 顯示載入中... 並禁用按鈕
            resultArea.innerHTML = '<p>成功! Python 正在為您分析...</p>';
            resultArea.classList.add("loading");
            generateButton.disabled = true;
            generateButton.innerText = "AI 分析中...";

            // 4. 準備要 POST 到 API 的 JSON 資料
            const requestData = {
                search_query: search_query,
                session_id: session_id,
                attribute_name: attribute_name
            };

            // 5. 使用 fetch 呼叫我們的 Flask API (/api/analyze)
            fetch("/api/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestData)
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errData => {
                        throw new Error(errData.error || `伺服器錯誤: ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                // 6. 成功! 處理從後端拿到的 JSON 資料
                resultArea.classList.remove("loading");
                
                if (data.status === "success") {
                    let html_output = "";
                    
                    // 處理 AI 生成的文字 (用 <pre> 保留格式)
                    if (data.analysis_text) {
                        html_output += `<pre>${data.analysis_text}</pre>`;
                    } else {
                        html_output += "<p>AI 未提供文字分析。</p>";
                    }

                    // 處理 AI 生成的圖表 (Base64 圖片)
                    if (data.chart_image_base64) {
                        html_output += `<h3>分析圖表</h3>`;
                        html_output += `<img src="data:image/png;base64,${data.chart_image_base64}" alt="AI 分析圖表">`;
                    } else {
                        html_output += "<p>AI 未生成圖表。</p>";
                    }
                    
                    resultArea.innerHTML = html_output;

                } else {
                    resultArea.innerHTML = `<p class="error-message">分析失敗：\n${data.error}</p>`;
                }
            })
            .catch(error => {
                // 7. 處理網路錯誤或 fetch 失敗
                console.error("Fetch 呼叫失敗:", error);
                resultArea.classList.remove("loading");
                resultArea.innerHTML = `<p class="error-message">請求失敗：\n${error.message}</p>`;
            })
            .finally(() => {
                // 8. 無論成功或失敗，最後都要恢復按鈕
                generateButton.disabled = false;
                generateButton.innerText = "生成圖表";
            });
        });
    }

    // --- 【新增】在頁面載入時，也執行一次連結更新，確保初始狀態正確 ---
    updateReportLinks();

}); // DOMContentLoaded 結束


// --- 2. 【整合版】比賽報告連結邏輯 ---
// 響應 HTML 中的 onchange="updateReportLinks()"
function updateReportLinks() {
    const select = document.getElementById("match_link_select");
    const reportBtn = document.getElementById("report-btn");
    const actualLink = document.getElementById("actual-link");
    
    if (!select || !reportBtn || !actualLink) {
        // 如果找不到元素，就提早退出，避免錯誤
        return;
    }
    
    const selectedUrl = select.value;
    const selectedOption = select.options[select.selectedIndex];
    const selectedText = selectedOption.textContent;

    if (selectedUrl) {
        // 更新「前往報告」按鈕
        reportBtn.href = selectedUrl;
        reportBtn.textContent = "前往報告";
        reportBtn.classList.remove("btn-disabled");
        
        // 更新「預覽連結」文字 (採用你提供的 '前往：' 格式)
        actualLink.href = selectedUrl;
        actualLink.textContent = `前往：${selectedText.trim()}`;
    } else {
        // 重設「前往報告」按鈕
        reportBtn.href = "#";
        reportBtn.textContent = "請先選擇比賽";
        reportBtn.classList.add("btn-disabled");

        // 重設「預覽連結」文字 (採用你提供的 '請先選擇' 格式)
        actualLink.href = "#";
        actualLink.textContent = "請先選擇一個連結";
    }
}

