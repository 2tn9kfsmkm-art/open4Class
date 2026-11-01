"""视觉 token：颜色与字号只在这里定义，QSS 里用 `@名字` 引用。

设计原则（HANDOFF §7.6）：
    - 深红 = 品牌 / 主操作
    - 琥珀金 = 次强调（倒计时数字、徽标）
    - 灰阶 = 90% 的内容
    - 语义色 = 状态提示（成功/警告/危险/信息）

QSS 里写 `color: @primary;`，由 `render()` 替换成实际值；
以后换色只改这一个文件，不用全项目搜索替换。
"""

COLORS = {
    # 品牌主色
    'primary': '#9B0D14',
    'primary-hover': '#8A0B12',
    'primary-pressed': '#790910',
    'primary-deep': '#5C070C',
    'primary-soft': '#F5E8E9',
    'primary-tint': '#FEFAFA',
    'primary-muted': '#E8C8CA',
    # 次强调
    'accent': '#C9A227',
    # 中性灰阶
    'neutral-50': '#FAFAFA',
    'neutral-100': '#F2F2F2',
    'neutral-150': '#F0F0F0',
    'neutral-200': '#DDDDDD',
    'neutral-250': '#EEEEEE',
    'neutral-300': '#CCCCCC',
    'neutral-500': '#9E9E9E',
    'neutral-600': '#888888',
    'neutral-650': '#666666',
    'neutral-800': '#333333',
    'neutral-900': '#1A1A1A',
    'scrollbar': '#C9A1A3',
    'tab-bg': '#F9F5F5',
    # 语义色
    'success': '#2E7D32',
    'warning': '#ED6C02',
    'danger': '#C62828',
    'info': '#0288D1',
    # 基础
    'white': '#FFFFFF',
}

FONTS = {
    'font-display': '40pt',     # 主标题（学校 + 班级）
    'font-h1': '24pt',          # 侧栏、主区域文字
    'font-h2': '20pt',          # 按钮、应用图标区
    'font-body': '11pt',        # 对话框正文（设置、导入、询问）
    'font-small': '10pt',       # 说明文字
    'font-table': '28pt',       # 表格内容
}


def render(qss: str) -> str:
    """把 QSS 里的 @token 替换成实际值。

    未知的 @xxx 原样保留，方便发现拼错的名字。
    """
    merged = {**COLORS, **FONTS}
    # 长的先替换：否则 @primary 会把 @primary-muted 变成 "#9B0D14-muted"
    for name in sorted(merged, key=len, reverse=True):
        qss = qss.replace('@' + name, merged[name])
    return qss
