from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import audio_io
from app.core.jobs import Job
from app.core.validation import analyze_audio

from ..context import AppContext, run_background, ui_soon
from ..widgets import make_label


class VoicesPage(QWidget):
    def __init__(self, ctx: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setAcceptDrops(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(make_label("音色库", "PageTitle"))
        title_box.addWidget(make_label("管理参考音频与克隆音色，可随时复用", "PageSub"))
        head.addLayout(title_box, 1)
        self.import_btn = QPushButton("导入音频")
        self.import_btn.setObjectName("Primary")
        self.import_btn.clicked.connect(self._import)
        self.demo_btn = QPushButton("添加演示音色")
        self.demo_btn.clicked.connect(self._add_demo)
        head.addWidget(self.demo_btn)
        head.addWidget(self.import_btn)
        root.addLayout(head)

        self.list = QListWidget()
        self.list.setSpacing(6)
        self.list.itemDoubleClicked.connect(lambda item: self._play_voice(item))
        root.addWidget(self.list, 1)

    def refresh(self) -> None:
        self.list.clear()
        for voice in self.ctx.voices.list():
            item = QListWidgetItem()
            item.setData(Qt.UserRole, voice.id)
            widget = voice_card_widget(voice, self.ctx, on_changed=self.refresh)
            item.setSizeHint(widget.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)

    def _voice_by_item(self, item: QListWidgetItem):
        return self.ctx.voices.get(item.data(Qt.UserRole))

    def _play_voice(self, item: QListWidgetItem) -> None:
        voice = self._voice_by_item(item)
        if voice and voice.wav_path and Path(voice.wav_path).exists():
            self._play_path_async(voice.wav_path)
        elif voice:
            self.ctx.notify("该演示音色没有参考音频，可在 TTS/VC 页选择使用")

    def _play_path_async(self, path: str) -> None:
        """后台解码后播放，避免在主线程解码大文件导致界面冻结。"""
        def work():
            return audio_io.decode_audio(path, self.ctx.config.settings)

        def done(result):
            sr, data = result
            self.ctx.player.play(data, sr)

        def error(exc):
            self.ctx.notify(f"播放失败：{exc}")

        run_background(work, ui_soon(done), ui_soon(error))

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择参考音频",
            "",
            "音频文件 (*.wav *.mp3 *.m4a *.flac *.ogg *.aac);;所有文件 (*)",
        )
        if not path:
            return
        self.ctx.notify("正在导入并校验音频…")
        self._import_path(path)

    def _import_path(self, path: str) -> None:
        def work():
            print(f"[导入] 开始解码: {path}", flush=True)
            sr, data = audio_io.decode_audio(path, self.ctx.config.settings)
            print(f"[导入] 解码完成 sr={sr} 样本数={len(data)}", flush=True)
            report = analyze_audio(data, sr, size_bytes=Path(path).stat().st_size)
            print(f"[导入] 校验完成 ok={report.ok} 时长={report.duration:.1f}s", flush=True)
            return report

        def done(report):
            print(f"[导入] done 回调，ok={report.ok}", flush=True)
            if not report.ok:
                QMessageBox.warning(self, "无法导入", "\n".join(report.warnings))
                return
            name, ok = QInputDialog.getText(self, "命名音色", "音色名称", text=Path(path).stem)
            if not ok or not name.strip():
                return
            prompt, ok2 = QInputDialog.getText(
                self,
                "参考文字（可选）",
                "GPT-SoVITS 参考音频对应的文字（可留空）",
            )
            if not ok2:
                return
            self._save_imported(path, name, report, prompt.strip())

        def error(exc):
            print(f"[导入] 失败: {exc}", flush=True)
            QMessageBox.warning(self, "导入失败", str(exc))

        run_background(work, ui_soon(done), ui_soon(error))

    def _save_imported(self, path: str, name: str, report, prompt: str) -> None:
        """解码 + 写文件在后台线程执行，避免冻结 UI。"""
        self.ctx.notify("正在保存音色…")

        def work():
            voice = self.ctx.voices.add_from_file(name, path, report)
            if prompt:
                self.ctx.voices.save_prompt_text(voice.id, prompt)
            return voice

        def done(voice):
            self.refresh()
            self.ctx.notify(f"音色“{voice.name}”已保存（预估相似度 {voice.similarity_estimate}/5）")

        def error(exc):
            QMessageBox.warning(self, "导入失败", str(exc))

        run_background(work, ui_soon(done), ui_soon(error))

    def _add_demo(self) -> None:
        voice = self.ctx.voices.add_demo()
        self.refresh()
        self.ctx.notify(f"演示音色“{voice.name}”已添加")

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls:
            self._import_path(urls[0].toLocalFile())


class _RefRow(QWidget):
    """附加参考音频的一行：文件名 + 台词编辑 + 删除。"""

    removed = Signal(object)

    def __init__(self, wav_path: str = "", prompt_text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.path = wav_path
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)
        self.path_label = make_label(Path(wav_path).name if wav_path else "（未选择）", "Muted")
        lay.addWidget(self.path_label, 1)
        self.prompt_edit = QLineEdit(prompt_text)
        self.prompt_edit.setPlaceholderText("该参考音频的台词（逐字准确）")
        lay.addWidget(self.prompt_edit, 2)
        del_btn = QPushButton("删除")
        del_btn.setObjectName("Ghost")
        del_btn.clicked.connect(lambda: self.removed.emit(self))
        lay.addWidget(del_btn)


class RefGroupDialog(QDialog):
    """多参考音频管理：主参考台词 + 附加参考列表（每条独立台词）。"""

    def __init__(self, voice, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"多参考音频 — {voice.name}")
        self.setMinimumWidth(640)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        main_card = QWidget()
        main_card.setObjectName("Card")
        ml = QVBoxLayout(main_card)
        ml.setContentsMargins(14, 12, 14, 12)
        ml.addWidget(make_label("主参考音频", "SectionTitle"))
        ml.addWidget(make_label(f"文件：{Path(voice.wav_path).name}", "Muted"))
        self.main_prompt = QPlainTextEdit(voice.prompt_text or "")
        self.main_prompt.setPlaceholderText("主参考音频的台词（逐字准确，决定音色相似度）")
        self.main_prompt.setFixedHeight(56)
        ml.addWidget(self.main_prompt)
        root.addWidget(main_card)

        extra_card = QWidget()
        extra_card.setObjectName("Card")
        el = QVBoxLayout(extra_card)
        el.setContentsMargins(14, 12, 14, 12)
        el.addWidget(make_label("附加参考音频（多参考，可添加多条）", "SectionTitle"))
        self.ref_list = QListWidget()
        self.ref_list.setMinimumHeight(110)
        el.addWidget(self.ref_list)
        add_btn = QPushButton("+ 添加参考音频")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self._add_row)
        el.addWidget(add_btn)
        hint = make_label(
            "建议各参考音频声线/风格一致；每条台词逐字填写可提升克隆稳定性。", "Muted"
        )
        hint.setWordWrap(True)
        el.addWidget(hint)
        root.addWidget(extra_card)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("保存")
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        root.addLayout(btn_row)

        for r in getattr(voice, "extra_refs", []):
            self._add_row(r.get("wav_path", ""), r.get("prompt_text", ""), pick=False)

    def _add_row(self, wav_path: str = "", prompt_text: str = "", pick: bool = True) -> None:
        if pick and not wav_path:
            wav_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择参考音频",
                "",
                "音频文件 (*.wav *.mp3 *.m4a *.flac *.ogg *.aac);;所有文件 (*)",
            )
            if not wav_path:
                return
        row = _RefRow(wav_path, prompt_text)
        row.removed.connect(self._remove_row)
        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        self.ref_list.addItem(item)
        self.ref_list.setItemWidget(item, row)

    def _remove_row(self, row) -> None:
        for i in range(self.ref_list.count()):
            item = self.ref_list.item(i)
            if self.ref_list.itemWidget(item) is row:
                self.ref_list.takeItem(i)
                break

    def result_data(self) -> tuple[str, list[dict]]:
        extra = []
        for i in range(self.ref_list.count()):
            item = self.ref_list.item(i)
            row = self.ref_list.itemWidget(item)
            if row and row.path:
                extra.append(
                    {
                        "wav_path": row.path,
                        "prompt_text": row.prompt_edit.text().strip(),
                        "prompt_language": "",
                    }
                )
        return self.main_prompt.toPlainText().strip(), extra


def voice_card_widget(voice, ctx: AppContext, on_changed=None) -> QWidget:
    card = QWidget()
    layout = QHBoxLayout(card)
    layout.setContentsMargins(10, 6, 10, 6)
    info = QVBoxLayout()
    info.setSpacing(2)
    name_label = make_label(voice.name, "SectionTitle")
    kind_text = {"zero_shot": "零样本", "rvc": "RVC 训练", "demo": "演示"}.get(voice.kind, voice.kind)
    if voice.rvc_model_path:
        model_name = Path(voice.rvc_model_path).name
        kind_text = f"RVC · 模型：{model_name}"
    meta = (
        f"{kind_text} · {voice.duration:.1f} 秒 · {voice.sample_rate} Hz"
        + (f" · 预估相似度 {voice.similarity_estimate}/5" if voice.similarity_estimate else "")
        + (f" · 参考文字：{voice.prompt_text[:20]}" if voice.prompt_text else " · 参考文字：未填")
        + (f" · 附加参考 x{len(voice.extra_refs)}" if getattr(voice, "extra_refs", None) else "")
    )
    if not voice.rvc_model_path and ctx.config.settings.rvc_model_path:
        meta += " · 使用全局 RVC 模型"
    info.addWidget(name_label)
    meta_label = make_label("", "Muted")
    # QLabel 没有 elide 模式，用字体度量手动裁剪长文本（避免挤压右侧按钮区）
    meta_label.setText(QFontMetrics(meta_label.font()).elidedText(meta, Qt.ElideMiddle, 400))
    info.addWidget(meta_label)
    layout.addLayout(info, 1)
    btns = QHBoxLayout()
    btns.setSpacing(6)
    play = QPushButton("播放")
    play.setObjectName("Ghost")

    def do_play():
        if not voice.wav_path:
            ctx.notify("该演示音色没有参考音频")
            return

        def work():
            return audio_io.decode_audio(voice.wav_path, ctx.config.settings)

        def done(result):
            sr, data = result
            ctx.player.play(data, sr)

        def error(exc):
            ctx.notify(f"播放失败：{exc}")

        run_background(work, ui_soon(done), ui_soon(error))

    play.clicked.connect(do_play)
    rename = QPushButton("重命名")
    rename.setObjectName("Ghost")

    def do_rename():
        name, ok = QInputDialog.getText(card, "重命名", "新名称", text=voice.name)
        if ok and name.strip():
            ctx.voices.rename(voice.id, name)
            ctx.notify("已重命名")
            if on_changed:
                on_changed()

    rename.clicked.connect(do_rename)
    prompt_btn = QPushButton("参考文字")
    prompt_btn.setObjectName("Ghost")

    def do_edit_prompt():
        cur = voice.prompt_text or ""
        text, ok = QInputDialog.getMultiLineText(
            card,
            "参考文字",
            f"“{voice.name}”的参考音频台词\n（逐字准确可显著提升克隆相似度）：",
            cur,
        )
        if ok:
            voice.prompt_text = text.strip()
            ctx.voices.update(voice)
            ctx.notify("参考文字已更新")
            if on_changed:
                on_changed()

    prompt_btn.clicked.connect(do_edit_prompt)
    refgroup_btn = QPushButton("多参考")
    refgroup_btn.setObjectName("Ghost")

    def do_ref_group():
        dlg = RefGroupDialog(voice, card)
        if dlg.exec() == QDialog.Accepted:
            prompt_text, extra = dlg.result_data()
            voice.prompt_text = prompt_text
            voice.extra_refs = extra
            ctx.voices.update(voice)
            ctx.notify(f"已保存主参考 + {len(extra)} 条附加参考")
            if on_changed:
                on_changed()

    refgroup_btn.clicked.connect(do_ref_group)
    delete = QPushButton("删除")
    delete.setObjectName("Ghost")

    def do_delete():
        r = QMessageBox.question(card, "删除音色", f"确认删除“{voice.name}”？")
        if r == QMessageBox.Yes:
            ctx.voices.delete(voice.id)
            ctx.notify("已删除音色")
            if on_changed:
                on_changed()

    delete.clicked.connect(do_delete)

    def bind_rvc_model():
        start_dir = str(Path(voice.rvc_model_path).parent) if voice.rvc_model_path else ""
        path, _ = QFileDialog.getOpenFileName(
            card, "选择 RVC 模型（.pth）", start_dir,
            "RVC 模型 (*.pth);;所有文件 (*)",
        )
        if not path:
            return
        voice.rvc_model_path = path
        voice.kind = "rvc"
        ctx.voices.update(voice)
        ctx.notify(f"已为“{voice.name}”绑定 RVC 模型")
        if on_changed:
            on_changed()

    def unbind_rvc_model():
        voice.rvc_model_path = ""
        voice.kind = "zero_shot" if voice.wav_path else "demo"
        ctx.voices.update(voice)
        ctx.notify("已解除绑定（回退全局模型）")
        if on_changed:
            on_changed()

    rvc_btn = QPushButton("RVC ✓" if voice.rvc_model_path else "RVC 模型")
    rvc_btn.setObjectName("Ghost")

    def do_rvc_menu():
        menu = QMenu(card)
        menu.addAction("绑定 / 更换 RVC 模型…", bind_rvc_model)
        if voice.rvc_model_path:
            menu.addAction("解除绑定（回退全局模型）", unbind_rvc_model)
        menu.exec(rvc_btn.mapToGlobal(QPoint(0, rvc_btn.height())))

    rvc_btn.clicked.connect(do_rvc_menu)
    btns.addWidget(play)
    btns.addWidget(rename)
    btns.addWidget(prompt_btn)
    btns.addWidget(refgroup_btn)
    btns.addWidget(rvc_btn)
    btns.addWidget(delete)
    layout.addLayout(btns)
    return card
