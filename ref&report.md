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


@Article{s22072625,
    AUTHOR = {Bin Sawad, Abdullah and Narayan, Bhuva and Alnefaie, Ahlam and Maqbool, Ashwaq and Mckie, Indra and Smith, Jemma and Yuksel, Berkan and Puthal, Deepak and Prasad, Mukesh and Kocaballi, A. Baki},
    TITLE = {A Systematic Review on Healthcare Artificial Intelligent Conversational Agents for Chronic Conditions},
    JOURNAL = {Sensors},
    VOLUME = {22},
    YEAR = {2022},
    NUMBER = {7},
    ARTICLE-NUMBER = {2625},
    URL = {https://www.mdpi.com/1424-8220/22/7/2625},
    PubMedID = {35408238},
    ISSN = {1424-8220},
    DOI = {10.3390/s22072625}
}

@article{https://doi.org/10.1002/wps.21352,
    author = {Hua, Yining and Siddals, Steve and Ma, Zilin and Galatzer-Levy, Isaac and Xia, Winna and Hau, Christine and Na, Hongbin and Flathers, Matthew and Linardon, Jake and Ayubcha, Cyrus and Torous, John},
    title = {Charting the evolution of artificial intelligence mental health chatbots from rule-based systems to large language models: a systematic review},
    journal = {World Psychiatry},
    volume = {24},
    number = {3},
    pages = {383-394},
    keywords = {Artificial intelligence, chatbots, rule-based systems, machine learning, large language models, foundational bench testing, pilot feasibility testing, clinical efficacy testing, mental health care},
    doi = {https://doi.org/10.1002/wps.21352},
    url = {https://onlinelibrary.wiley.com/doi/abs/10.1002/wps.21352},
    eprint = {https://onlinelibrary.wiley.com/doi/pdf/10.1002/wps.21352},
    year = {2025}
}

@article{LI2023104494,
    title = {Feasibility and effectiveness of artificial intelligence-driven conversational agents in healthcare interventions: A systematic review of randomized controlled trials},
    journal = {International Journal of Nursing Studies},
    volume = {143},
    pages = {104494},
    year = {2023},
    issn = {0020-7489},
    doi = {https://doi.org/10.1016/j.ijnurstu.2023.104494},
    url = {https://www.sciencedirect.com/science/article/pii/S0020748923000597},
    author = {Yan Li and Surui Liang and Bingqian Zhu and Xu Liu and Jing Li and Dapeng Chen and Jing Qin and Dan Bressington},
    keywords = {Artificial intelligence, Conversational agents, Healthcare, Systematic review, Randomized controlled trials}
}

@Article{info:doi/10.2196/69639,
    author="Feng, Yi
    and Hang, Yaming
    and Wu, Wenzhi
    and Song, Xiaohang
    and Xiao, Xiyao
    and Dong, Fangbai
    and Qiao, Zhihong",
    title="Effectiveness of AI-Driven Conversational Agents in Improving Mental Health Among Young People: Systematic Review and Meta-Analysis",
    journal="J Med Internet Res",
    year="2025",
    month="May",
    day="14",
    volume="27",
    pages="e69639",
    keywords="artificial intelligence; conversational agents; meta-analysis; mental health intervention; young people",
    issn="1438-8871",
    doi="10.2196/69639",
    url="https://www.jmir.org/2025/1/e69639",
    url="https://doi.org/10.2196/69639"
}

@article{10.1371/journal.pdig.0001201,
    doi = {10.1371/journal.pdig.0001201},
    author = {Feng, Shi AND Li, Xiufang (Leah) AND Wake, Alexandra Nicole},
    journal = {PLOS Digital Health},
    publisher = {Public Library of Science},
    title = {Engaging Artificial Intelligence (AI)-based chatbots in digital health: A systematic review},
    year = {2026},
    month = {02},
    volume = {5},
    url = {https://doi.org/10.1371/journal.pdig.0001201},
    pages = {1-17},
    number = {2}
}

@misc{caetano2025agenticworkflowsconversationalhumanai,
    title={Agentic Workflows for Conversational Human-AI Interaction Design}, 
    author={Arthur Caetano and Kavya Verma and Atieh Taheri and Radha Kumaran and Zichen Chen and Jiaao Chen and Tobias Höllerer and Misha Sra},
    year={2025},
    eprint={2501.18002},
    archivePrefix={arXiv},
    primaryClass={cs.HC},
    url={https://arxiv.org/abs/2501.18002}
}

@misc{evolution2025conversational,
    title={The evolution of conversational AI: Enter the era of agentic AI systems},
    author={LivePerson},
    year={2025},
    url={https://www.liveperson.com/blog/evolution-of-conversational-ai/}
}

@misc{kolthoff2024zeroshotpromptingapproachesllmbased,
    title={Zero-Shot Prompting Approaches for LLM-based Graphical User Interface Generation}, 
    author={Kristian Kolthoff and Felix Kretzer and Lennart Fiebig and Christian Bartelt and Alexander Maedche and Simone Paolo Ponzetto},
    year={2024},
    eprint={2412.11328},
    archivePrefix={arXiv},
    primaryClass={cs.SE},
    url={https://arxiv.org/abs/2412.11328}
}

@misc{kolthoff2025guidellmdrivenguigeneration,
    title={GUIDE: LLM-Driven GUI Generation Decomposition for Automated Prototyping}, 
    author={Kristian Kolthoff and Felix Kretzer and Christian Bartelt and Alexander Maedche and Simone Paolo Ponzetto},
    year={2025},
    eprint={2502.21068},
    archivePrefix={arXiv},
    primaryClass={cs.SE},
    url={https://arxiv.org/abs/2502.21068}
}

@misc{liu2025crowdgenuialigningllmbasedui,
    title={CrowdGenUI: Aligning LLM-Based UI Generation with Crowdsourced User Preferences}, 
    author={Yimeng Liu and Misha Sra and Chang Xiao},
    year={2025},
    eprint={2411.03477},
    archivePrefix={arXiv},
    primaryClass={cs.HC},
    url={https://arxiv.org/abs/2411.03477}
}

@misc{langgraph2024framework,
    title={LangGraph: Agent Orchestration Framework for Reliable AI Agents},
    author={LangChain},
    year={2024},
    url={https://www.langchain.com/langgraph}
}

@INPROCEEDINGS{10554790,
    author={Wang, Wei and Khalajzadeh, Hourieh and Grundy, John and Madugalla, Anuradha and Obie, Humphrey O.},
    booktitle={2024 IEEE/ACM 46th International Conference on Software Engineering: Software Engineering in Society (ICSE-SEIS)}, 
    title={Adaptive User Interfaces for Software Supporting Chronic Disease}, 
    year={2024},
    volume={},
    number={},
    pages={118-129},
    keywords={Surveys;Human computer interaction;Prototypes;User experience;Software;Usability;Interviews;adaptive user interface;AUI;chronic disease;mHealth applications},
    doi={}
}

@article{10.1001/jamanetworkopen.2024.57879,
    author = {Huo, Bright and Boyle, Amy and Marfo, Nana and Tangamornsuksan, Wimonchat and Steen, Jeremy P. and McKechnie, Tyler and Lee, Yung and Mayol, Julio and Antoniou, Stavros A. and Thirunavukarasu, Arun James and Sanger, Stephanie and Ramji, Karim and Guyatt, Gordon},
    title = {Large Language Models for Chatbot Health Advice Studies: A Systematic Review},
    journal = {JAMA Network Open},
    volume = {8},
    number = {2},
    pages = {e2457879-e2457879},
    year = {2025},
    month = {02},
    issn = {2574-3805},
    doi = {10.1001/jamanetworkopen.2024.57879},
    url = {https://doi.org/10.1001/jamanetworkopen.2024.57879},
    eprint = {https://jamanetwork.com/journals/jamanetworkopen/articlepdf/2829839/huo_2025_oi_241622_1742229230.09331.pdf}
}

@misc{makridis2025humainechatbotrealtimepersonalizedconversational,
    title={HumAIne-Chatbot: Real-Time Personalized Conversational AI via Reinforcement Learning}, 
    author={Georgios Makridis and George Fragiadakis and Jorge Oliveira and Tomaz Saraiva and Philip Mavrepis and Georgios Fatouros and Dimosthenis Kyriazis},
    year={2025},
    eprint={2509.04303},
    archivePrefix={arXiv},
    primaryClass={cs.HC},
    url={https://arxiv.org/abs/2509.04303}
}

@ARTICLE{10.3389/frai.2025.1623339,
    AUTHOR={Imrie, Fergus  and Rauba, Paulius  and van der Schaar, Mihaela },        
    TITLE={Redefining digital health interfaces with large language models},      
    JOURNAL={Frontiers in Artificial Intelligence},    
    VOLUME={Volume 8 - 2025},
    YEAR={2025},
    URL={https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1623339},
    DOI={10.3389/frai.2025.1623339},
    ISSN={2624-8212}
}

@manual{playwright2020automation,
    title={Playwright: Reliable End-to-End Testing and Browser Automation},
    author={Microsoft},
    year={2020},
    url={https://playwright.dev}
}

@manual{aws2023bedrock,
    title={Amazon Bedrock: Build and Scale Generative AI Applications},
    author={Amazon Web Services},
    year={2023},
    url={https://aws.amazon.com/bedrock}
}

@manual{alibaba2023dashscope,
    title={DashScope API Documentation},
    author={Alibaba Cloud},
    year={2023},
    url={https://dashscope.aliyuncs.com}
}

@manual{fastapi2019documentation,
    title={FastAPI Documentation: Modern Fast Web APIs},
    author={Tiangolo, Sebastián},
    year={2019},
    url={https://fastapi.tiangolo.com}
}

@article{python2022performance,
    title={Python 3.11 Performance Improvements: A Comprehensive Analysis},
    author={Python Software Foundation},
    journal={Python Developer Guide},
    year={2022},
    url={https://docs.python.org/3/whatsnew/3.11.html}
}
@inproceedings{NIPS2015_86df7dcf,
    author = {Sculley, D. and Holt, Gary and Golovin, Daniel and Davydov, Eugene and Phillips, Todd and Ebner, Dietmar and Chaudhary, Vinay and Young, Michael and Crespo, Jean-Fran\c{c}ois and Dennison, Dan},
    booktitle = {Advances in Neural Information Processing Systems},
    editor = {C. Cortes and N. Lawrence and D. Lee and M. Sugiyama and R. Garnett},
    pages = {},
    publisher = {Curran Associates, Inc.},
    title = {Hidden Technical Debt in Machine Learning Systems},
    url = {https://proceedings.neurips.cc/paper_files/paper/2015/file/86df7dcfd896fcaf2674f757a2463eba-Paper.pdf},
    volume = {28},
    year = {2015}
}

@misc{greshake2023youvesignedforcompromising,
    title={Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection}, 
    author={Kai Greshake and Sahar Abdelnabi and Shailesh Mishra and Christoph Endres and Thorsten Holz and Mario Fritz},
    year={2023},
    eprint={2302.12173},
    archivePrefix={arXiv},
    primaryClass={cs.CR},
    url={https://arxiv.org/abs/2302.12173}, 
}

@manual{python_asyncio_docs,
  title={asyncio --- Asynchronous I/O},
  author={{Python Software Foundation}},
  year={2024},
  organization={Python Documentation},
  edition={Python 3.11},
  url={https://docs.python.org/3/library/asyncio.html},
  note={Accessed: 2026-03-05}
}

@manual{owasp2023apisecurity,
    title={OWASP API Security Top 10},
    author={OWASP Foundation},
    year={2023},
    url={https://owasp.org/www-project-api-security}
}
