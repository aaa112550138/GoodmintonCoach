document.addEventListener("DOMContentLoaded", function() {
    
    // ==========================================
    // PART 1: 【舊功能】傳統單選分析表單邏輯
    // ==========================================
    const analysisForm = document.getElementById("analysis-form");
    const oldResultArea = document.getElementById("analysis-result-area");
    const oldGenerateButton = document.getElementById("generate-button");

    if (analysisForm) {
        analysisForm.addEventListener("submit", function(event) {
            event.preventDefault(); 

            const search_query = document.getElementById("search_input").value;
            const session_id = document.getElementById("session_select").value;
            const attribute_name = document.getElementById("attribute_select").value;

            if (!session_id || !attribute_name) {
                oldResultArea.innerHTML = `<p class="error-message">錯誤：請務必選擇「場次」和「屬性」。</p>`;
                return;
            }

            // 顯示載入中
            oldResultArea.innerHTML = '<p>正在請求 Python 分析...</p>';
            oldGenerateButton.disabled = true;
            oldGenerateButton.innerText = "分析中...";

            // 舊功能維持使用 fetch (AJAX) 不換頁
            fetch("/api/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ search_query, session_id, attribute_name })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    let html = "";
                    if (data.analysis_text) html += `<pre>${data.analysis_text}</pre>`;
                    if (data.chart_image_base64) html += `<h3>分析圖表</h3><img src="data:image/png;base64,${data.chart_image_base64}" alt="Chart">`;
                    oldResultArea.innerHTML = html || "<p>AI 未提供內容。</p>";
                } else {
                    oldResultArea.innerHTML = `<p class="error-message">錯誤：${data.error}</p>`;
                }
            })
            .catch(err => {
                oldResultArea.innerHTML = `<p class="error-message">請求失敗：${err.message}</p>`;
            })
            .finally(() => {
                oldGenerateButton.disabled = false;
                oldGenerateButton.innerText = "生成圖表 (舊版)";
            });
        });
    }

    // ==========================================
    // PART 2: 【新功能】多選下拉選單 UI 邏輯
    // ==========================================
    // 注意：因為使用 HTML Form POST (target="_blank")，
    // 這裡只需要處理「選單的顯示」與「文字更新」，不需要寫 fetch 送出資料。
    
    const dropdown = document.querySelector('.custom-dropdown');
    if (dropdown) {
        const trigger = dropdown.querySelector('.select-trigger');
        const triggerText = dropdown.querySelector('.trigger-text');
        const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');

        // 1. 點擊觸發開關
        trigger.addEventListener('click', function(e) {
            e.stopPropagation();
            dropdown.classList.toggle('open');
        });

        // 2. 點擊外部關閉選單
        document.addEventListener('click', function(e) {
            if (!dropdown.contains(e.target)) dropdown.classList.remove('open');
        });

        // 3. 監聽勾選變化，更新顯示文字 (例如: "已選擇 3 個項目")
        checkboxes.forEach(box => {
            box.addEventListener('change', () => {
                let count = 0;
                checkboxes.forEach(b => { if(b.checked) count++; });
                
                if (count === 0) {
                    triggerText.textContent = "請選擇分析項目...";
                    triggerText.style.color = "#333";
                } else {
                    triggerText.textContent = `已選擇 ${count} 個項目`;
                    triggerText.style.color = "#007bff";
                }
            });
        });
    }
    
    // ==========================================
    // PART 3: 連結更新 (初始化)
    // ==========================================
    updateReportLinks();
});

// 獨立函式 (因為 HTML 有 onchange="updateReportLinks()")
function updateReportLinks() {
    const select = document.getElementById("match_link_select");
    const reportBtn = document.getElementById("report-btn");
    //const actualLink = document.getElementById("actual-link");
    console.log("偵hi");
    if (!select || !reportBtn ) return;
    console.log("偵hi");
    const selectedUrl = select.value;
    console.log("偵錯 1: select.value (下拉選單選取的值) =", selectedUrl);
    if (selectedUrl) {
        reportBtn.href = selectedUrl;
        reportBtn.textContent = "前往報告";
        reportBtn.classList.remove("btn-disabled");
        
    } else {
        reportBtn.href = "#";
        reportBtn.textContent = "請先選擇比賽";
        reportBtn.classList.add("btn-disabled");
        
    }
}