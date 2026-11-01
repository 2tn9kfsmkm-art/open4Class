import os
import sys
import shutil
import copy
from datetime import datetime

from pandas import DataFrame

from tools.PandasQModel import PandasQItemModel
from core.weekday import weekday2word

APP_NAME = 'ClassManager'   # 换成你的应用名，会作为 %APPDATA%\ClassManager 的目录名

def _is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False) or '__compiled__' in globals())

def _resource_base() -> str:
    """只读资源根：onefile→_MEIPASS 临时目录；standalone→exe 旁边；开发→项目根"""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS + os.sep
    if _is_frozen():
        return os.path.dirname(sys.executable) + os.sep
    return os.path.dirname(os.path.abspath(__file__)) + os.sep

def _data_base() -> str:
    """可写数据根：永远在系统用户目录，持久化、不受 exe 位置影响"""
    if os.name == 'nt':          # Windows → %APPDATA%\ClassManager\
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
        return os.path.join(base, APP_NAME) + os.sep
    if sys.platform == 'darwin': # macOS → ~/Library/Application Support/ClassManager/
        return os.path.expanduser(f'~/Library/Application Support/{APP_NAME}/')
    # Linux → $XDG_DATA_HOME/ClassManager/ 或 ~/.local/share/ClassManager/
    base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return os.path.join(base, APP_NAME) + os.sep

RESOURCE_BASE = _resource_base()
DATA_BASE = _data_base()

# ---------- 只读资源（打包进 exe）----------
QSS_DIR      = RESOURCE_BASE + 'stylesheet' + os.sep
RESOURCE_DIR = RESOURCE_BASE + 'resources'  + os.sep
MSG_RES_BASE = RESOURCE_BASE + 'messages'   + os.sep


# ---------- 目录布局迁移：旧版 datas/ + 根目录 db → 统一收进 data/ ----------
def _migrate_layout() -> None:
    """把旧版的数据文件搬进 data/，然后删掉 datas/。

    旧：ClassManager/{classmanager.db, datas/settings.json, datas/*.csv}
    新：ClassManager/data/{classmanager.db, settings.json, data.json}
    """
    old_datas = DATA_BASE + 'datas' + os.sep
    new_dir = DATA_BASE + 'data' + os.sep
    old_db = DATA_BASE + 'classmanager.db'

    if not os.path.isdir(old_datas) and not os.path.exists(old_db):
        return

    os.makedirs(new_dir, exist_ok=True)

    # 先留一份副本，搬完再删 datas/，出问题还能找回
    try:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = DATA_BASE + 'backup' + os.sep + f'layout-{stamp}'
        if os.path.isdir(old_datas):
            shutil.copytree(old_datas, backup_dir + os.sep + 'datas',
                            dirs_exist_ok=True)
    except Exception as e:                      # noqa: BLE001
        print(f'[config] 迁移前备份失败（继续）: {e!r}')

    # 1) 根目录下的数据库文件
    for name in ('classmanager.db', 'classmanager.db-wal',
                 'classmanager.db-shm', 'classmanager.db.migrated_at'):
        src = DATA_BASE + name
        if os.path.exists(src) and not os.path.exists(new_dir + name):
            try:
                shutil.move(src, new_dir + name)
            except OSError as e:
                print(f'[config] 移动 {name} 失败: {e!r}')

    # 2) datas/ 里留下的 json（settings.json / data.json）
    if os.path.isdir(old_datas):
        for name in os.listdir(old_datas):
            if name.lower().endswith('.json'):
                src = old_datas + name
                dst = new_dir + name
                if not os.path.exists(dst):
                    try:
                        shutil.move(src, dst)
                    except OSError as e:
                        print(f'[config] 移动 {name} 失败: {e!r}')
        shutil.rmtree(old_datas, ignore_errors=True)


_migrate_layout()

# ---------- 可写数据（统一放在 data/）----------
FILE_DIR    = DATA_BASE + 'data' + os.sep
DATA_DIR    = FILE_DIR                      # 语义更清楚的名字
MESSAGE_DIR = DATA_BASE + 'messages' + os.sep
MESSAGE_MAIN_PATH  = MESSAGE_DIR + 'message.html'
MESSAGE_IMAGE_DIR  = MESSAGE_DIR + 'images' + os.sep
SETTINGS_JSON_PATH = FILE_DIR + 'settings.json'
DB_PATH = FILE_DIR + 'classmanager.db'

ENCODING = 'utf-8'
CLASS_WEEKDAYS = ['周一', '周二', '周三', '周四', '周五']
DEFAULT_CLASS_ROWS = 8
MAX_THREAD_COUNT = 4
ONDUTY_JOBS = ['扫', '擦', '排', '理']

# ---------- 创建可写目录（绝不创建只读目录）----------
for _dir in (FILE_DIR, MESSAGE_DIR, MESSAGE_IMAGE_DIR):
    os.makedirs(_dir, exist_ok=True)

# ---------- messages/ 首次初始化：从只读资源复制 ----------
def _init_messages():
    src_html = MSG_RES_BASE + os.sep + 'message.html'
    dst_html = MESSAGE_DIR + 'message.html'
    if not os.path.exists(dst_html) and os.path.exists(src_html):
        shutil.copyfile(src_html, dst_html)

    src_img = MSG_RES_BASE + os.sep + 'images'
    dst_img = MESSAGE_DIR + 'images'
    if os.path.isdir(src_img):
        for name in os.listdir(src_img):
            s = os.path.join(src_img, name)
            d = os.path.join(dst_img, name)
            if os.path.isfile(s) and not os.path.exists(d):
                shutil.copyfile(s, d)

_init_messages()

# ---------- 下面保持原样 ----------
ERROR_MODEL = PandasQItemModel(['加载出错'])

basedate = datetime(2025, 3, 7)
today = datetime.now()
str_date = today.strftime('%Y-%m-%d')
weekday = today.weekday()
wordday = weekday2word(weekday)

classday = 0
class_wordday = wordday
import json

SETTINGS_JSON_PATH = FILE_DIR + 'settings.json'

DEFAULT_COUNTDOWNS = [
    {'label': '高考', 'date': '2027-06-07'},
    {'label': '春考', 'date': '2027-01-02'},
]

# 作息时间表：悬浮窗靠它判断"第几节 / 课间"。可在 settings.json 里改。
DEFAULT_LESSON_TIMES = [
    ["07:40", "08:20"], ["08:30", "09:10"], ["09:20", "10:00"],
    ["10:10", "10:50"], ["11:00", "11:40"], ["13:00", "13:40"],
    ["13:50", "14:30"], ["14:40", "15:20"], ["15:30", "16:10"],
    ["16:20", "17:00"],
]

DEFAULT_USER_SETTINGS = {
    'class_short_name': '高三八班',
    'class_full_name': '高三（8）班',
    'school_name': '市西中学',
    'onduty_jobs': ['扫', '擦', '排', '理'],
    'onduty_daily_template': ['扫', '扫', '擦', '排', '理'],
    'lesson_times': DEFAULT_LESSON_TIMES,
    'countdowns': DEFAULT_COUNTDOWNS,
}


def load_user_settings() -> dict:
    if not os.path.exists(SETTINGS_JSON_PATH):
        with open(SETTINGS_JSON_PATH, 'w', encoding=ENCODING) as f:
            json.dump(DEFAULT_USER_SETTINGS, f, ensure_ascii=False, indent=2)
        return copy.deepcopy(DEFAULT_USER_SETTINGS)
    try:
        with open(SETTINGS_JSON_PATH, 'r', encoding=ENCODING) as f:
            data = json.load(f)
    except Exception:
        return copy.deepcopy(DEFAULT_USER_SETTINGS)
    merged = copy.deepcopy(DEFAULT_USER_SETTINGS)
    if isinstance(data, dict):
        merged.update(data)
    return merged


def save_user_settings(data: dict) -> None:
    with open(SETTINGS_JSON_PATH, 'w', encoding=ENCODING) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_onduty_jobs() -> list:
    return load_user_settings()['onduty_jobs']


def get_onduty_daily_template() -> list:
    return load_user_settings()['onduty_daily_template']
