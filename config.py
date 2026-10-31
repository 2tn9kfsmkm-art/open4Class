import os
import sys
import shutil
import copy
from datetime import datetime

from pandas import DataFrame

from tools.PandasQModel import PandasQItemModel
from tools.num2word import weekday2word

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

# ---------- 可写数据（放 exe 旁边）----------
FILE_DIR    = DATA_BASE + 'datas' + os.sep
BUFFER_DIR  = FILE_DIR + 'loadings' + os.sep
MESSAGE_DIR = DATA_BASE + 'messages' + os.sep
MESSAGE_MAIN_PATH  = MESSAGE_DIR + 'message.html'
MESSAGE_IMAGE_DIR  = MESSAGE_DIR + 'images' + os.sep
SETTINGS_JSON_PATH = FILE_DIR + 'settings.json'

ENCODING = 'utf-8'
MAX_THREAD_COUNT = 4
ONDUTY_JOBS = ['扫', '擦', '排', '理']

# ---------- 创建可写目录（绝不创建只读目录）----------
for _dir in (FILE_DIR, BUFFER_DIR, MESSAGE_DIR, MESSAGE_IMAGE_DIR):
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

# ---------- 初始数据文件：从只读资源复制（课表/课程单必须存在）----------
def _init_datas():
    """把只读资源中 datas 下的初始 csv 复制到可写目录（仅当目标不存在）。"""
    src_dir = RESOURCE_BASE + 'datas' + os.sep
    if not os.path.isdir(src_dir):
        return
    for name in os.listdir(src_dir):
        s = os.path.join(src_dir, name)
        d = os.path.join(FILE_DIR, name)
        if os.path.isfile(s) and not os.path.exists(d):
            shutil.copyfile(s, d)

_init_datas()

# ---------- 最小数据集：没有 datas/ 时也要能启动 ----------
CLASS_WEEKDAYS = ['周一', '周二', '周三', '周四', '周五']
DEFAULT_CLASS_ROWS = 8


def ensure_minimal_data(target_dir: str = '') -> list:
    """补齐"缺了就启动不了"的数据文件，返回本次新建的文件名列表。

    分发包里不带 datas/ 时，课表.csv 与 课程单.csv 会缺失；而
    classlist_chain.load() 直接 q_read_csv()，文件不在就抛 FileNotFoundError，
    一路冲到 Main.__init__，表现为双击闪退。这里补出空骨架。

    其余文件各有兜底，不在这里处理：
    - 名单.csv / 未来值日.csv / 应用路径.csv：对应的 Chain.load 会新建
    - settings.json：load_user_settings 会新建
    - data.json：Main.ensure_data_json 会新建

    Args:
        target_dir: 目标目录，默认 FILE_DIR（测试时可传临时目录）。
    Returns:
        本次新建的文件名列表；已存在的不覆盖，重复调用幂等。
    """
    directory = target_dir or FILE_DIR
    os.makedirs(directory, exist_ok=True)
    created = []

    classlist = os.path.join(directory, '课表.csv')
    if not os.path.exists(classlist):
        DataFrame(
            index=range(DEFAULT_CLASS_ROWS), columns=CLASS_WEEKDAYS,
        ).to_csv(classlist, index=False, encoding=ENCODING)
        created.append('课表.csv')

    courses = os.path.join(directory, '课程单.csv')
    if not os.path.exists(courses):
        DataFrame(columns=['课程']).to_csv(
            courses, index=False, encoding=ENCODING)
        created.append('课程单.csv')

    return created


ensure_minimal_data()

# ---------- 下面保持原样 ----------
ERROR_MODEL = PandasQItemModel(['加载出错'])

basedate = datetime(2025, 3, 7)
today = datetime.now()
str_date = today.strftime('%Y-%m-%d')
weekday = today.weekday()
wordday = weekday2word(weekday)

onduty_today_path = BUFFER_DIR + str_date + ' onduty.csv'
classday = 0
class_wordday = wordday
classlist_path = BUFFER_DIR + str_date + ' classlist.csv'

import json

SETTINGS_JSON_PATH = FILE_DIR + 'settings.json'

DEFAULT_USER_SETTINGS = {
    'class_short_name': '高三八班',
    'class_full_name': '高三（8）班',
    'school_name': '市西中学',
    'onduty_jobs': ['扫', '擦', '排', '理'],
    'onduty_daily_template': ['扫', '扫', '擦', '排', '理'],
}


def load_user_settings() -> dict:
    """读取 settings.json；不存在时自动生成默认值。字段缺失用默认值补齐。"""
    if not os.path.exists(SETTINGS_JSON_PATH):
        with open(SETTINGS_JSON_PATH, 'w', encoding=ENCODING) as f:
            json.dump(DEFAULT_USER_SETTINGS, f, ensure_ascii=False, indent=2)
        return dict(DEFAULT_USER_SETTINGS)
    try:
        with open(SETTINGS_JSON_PATH, 'r', encoding=ENCODING) as f:
            data = json.load(f)
    except Exception:
        return dict(DEFAULT_USER_SETTINGS)
    merged = dict(DEFAULT_USER_SETTINGS)
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

DEFAULT_COUNTDOWNS = [
    {'label': '高考', 'date': '2027-06-07'},
    {'label': '春考', 'date': '2027-01-02'},
]

DEFAULT_USER_SETTINGS = {
    'class_short_name': '高三八班',
    'class_full_name': '高三（8）班',
    'school_name': '市西中学',
    'onduty_jobs': ['扫', '擦', '排', '理'],
    'onduty_daily_template': ['扫', '扫', '擦', '排', '理'],
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