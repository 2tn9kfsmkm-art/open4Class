"""data.json 的最简包装：属性读写即文件读写。

注意：这里的写失败**不能**让程序起不来。打包后没有控制台，
一旦抛异常，双击就是"没反应"，用户完全看不到原因。
"""

import json
import os


class JsonDataModel:
    def __init__(self, origin: str):
        self.origin = origin
        self.update()

    def __getattribute__(self, name: str):
        if name in ['origin', 'data', 'update', '_read', '_write']:
            return super().__getattribute__(name)
        return self.data[name]

    def __setattr__(self, name, value):
        if name == 'origin' or name == 'data':
            super().__setattr__(name, value)
        else:
            self.update(**{name: value})

    def update(self, **kwargs):
        if len(kwargs):
            self.data.update(kwargs)
            self._write()
        else:
            self.data = self._read()

    def _read(self) -> dict:
        try:
            with open(self.origin, 'r', encoding='utf-8-sig') as f:
                payload = json.load(f)
            return payload if isinstance(payload, dict) else {}
        except Exception:                        # noqa: BLE001
            return {}

    def _write(self) -> bool:
        """写失败只记日志，不抛异常（文件被占用、目录只读都可能发生）。"""
        try:
            with open(self.origin, 'w', encoding='utf-8') as f:
                json.dump(self.data, f)
            return True
        except Exception as e:                   # noqa: BLE001
            try:
                from services.diag import log
                log('json', f'写入失败 {os.path.basename(self.origin)}: {e!r}')
            except Exception:                    # noqa: BLE001
                pass
            return False
