# 社区台风-内涝韧性指引 · AI4Climate Track05 原型

一句话：输入小区名，系统融合台风路径预报、降雨预报、地形内涝风险，输出复合风险评分 + AI 生成的居民可行动应急指引（72h / 24h / 6h 三条时间线）。

## 本地运行（3 步）

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 方式一：命令行一键演示（纯离线）
python run_demo.py --address 繁裕小区
# 方式二：Web demo
uvicorn app.main:app --host 127.0.0.1 --port 8000
# 浏览器打开 http://127.0.0.1:8000
```

## 架构

```
                ┌──────────────┐
  地址 ────────▶│  pipeline.py │  全链路编排
                └──────┬───────┘
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
 ┌────────────┐ ┌──────────┐ ┌────────────┐
 │data_ingest │ │risk_engine│ │ guidance   │
 │台风路径    │ │复合评分   │ │ 指引生成   │
 │降雨预报    │ │40+30+30   │ │ LLM优先    │
 │内涝底图    │ │规则透明   │ │ 无key降级  │
 └─────┬──────┘ └────┬─────┘ └─────┬──────┘
       │  mock回退    │ 可解释分项   │ 模板保底
       ▼             ▼              ▼
  ┌─────────────────────────────────────┐
  │ app/main.py (FastAPI) + 单页前端    │
  │ run_demo.py (CLI 离线演示)          │
  └─────────────────────────────────────┘
```

## 模块说明

- `data_ingest/`：台风路径 / 降雨预报 / 内涝底图接入。真实接口（中央气象台、Open-Meteo）以 TODO 占位，当前全部走 `data/mock/` 内置数据，保证评审离线可跑。
- `risk_engine/`：复合风险评分，台风接近度 40 分 + 降雨强度 30 分 + 地形内涝 30 分，规则显式可解释。
- `guidance/`：指引生成。配置 `AI4C_LLM_API_KEY`（OpenAI 兼容接口）则调 LLM；无 key 时用规则模板降级，离线也有完整输出。
  环境变量：`AI4C_LLM_API_KEY` / `AI4C_LLM_BASE_URL`（默认 https://api.openai.com/v1）/ `AI4C_LLM_MODEL`（默认 gpt-4o-mini）。
  已验证：商汤 SenseNova（`AI4C_LLM_BASE_URL=https://token.sensenova.cn/v1`，`AI4C_LLM_MODEL=sensenova-6.8-flash-lite`）、Qwen2.5-7B（SiliconFlow）、DeepSeek API。
- `app/`：FastAPI Web demo；`run_demo.py`：CLI 一键演示。

## AI 必不可少的论证

预报数据（路径、毫米数、风险等级）普通人看不懂、不会转成行动。AI 的任务是"翻译"：把技术性预报变成具体、分时、可执行的居民行动清单，这是规则模板写不好的部分（措辞、优先级、场景适配），也是 LLM 的核心价值。

## 评审离线说明

全链路默认走内置 mock 数据，无需联网、无需 key 即可看到完整流程：风险评分 → 分项解释 → 三条时间线指引。
