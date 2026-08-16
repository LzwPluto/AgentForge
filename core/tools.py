import os
import sys
import re
import difflib
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from config import config


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    def to_string(self) -> str:
        if self.success:
            return self.output
        return f"Error: {self.error}\nOutput:\n{self.output}" if self.output else f"Error: {self.error}"


class SandboxTools:
    """沙箱文件与系统执行工具集"""

    @staticmethod
    def _resolve_path(rel_or_abs_path: str) -> Path:
        """安全解析路径到工作区沙箱"""
        ws = config.get_resolved_workspace()
        target = Path(rel_or_abs_path)
        if not target.is_absolute():
            target = (ws / target).resolve()
        else:
            target = target.resolve()
        return target

    @classmethod
    def view_file(
        cls,
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> ToolResult:
        """查看文件内容，支持按行范围切片展示"""
        try:
            target_path = cls._resolve_path(path)
            if not target_path.exists():
                return ToolResult(success=False, output="", error=f"文件不存在: {path}")
            if target_path.is_dir():
                return ToolResult(success=False, output="", error=f"目标是目录而非文件: {path}")

            # 尝试常见编码读取
            content = ""
            for encoding in ("utf-8", "gbk", "utf-16", "latin-1"):
                try:
                    with open(target_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            lines = content.splitlines(keepends=True)
            total_lines = len(lines)

            s = 1 if start_line is None or start_line < 1 else start_line
            e = total_lines if end_line is None or end_line > total_lines else end_line

            if s > total_lines:
                return ToolResult(
                    success=True,
                    output=f"文件共有 {total_lines} 行，指定起始行 {s} 超出范围。",
                    data={"total_lines": total_lines, "lines": []},
                )

            selected_lines = lines[s - 1 : e]
            formatted_output = [f"File: {path} (Lines {s}-{e} of {total_lines})"]
            for idx, line in enumerate(selected_lines, start=s):
                clean_line = line.rstrip("\r\n")
                formatted_output.append(f"{idx:4d} | {clean_line}")

            return ToolResult(
                success=True,
                output="\n".join(formatted_output),
                data={"total_lines": total_lines, "start_line": s, "end_line": e},
            )
        except Exception as ex:
            return ToolResult(success=False, output="", error=f"读取文件失败: {str(ex)}")

    @classmethod
    def write_file(cls, path: str, content: str, overwrite: bool = True) -> ToolResult:
        """创建或覆写文件"""
        try:
            target_path = cls._resolve_path(path)
            if target_path.exists() and not overwrite:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文件已存在且 overwrite=False: {path}",
                )

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)

            line_count = len(content.splitlines())
            return ToolResult(
                success=True,
                output=f"成功写入文件 {path} (共 {line_count} 行, {len(content.encode('utf-8'))} 字节)",
                data={"path": str(target_path), "line_count": line_count},
            )
        except Exception as ex:
            return ToolResult(success=False, output="", error=f"写入文件失败: {str(ex)}")

    @classmethod
    def edit_file_exact(
        cls,
        path: str,
        target_content: str,
        replacement_content: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> ToolResult:
        """精准替换指定文件中的代码片段（严格按内容匹配，防止模型幻觉篡改其它代码）"""
        try:
            target_path = cls._resolve_path(path)
            if not target_path.exists():
                return ToolResult(success=False, output="", error=f"文件不存在: {path}")

            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                original_text = f.read()

            normalized_target = target_content.replace("\r\n", "\n")
            normalized_replacement = replacement_content.replace("\r\n", "\n")
            normalized_orig = original_text.replace("\r\n", "\n")

            if start_line is not None or end_line is not None:
                lines = normalized_orig.splitlines(keepends=True)
                total_lines = len(lines)
                s = 1 if start_line is None else max(1, start_line)
                e = total_lines if end_line is None else min(total_lines, end_line)

                prefix = "".join(lines[: s - 1])
                search_region = "".join(lines[s - 1 : e])
                suffix = "".join(lines[e:])

                matches = search_region.count(normalized_target)
                if matches == 0:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"在指定行范围 [{s}, {e}] 未找到匹配的目标内容。请使用 view_file 查看最新行号与代码后再替换。",
                    )
                elif matches > 1:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"在指定行范围 [{s}, {e}] 找到 {matches} 处重复匹配。请提供更多上下文行以确保唯一性。",
                    )

                new_region = search_region.replace(normalized_target, normalized_replacement, 1)
                new_full_text = prefix + new_region + suffix
            else:
                matches = normalized_orig.count(normalized_target)
                if matches == 0:
                    return ToolResult(
                        success=False,
                        output="",
                        error="在整个文件中未找到匹配的目标内容。请确保缩进、空格与换行完全一致，或先通过 view_file 确认内容。",
                    )
                elif matches > 1:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"在文件中找到 {matches} 处完全相同的目标内容。请指定 start_line/end_line 范围或包含更多上下文代码。",
                    )

                new_full_text = normalized_orig.replace(normalized_target, normalized_replacement, 1)

            # 写回文件
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_full_text)

            # 生成 Diff 摘要
            diff = difflib.unified_diff(
                normalized_orig.splitlines(keepends=True),
                new_full_text.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=3,
            )
            diff_text = "".join(diff)

            return ToolResult(
                success=True,
                output=f"成功编辑文件 {path}。\n\n--- Diff ---\n{diff_text}",
                data={"diff": diff_text, "path": str(target_path)},
            )
        except Exception as ex:
            return ToolResult(success=False, output="", error=f"编辑文件失败: {str(ex)}")

    @classmethod
    def list_dir(
        cls,
        path: str = ".",
        max_depth: int = 3,
        show_hidden: bool = False,
    ) -> ToolResult:
        """递归列出目录结构与文件大小"""
        try:
            target_path = cls._resolve_path(path)
            if not target_path.exists():
                return ToolResult(success=False, output="", error=f"目录不存在: {path}")
            if not target_path.is_dir():
                return ToolResult(success=False, output="", error=f"目标是文件而非目录: {path}")

            tree_lines = [f"Directory: {target_path}"]

            def _walk(current: Path, depth: int, prefix: str = ""):
                if depth > max_depth:
                    return
                try:
                    entries = sorted(list(current.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
                except PermissionError:
                    tree_lines.append(f"{prefix}└── [权限拒绝]")
                    return

                # 忽略常见无关目录
                ignore_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".idea", ".vscode", "node_modules", "dist", "build"}
                entries = [e for e in entries if (show_hidden or not e.name.startswith(".")) and e.name not in ignore_dirs]

                for idx, entry in enumerate(entries):
                    is_last = idx == len(entries) - 1
                    connector = "└── " if is_last else "├── "
                    sub_prefix = "    " if is_last else "│   "

                    if entry.is_dir():
                        tree_lines.append(f"{prefix}{connector}📁 {entry.name}/")
                        _walk(entry, depth + 1, prefix + sub_prefix)
                    else:
                        size_str = cls._format_size(entry.stat().st_size)
                        tree_lines.append(f"{prefix}{connector}📄 {entry.name} ({size_str})")

            _walk(target_path, 1)
            return ToolResult(success=True, output="\n".join(tree_lines))
        except Exception as ex:
            return ToolResult(success=False, output="", error=f"遍历目录失败: {str(ex)}")

    @classmethod
    def grep_search(
        cls,
        query: str,
        path: str = ".",
        is_regex: bool = False,
        case_sensitive: bool = False,
        file_pattern: Optional[str] = None,
    ) -> ToolResult:
        """在目录或文件中搜索文本关键字或正则"""
        try:
            target_path = cls._resolve_path(path)
            if not target_path.exists():
                return ToolResult(success=False, output="", error=f"搜索路径不存在: {path}")

            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(query if is_regex else re.escape(query), flags)

            ignore_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".idea", ".vscode", "node_modules"}
            matched_lines = []

            def _search_file(f_path: Path):
                if file_pattern and not f_path.match(file_pattern):
                    return
                try:
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_idx, line in enumerate(f, start=1):
                            if pattern.search(line):
                                rel = f_path.relative_to(config.get_resolved_workspace())
                                matched_lines.append(f"{rel}:{line_idx}: {line.strip()}")
                except Exception:
                    pass

            if target_path.is_file():
                _search_file(target_path)
            else:
                for root, dirs, files in os.walk(target_path):
                    dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
                    for file_name in files:
                        _search_file(Path(root) / file_name)

            if not matched_lines:
                return ToolResult(success=True, output=f"未找到与 '{query}' 相关的匹配内容。")

            capped_results = matched_lines[:60]
            summary = f"找到 {len(matched_lines)} 处匹配"
            if len(matched_lines) > 60:
                summary += " (已截取前 60 条结果)"
            summary += ":\n" + "\n".join(capped_results)

            return ToolResult(success=True, output=summary, data={"total_matches": len(matched_lines)})
        except Exception as ex:
            return ToolResult(success=False, output="", error=f"检索失败: {str(ex)}")

    @classmethod
    async def run_command(
        cls,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> ToolResult:
        """异步执行 Shell/PowerShell 终端命令，捕获标准输出与错误输出"""
        try:
            work_dir = cls._resolve_path(cwd) if cwd else config.get_resolved_workspace()
            work_dir.mkdir(parents=True, exist_ok=True)
            timeout_sec = timeout or config.command_timeout_seconds

            # 确保 AI 专用独立隔离沙箱虚拟环境就绪
            config.ensure_sandbox_env()
            sb_env_path = config.get_resolved_sandbox_env()
            sb_py = config.get_sandbox_python_path()

            # 构建强隔离环境变量：将 AI 专用沙箱 bin/Scripts/根目录 置于 PATH 最前列，注入 VIRTUAL_ENV 并清空干扰
            isolated_env = os.environ.copy()
            path_entries = []
            if sb_py and sb_py.exists():
                path_entries.append(str(sb_py.parent))
            scripts_dir = sb_env_path / ("Scripts" if os.name == "nt" else "bin")
            if scripts_dir.exists() and str(scripts_dir) not in path_entries:
                path_entries.append(str(scripts_dir))

            if path_entries:
                isolated_env["PATH"] = f"{os.pathsep.join(path_entries)}{os.pathsep}{isolated_env.get('PATH', '')}"
                isolated_env["VIRTUAL_ENV"] = str(sb_env_path)
            isolated_env.pop("PYTHONPATH", None)
            isolated_env.pop("PYTHONHOME", None)

            # 创建子进程在独立沙箱中异步执行 (Windows 下静默隐藏控制台窗口)
            extra_kwargs = {}
            if sys.platform == "win32":
                extra_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(work_dir),
                env=isolated_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **extra_kwargs
            )


            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(), timeout=float(timeout_sec)
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                return ToolResult(
                    success=False,
                    output="",
                    error=f"命令执行超时 ({timeout_sec}s): {command}",
                )

            # 解码输出 (适配 Windows 常见编码)
            def _decode(raw: bytes) -> str:
                for enc in ("utf-8", "gbk", "cp936", "latin-1"):
                    try:
                        return raw.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return raw.decode("utf-8", errors="replace")

            stdout_str = _decode(stdout_data).strip()
            stderr_str = _decode(stderr_data).strip()
            exit_code = proc.returncode

            combined_output = []
            if stdout_str:
                combined_output.append(f"STDOUT:\n{stdout_str}")
            if stderr_str:
                combined_output.append(f"STDERR:\n{stderr_str}")

            output_text = "\n\n".join(combined_output) if combined_output else "(No output)"

            if exit_code == 0:
                return ToolResult(
                    success=True,
                    output=f"命令执行成功 (Exit code: 0)\n{output_text}",
                    data={"exit_code": 0, "stdout": stdout_str, "stderr": stderr_str},
                )
            else:
                return ToolResult(
                    success=False,
                    output=output_text,
                    error=f"命令执行返回非零状态码: {exit_code}",
                    data={"exit_code": exit_code, "stdout": stdout_str, "stderr": stderr_str},
                )
        except Exception as ex:
            return ToolResult(success=False, output="", error=f"执行命令异常: {str(ex)}")

    @classmethod
    def get_git_diff(cls, path: Optional[str] = None) -> ToolResult:
        """获取工作区或特定文件的 Git Diff 变更"""
        try:
            ws = config.get_resolved_workspace()
            if not (ws / ".git").exists():
                return ToolResult(
                    success=True,
                    output="当前工作区暂未初始化 Git 仓库。\n（Agent 仍可正常进行精准文件读写与自闭环编码，可在终端运行 git init 开启 Diff 追踪）",
                )

            cmd = ["git", "diff", "--no-color"]
            if path:
                cmd.append(path)

            extra_kwargs = {}
            if sys.platform == "win32":
                extra_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            res = subprocess.run(
                cmd,
                cwd=str(ws),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                **extra_kwargs
            )
            if res.returncode == 0:
                diff_output = res.stdout.strip()
                if not diff_output:
                    return ToolResult(success=True, output="当前工作区代码暂无未提交变动 (Working tree clean)")
                return ToolResult(success=True, output=diff_output, data={"diff": diff_output})
            else:
                return ToolResult(success=True, output="当前工作区代码暂无未提交变动 (Working tree clean)")
        except Exception as ex:
            return ToolResult(success=True, output="工作区就绪，暂无 Diff 变动记录。")


    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """友好格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"


# OpenAI 兼容格式的 Tool 定义
OPENAI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "view_file",
            "description": "查看指定文件的代码内容，支持按行号范围切片展示。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对工作区或绝对文件路径"},
                    "start_line": {"type": "integer", "description": "起始行号 (1-indexed, 可选)"},
                    "end_line": {"type": "integer", "description": "结束行号 (1-indexed, 可选)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "创建新文件或完全覆盖已有文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的完整文件内容"},
                    "overwrite": {"type": "boolean", "description": "是否允许覆盖已有文件，默认为 true"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file_exact",
            "description": "高精度局部代码重构与替换。目标内容必须与文件现有代码精确匹配（包括缩进与换行）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目标文件路径"},
                    "target_content": {"type": "string", "description": "需要被替换的精确原代码块"},
                    "replacement_content": {"type": "string", "description": "替换后的新代码块"},
                    "start_line": {"type": "integer", "description": "搜索起始行范围 (可选)"},
                    "end_line": {"type": "integer", "description": "搜索结束行范围 (可选)"},
                },
                "required": ["path", "target_content", "replacement_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "递归查看工作区目录结构树与文件大小，了解项目架构。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认为 '.'"},
                    "max_depth": {"type": "integer", "description": "最大递归深度，默认为 3"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "在项目中按关键字或正则表达式搜索包含特定类、函数或变量的文件与行号。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键字或正则匹配模式"},
                    "path": {"type": "string", "description": "搜索根目录，默认为 '.'"},
                    "is_regex": {"type": "boolean", "description": "是否为正则表达式，默认为 false"},
                    "file_pattern": {"type": "string", "description": "匹配的文件通配符模式 (如 *.py)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在终端中异步执行 Shell/PowerShell 命令（如运行 pytest 测试、执行构建脚本、安装依赖等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要在终端执行的命令字符串"},
                    "cwd": {"type": "string", "description": "执行目录 (可选，默认为工作区根目录)"},
                    "timeout": {"type": "integer", "description": "超时时间（秒，可选）"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_git_diff",
            "description": "查看当前工作区或特定文件的 Git Diff 代码变更细节。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "指定文件路径 (可选，留空则查看全部变动)"},
                },
            },
        },
    },
]


class ToolDispatcher:
    """工具调用调度器"""

    @classmethod
    async def dispatch(cls, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """根据工具名称分发执行"""
        if tool_name == "view_file":
            return SandboxTools.view_file(
                path=arguments.get("path", ""),
                start_line=arguments.get("start_line"),
                end_line=arguments.get("end_line"),
            )
        elif tool_name == "write_file":
            return SandboxTools.write_file(
                path=arguments.get("path", ""),
                content=arguments.get("content", ""),
                overwrite=arguments.get("overwrite", True),
            )
        elif tool_name == "edit_file_exact":
            return SandboxTools.edit_file_exact(
                path=arguments.get("path", ""),
                target_content=arguments.get("target_content", ""),
                replacement_content=arguments.get("replacement_content", ""),
                start_line=arguments.get("start_line"),
                end_line=arguments.get("end_line"),
            )
        elif tool_name == "list_dir":
            return SandboxTools.list_dir(
                path=arguments.get("path", "."),
                max_depth=arguments.get("max_depth", 3),
            )
        elif tool_name == "grep_search":
            return SandboxTools.grep_search(
                query=arguments.get("query", ""),
                path=arguments.get("path", "."),
                is_regex=arguments.get("is_regex", False),
                file_pattern=arguments.get("file_pattern"),
            )
        elif tool_name == "run_command":
            return await SandboxTools.run_command(
                command=arguments.get("command", ""),
                cwd=arguments.get("cwd"),
                timeout=arguments.get("timeout"),
            )
        elif tool_name == "get_git_diff":
            return SandboxTools.get_git_diff(
                path=arguments.get("path"),
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"未知工具名称: '{tool_name}'",
            )
