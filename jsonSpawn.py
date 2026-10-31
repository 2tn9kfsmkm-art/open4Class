import os
import json
from datetime import datetime

from config import FILE_DIR, ENCODING


def ensure_data_json():
    path = FILE_DIR + 'data.json'
    if not os.path.exists(path):
        with open(path, 'w', encoding=ENCODING) as f:
            json.dump({'last_login': datetime.today().strftime('%Y%m%d')}, f)


if __name__ == '__main__':
    ensure_data_json()