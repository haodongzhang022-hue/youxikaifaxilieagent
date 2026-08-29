# ============================================================
# 协议生成工具链 (Protocol Toolchain)
# 版本: v1.0
# 对齐: Issue #112「游戏向架构师的开发」· wp_server 协议先行
# 说明: 从 protocol.proto 生成各语言代码的轻量工具链。
#       - 解析 protocol.proto 的 message/enum 定义
#       - 生成 Python dataclass / TS interface / C# class / C++ struct
#       - 支持协议版本管理与向后兼容检查
#
# 设计原则:
#   1. 跨语言: 同一协议定义生成多语言代码
#   2. 版本控制: protocol_version 字段全局递增
#   3. 向后兼容: 字段只增不改，新增字段用 optional 标记
#   4. 纯 Python: 无外部依赖，可在 CI 中直接运行
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# 一、协议解析器
# ============================================================

@dataclass
class ProtoField:
    """协议字段定义"""
    name: str
    type: str
    number: int
    repeated: bool = False
    optional: bool = False
    comment: str = ""


@dataclass
class ProtoMessage:
    """协议消息定义"""
    name: str
    fields: List[ProtoField] = field(default_factory=list)
    comment: str = ""


@dataclass
class ProtoEnum:
    """协议枚举定义"""
    name: str
    values: Dict[str, int] = field(default_factory=dict)
    comment: str = ""


class ProtocolParser:
    """解析 protocol.proto 定义文件"""

    def __init__(self):
        self.messages: Dict[str, ProtoMessage] = {}
        self.enums: Dict[str, ProtoEnum] = {}

    def parse(self, proto_path: str) -> Dict[str, Any]:
        """解析 .proto 文件"""
        content = Path(proto_path).read_text(encoding="utf-8")
        self._parse_content(content)
        return self.to_dict()

    def parse_content(self, content: str) -> Dict[str, Any]:
        """直接解析 proto 文本内容"""
        self._parse_content(content)
        return self.to_dict()

    def _parse_content(self, content: str) -> None:
        """解析 proto 内容"""
        # 提取 message 定义
        message_pattern = re.compile(
            r'message\s+(\w+)\s*\{([^}]*)\}', re.DOTALL)
        for match in message_pattern.finditer(content):
            name = match.group(1)
            body = match.group(2)
            msg = ProtoMessage(name=name)
            self._parse_message_fields(msg, body)
            self.messages[name] = msg

        # 提取 enum 定义
        enum_pattern = re.compile(
            r'enum\s+(\w+)\s*\{([^}]*)\}', re.DOTALL)
        for match in enum_pattern.finditer(content):
            name = match.group(1)
            body = match.group(2)
            enum = ProtoEnum(name=name)
            for line in body.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                parts = line.split("=")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = int(parts[1].split(";")[0].strip())
                    enum.values[key] = val
            self.enums[name] = enum

    def _parse_message_fields(self, msg: ProtoMessage, body: str) -> None:
        """解析 message 字段"""
        for line in body.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            # 提取注释
            comment = ""
            if "//" in line:
                line, comment = line.split("//", 1)
                comment = comment.strip()

            line = line.rstrip(";").strip()
            parts = line.split()
            if len(parts) < 3:
                continue

            # 检测 repeated / optional
            repeated = "repeated" in parts
            optional = "optional" in parts
            if repeated:
                parts = [p for p in parts if p != "repeated"]
            if optional:
                parts = [p for p in parts if p != "optional"]

            if len(parts) >= 3:
                ftype, fname = parts[0], parts[1]
                # 从剩余部分提取字段编号
                fnum_str = ""
                for p in parts[2:]:
                    if p.startswith("="):
                        fnum_str = p[1:].strip()
                    elif "=" in p:
                        fnum_str = p.split("=")[1].strip()
                msg.fields.append(ProtoField(
                    name=fname,
                    type=ftype,
                    number=int(fnum_str) if fnum_str else 0,
                    repeated=repeated,
                    optional=optional,
                    comment=comment,
                ))

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict"""
        return {
            "messages": {
                name: {
                    "name": m.name,
                    "fields": [
                        {
                            "name": f.name,
                            "type": f.type,
                            "number": f.number,
                            "repeated": f.repeated,
                            "optional": f.optional,
                            "comment": f.comment,
                        }
                        for f in m.fields
                    ],
                }
                for name, m in self.messages.items()
            },
            "enums": {
                name: {"name": e.name, "values": e.values}
                for name, e in self.enums.items()
            },
        }


# ============================================================
# 二、代码生成器（多语言）
# ============================================================

class ProtocolCodegen:
    """从协议定义生成各语言代码"""

    def __init__(self, parsed: Dict[str, Any]):
        self.parsed = parsed
        self.messages = parsed["messages"]
        self.enums = parsed["enums"]

    # ---- Python ----
    def generate_python(self, module_name: str = "generated_protocol.py") -> str:
        """生成 Python dataclass 代码"""
        lines = [
            '"""自动生成的协议定义（从 protocol.proto 生成）"""',
            "from __future__ import annotations",
            "from dataclasses import dataclass, field",
            "from typing import Any, Dict, List, Optional",
            "",
        ]

        # 生成枚举
        for enum_name, enum in self.enums.items():
            lines.append(f"class {enum_name}:")

            for value_name, value in enum["values"].items():
                lines.append(f"    {value_name} = {value}")
            lines.append("")
            lines.append("")

        # 生成消息
        for msg_name, msg in self.messages.items():
            lines.append("@dataclass")
            lines.append(f"class {msg_name}:")

            fields = msg["fields"]
            if not fields:
                lines.append("    pass")
            else:
                for f in fields:
                    ftype = self._py_type(f["type"])
                    default = ""
                    if f["repeated"]:
                        default = " = field(default_factory=list)"
                    elif f["optional"]:
                        default = " = None"
                    elif ftype == "str":
                        default = ' = ""'
                    elif ftype == "int":
                        default = " = 0"
                    elif ftype == "bool":
                        default = " = False"
                    lines.append(
                        f"    {f['name']}: {ftype}{default}"
                        f"  # field {f['number']}"
                    )
            lines.append("")
            lines.append("")

        return "\n".join(lines)

    # ---- TypeScript ----
    def generate_typescript(self) -> str:
        """生成 TypeScript interface 代码"""
        lines = [
            "// 自动生成的协议定义（从 protocol.proto 生成）",
            "",
        ]

        # 生成枚举
        for enum_name, enum in self.enums.items():
            lines.append(f"export enum {enum_name} {{")
            for value_name, value in enum["values"].items():
                lines.append(f"  {value_name} = {value},")
            lines.append("}")
            lines.append("")

        # 生成接口
        for msg_name, msg in self.messages.items():
            lines.append(f"export interface {msg_name} {{")
            for f in msg["fields"]:
                ftype = self._ts_type(f["type"])
                optional = "?" if f["optional"] else ""
                if f["repeated"]:
                    ftype = f"{ftype}[]"
                lines.append(f"  {f['name']}{optional}: {ftype};")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    # ---- C# ----
    def generate_csharp(self) -> str:
        """生成 C# class 代码"""
        lines = [
            "// 自动生成的协议定义（从 protocol.proto 生成）",
            "using System;",
            "using System.Collections.Generic;",
            "",
            "namespace Game.Protocol",
            "{",
        ]

        # 生成枚举
        for enum_name, enum in self.enums.items():
            lines.append(f"    public enum {enum_name} {{")
            for value_name, value in enum["values"].items():
                lines.append(f"        {value_name} = {value},")
            lines.append("    }")
            lines.append("")

        # 生成类
        for msg_name, msg in self.messages.items():
            lines.append(f"    [Serializable]")
            lines.append(f"    public class {msg_name} {{")
            for f in msg["fields"]:
                ftype = self._cs_type(f["type"])
                if f["repeated"]:
                    ftype = f"List<{ftype}>"
                    lines.append(f"        public {ftype} {f['name']} = new {ftype}();")
                else:
                    lines.append(f"        public {ftype} {f['name']} {{ get; set; }}")
            lines.append("    }")
            lines.append("")

        lines.append("}")
        return "\n".join(lines)

    # ---- C++ ----
    def generate_cpp(self) -> str:
        """生成 C++ struct 代码"""
        lines = [
            "// 自动生成的协议定义（从 protocol.proto 生成）",
            "#pragma once",
            "#include <string>",
            "#include <vector>",
            "#include <cstdint>",
            "",
            "namespace game_protocol {",
            "",
        ]

        # 生成枚举
        for enum_name, enum in self.enums.items():
            lines.append(f"enum class {enum_name} {{")
            for value_name, value in enum["values"].items():
                lines.append(f"    {value_name} = {value},")
            lines.append("};")
            lines.append("")

        # 生成结构体
        for msg_name, msg in self.messages.items():
            lines.append(f"struct {msg_name} {{")
            for f in msg["fields"]:
                ftype = self._cpp_type(f["type"])
                if f["repeated"]:
                    ftype = f"std::vector<{ftype}>"
                lines.append(f"    {ftype} {f['name']};")
            lines.append("};")
            lines.append("")

        lines.append("}  // namespace game_protocol")
        return "\n".join(lines)

    # ---- 类型映射 ----
    def _py_type(self, proto_type: str) -> str:
        mapping = {
            "string": "str",
            "int32": "int",
            "int64": "int",
            "bool": "bool",
            "bytes": "bytes",
        }
        return mapping.get(proto_type, proto_type)

    def _ts_type(self, proto_type: str) -> str:
        mapping = {
            "string": "string",
            "int32": "number",
            "int64": "number",
            "bool": "boolean",
            "bytes": "Uint8Array",
        }
        return mapping.get(proto_type, proto_type)

    def _cs_type(self, proto_type: str) -> str:
        mapping = {
            "string": "string",
            "int32": "int",
            "int64": "long",
            "bool": "bool",
            "bytes": "byte[]",
        }
        return mapping.get(proto_type, proto_type)

    def _cpp_type(self, proto_type: str) -> str:
        mapping = {
            "string": "std::string",
            "int32": "int32_t",
            "int64": "int64_t",
            "bool": "bool",
            "bytes": "std::vector<uint8_t>",
        }
        return mapping.get(proto_type, proto_type)


# ============================================================
# 三、协议版本与兼容性检查
# ============================================================

class ProtocolVersionManager:
    """协议版本管理与向后兼容检查"""

    def __init__(self, current_version: str = "1.0"):
        self.current_version = current_version

    def check_backward_compat(self, old_schema: Dict[str, Any],
                              new_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查新 schema 是否向后兼容旧 schema。

        兼容规则:
          - 不删除已有字段
          - 不修改已有字段类型
          - 新增字段必须标记 optional 或 renumber
        """
        violations = []

        old_msgs = old_schema.get("messages", {})
        new_msgs = new_schema.get("messages", {})

        for msg_name, old_msg in old_msgs.items():
            if msg_name not in new_msgs:
                violations.append(f"消息 '{msg_name}' 被删除")
                continue

            old_fields = {f["name"]: f for f in old_msg["fields"]}
            new_fields = {f["name"]: f for f in new_msgs[msg_name]["fields"]}

            for field_name, old_field in old_fields.items():
                if field_name not in new_fields:
                    violations.append(f"字段 '{msg_name}.{field_name}' 被删除")
                    continue

                new_field = new_fields[field_name]
                if old_field["type"] != new_field["type"]:
                    violations.append(
                        f"字段 '{msg_name}.{field_name}' 类型从 {old_field['type']} 变为 {new_field['type']}")

        return {
            "backward_compatible": len(violations) == 0,
            "violations": violations,
            "version": self.current_version,
        }


# ============================================================
# 四、入口
# ============================================================

def main():
    """主入口：解析 protocol.proto 并生成各语言代码"""
    import os

    proto_path = os.path.join(os.path.dirname(__file__), "..", "..", "server", "proto", "protocol.proto")
    proto_path = os.path.abspath(proto_path)

    parser = ProtocolParser()
    parsed = parser.parse(proto_path)
    codegen = ProtocolCodegen(parsed)

    print("=== 协议生成工具链 ===")
    print()
    print(f"解析 message 数: {len(parsed['messages'])}")
    print(f"解析 enum 数: {len(parsed['enums'])}")
    print()

    # 生成 Python
    py_code = codegen.generate_python()
    print(f"Python 代码生成: {len(py_code.splitlines())} 行")
    print()

    # 生成 TS
    ts_code = codegen.generate_typescript()
    print(f"TypeScript 代码生成: {len(ts_code.splitlines())} 行")
    print()

    # 生成 C#
    cs_code = codegen.generate_csharp()
    print(f"C# 代码生成: {len(cs_code.splitlines())} 行")
    print()

    # 生成 C++
    cpp_code = codegen.generate_cpp()
    print(f"C++ 代码生成: {len(cpp_code.splitlines())} 行")
    print()

    # 版本兼容检查
    manager = ProtocolVersionManager()
    result = manager.check_backward_compat(parsed, parsed)  # 自比较
    print(f"向后兼容检查: {result['backward_compatible']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
