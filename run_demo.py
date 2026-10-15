"""一键离线全链路演示：python run_demo.py --address 繁裕小区"""
from __future__ import annotations

import argparse
import json

from pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="AI4Climate Track05 原型离线演示")
    parser.add_argument("--address", default="繁裕小区", help="小区名关键字")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    parser.add_argument("--replay", action="store_true",
                        help="历史复盘模式：贝碧嘉2024真实路径+ERA5降水（目标切到临港书院社区）")
    args = parser.parse_args()

    if args.replay:
        result = run_pipeline("书院社区", typhoon_mode="replay", replay_case="bebinca",
                              rain_start="2024-09-14", rain_end="2024-09-17")
    else:
        result = run_pipeline(args.address)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    c, risk, g = result["community"], result["risk"], result["guidance"]
    print("=" * 48)
    print(f"小区：{c['name']}")
    print(f"地址：{c['address']}")
    print(f"综合风险：{risk['score']} 分 → 等级【{risk['level']}】（台风 {risk['typhoon_name']}）")
    print("-" * 48)
    print("分项评分（透明规则）：")
    for f in risk["factors"]:
        print(f"  · {f['name']}：{f['score']}/{f['max']} —— {f['reason']}")
    print("-" * 48)
    print(f"居民行动指引 {g['header']}")
    if g["mode"] == "llm":
        print(g["text"])
    else:
        for tl, title in (("72h", "未来72小时"), ("24h", "未来24小时"), ("6h", "未来6小时")):
            print(f"\n【{title}】")
            for i, item in enumerate(g["timelines"][tl], 1):
                print(f"  {i}. {item}")
    print("=" * 48)
    print(f"数据来源：台风={result['data_sources']['typhoon']} / 降雨={result['data_sources']['rainfall']}")


if __name__ == "__main__":
    main()
