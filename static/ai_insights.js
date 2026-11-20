/**
 * ai_insights.js - Interactive AI Health Insights & Q&A Client for MediTrust
 * Enhanced with Streaming Typewriter Effects & Thinking Indicators
 */

document.addEventListener("DOMContentLoaded", function () {
    const configEl = document.getElementById("aiInsightConfig");
    if (!configEl) return;

    const category = configEl.dataset.category || "blood_pressure";
    const spinner = document.getElementById("aiInsightSpinner");
    const content = document.getElementById("aiInsightContent");
    const emptyBox = document.getElementById("aiInsightEmpty");
    const paragraph = document.getElementById("aiInsightParagraph");
    const refreshBtn = document.getElementById("refreshInsightBtn");
    const askBtn = document.getElementById("aiAskFollowupBtn");
    const questionInput = document.getElementById("aiFollowupInput");
    const qaThread = document.getElementById("aiQaThread");
    const qaSpinner = document.getElementById("aiQaSpinner");

    let currentInsight = "";

    // TYPEWRITER ENGINE
    function typeWriter(element, text, speed = 16, onComplete = null) {
        element.innerHTML = "";
        const cursor = document.createElement("span");
        cursor.className = "typing-cursor";
        cursor.textContent = "▌";
        cursor.style.cssText = "display:inline-block; font-weight:900; color:#087E75; animation:blink 0.8s infinite; margin-left:2px;";
        element.appendChild(cursor);

        const words = text.split(" ");
        let i = 0;

        function step() {
            if (i < words.length) {
                const span = document.createTextNode((i > 0 ? " " : "") + words[i]);
                element.insertBefore(span, cursor);
                i++;

                const lastWord = words[i - 1];
                const pause = (lastWord.includes(".") || lastWord.includes("\n") || lastWord.includes("!") || lastWord.includes("?")) ? 75 : speed;
                setTimeout(step, pause);
            } else {
                cursor.remove();
                if (onComplete) onComplete();
            }
        }
        step();
    }

    function loadInsight() {
        if (!spinner || !content) return;
        spinner.style.display = "block";
        content.style.display = "none";
        if (emptyBox) emptyBox.style.display = "none";

        fetch("/api/health-insights/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ category: category })
        })
        .then(res => res.json())
        .then(data => {
            spinner.style.display = "none";
            if (data.success && data.insight) {
                currentInsight = data.insight;
                content.style.display = "block";
                // Stream initial 5-7 sentence insight with typewriter
                typeWriter(paragraph, data.insight, 15);
            } else {
                if (emptyBox) {
                    emptyBox.textContent = data.error || "No measurement records available yet.";
                    emptyBox.style.display = "block";
                }
            }
        })
        .catch(err => {
            spinner.style.display = "none";
            if (emptyBox) {
                emptyBox.textContent = "Unable to load AI insight at this moment.";
                emptyBox.style.display = "block";
            }
        });
    }

    if (refreshBtn) {
        refreshBtn.addEventListener("click", function () {
            loadInsight();
        });
    }

    function handleAsk() {
        const question = (questionInput ? questionInput.value : "").trim();
        if (!question) {
            alert("Please enter a question.");
            return;
        }

        // Add user question bubble to thread
        const userBubble = document.createElement("div");
        userBubble.style.cssText = "align-self: flex-end; max-width: 85%; background: #087E75; color: white; padding: 10px 15px; border-radius: 12px 12px 2px 12px; font-size: 13.5px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); animation: fadeIn 0.2s ease-in;";
        userBubble.innerHTML = "<strong>You:</strong> " + escapeHtml(question);
        qaThread.appendChild(userBubble);

        questionInput.value = "";
        askBtn.disabled = true;
        if (qaSpinner) qaSpinner.style.display = "block";

        fetch("/api/health-insights/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                category: category,
                question: question,
                previous_insight: currentInsight
            })
        })
        .then(res => res.json())
        .then(data => {
            if (qaSpinner) qaSpinner.style.display = "none";
            askBtn.disabled = false;

            const aiBubble = document.createElement("div");
            aiBubble.style.cssText = "align-self: flex-start; max-width: 90%; background: #ffffff; color: #1e293b; border: 1px solid #bbf7d0; padding: 14px 18px; border-radius: 12px 12px 12px 2px; font-size: 13.5px; line-height: 1.7; box-shadow: 0 2px 8px rgba(0,0,0,0.04); animation: fadeIn 0.25s ease-in;";

            const headerDiv = document.createElement("div");
            headerDiv.style.cssText = "display: flex; align-items: center; gap: 6px; margin-bottom: 8px;";
            headerDiv.innerHTML = "<strong style='color: #065f46;'>✨ MediTrust AI Assistant</strong>";
            aiBubble.appendChild(headerDiv);

            const textSpan = document.createElement("div");
            aiBubble.appendChild(textSpan);
            qaThread.appendChild(aiBubble);

            if (data.success && data.answer) {
                // Stream follow-up answer line by line
                typeWriter(textSpan, data.answer, 15);
            } else {
                textSpan.innerHTML = "<span style='color: #dc2626;'>Could not answer question: " + escapeHtml(data.error || "Unknown error") + "</span>";
            }
        })
        .catch(err => {
            if (qaSpinner) qaSpinner.style.display = "none";
            askBtn.disabled = false;
            const errBubble = document.createElement("div");
            errBubble.style.cssText = "align-self: flex-start; background: #fee2e2; color: #991b1b; padding: 10px 14px; border-radius: 10px; font-size: 13px;";
            errBubble.textContent = "Network error while reaching AI assistant.";
            qaThread.appendChild(errBubble);
        });
    }

    if (askBtn) {
        askBtn.addEventListener("click", handleAsk);
    }

    if (questionInput) {
        questionInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                e.preventDefault();
                handleAsk();
            }
        });
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    // Initial load
    loadInsight();
});
