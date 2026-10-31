"""bootstrap.py 的状态判定、落盘、备份与重置。

所有用例都传 root=临时目录，完全不碰真实的 %APPDATA%\\ClassManager。
"""

import json
from pathlib import Path

import pytest
from pandas import DataFrame, read_csv

import bootstrap

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"]


@pytest.fixture
def root(tmp_dir):
    """模拟 %APPDATA%\\ClassManager 的结构，返回路径字符串。"""
    (tmp_dir / "datas").mkdir()
    (tmp_dir / "messages").mkdir()
    return tmp_dir


def rd(root: Path, *parts) -> str:
    return str(root.joinpath(*parts))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ 状态

class TestState:
    def test_not_initialized_by_default(self, root):
        assert bootstrap.is_initialized(str(root)) is False

    def test_mark_then_initialized(self, root):
        bootstrap.mark_initialized(str(root))
        assert bootstrap.is_initialized(str(root)) is True

    def test_state_file_content(self, root):
        bootstrap.mark_initialized(str(root), note="测试")
        payload = read_json(root / "setup.json")
        assert payload["completed"] is True
        assert payload["note"] == "测试"

    def test_corrupt_state_file_counts_as_not_initialized(self, root):
        (root / "setup.json").write_text("{坏掉的", encoding="utf-8")
        assert bootstrap.is_initialized(str(root)) is False

    def test_completed_false_is_not_initialized(self, root):
        (root / "setup.json").write_text('{"completed": false}', encoding="utf-8")
        assert bootstrap.is_initialized(str(root)) is False


# ------------------------------------------------------------ 老用户推断

class TestLegacyInference:
    def test_false_when_nothing_exists(self, root):
        assert bootstrap.infer_legacy_state(str(root)) is False

    def test_false_when_names_exist_but_classlist_missing(self, root):
        DataFrame({"name": ["张三", "李四"]}).to_csv(rd(root, "datas/名单.csv"), index=False)
        assert bootstrap.infer_legacy_state(str(root)) is False

    def test_false_when_classlist_is_only_skeleton(self, root):
        """自举生成的 8 行空课表不能算"已初始化"。"""
        DataFrame({"name": ["张三"]}).to_csv(rd(root, "datas/名单.csv"), index=False)
        DataFrame(index=range(8), columns=WEEKDAYS).to_csv(
            rd(root, "datas/课表.csv"), index=False)
        assert bootstrap.infer_legacy_state(str(root)) is False

    def test_false_when_names_empty(self, root):
        DataFrame({"name": []}).to_csv(rd(root, "datas/名单.csv"), index=False)
        DataFrame([["语文", "数学", "", "", ""]], columns=WEEKDAYS).to_csv(
            rd(root, "datas/课表.csv"), index=False)
        assert bootstrap.infer_legacy_state(str(root)) is False

    def test_true_with_real_data(self, root):
        DataFrame({"name": ["张三", "李四"]}).to_csv(rd(root, "datas/名单.csv"), index=False)
        DataFrame([["语文", "数学", "英语", "物理", "化学"]], columns=WEEKDAYS).to_csv(
            rd(root, "datas/课表.csv"), index=False)
        assert bootstrap.infer_legacy_state(str(root)) is True


# ------------------------------------------------------------------ 落盘

class TestSaveAll:
    INFO = {
        "school_name": "市西中学",
        "class_full_name": "高三（8）班",
        "class_short_name": "高三八班",
        "onduty_jobs": ["扫", "擦"],
        "onduty_daily_template": ["扫", "扫"],
    }

    def save(self, root, onduty=None):
        classlist = DataFrame(
            [["语文", "数学", "语文", "", ""]],
            columns=WEEKDAYS,
        )
        return bootstrap.save_all(
            self.INFO, ["张三", "李四"], classlist, onduty=onduty, root=str(root))

    def test_writes_names(self, root):
        self.save(root)
        assert read_csv(rd(root, "datas/名单.csv"))["name"].tolist() == ["张三", "李四"]

    def test_writes_classlist_with_five_columns(self, root):
        self.save(root)
        df = read_csv(rd(root, "datas/课表.csv"))
        assert list(df.columns) == WEEKDAYS
        assert df.iloc[0, 0] == "语文"

    def test_courses_are_deduplicated(self, root):
        self.save(root)
        rows = read_csv(rd(root, "datas/课程单.csv"))["课程"].tolist()
        assert sorted(rows) == ["数学", "语文"]

    def test_writes_onduty_when_given(self, root):
        onduty = DataFrame({"2026-11-02": ["张三 扫"], "2026-11-03": ["李四 扫"]})
        self.save(root, onduty=onduty)
        assert read_csv(rd(root, "datas/未来值日.csv")).shape[1] == 2

    def test_no_onduty_file_when_omitted(self, root):
        self.save(root)
        assert not (root / "datas/未来值日.csv").exists()

    def test_writes_settings(self, root):
        self.save(root)
        cfg = read_json(root / "datas/settings.json")
        assert cfg["class_short_name"] == "高三八班"
        assert cfg["onduty_jobs"] == ["扫", "擦"]

    def test_preserves_existing_countdowns(self, root):
        (root / "datas/settings.json").write_text(
            json.dumps({"countdowns": [{"label": "高考", "date": "2027-06-07"}]},
                       ensure_ascii=False),
            encoding="utf-8")
        self.save(root)
        cfg = read_json(root / "datas/settings.json")
        assert cfg["countdowns"][0]["label"] == "高考"

    def test_marks_initialized(self, root):
        self.save(root)
        assert bootstrap.is_initialized(str(root)) is True

    def test_writes_last_login(self, root):
        self.save(root)
        assert len(read_json(root / "datas/data.json")["last_login"]) == 8

    def test_rejects_empty_names(self, root):
        with pytest.raises(ValueError):
            bootstrap.save_all(self.INFO, [], DataFrame([[""] * 5]), root=str(root))

    def test_rejects_wrong_column_count(self, root):
        with pytest.raises(ValueError):
            bootstrap.save_all(
                self.INFO, ["张三"], DataFrame([["语文", "数学"]]), root=str(root))

    def test_summary_counts(self, root):
        summary = self.save(root)
        assert summary["students"] == 2
        assert summary["courses"] == 2


# ------------------------------------------------------------------ 备份/重置

class TestBackupAndReset:
    def seed(self, root):
        (root / "datas/名单.csv").write_text("name\n张三\n", encoding="utf-8")
        (root / "datas/loadings").mkdir(exist_ok=True)
        (root / "datas/loadings/x classlist.csv").write_text("周一\n语文\n", encoding="utf-8")
        (root / "messages/message.html").write_text("<html></html>", encoding="utf-8")
        bootstrap.mark_initialized(str(root))

    def test_backup_copies_everything(self, root):
        self.seed(root)
        dest = Path(bootstrap.backup_all(str(root)))
        assert (dest / "datas/名单.csv").exists()
        assert (dest / "messages/message.html").exists()
        assert (dest / "setup.json").exists()

    def test_backup_does_not_recurse_into_backup(self, root):
        self.seed(root)
        bootstrap.backup_all(str(root))
        second = Path(bootstrap.backup_all(str(root)))
        assert not (second / "backup").exists()

    def test_reset_clears_data_and_state(self, root):
        self.seed(root)
        bootstrap.reset_all(str(root))
        assert list((root / "datas").iterdir()) == []
        assert bootstrap.is_initialized(str(root)) is False

    def test_reset_clears_messages_by_default(self, root):
        self.seed(root)
        bootstrap.reset_all(str(root))
        assert list((root / "messages").iterdir()) == []

    def test_reset_can_keep_messages(self, root):
        self.seed(root)
        bootstrap.reset_all(str(root), keep_messages=True)
        assert (root / "messages/message.html").exists()

    def test_reset_returns_backup_containing_old_data(self, root):
        self.seed(root)
        dest = Path(bootstrap.reset_all(str(root)))
        assert (dest / "datas/名单.csv").read_text(encoding="utf-8").strip() == "name\n张三"
