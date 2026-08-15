import re
import time
from typing import List, Tuple, Any
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import (
    Label, Input, Button, Static, TabbedContent, TabPane,
    Select, Checkbox, TextArea
)
from textual.binding import Binding

from config import config, APIProviderConfig, AgentSlotConfig, CONFIG_PATH


def is_valid_select_value(val: Any) -> bool:
    """检查是否为合法的 Select 选项值，严格过滤 Select.NULL 与 Select.BLANK"""
    if val is None:
        return False
    s = str(val).strip()
    if not s or s in ("Select.NULL", "Select.BLANK", "None", "NULL", "BLANK"):
        return False
    if hasattr(Select, "BLANK") and val is Select.BLANK:
        return False
    if hasattr(Select, "NULL") and val is Select.NULL:
        return False
    return True


class ConfigModal(ModalScreen[bool]):
    """多 API 供应商管理与自定义 5 角色分工（支持思考程度调节/关闭思考）设置弹窗"""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "返回/关闭 (ESC)", show=True),
        Binding("ctrl+s", "save_and_dismiss", "保存并应用 (Ctrl+S)", show=True),
    ]

    DEFAULT_CSS = """
    ConfigModal {
        align: center middle;
    }

    #dialog {
        padding: 0 1;
        width: 98;
        height: 94%;
        max-height: 44;
        border: thick #6366f1;
        background: #0f172a;
    }

    #modal-header {
        height: 3;
        background: #1e293b;
        padding: 0 1;
        align: left middle;
    }

    #modal-title {
        width: 1fr;
        color: #818cf8;
        text-style: bold;
    }

    .header-btn {
        margin-left: 1;
    }

    TabbedContent {
        height: 1fr;
    }

    .form-group {
        margin: 1 0;
    }

    .form-label {
        color: #38bdf8;
        text-style: bold;
    }

    .sub-label {
        color: #94a3b8;
    }

    #prov-mgr-bar {
        height: 3;
        align: left middle;
        margin-bottom: 1;
    }

    #select_provider {
        width: 1fr;
    }

    #slot-nav {
        margin-bottom: 1;
        height: 3;
    }

    .slot-btn {
        margin-right: 1;
    }

    .checkbox-row {
        height: 3;
        margin: 0 0 1 0;
        align: left middle;
    }

    .checkbox-row Checkbox {
        margin-right: 4;
        width: auto;
    }

    #slot_prompt {
        height: 8;
        min-height: 6;
    }

    #modal-footer {
        height: 3;
        background: #1e293b;
        padding: 0 1;
        align: right middle;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_provider_idx = 0
        self.current_slot_idx = 0
        self.temp_providers = [p.model_copy() for p in config.providers]
        self.temp_slots = [s.model_copy() for s in config.agent_slots]
        self._sanitize_temp_data()

    def _sanitize_temp_data(self) -> None:
        """确保临时数据中没有 Select.NULL 或孤立的 provider_id"""
        if not self.temp_providers:
            self.temp_providers = [p.model_copy() for p in config.providers]
        valid_ids = [p.id for p in self.temp_providers]
        default_id = valid_ids[0] if valid_ids else "deepseek"

        for s in self.temp_slots:
            if not is_valid_select_value(s.provider_id) or s.provider_id not in valid_ids:
                s.provider_id = default_id
            m_opts = self._get_model_options_for_provider(s.provider_id)
            if not is_valid_select_value(s.model) or not any(m[1] == s.model for m in m_opts):
                s.model = m_opts[0][1] if m_opts else "deepseek-chat"
            if not hasattr(s, "thinking_mode") or s.thinking_mode not in ("deep", "lite", "off"):
                s.thinking_mode = "deep"

    def _get_model_options_for_provider(self, provider_id: str) -> List[Tuple[str, str]]:
        """获取指定供应商的所有可用模型列表 (以下拉元组格式)"""
        for p in self.temp_providers:
            if p.id == provider_id and p.models:
                return [(m, m) for m in p.models]
        return [("deepseek-chat", "deepseek-chat")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            with Horizontal(id="modal-header"):
                yield Static("⚙️ [bold #818cf8]OpenCode 系统设置: 多 API 与角色分工[/bold #818cf8]", id="modal-title")
                yield Button("◀ 返回 (ESC)", variant="default", id="btn_top_cancel", classes="header-btn")
                yield Button("💾 保存并应用", variant="success", id="btn_top_save", classes="header-btn")

            with TabbedContent():
                # ----------------------------------------------------
                # TAB 1: API 供应商管理 (支持自定义新增/删除/编辑)
                # ----------------------------------------------------
                with TabPane("🔑 API 供应商配置", id="tab_providers"):
                    with ScrollableContainer():
                        yield Static("[dim green]✔ 支持自由新增任意 OpenAI 兼容供应商，设置将永久持久化保存！[/dim green]\n")
                        
                        yield Label("选择或切换要编辑的 API 供应商:", classes="form-label")
                        with Horizontal(id="prov-mgr-bar"):
                            provider_options = [(p.name, str(idx)) for idx, p in enumerate(self.temp_providers)]
                            cur_p_idx_str = str(self.current_provider_idx) if 0 <= self.current_provider_idx < len(self.temp_providers) else "0"
                            yield Select(
                                options=provider_options,
                                value=cur_p_idx_str,
                                id="select_provider",
                            )
                            yield Button("➕ 新增供应商", variant="primary", id="btn_add_provider")
                            yield Button("🗑️ 删除该供应商", variant="error", id="btn_del_provider")

                        cur_p = self.temp_providers[self.current_provider_idx] if 0 <= self.current_provider_idx < len(self.temp_providers) else self.temp_providers[0]

                        with Vertical(classes="form-group"):
                            yield Label("供应商显示名称 (可自定义):", classes="form-label")
                            yield Input(
                                value=cur_p.name,
                                placeholder="例如: 阶跃星辰 StepFun / Kimi / 智谱AI / 我的中转站",
                                id="prov_name",
                            )

                        with Vertical(classes="form-group"):
                            yield Label("API Base URL (兼容 OpenAI 规范):", classes="form-label")
                            yield Input(
                                value=cur_p.base_url,
                                placeholder="https://api.example.com/v1",
                                id="prov_base_url",
                            )

                        with Vertical(classes="form-group"):
                            yield Label("API 密钥 (API Key):", classes="form-label")
                            yield Input(
                                value=cur_p.api_key,
                                password=True,
                                placeholder="sk-...",
                                id="prov_api_key",
                            )

                        with Vertical(classes="form-group"):
                            yield Label("可用模型列表 (支持顿号、逗号、空格分隔):", classes="form-label")
                            yield Input(
                                value="、".join(cur_p.models),
                                placeholder="deepseek-chat、deepseek-reasoner 或 custom-model",
                                id="prov_models",
                            )

                # ----------------------------------------------------
                # TAB 2: 5 个角色分工与思考程度设置
                # ----------------------------------------------------
                with TabPane("🤖 角色分工与思考设置 (最多5人)", id="tab_slots"):
                    with ScrollableContainer():
                        with Horizontal(id="slot-nav"):
                            yield Button("槽位 1", id="nav_slot_0", classes="slot-btn", variant="primary")
                            yield Button("槽位 2", id="nav_slot_1", classes="slot-btn")
                            yield Button("槽位 3", id="nav_slot_2", classes="slot-btn")
                            yield Button("槽位 4", id="nav_slot_3", classes="slot-btn")
                            yield Button("槽位 5", id="nav_slot_4", classes="slot-btn")

                        cur_slot = self.temp_slots[0]

                        # 单行并排复选框
                        with Horizontal(classes="checkbox-row"):
                            yield Checkbox("启用该角色成员", value=cur_slot.enabled, id="slot_enabled")
                            yield Checkbox("允许调用沙箱工具", value=cur_slot.allow_tools, id="slot_allow_tools")

                        with Horizontal(classes="form-group"):
                            with Vertical(classes="form-group"):
                                yield Label("角色图标:", classes="sub-label")
                                yield Input(value=cur_slot.icon, id="slot_icon", max_length=4)
                            with Vertical(classes="form-group"):
                                yield Label("自定义角色名称:", classes="sub-label")
                                yield Input(value=cur_slot.name, id="slot_name")

                        with Horizontal(classes="form-group"):
                            with Vertical(classes="form-group"):
                                yield Label("绑定的 API 供应商:", classes="sub-label")
                                prov_choices = [(p.name, p.id) for p in self.temp_providers]
                                valid_prov_ids = [p.id for p in self.temp_providers]
                                cur_prov_val = cur_slot.provider_id if cur_slot.provider_id in valid_prov_ids else valid_prov_ids[0]
                                yield Select(
                                    options=prov_choices,
                                    value=cur_prov_val,
                                    id="slot_provider_select",
                                )
                            with Vertical(classes="form-group"):
                                yield Label("选择绑定的模型:", classes="sub-label")
                                initial_models = self._get_model_options_for_provider(cur_prov_val)
                                cur_m_val = cur_slot.model if any(m[1] == cur_slot.model for m in initial_models) else initial_models[0][1]
                                yield Select(
                                    options=initial_models,
                                    value=cur_m_val,
                                    id="slot_model_select",
                                )
                            with Vertical(classes="form-group"):
                                yield Label("深度思考程度 (Thinking):", classes="sub-label")
                                think_opts = [
                                    ("🧠 深度思考 (Deep)", "deep"),
                                    ("⚡ 轻度思考 (Lite)", "lite"),
                                    ("🚫 关闭思考 (Off)", "off"),
                                ]
                                cur_think = getattr(cur_slot, "thinking_mode", "deep")
                                if cur_think not in ("deep", "lite", "off"):
                                    cur_think = "deep"
                                yield Select(
                                    options=think_opts,
                                    value=cur_think,
                                    id="slot_thinking_select",
                                )

                        with Vertical(classes="form-group"):
                            yield Label("角色职责与系统提示词 (Prompt):", classes="sub-label")
                            yield TextArea(
                                text=cur_slot.system_prompt,
                                id="slot_prompt",
                                show_line_numbers=False,
                            )

                # ----------------------------------------------------
                # TAB 3: 全局与沙箱配置
                # ----------------------------------------------------
                with TabPane("📁 工作区与全局", id="tab_global"):
                    with ScrollableContainer():
                        with Vertical(classes="form-group"):
                            yield Label("工作区沙箱根路径 (WORKSPACE_ROOT):", classes="form-label")
                            yield Input(value=config.workspace_root, id="global_workspace")

                        with Vertical(classes="form-group"):
                            yield Label("最大圆桌循环接力轮数 (MAX_LOOPS):", classes="form-label")
                            yield Input(value=str(config.max_loops_per_task), id="global_max_loops")

                        with Vertical(classes="form-group"):
                            yield Label("沙箱命令超时时间 (秒):", classes="form-label")
                            yield Input(value=str(config.command_timeout_seconds), id="global_timeout")

                        yield Static(f"\n[dim cyan]📁 永久配置文件位置: {CONFIG_PATH}[/dim cyan]")

            # 底部固定操作栏
            with Horizontal(id="modal-footer"):
                yield Button("◀ 返回主界面 (ESC)", variant="default", id="btn_cancel")
                yield Button("💾 保存并应用配置", variant="success", id="btn_save")

    def _save_current_provider_form(self) -> None:
        idx = self.current_provider_idx
        if 0 <= idx < len(self.temp_providers):
            name_val = self.query_one("#prov_name", Input).value.strip()
            if name_val:
                self.temp_providers[idx].name = name_val
            self.temp_providers[idx].base_url = self.query_one("#prov_base_url", Input).value.strip()
            self.temp_providers[idx].api_key = self.query_one("#prov_api_key", Input).value.strip()
            models_str = self.query_one("#prov_models", Input).value.strip()
            parsed_models = [m.strip() for m in re.split(r'[,，、\s]+', models_str) if m.strip()]
            if not parsed_models:
                parsed_models = ["default"]
            self.temp_providers[idx].models = parsed_models

    def _refresh_provider_ui(self, idx: int) -> None:
        """根据索引刷新供应商管理界面与 Tab 2 联动选项"""
        if 0 <= idx < len(self.temp_providers):
            self.current_provider_idx = idx
            provider_options = [(p.name, str(i)) for i, p in enumerate(self.temp_providers)]
            select_prov = self.query_one("#select_provider", Select)
            select_prov.set_options(provider_options)
            select_prov.value = str(idx)

            p = self.temp_providers[idx]
            self.query_one("#prov_name", Input).value = p.name
            self.query_one("#prov_base_url", Input).value = p.base_url
            self.query_one("#prov_api_key", Input).value = p.api_key
            self.query_one("#prov_models", Input).value = "、".join(p.models)

            try:
                prov_choices = [(p.name, p.id) for p in self.temp_providers]
                slot_prov_select = self.query_one("#slot_provider_select", Select)
                slot_prov_select.set_options(prov_choices)
            except Exception:
                pass

    def _save_current_slot_form(self) -> None:
        idx = self.current_slot_idx
        if 0 <= idx < len(self.temp_slots):
            self.temp_slots[idx].enabled = self.query_one("#slot_enabled", Checkbox).value
            self.temp_slots[idx].allow_tools = self.query_one("#slot_allow_tools", Checkbox).value
            self.temp_slots[idx].icon = self.query_one("#slot_icon", Input).value.strip() or "🤖"
            self.temp_slots[idx].name = self.query_one("#slot_name", Input).value.strip() or f"角色 {idx+1}"
            
            prov_val = self.query_one("#slot_provider_select", Select).value
            if is_valid_select_value(prov_val) and any(p.id == str(prov_val) for p in self.temp_providers):
                self.temp_slots[idx].provider_id = str(prov_val)

            model_val = self.query_one("#slot_model_select", Select).value
            if is_valid_select_value(model_val):
                self.temp_slots[idx].model = str(model_val)

            think_val = self.query_one("#slot_thinking_select", Select).value
            if is_valid_select_value(think_val):
                self.temp_slots[idx].thinking_mode = str(think_val)

            self.temp_slots[idx].system_prompt = self.query_one("#slot_prompt", TextArea).text.strip()

    def _load_slot_form(self, idx: int) -> None:
        if 0 <= idx < len(self.temp_slots):
            slot = self.temp_slots[idx]
            self.query_one("#slot_enabled", Checkbox).value = slot.enabled
            self.query_one("#slot_allow_tools", Checkbox).value = slot.allow_tools
            self.query_one("#slot_icon", Input).value = slot.icon
            self.query_one("#slot_name", Input).value = slot.name
            
            prov_choices = [(p.name, p.id) for p in self.temp_providers]
            slot_prov_select = self.query_one("#slot_provider_select", Select)
            slot_prov_select.set_options(prov_choices)
            
            target_prov = slot.provider_id if any(p.id == slot.provider_id for p in self.temp_providers) else self.temp_providers[0].id
            slot_prov_select.value = target_prov

            model_opts = self._get_model_options_for_provider(target_prov)
            model_select = self.query_one("#slot_model_select", Select)
            model_select.set_options(model_opts)
            if any(m[1] == slot.model for m in model_opts):
                model_select.value = slot.model
            elif model_opts:
                model_select.value = model_opts[0][1]

            cur_think = getattr(slot, "thinking_mode", "deep")
            if cur_think not in ("deep", "lite", "off"):
                cur_think = "deep"
            self.query_one("#slot_thinking_select", Select).value = cur_think

            self.query_one("#slot_prompt", TextArea).text = slot.system_prompt

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "select_provider":
            self._save_current_provider_form()
            try:
                if is_valid_select_value(event.value):
                    new_idx = int(event.value)
                    if new_idx != self.current_provider_idx and 0 <= new_idx < len(self.temp_providers):
                        self.current_provider_idx = new_idx
                        p = self.temp_providers[new_idx]
                        self.query_one("#prov_name", Input).value = p.name
                        self.query_one("#prov_base_url", Input).value = p.base_url
                        self.query_one("#prov_api_key", Input).value = p.api_key
                        self.query_one("#prov_models", Input).value = "、".join(p.models)
            except Exception:
                pass

        elif event.select.id == "slot_provider_select":
            try:
                if is_valid_select_value(event.value):
                    new_prov_id = str(event.value)
                    new_opts = self._get_model_options_for_provider(new_prov_id)
                    model_select = self.query_one("#slot_model_select", Select)
                    model_select.set_options(new_opts)
                    if new_opts:
                        model_select.value = new_opts[0][1]
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id.startswith("nav_slot_"):
            self._save_current_slot_form()
            target_idx = int(btn_id.replace("nav_slot_", ""))
            self.current_slot_idx = target_idx
            for i in range(5):
                b = self.query_one(f"#nav_slot_{i}", Button)
                b.variant = "primary" if i == target_idx else "default"
            self._load_slot_form(target_idx)

        elif btn_id == "btn_add_provider":
            self._save_current_provider_form()
            new_idx = len(self.temp_providers)
            new_p = APIProviderConfig(
                id=f"custom_{int(time.time()*1000)}",
                name=f"自定义供应商 {new_idx + 1}",
                base_url="https://api.example.com/v1",
                api_key="",
                models=["custom-model-1", "custom-model-2"],
            )
            self.temp_providers.append(new_p)
            self._refresh_provider_ui(new_idx)

        elif btn_id == "btn_del_provider":
            if len(self.temp_providers) > 1:
                self.temp_providers.pop(self.current_provider_idx)
                next_idx = max(0, self.current_provider_idx - 1)
                self._refresh_provider_ui(next_idx)

        elif btn_id in ("btn_save", "btn_top_save"):
            self.action_save_and_dismiss()

        elif btn_id in ("btn_cancel", "btn_top_cancel"):
            self.action_dismiss_modal()

    def action_dismiss_modal(self) -> None:
        self.dismiss(False)

    def action_save_and_dismiss(self) -> None:
        self._save_current_provider_form()
        self._save_current_slot_form()

        ws = self.query_one("#global_workspace", Input).value.strip()
        if ws:
            config.workspace_root = ws
        try:
            loops = int(self.query_one("#global_max_loops", Input).value.strip())
            config.max_loops_per_task = loops
        except ValueError:
            pass
        try:
            tout = int(self.query_one("#global_timeout", Input).value.strip())
            config.command_timeout_seconds = tout
        except ValueError:
            pass

        config.providers = self.temp_providers
        config.agent_slots = self.temp_slots
        config.save_to_file()
        self.dismiss(True)
