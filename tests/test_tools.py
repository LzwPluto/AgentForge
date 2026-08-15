import os
import pytest
import asyncio
from pathlib import Path
from core.tools import SandboxTools, ToolDispatcher
from config import config


@pytest.fixture
def temp_workspace(tmp_path):
    orig_ws = config.workspace_root
    config.workspace_root = str(tmp_path)
    yield tmp_path
    config.workspace_root = orig_ws


def test_write_and_view_file(temp_workspace):
    file_rel = "demo/hello.py"
    content = "def hello():\n    print('Hello World')\n\nif __name__ == '__main__':\n    hello()\n"
    
    # 1. 写文件
    res = SandboxTools.write_file(file_rel, content)
    assert res.success is True
    assert "成功写入" in res.output

    # 2. 读文件 (完整)
    res_view = SandboxTools.view_file(file_rel)
    assert res_view.success is True
    assert "Hello World" in res_view.output
    assert "1 | def hello():" in res_view.output

    # 3. 读文件 (按行范围)
    res_slice = SandboxTools.view_file(file_rel, start_line=2, end_line=3)
    assert res_slice.success is True
    assert "2 |     print('Hello World')" in res_slice.output


def test_edit_file_exact(temp_workspace):
    file_rel = "math_util.py"
    content = "def add(a, b):\n    return a - b\n"
    SandboxTools.write_file(file_rel, content)

    # 精确替换 bug 代码 a - b -> a + b
    res_edit = SandboxTools.edit_file_exact(
        path=file_rel,
        target_content="return a - b",
        replacement_content="return a + b",
    )
    assert res_edit.success is True
    assert "+    return a + b" in res_edit.output

    # 再次读取验证
    res_view = SandboxTools.view_file(file_rel)
    assert "return a + b" in res_view.output


def test_list_dir_and_grep(temp_workspace):
    SandboxTools.write_file("src/a.py", "def test_alpha(): pass\n")
    SandboxTools.write_file("src/b.py", "def test_beta(): pass\n")

    # list_dir
    res_list = SandboxTools.list_dir(".")
    assert res_list.success is True
    assert "src/" in res_list.output
    assert "a.py" in res_list.output

    # grep_search
    res_grep = SandboxTools.grep_search("test_beta", ".")
    assert res_grep.success is True
    assert "test_beta" in res_grep.output
    assert "b.py" in res_grep.output


@pytest.mark.asyncio
async def test_run_command_async(temp_workspace):
    # 执行跨平台简单的 echo 命令
    res = await SandboxTools.run_command("python -c \"print('Sandbox Test OK')\"")
    assert res.success is True
    assert "Sandbox Test OK" in res.output
