### I. Panorama Comparison Matrix of 10 State-of-the-Art Paradigms (The 10 State-of-the-Art Paradigms)

| ID | Paradigm & Representative Work | Core Technical Driver | Primary Use Cases | Advantages | Limitations & Critical Gaps | Link |
| --- | --- | --- | --- | --- | --- | --- |
| **1** | **Zero-Shot GUI Gen**<br>(Kolthoff et al., 2024) | End-to-end code generation by LLMs (Direct Prompting) | General UI prototypes, one-off forms | Minimal architecture; relies on the pretrained model’s front-end prior knowledge. | **Highly uncontrollable, high latency.** In healthcare it can produce fatal “visual-logic contradictions” (e.g., rendering severe warnings in green). | [2412.11328](https://arxiv.org/pdf/2412.11328) |
| **2** | **Task Decomposition (GUIDE)**<br>(Kolthoff et al., 2025) | Task decomposition + Retrieval-Augmented Generation (RAG) + Figma API | Iterative professional UI design for complex apps | Improves structure; supports component-level refinement; strong visual consistency. | **Not real-time; offline dependencies.** Tightly coupled to offline design tools, unsuitable for second-level latency requirements in consumer-facing chatbots. | [2502.21068](https://arxiv.org/pdf/2502.21068) |
| **3** | **Preference Alignment (CrowdGenUI)**<br>(Liu et al., 2025) | Alignment via crowdsourced human preferences | Personalized web pages and commercial landing pages | UI aligns well with mainstream aesthetics and ergonomics. | **Optimizes for preference at the expense of factuality.** In healthcare, it may hide or weaken essential medical disclaimers to satisfy user tastes. | [2411.03477](https://arxiv.org/pdf/2411.03477) |
| **4** | **RL-Driven Profiling (HumAIne)**<br>(Makridis et al., 2025) | Virtual personas + reinforcement learning (RL) for dynamic adjustment | Long-horizon emotional companionship and dialogue systems | Captures user emotion; dynamically adjusts tone and information density. | **Text-only.** Fails to extend agentic logic to rich visual components (e.g., dynamic charts, medical progress cards). | [2509.04303v1](https://arxiv.org/pdf/2509.04303v1) |
| **5** | **Rule-Based AUI**<br>(Wang et al., 2024) | Heuristic rules + static component-tree library | Traditional mHealth apps for chronic-disease management | Rigorously clinically tested; **100% safety and compliance.** | **Lacks generation and generalization.** Cannot dynamically create new layouts for open-domain natural-language health Q&A. | [10.1145/3639475.3640104](https://dl.acm.org/doi/epdf/10.1145/3639475.3640104) |
| **6** | **Generative UI via DSL**<br>(e.g., Vercel v0 paradigm) | LLM generates domain-specific languages (DSL) / React code | Industrial front-end code auto-generation tools | Interactive components; high code reuse; supports complex states. | **Huge token cost and long-context loss.** Requiring the LLM to emit large volumes of code is expensive and often breaks pages (e.g., missing closing tags). | [2506.13663](https://arxiv.org/pdf/2506.13663) |
| **7** | **Semantic Guardrails**<br>(e.g., NeMo Guardrails) | Vector-retrieval-based semantic boundary checks | Enterprise and medical Q&A with strict compliance requirements | Effectively blocks jailbreaks and non-compliant medical responses. | **Guardrails stop at the text layer.** Lacks a safety backstop for “visual rendering safety.” | [2023.emnlp-demo.40.pdf](https://aclanthology.org/2023.emnlp-demo.40.pdf) |
| **8** | **Multi-Agent Dev**<br>(e.g., ChatDev / MetaGPT) | Role-playing agents (PM, Coder, Tester) collaboration | Automated software engineering and medium/large codebase generation | Multi-round reviews significantly reduce code bugs. | **Extremely computationally redundant.** UI generation can require minutes of agent dialogue, incompatible with real-time chatbots. | [2307.07924](https://arxiv.org/pdf/2307.07924) |
| **9** | **RAG-Augmented UI Assembly**<br>(General NLP-to-UI) | Intent recognition + retrieval & stitching of local UI code snippets | Small vertical micro-app generation | Lower hallucination by composing existing snippets. | **Heavily dependent on retrieval coverage.** CSS collisions can fragment final styling. | [2311.06495](https://arxiv.org/pdf/2311.06495) |
| **10** | **VLM-Driven UI Grounding**<br>(Design2Code) | Vision-language models reverse-parse UI images | Sketch-to-code, multimodal understanding | Converts image inputs (e.g., handwritten prescriptions, food photos) into UI. | **Lacks structured data abstraction.** Outputs tend to be pixel-level imitation and cannot reliably inject complex backend reasoning data into UI. | [2403.03163](https://arxiv.org/pdf/2403.03163) |

| Core Technical Quadrant | Representative Paradigms & Papers | Mechanism | Advantages | Gaps in Healthcare |
| --- | --- | --- | --- | --- |
| I. End-to-End Gen | 1. Zero-Shot GUI Gen (Kolthoff et al., 2024)<br>6. Generative UI via DSL (Vercel v0 paradigm) | Relies on pretrained LLM knowledge to output HTML/React/DSL code in one shot. | Minimal architecture; no retrieval; components can support complex interactions and state. | Severe latency and low controllability. Forces the LLM to act as a “syntax compiler,” prone to tag errors and “visual-logic contradictions,” with high token cost. |
| II. Decomposition & RAG | 2. Task Decomp. (GUIDE) (Kolthoff et al., 2025)<br>9. RAG-Augmented UI (LayoutPrompter) | Decomposes complex UI requests and uses RAG to retrieve and stitch existing snippets. | Improves structure; supports component-level feature refinement and consistency. | Heavy offline dependencies and CSS collisions. Tight coupling to offline tools (e.g., Figma) or style conflicts in stitching; not suitable for second-level consumer-facing real-time systems. |
| III. Alignment & RL | 3. Preference Alignment (Liu et al., 2025)<br>4. RL-Driven Profiling (Makridis et al., 2025) | Adjusts style based on crowdsourced feedback (CrowdGenUI) or RL (HumAIne). | UI and text better match individual aesthetics, emotional preference, and cognitive load. | Preference can override factuality. In healthcare, over-alignment may hide key disclaimers; current methods are mostly text-only and lack visual-component alignment. |
| IV. Agent & Safety | 5. Rule-Based AUI (Wang et al., 2024)<br>7. Semantic Guardrails (NeMo Guardrails)<br>8. Multi-Agent Dev (ChatDev/MetaGPT) | Hard-coded rules, multi-agent reviews, or semantic retrieval-based checks. | Clinical safety and compliance can reach 100%; multi-round reviews reduce code bugs. | Lack of real-time responsiveness and flexibility. Multi-agent approaches incur minute-level latency; guardrails are mostly text-only and lack a visual-layer backstop. |
| V. Vision-Language | 10. VLM-Driven Grounding (Design2Code, 2024) | Uses VLMs to reverse-parse sketches/images into front-end code. | Breaks the text-only constraint; can understand prescriptions or dashboard screenshots and produce UI. | Lacks structured abstraction. Outputs are pixel-level imitation, making it hard to inject complex backend reasoning data (e.g., nutrition computation) dynamically and precisely. |

#### Zero-Shot GUI Gen

[https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/Zero-Shot.png](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/Zero-Shot.png)

**Abstract**
- Explores the feasibility of zero-shot prompting for high-fidelity GUI prototype generation, proposing retrieval augmentation and self-critique loops to improve relevance and overall quality.

**Methodology**
- Stepwise refinement: decomposes GUI generation into “requirements → structure → layout → code” instead of one-shot end-to-end output.
- Retrieval augmentation: retrieves top-n similar GUIs as external references to reduce hallucination and style drift.
- Iterative self-correction: uses self-critique and multi-round iteration to reduce layout / functionality / styling defects.
- Baselines: ZS-Instruction (direct code-only output) and ZS-CoT (step-by-step reasoning before code).
- PDGG: feature extraction → component/library design → layout design → code generation.
- RAGG: on Rico+S2W, uses S-BERT to retrieve top-n GUIs, then uses an LLM for binary filtering and 1–10 fine-grained reranking; supports feature aggregation before generation or direct inspiration from retrieved GUIs.
- SCGG: alternates between a feedback LLM (points out defects) and a generation LLM (iteratively improves using feedback).
- Content enhancement: fills in realistic data and richer image descriptions; uses generative images (e.g., DALL·E) to improve perceived fidelity.

**Experiments**
- RQ1 (reranking): multimodal LLM zero-shot reranking outperforms BERT-LTR (mean precision 0.818 vs 0.501); binary relevance judgment achieves P=0.757, R=0.814, F1=0.784.
- RQ2 (generation quality): SCGG outperforms baselines and PDGG on functionality completeness, information organization, visual quality, error rate, and satisfaction; larger-k RAGG improves functional breadth and app completeness.
- RQ3 (number of examples): k=7 significantly outperforms k=1/3; increasing k from 1→5 improves functional metrics most, while 5→7 further improves overall dimensions.
- RQ4 (number of critique loops): loop count has limited impact on most metrics; extra loops tend to add features and complete app structure (e.g., navigation, header/footer) rather than refining base layout.
- RQ5 (content generation): automatic content completion improves visual quality, satisfaction, and app completeness and mitigates “missing content leads to incomplete implementation.”

#### GUIDE

[https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/GUIDE.png](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/GUIDE.png)

**Abstract**
- Decomposes high-level GUI descriptions into editable fine-grained requirements and retrieves component specs to generate editable Material Design-style prototypes inside Figma, improving controllability and editability.

**Methodology**
- Entry point: developers input a high-level GUI description in a Figma plugin.
- Functional decomposition: the LLM outputs a fine-grained feature list / JSON that users can edit, add, or delete.
- Component assembly (RAG): selects candidate components, retrieves full JSON specs, fills attributes (icons, position/size, etc.), and auto-validates format.
- Prototyping: renders editable GUI components inside Figma.
- Implementation: TypeScript Figma plugin + Python Quart REST API with gunicorn/nginx; uses OpenAI GPT-4o (2024/10).

**Experiments**
- Design: small between-subjects study (11 participants) building prototypes under “with/without assistant” conditions (4 tasks within 45 minutes), evaluated online by 28 UI/UX-experienced crowd workers.
- Results: the assisted group completed 3.2 prototypes per person vs 2.33 in control; rating distributions were higher with significant rank-sum tests.

#### CrowdGenUI

[https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/CrowdGenUI.png](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/CrowdGenUI.png)

**Abstract**
- Uses crowdsourced UI control preferences to guide LLM reasoning and component selection, aligning generated controls with predictability, efficiency, and explorability.

**Methodology**
- Input: task description + user preferences (text).
- Reasoning: an LLM (GPT-4o) performs a CoT-style process of “match similar tasks → extract preference-relevant components → select suitable components,” and outputs a JSON reasoning result.
- Implementation: generates Python UI code (Jupyter Widgets) from the reasoning result; example code reduces errors and enables more complex components beyond defaults.

**Experiments**
- Preference library: 720 preferences collected from 50 participants across the three design principles.
- User study: N=78 (Prolific), comparing no-library vs different library sizes (10/25/30).
- Results: preference-library conditions outperform no-library; a size of 30 performs best and is most stable, while smaller libraries show higher variance due to preference diversity.

#### HumAIne-Chatbot

[https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/HumAIne-Chatbot.png](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/HumAIne-Chatbot.png)

**Abstract**
- Drives dialogue policy with “user profiling + online reinforcement learning,” adapting content and style in real time based on users’ implicit and explicit signals.

**Methodology**
- Persona prior: pretrains on diverse GPT-generated virtual personas to learn broad priors over user types.
- Online RL: combines implicit signals (typing speed, emotion, engagement duration, etc.) and explicit feedback (like/dislike) to optimize personalized policies (e.g., PPO).
- Policy realization: dynamically adjusts language complexity, verbosity, expertise level, and conversational style; can be combined with RAG/LLM generation pipelines.
- Metrics: profiling inputs include session length, response time, typing speed, grammatical accuracy, language complexity, affect, and pre-session questionnaire answers; performance includes user ratings, comments, usability, and satisfaction dimensions (expectation, impression, ease of use, engagement).

**Experiments**
- Setup: 50 synthetic personas across 10 topic domains, 150 total dialogues, A/B comparison of personalized vs non-personalized conditions.
- Results: mean satisfaction 0.173 vs 0.119 (+45.0%) with p<0.001; secondary metrics (relevance, personalization match, task completion) also improve.
- Limitations: synthetic personas cannot fully replicate real users; evaluation focuses on short-term conversations and does not establish long-term free-form dialogue performance.

#### Rule-Based AUI

[https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/Rule-Based%20AUI.png](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/Rule-Based%20AUI.png)

**Abstract**
- Builds and evaluates a rule-based, taxonomy-driven adaptive user interface (AUI) prototype for chronic-disease mHealth, aiming to balance usability, transparency, and information load.

**Methodology**
- Prototype construction: uses a systematic literature review (SLR) to refine adaptation categories and build an AUI prototype with three core adaptation types.
- Presentation adaptation: changes visual parameters (color, size, typography) spanning theme/layout and information architecture organization.
- Content adaptation: adapts text/images to user needs via complexity simplification (plain language, minimal design, text-to-image) and element rearrangement (repositioning/hiding).
- Behavioral adaptation: adapts navigation and interaction modes (navigation adaptation, add-on features, persuasive strategies, multimodal interaction, difficulty adjustment), often involving multi-step coupling.
- Controllability and explainability: provides switching logic and rationale for each adaptation to improve usability and transparency.

**Experiments**
- Study process: focus groups and interviews (22 participants) plus surveys (90 participants), iterating the prototype with mixed qualitative/quantitative analysis; additionally evaluated by 3 co-authors and tested with 2 mHealth users.
- Findings (challenges): adaptation content (predictability, comprehension cost, intrusiveness, mismatch, resistance to negative health data, age differences), initiator (incomplete/forged data, higher cognitive load for older users, opacity risks), method (privacy concerns and decision fatigue), timing (burden from frequent changes and multi-context complexity).
- Findings (mitigations): controllability/autonomy (panels, stepwise guidance, granularity, toggles, priorities), adaptation support (entry points, onboarding/tutorials, contextual explanations and suggestions), consistency alignment (terminology simplification and visual consistency).
- Note: must consider both active and passive user participation and secondary users such as family members and caregivers.

#### DesignCoder

[https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/DesignCoder.png](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/blob/main/img_for_ref/DesignCoder.png)

**Abstract**
- Proposes DesignCoder, a hierarchical-aware and self-correcting design-to-code framework that improves visual fidelity, structural similarity, and code quality for React Native generation.

**Methodology**
- Target setting: industrial design-to-code generation, jointly optimizing visual consistency, maintainability, and usability via design metadata.
- UI grouping chain: partitions UI into mutually exclusive subregions via visual semantics, then uses a two-stage prompting scheme to extract element semantics and build hierarchical component subtrees.
- Hierarchical code generation: divides and conquers across component subtrees; integrates layout and style prompts to produce component and style code.
- Self-correction: uses Appium to compare rendered output with the design, identifies visual issues (misalignment, deformation, missing elements), fixes in parallel per subtree, and merges according to the component tree.

**Experiments**
- Research questions: RQ1 compares against baselines for visual consistency and structural similarity; RQ2 uses ablations to quantify module contributions; RQ3 uses user studies and case studies to assess code quality from developers’ perspectives.
- Dataset: 300 mobile UI designs across 5 scenarios, sourced from Figma communities and enterprise Sketch files.
- Baselines: specialized design-to-code methods (Prototype2Code, DeclarUI, etc.) and general multimodal models (GPT-4o, Claude-3.5, etc.).
- Metrics: visual metrics such as MSE, CLIP, SSIM; structural metrics such as TreeBLEU, TED, CM.
- Results: significantly outperforms baselines on both visual and structural metrics; ablations show the grouping chain and code self-optimization are critical; developer studies report better usability/readability/maintainability with less modification time and improved visual fidelity and responsiveness.
- Limitations: potential threats to internal validity.

### II. Intersection Gaps (Intersection Gaps)

By cross-comparing the 10 paradigms above, we can extract three macro-level contradictions that remain unresolved in the “intelligent health interaction UI” space:
1. **The Latency vs. Generative Freedom Trade-off**  
   Existing work (e.g., paradigms 1, 6, 9) tries to make LLMs both the “reasoning brain” and the “front-end coder.” In medical chat, latency is highly sensitive. Forcing the model to emit long and fragile HTML/CSS inevitably causes 5–10 seconds of unacceptable delay in IM-like real-time settings.
2. **Misalignment of Textual Guardrails and Visual Rendering Safety**  
   Guardrail systems such as NeMo Guardrails (paradigm 7) can prevent unsafe text (e.g., toxic medical advice). However, the community largely ignores **visual guardrails**. Even if the text is correct, a hallucinated UI can still be deadly (e.g., placing emergency phone numbers inside a deeply nested accordion requiring multiple scrolls).
3. **Disconnect between Agentic Depth and Engineering Robustness**  
   While ChatDev (paradigm 8) shows multi-agent collaboration can improve code quality, its non-deterministic conversational loops make it hard to deploy in consumer-facing systems. There is still a need for a lightweight graph-based state machine with strict data constraints to balance “self-correction” with deterministic system responses.

### III. Wabi C: Academic and Engineering Superiority

- **Semantic Dimensionality Reduction: From “Syntax Compiler” to “Structured Data Filler” (Semantic Dimensionality Reduction)**  
  Wabi C fundamentally differs from Design2Code or the Vercel v0 paradigm. By introducing strongly typed dataclasses in plan.py, the LLM is stripped of the ability to write front-end code and reduced to a pure “semantic extractor.” This decoupling not only avoids CSS conflicts but is also the core reason Wabi C can **reduce inference latency by 48% and token cost by over 50%** in experiments.
- **Deterministic Short-Circuiting: Medical-Grade Dual-Track Visual Guardrails (Deterministic Dual-Track Visual Guardrails)**  
  To address the pain points of paradigms 7 and 5, Wabi C introduces a state-graph-based bypass mechanism in template.py. When high-risk intents such as depression or emergency are detected, the system short-circuits the generative flow and forces a clinically validated static HTML template. This reconciles “adaptive flexibility for everyday nutrition Q&A” with “zero-hallucination absolute safety in crisis.”
- **Lightweight Self-Healing Loop: Eliminating Hidden Technical Debt (Lightweight Self-Healing Graph Loop)**  
  Unlike ChatDev’s long dialogues, Wabi C’s Checker node provides an engineering-lightweight self-healing approach. By validating JSON schema correctness and triggering bounded retries on failure, it removes hidden technical debt in generative UIs and maintains a success rate above 98%.

### IV. WABI C: Future Work / Next Steps (Future Work / Next Steps)

**1. Dynamic Component Schema Retrieval via RAG (Dynamic Component Retrieval via RAG)**
- Inspiration: LayoutPrompter (Paradigm 9) & GUIDE (Paradigm 2).
- Improvement: currently Wabi C hard-codes schemas for 28 components into a single system prompt, which is token-heavy and restricts library scaling. A lightweight vector retrieval layer could dynamically fetch the top-10 most relevant component schemas for a given user_input and feed them to the Planner, enabling an unbounded component library.

**2. RLHF for Visual Density Alignment (RLHF for Visual Density Alignment)**
- Inspiration: CrowdGenUI (Paradigm 3) & HumAIne (Paradigm 4).
- Improvement: addresses “severe redundancy and overly high information density.” Future work could collect implicit feedback (time-on-screen, card-collapse CTR, preferred components) and train a lightweight preference model. For elderly users, the Planner favors single-column large-text components; for younger power users, it generates higher-density dashboards and charts.

**3. Benchmarking Across Models/Parameters and Metric Calibration (Benchmarking & Metric Calibration)**
- Improvement: systematically evaluate different base models and key parameters (temperature, top-p, max output length, retry limits, etc.), building reproducible multi-dimensional benchmarks across “quality–latency–cost–safety.”
- Metrics: beyond visual/structural metrics, add task completion rate, visibility of critical safety information (e.g., disclaimers visible above the fold), WCAG violation rate, and human usability ratings; version and revisit metric weights according to product goals.

**4. Static Auditing for Visual Accessibility & Compliance (Static Auditing for Visual Accessibility & Compliance)**
- Inspiration: Rule-based AUI (Paradigm 5) & Semantic Guardrails (Paradigm 7).
- Improvement: extend Checker beyond JSON validation to rule-based front-end static analysis before HTML rendering, such as WCAG contrast checks and enforcing a “Disclaimer” node, broadening “medical safety” into “visual accessibility safety.”
