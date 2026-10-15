"""数据接入基类：统一拉取接口 + mock 回退，保证离线可跑。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# mock 数据目录：data_ingest/../data/mock
MOCK_DIR = Path(__file__).resolve().parent.parent / "data" / "mock"


@dataclass
class FetchResult:
    data: dict
    source: str  # "live" 真实接口 / "mock" 内置模拟数据
    note: str = ""


class BaseFetcher:
    """子类只需实现 _fetch_live；真实接口不可用时自动回退 mock。"""

    mock_file: str = ""

    def fetch(self, **kwargs) -> FetchResult:
        try:
            data = self._fetch_live(**kwargs)
            return FetchResult(data=data, source="live")
        except Exception as e:  # 真实接口不可用时静默回退，保证 demo 不中断
            data = self._load_mock()
            return FetchResult(
                data=data, source="mock",
                note=f"真实接口不可用（{e}），已回退内置 mock 数据",
            )

    def _fetch_live(self, **kwargs) -> dict:
        raise NotImplementedError("子类实现真实接口接入")

    def _load_mock(self) -> dict:
        path = MOCK_DIR / self.mock_file
        return json.loads(path.read_text(encoding="utf-8"))
