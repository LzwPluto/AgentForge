import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import sys

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).parent.resolve()
else:
    PROJECT_ROOT = Path(__file__).parent.resolve()

CONFIG_JSON_FILE = "agentforge_config.json"
LEGACY_CONFIG_JSON_FILE = "opencode_config.json"

if (PROJECT_ROOT / CONFIG_JSON_FILE).exists():
    CONFIG_PATH = PROJECT_ROOT / CONFIG_JSON_FILE
elif (PROJECT_ROOT / LEGACY_CONFIG_JSON_FILE).exists():
    CONFIG_PATH = PROJECT_ROOT / LEGACY_CONFIG_JSON_FILE
else:
    CONFIG_PATH = PROJECT_ROOT / CONFIG_JSON_FILE

BACKUP_CONFIG_PATH = PROJECT_ROOT / "agentforge_config.backup.json"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=False)

ALL_TOOLS = [
    "view_file",
    "write_file",
    "edit_file_exact",
    "list_dir",
    "grep_search",
    "run_command",
    "get_git_diff",
]


class APIProviderConfig(BaseModel):
    """API 供应商配置"""
    id: str = Field(description="唯一ID，如 deepseek, openai, siliconflow, qwen, ollama")
    name: str = Field(description="展示名称，如 DeepSeek官方")
    base_url: str = Field(description="API Base URL")
    api_key: str = Field(default="", description="API Key")
    models: List[str] = Field(default_factory=list, description="预设/常用模型列表")


class AgentSlotConfig(BaseModel):
    """角色分工槽位配置 (最多 5 个槽位)"""
    slot_id: str = Field(description="槽位标识: slot_1 ~ slot_5")
    slot_index: int = Field(description="槽位序号: 1 ~ 5")
    enabled: bool = Field(default=True, description="是否启用该角色成员")
    name: str = Field(description="自定义角色名称，如 '作家 (创作/起草)'、'审核员 (润色/审校)'")
    icon: str = Field(default="✍️", description="角色图标 Emoji")
    role_type: str = Field(default="custom", description="内置参考类型: writer, reviewer, coder, lead, custom")
    system_prompt: str = Field(description="自定义角色的任务职责与系统提示词")
    provider_id: str = Field(description="绑定的 API 供应商 ID")
    model: str = Field(description="绑定的具体模型名称")
    allow_tools: bool = Field(default=True, description="是否允许该角色调用沙箱工具")
    thinking_mode: str = Field(
        default="deep",
        description="思考模式: deep(深度思考), lite(轻度思考), off(关闭思考)"
    )
    isolate_thinking: bool = Field(
        default=True,
        description="是否对其他 AI 隐藏本角色的思考过程 (仅人类监督可见，防止思维干扰或提示词策略泄露)"
    )
    allowed_tools: List[str] = Field(
        default_factory=lambda: list(ALL_TOOLS),
        description="该角色允许调用的工具列表"
    )




# 默认预设 Providers
DEFAULT_PROVIDERS = [
    APIProviderConfig(
        id="deepseek",
        name="DeepSeek 官方",
        base_url="https://api.deepseek.com/v1",
        api_key=os.getenv("OPENAI_API_KEY", ""),
        models=["deepseek-chat", "deepseek-reasoner"],
    ),
    APIProviderConfig(
        id="openai",
        name="OpenAI 官方",
        base_url="https://api.openai.com/v1",
        api_key="",
        models=["gpt-4o", "gpt-4o-mini", "o1-mini", "o3-mini"],
    ),
    APIProviderConfig(
        id="qwen",
        name="阿里通义千问 (DashScope)",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="",
        models=["qwen-max", "qwen-plus", "qwen-turbo", "qwen2.5-coder-32b-instruct"],
    ),
    APIProviderConfig(
        id="siliconflow",
        name="硅基流动 (SiliconFlow)",
        base_url="https://api.siliconflow.cn/v1",
        api_key="",
        models=["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Qwen/Qwen2.5-Coder-32B-Instruct"],
    ),
    APIProviderConfig(
        id="ollama",
        name="Ollama 本地大模型",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        models=["qwen2.5-coder", "deepseek-r1:14b", "llama3.1"],
    ),
]

# 默认预设 5 大角色槽位 (全员享有全部工具权限，默认槽位 1 作家 + 槽位 2 审核员)
DEFAULT_SLOTS = [
    AgentSlotConfig(
        slot_id="slot_1",
        slot_index=1,
        enabled=True,
        name="作家 (创作/起草)",
        icon="✍️",
        role_type="writer",
        system_prompt="你是一位富有创意和文采的专业主创/作家。负责根据用户目标进行大纲构思、正文创作与草稿编写。你可以使用 write_file 编写章节或代码文件，使用 edit_file_exact 修改文本。在圆桌群聊中，你与审核员及其他团队成员紧密配合，听取他们的审校反馈并持续迭代。",
        provider_id="deepseek",
        model="deepseek-chat",
        allowed_tools=list(ALL_TOOLS),
    ),
    AgentSlotConfig(
        slot_id="slot_2",
        slot_index=2,
        enabled=True,
        name="审核员 (润色/审校)",
        icon="🧐",
        role_type="reviewer",
        system_prompt="你是一位严谨细致的首席审核与润色专家。负责紧跟作家的每一轮创作内容，仔细审校逻辑连贯性、设定一致性、文笔文采或代码质量。你可以使用 view_file 查看最新文件，使用 edit_file_exact 直接对文件进行润色修正，或在发言中提供精辟的修改建议。当确认全部内容已打磨完善时，请在回复中输出【目标已达成】。",
        provider_id="deepseek",
        model="deepseek-chat",
        allowed_tools=list(ALL_TOOLS),
    ),
    AgentSlotConfig(
        slot_id="slot_3",
        slot_index=3,
        enabled=True,
        name="全栈专家 (编码/拓展)",
        icon="💻",
        role_type="coder",
        system_prompt="你是一个全能的工程开发与技术拓展专家。负责编写高质量的代码实现、自动化脚本、数据处理或技术支撑。可以使用全量沙箱工具完成文件编写与调试。",
        provider_id="deepseek",
        model="deepseek-chat",
        allowed_tools=list(ALL_TOOLS),
    ),
    AgentSlotConfig(
        slot_id="slot_4",
        slot_index=4,
        enabled=False,
        name="测试员 (运行/验证)",
        icon="🏃",
        role_type="runner",
        system_prompt="你是一个专业的验证与运行测试专家。负责执行命令、运行脚本或检查一致性，确保所有产出无错误。",
        provider_id="deepseek",
        model="deepseek-chat",
        allowed_tools=list(ALL_TOOLS),
    ),
    AgentSlotConfig(
        slot_id="slot_5",
        slot_index=5,
        enabled=False,
        name="总策划 (架构/统筹)",
        icon="👔",
        role_type="lead",
        system_prompt="你是一个高屋建瓴的总策划与架构统筹专家。负责把控全局方向与最终交付验收。",
        provider_id="deepseek",
        model="deepseek-chat",
        allowed_tools=list(ALL_TOOLS),
    ),
]


class AppConfig(BaseModel):
    """全局应用多 API 与多 Agent 配置"""
    providers: List[APIProviderConfig] = Field(default_factory=lambda: [p.model_copy() for p in DEFAULT_PROVIDERS])
    agent_slots: List[AgentSlotConfig] = Field(default_factory=lambda: [s.model_copy() for s in DEFAULT_SLOTS])
    workspace_root: str = Field(default_factory=lambda: str(PROJECT_ROOT))
    sandbox_env_dir: str = Field(default="sandbox_env", description="内置 AI 独立测试沙箱虚拟环境目录")
    max_loops_per_task: int = Field(default=10, description="最大循环接力轮数")
    command_timeout_seconds: int = Field(default=60)
    isolate_all_thinking: bool = Field(
        default=True,
        description="全局开启 AI 思考过程隔离保护 (开启后所有成员的思考过程均不对其他 AI 公开，仅人类在前端监督可见)"
    )

    def get_provider(self, provider_id: str) -> Optional[APIProviderConfig]:
        for p in self.providers:
            if p.id == provider_id:
                return p
        return self.providers[0] if self.providers else None

    def get_slot(self, slot_id_or_index: Any) -> Optional[AgentSlotConfig]:
        for s in self.agent_slots:
            if s.slot_id == str(slot_id_or_index) or s.slot_index == slot_id_or_index:
                return s
        return None

    def get_enabled_slots(self) -> List[AgentSlotConfig]:
        return [s for s in sorted(self.agent_slots, key=lambda x: x.slot_index) if s.enabled]

    @property
    def default_model(self) -> str:
        if self.agent_slots and self.agent_slots[0].model:
            return self.agent_slots[0].model
        if self.providers and self.providers[0].models:
            return self.providers[0].models[0]
        return "deepseek-chat"

    def get_model_for_role(self, role: str) -> str:
        for s in self.agent_slots:
            if s.role_type == role.lower():
                return s.model
        return self.default_model

    def get_resolved_workspace(self) -> Path:
        p = Path(self.workspace_root).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_resolved_sandbox_env(self) -> Path:
        """获取内置 AI 独立隔离测试沙箱虚拟环境路径"""
        p = Path(self.sandbox_env_dir)
        if not p.is_absolute():
            p = (PROJECT_ROOT / p).resolve()
        return p

    def get_sandbox_python_path(self) -> Optional[Path]:
        """获取内置 AI 独立沙箱 Python 解释器路径 (支持全便携式独立 Python 与标准 venv 格式)"""
        sb_env = self.get_resolved_sandbox_env()
        # 1. 独立便携式内置 Python 根目录: sandbox_env/python.exe
        cand1 = sb_env / "python.exe"
        if cand1.exists():
            return cand1
        # 2. 虚拟环境格式: sandbox_env/Scripts/python.exe
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        exe_name = "python.exe" if os.name == "nt" else "python"
        cand2 = sb_env / bin_dir / exe_name
        if cand2.exists():
            return cand2
        # 3. Unix 格式: sandbox_env/bin/python
        cand3 = sb_env / "bin" / "python"
        if cand3.exists():
            return cand3
        return None

    def find_system_python(self) -> Optional[Path]:
        """寻找系统中可用于创建 venv 的真实 Python 解释器"""
        import sys
        if not getattr(sys, "frozen", False):
            if sys.executable and Path(sys.executable).exists():
                return Path(sys.executable)

        # 1. 检查环境变量 PATH
        for name in ["python", "python3", "py"]:
            p = shutil.which(name)
            if p:
                cand = Path(p).resolve()
                if getattr(sys, "frozen", False) and cand == Path(sys.executable).resolve():
                    continue
                if cand.exists():
                    return cand

        # 2. 检查 Windows 常见安装目录
        if sys.platform == "win32":
            import glob
            patterns = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python3*\python.exe"),
                r"C:\Program Files\Python3*\python.exe",
                r"C:\Program Files (x86)\Python3*\python.exe",
                r"C:\Python3*\python.exe",
                r"D:\Python3*\python.exe",
                r"D:\Program Files\Python3*\python.exe",
            ]
            for pat in patterns:
                matches = sorted(glob.glob(pat), reverse=True)
                for m in matches:
                    p = Path(m)
                    if p.exists():
                        return p

            # 3. 检查 Windows 注册表
            try:
                import winreg
                for root_key in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                    try:
                        with winreg.OpenKey(root_key, r"Software\Python\PythonCore") as core_key:
                            num_subkeys, _, _ = winreg.QueryInfoKey(core_key)
                            for i in range(num_subkeys):
                                ver_name = winreg.EnumKey(core_key, i)
                                try:
                                    with winreg.OpenKey(core_key, rf"{ver_name}\InstallPath") as inst_key:
                                        inst_dir, _ = winreg.QueryValueEx(inst_key, "")
                                        if inst_dir:
                                            py = Path(inst_dir) / "python.exe"
                                            if py.exists():
                                                return py
                                except Exception:
                                    pass
                    except Exception:
                        pass
            except Exception:
                pass

        return None

    def ensure_sandbox_env(self) -> Tuple[bool, str]:
        """确保内置 AI 独立沙箱已构建就绪，若不存在则自动静默构建"""
        py_exe = self.get_sandbox_python_path()
        if py_exe and py_exe.exists():
            return True, str(py_exe)

        import sys
        import subprocess
        sb_env = self.get_resolved_sandbox_env()
        python_runner = self.find_system_python()

        if not python_runner:
            return False, "未在系统中检测到 Python 运行环境。独立 EXE 运行模式下，AI 的文件编写与多智能体协同均正常可用；如需运行需 Python 解释器的终端脚本，请在系统中安装 Python 3.10+。"

        try:
            sb_env.parent.mkdir(parents=True, exist_ok=True)
            extra_kwargs = {}
            if sys.platform == "win32":
                extra_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            res = subprocess.run(
                [str(python_runner), "-m", "venv", str(sb_env)],
                capture_output=True,
                **extra_kwargs
            )
            if res.returncode != 0:
                err_msg = res.stderr.decode("utf-8", errors="ignore").strip() or f"exit code {res.returncode}"
                return False, f"创建沙箱虚拟环境失败: {err_msg}"

            py_exe = self.get_sandbox_python_path()
            if py_exe and py_exe.exists():
                return True, str(py_exe)
            return False, "未能生成 sandbox_env Python 解释器"
        except Exception as e:
            return False, f"构建 AI 独立沙箱环境失败: {e}"


    def sanitize(self) -> None:
        """自愈校验：修复任何无效或 Select.NULL / Select.BLANK 的供应商或模型配置"""
        if not self.providers:
            self.providers = [p.model_copy() for p in DEFAULT_PROVIDERS]
        valid_prov_ids = [p.id for p in self.providers]
        default_prov_id = valid_prov_ids[0]

        for s in self.agent_slots:
            if not s.provider_id or str(s.provider_id) in ("Select.NULL", "Select.BLANK", "None", "NULL") or s.provider_id not in valid_prov_ids:
                s.provider_id = default_prov_id
            
            prov = self.get_provider(s.provider_id)
            valid_models = prov.models if (prov and prov.models) else ["deepseek-chat"]
            if not s.model or str(s.model) in ("Select.NULL", "Select.BLANK", "None", "NULL"):
                s.model = valid_models[0]
            
            if not s.allowed_tools:
                s.allowed_tools = list(ALL_TOOLS)

    def save_to_file(self, file_path: Optional[Path] = None) -> None:
        target = file_path or CONFIG_PATH
        self.sanitize()
        try:
            with open(target, "w", encoding="utf-8") as f:
                json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)

            backup_target = BACKUP_CONFIG_PATH
            shutil.copyfile(str(target), str(backup_target))

            primary_key = self.providers[0].api_key if self.providers else ""
            primary_url = self.providers[0].base_url if self.providers else ""
            env_lines = [
                f"# AgentForge 自动持久化配置\n",
                f"OPENAI_API_KEY={primary_key}\n",
                f"OPENAI_BASE_URL={primary_url}\n",
                f"DEFAULT_MODEL={self.default_model}\n",
                f"WORKSPACE_ROOT={self.workspace_root}\n",
                f"MAX_LOOPS_PER_TASK={self.max_loops_per_task}\n",
                f"COMMAND_TIMEOUT_SECONDS={self.command_timeout_seconds}\n",
            ]
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.writelines(env_lines)

        except Exception as e:
            print(f"[Warn] 保存配置文件失败: {e}")

    @classmethod
    def load_from_file(cls, file_path: Optional[Path] = None) -> "AppConfig":
        candidates = [
            file_path,
            CONFIG_PATH,
            BACKUP_CONFIG_PATH,
            Path.cwd() / CONFIG_JSON_FILE,
        ]

        for cand in candidates:
            if cand and cand.exists():
                try:
                    with open(cand, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cfg = cls.model_validate(data)
                    cfg.sanitize()
                    return cfg
                except Exception as e:
                    print(f"[Warn] 读取配置文件 {cand} 异常: {e}")

        env_key = os.getenv("OPENAI_API_KEY", "")
        env_url = os.getenv("OPENAI_BASE_URL", "")
        env_model = os.getenv("DEFAULT_MODEL", "")

        app_cfg = cls()
        if env_key:
            app_cfg.providers[0].api_key = env_key
        if env_url:
            app_cfg.providers[0].base_url = env_url

        if env_model:
            for s in app_cfg.agent_slots:
                s.model = env_model

        app_cfg.save_to_file(CONFIG_PATH)
        return app_cfg


config = AppConfig.load_from_file()
