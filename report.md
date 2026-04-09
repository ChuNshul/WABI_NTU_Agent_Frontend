### I. Core Performance & Cost Comparison

| Metric | Planner Mode | Direct Mode | Delta / Notes |
| :--- | :--- | :--- | :--- |
| **Total requests** | 50 | 49 (1 failed request) | - |
| **Success rate** | 98.0% | 98.0% | - |
| **Total token usage** | 67,338 | 53,508 | Planner uses ~25.8% more tokens |
| **Avg tokens / request** | 1,347 | 1,092 | Planner responses are more detailed |
| **Total cost (USD)** | $0.0271 | $0.0615 | Planner is more cost-efficient |
| **Cost / request (USD)** | $0.00054 | $0.00125 | Planner is >2× cheaper per request |
| **User satisfaction (1-5)** | **3.90** | 3.37 | Planner is notably higher |

### II. Latency Breakdown

| Stage | Planner Mode | Direct Mode | Notes |
| :--- | :--- | :--- | :--- |
| **LLM latency** | **2895 ms** | 5576 ms | Planner is ~48% faster |
| **Render latency** | 133 ms | **93 ms** | Direct is slightly faster in rendering |
| **Overall avg latency** | **3.03 s** | 5.67 s | Planner is significantly faster end-to-end |

### III. Multi-Dimensional Quality Ratings

| Dimension (1-5) | Planner Mode | Direct Mode | Winner |
| :--- | :--- | :--- | :--- |
| **Safety** | **4.417** | 4.122 | Planner |
| **Tone** | **4.061** | 3.980 | Planner |
| **Clarity** | **4.020** | 3.837 | Planner |
| **Helpfulness** | **3.939** | 3.633 | Planner |
| **Factuality** | 4.143 | **4.224** | **Direct is slightly better (lower hallucination risk)** |
| **Composite score** | **4.12** | 3.96 | Planner |

### IV. Visual Quality Comparison

#### 1. Direct mode

| Issue category | Observed behavior | Impact on rating |
| :--- | :--- | :--- |
| **Language consistency** | Typical Chinese-English mixing: UI titles are Chinese, but entities (e.g., “Chicken Salad”), restaurant names (e.g., “Med Lite”), and suggestions are in English with no localization. | Significantly lowers **Clarity** and **Satisfaction**. |
| **Missing visualization** | When users ask for “bar charts” or “donut charts”, the UI often falls back to plain text, numeric labels, or an unscaled green progress bar, losing visual comparability. | Lowers **Helpfulness** and **Clarity**. |
| **Visual logic contradictions** | Severe color misuse, e.g., marking “healthy” as red (typically danger) or displaying high-sodium warnings with green numbers. | Heavily penalizes **Clarity**, and can also affect **Safety**. |
| **Poor instruction following** | Frequently ignores structured instructions like “list criteria/key points first, then recommend”, and jumps straight to a restaurant list. | Drops **Helpfulness** to ~2–3. |
| **Inefficient layout** | For short content (e.g., a brief encouragement slogan), the UI still uses a large centered card, resulting in low information density and excessive whitespace. | Lowers **Clarity**. |

---

#### 2. Planner mode

| Issue category | Observed behavior | Impact on rating |
| :--- | :--- | :--- |
| **Extreme redundancy** | **Most prominent issue**: the dark-blue header already shows the full answer, and the white card below repeats the same text 100%, causing visual fatigue. | Heavily lowers **Clarity** and **Satisfaction**. |
| **Loss of key information** | **Critical product issue**: upstream text includes recommended dishes (e.g., “Salmon Nigiri”) and numeric details, but the UI renderer drops them and only keeps the store name. | **Helpfulness** can fall to ~1–2; information is not closed-loop. |
| **Over-componentization** | For very short replies (e.g., “drink Americano + nuts”), the UI still stacks multiple large components, forcing unnecessary scrolling for one sentence worth of content. | Lowers **Clarity**. |
| **Inconsistent units and terminology** | Mixed “千卡” and “kcal” on the same page; English headers like “Protein/Carbs” in a Chinese UI are unfriendly to some users. | Penalizes **Tone** and **Clarity**. |

---

### **Key Takeaways**

1. **Step-change in efficiency:** Although Planner handles more complex intent routing, its **LLM inference is nearly 2× faster** than Direct (2.89s vs 5.57s), and the per-request cost drops substantially.
2. **Quality is broadly better:** Except for **Factuality**, where Direct is slightly higher (+0.08) likely due to shorter answers and fewer opportunities to be wrong, Planner outperforms Direct on Safety, Tone, Clarity, and Helpfulness.
3. **Better user experience:** Satisfaction improves from 3.37 to 3.90, suggesting users prefer the Planner UI (e.g., dashboard/donut components) and the more structured information flow.
4. **Shared issues remain:** Both versions still struggle with Chinese-English mixing and factual cross-checks (e.g., distance-time consistency).
5. **Recommended next steps:** Improve parsing/rendering of the `dishes` field in `upstream_text`, remove duplicated text between the header and body to increase information density, and enforce a **Safety** disclaimer for medical/health-plan answers.
