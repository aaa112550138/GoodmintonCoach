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
                if (oldResultArea) oldResultArea.innerHTML = `<p class="error-message">錯誤：請務必選擇「場次」和「屬性」。</p>`;
                return;
            }

            // 顯示載入中
            if (oldResultArea) oldResultArea.innerHTML = '<p>正在請求 Python 分析...</p>';
            if (oldGenerateButton) {
                oldGenerateButton.disabled = true;
                oldGenerateButton.innerText = "分析中...";
            }

            // 舊功能維持使用 fetch (AJAX) 不換頁
            fetch("/api/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ search_query, session_id, attribute_name })
            })
            .then(res => res.json())
            .then(data => {
                if (oldResultArea) {
                    if (data.status === "success") {
                        let html = "";
                        if (data.analysis_text) html += `<pre>${data.analysis_text}</pre>`;
                        if (data.chart_image_base64) html += `<h3>分析圖表</h3><img src="data:image/png;base64,${data.chart_image_base64}" alt="Chart">`;
                        oldResultArea.innerHTML = html || "<p>AI 未提供內容。</p>";
                    } else {
                        oldResultArea.innerHTML = `<p class="error-message">錯誤：${data.error}</p>`;
                    }
                }
            })
            .catch(err => {
                if (oldResultArea) oldResultArea.innerHTML = `<p class="error-message">請求失敗：${err.message}</p>`;
            })
            .finally(() => {
                if (oldGenerateButton) {
                    oldGenerateButton.disabled = false;
                    oldGenerateButton.innerText = "生成圖表 (舊版)";
                }
            });
        });
    }

    // ==========================================
    // PART 2: 【新功能】多選下拉選單 UI 邏輯
    // ==========================================
    const dropdown = document.getElementById('llm-multi-select');
    if (dropdown) {
        const trigger = dropdown.querySelector('.select-trigger');
        const triggerText = dropdown.querySelector('.trigger-text');
        const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');

        // 1. 點擊觸發開關
        if (trigger) {
            trigger.addEventListener('click', function(e) {
                e.stopPropagation();
                dropdown.classList.toggle('open');
            });
        }

        // 2. 點擊外部關閉選單
        document.addEventListener('click', function(e) {
            if (!dropdown.contains(e.target)) {
                dropdown.classList.remove('open');
            }
        });

        // 3. 監聽勾選變化，更新顯示文字
        checkboxes.forEach(box => {
            box.addEventListener('change', updateTriggerText);
            // 點擊 label 也能觸發 checkbox (雖然 HTML 結構已經支援，但加上防止事件冒泡)
            if(box.parentElement) {
                box.parentElement.addEventListener('click', function(e) {
                    e.stopPropagation();
                });
            }
        });

        function updateTriggerText() {
            const selected = Array.from(checkboxes)
                                .filter(box => box.checked)
                                .map(box => box.parentElement.textContent.trim());
            
            if (selected.length === 0) {
                triggerText.textContent = "請選擇分析項目...";
                triggerText.style.color = "#888";
            } else if (selected.length <= 2) {
                triggerText.textContent = selected.join(', ');
                triggerText.style.color = "#333";
            } else {
                triggerText.textContent = `已選擇 ${selected.length} 個項目`;
                triggerText.style.color = "#333";
            }
        }
    }

    // ==========================================
    // PART 3: 比賽報告連結更新邏輯 (初始化)
    // ==========================================
    const matchSelect = document.getElementById("match_link_select");
    const reportBtn = document.getElementById("report-btn");

    if (matchSelect && reportBtn) {
        matchSelect.addEventListener('change', function() {
            const selectedUrl = this.value;
            console.log("選擇的報告 URL:", selectedUrl); // Debug log

            if (selectedUrl) {
                reportBtn.href = selectedUrl;
                reportBtn.textContent = "📄 前往閱讀報告";
                reportBtn.classList.remove("btn-disabled");
            } else {
                reportBtn.removeAttribute('href');
                reportBtn.textContent = "請先選擇比賽";
                reportBtn.classList.add("btn-disabled");
            }
        });
    }

    // ==========================================
    // PART 4: 刪除模版邏輯 (Delete Template)
    // ==========================================
    // 將 deleteTemplate 掛載到 window 物件，因為 HTML 中是用 onclick="deleteTemplate(...)" 呼叫的
    window.deleteTemplate = function(id) {
        if(!confirm('確定要刪除這個模版嗎？此動作無法復原。')) return;

        fetch('/api/delete-template/' + id, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if(data.success) {
                // 成功後重新整理頁面
                location.reload();
            } else {
                alert('刪除失敗: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('發生系統錯誤');
        });
    };
});