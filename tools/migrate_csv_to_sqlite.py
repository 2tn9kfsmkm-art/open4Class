"""把 datas/ 下的 CSV 一次性迁移进 SQLite。

用法::

    python -m tools.migrate_csv_to_sqlite --csv-dir <数据目录> --db <数据库路径> [--dry-run]

约定（HANDOFF §6.4）：
- 缺失的文件跳过并打印警告，不中断
- 迁移不删除 CSV，保留供回滚与人工核对
- ``--dry-run`` 只解析并打印统计，不写库
- 成功后写 ``<db>.migrated_at``，内含时间戳与行数
"""

import argparse
import json
import os
import sys
from datetime import date, datetime

import pandas as pd

from config import CLASS_WEEKDAYS
from core.models import AppEntry, OndutyEntry


def _read_csv(path: str, **kwargs):
    if not os.path.exists(path):
        print(f'  [跳过] 找不到 {os.path.basename(path)}')
        return None
    try:
        return pd.read_csv(path, encoding='utf-8', **kwargs)
    except Exception as e:                      # noqa: BLE001
        print(f'  [跳过] {os.path.basename(path)} 读取失败: {e!r}')
        return None


def _split_cell(cell: str) -> tuple[str, str]:
    """把 "{姓名} {职务}" 拆开；姓名内部允许有空格，按最后一个空格切。"""
    text = str(cell).strip()
    if not text:
        return '', ''
    parts = text.rsplit(None, 1)
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], parts[1]


def read_csv_dir(csv_dir: str) -> dict:
    """解析整个数据目录，返回待写入的结构（不碰数据库）。

    Returns:
        {
          'students': [姓名...],
          'courses': [课程...],
          'template': [(weekday, lesson_index, course_name)...],
          'onduty': [OndutyEntry...],
          'apps': [AppEntry...],
          'kv': {'user_settings': {...}, 'last_login': 'YYYYMMDD'},   # 可能缺项
        }
    """
    from ondutySpawn import read_names

    result = {'students': [], 'courses': [], 'template': [],
              'onduty': [], 'apps': [], 'kv': {}}

    # ---- 名单 ----
    path = os.path.join(csv_dir, '名单.csv')
    if os.path.exists(path):
        try:
            result['students'] = read_names(path)
        except Exception as e:                  # noqa: BLE001
            print(f'  [跳过] 名单.csv 解析失败: {e!r}')
    else:
        print('  [跳过] 找不到 名单.csv')

    # ---- 课程单 ----
    df = _read_csv(os.path.join(csv_dir, '课程单.csv'))
    if df is not None and df.shape[1]:
        result['courses'] = [str(v).strip() for v in df.iloc[:, 0].tolist()
                             if str(v).strip() and str(v) != 'nan']

    # ---- 周模板课表 ----
    df = _read_csv(os.path.join(csv_dir, '课表.csv'))
    if df is not None:
        columns = [str(c).strip() for c in df.columns]
        order = CLASS_WEEKDAYS if all(d in columns for d in CLASS_WEEKDAYS) else columns[:5]
        for weekday, col in enumerate(order, start=1):
            if col not in df.columns:
                continue
            for i, value in enumerate(df[col].tolist(), start=1):
                text = '' if value is None or pd.isna(value) else str(value).strip()
                if text:
                    result['template'].append((weekday, i, text))

    # ---- 值日 ----
    df = _read_csv(os.path.join(csv_dir, '未来值日.csv'))
    if df is not None:
        for col in df.columns:
            try:
                day = date.fromisoformat(str(col).strip())
            except ValueError:
                continue
            for slot, cell in enumerate(df[col].tolist()):
                if slot >= 5 or cell is None or pd.isna(cell):
                    continue
                student, job = _split_cell(cell)
                if student:
                    result['onduty'].append(
                        OndutyEntry(day, slot, student, job))

    # ---- 应用链接 ----
    df = _read_csv(os.path.join(csv_dir, '应用路径.csv'))
    if df is not None and df.shape[1] >= 2:
        name_col, path_col = df.columns[0], df.columns[1]
        for _, row in df.iterrows():
            name = str(row[name_col]).strip()
            target = str(row[path_col]).strip()
            if name and target and target != 'nan':
                result['apps'].append(AppEntry(name, target))

    # ---- 键值 ----
    settings_path = os.path.join(csv_dir, 'settings.json')
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                result['kv']['user_settings'] = json.load(f)
        except Exception as e:                  # noqa: BLE001
            print(f'  [跳过] settings.json 解析失败: {e!r}')
    else:
        print('  [跳过] 找不到 settings.json')

    data_path = os.path.join(csv_dir, 'data.json')
    if os.path.exists(data_path):
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            # data.json 目前只有 last_login，压成标量存 kv['last_login']
            result['kv']['last_login'] = (
                payload.get('last_login') if isinstance(payload, dict) else payload)
        except Exception as e:                  # noqa: BLE001
            print(f'  [跳过] data.json 解析失败: {e!r}')
    else:
        print('  [跳过] 找不到 data.json')

    return result


def _print_stats(data: dict) -> None:
    days = len({e.date for e in data['onduty']})
    print(f"  [1/6] 名单 → students：{len(data['students'])} 行")
    print(f"  [2/6] 课程单 → courses：{len(data['courses'])} 行")
    print(f"  [3/6] 课表 → classlist_template：{len(data['template'])} 个单元格")
    print(f"  [4/6] 未来值日 → onduty：{days} 天 × 最多 5 行 = {len(data['onduty'])} 行")
    print(f"  [5/6] 应用路径 → apps：{len(data['apps'])} 行")
    print(f"  [6/6] settings/data.json → kv：{len(data['kv'])} 行")


def migrate(csv_dir: str, db_path: str, dry_run: bool = False) -> dict:
    """执行迁移，返回统计字典。"""
    print(f'扫描 {csv_dir}')
    data = read_csv_dir(csv_dir)
    _print_stats(data)

    stats = {
        'students': len(data['students']),
        'courses': len(data['courses']),
        'template': len(data['template']),
        'onduty': len(data['onduty']),
        'apps': len(data['apps']),
        'kv': len(data['kv']),
    }

    if dry_run:
        print('--dry-run：未写入数据库')
        return stats

    from data.sqlite_repo import SqliteRepository

    repo = SqliteRepository(db_path)
    try:
        repo.replace_students(data['students'])
        repo.replace_courses(data['courses'])
        repo.save_classlist_template(data['template'])
        repo.replace_onduty(data['onduty'])
        repo.replace_apps(data['apps'])
        for key, value in data['kv'].items():
            repo.set_kv(key, value)
    finally:
        repo.close()

    marker = db_path + '.migrated_at'
    with open(marker, 'w', encoding='utf-8') as f:
        json.dump({
            'at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': os.path.abspath(csv_dir),
            **stats,
        }, f, ensure_ascii=False, indent=2)

    print(f'完成。数据库：{db_path}')
    print(f'标记文件：{marker}')
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='把 CSV 数据迁移进 SQLite')
    parser.add_argument('--csv-dir', required=True, help='存放 CSV 的数据目录')
    parser.add_argument('--db', required=True, help='目标 SQLite 文件')
    parser.add_argument('--dry-run', action='store_true', help='只统计不写库')
    args = parser.parse_args(argv)

    if not os.path.isdir(args.csv_dir):
        print(f'目录不存在：{args.csv_dir}')
        return 2

    migrate(args.csv_dir, args.db, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
