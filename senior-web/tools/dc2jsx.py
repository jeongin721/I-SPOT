"""온담 시니어 디자인(.dc.html) → React 화면 뼈대.

디자인 보드의 화면 한 장(x-dc 템플릿 + class Component extends DCLogic)을 그대로 옮긴다.
  - src/pages/<Name>.view.jsx : 마크업을 JSX 로(바인딩 {{ x }} → v.x, sc-if → 조건, sc-for → map). 문구 · 구조는 손대지 않는다.
  - src/pages/<Name>.css       : 이 화면에만 있는 규칙(.pg-<Name> 아래로 묶음)
  - src/styles/design.css      : 13화면이 함께 쓰는 규칙
  - src/design/<Name>.logic.js : 디자인의 화면 로직(예시 데이터 포함) — 화면 파일이 이 클래스를 이어받아 데이터만 바꾼다
디자인 링크(X.dc.html)는 PAGE_MAP 대로 '#/화면' 으로 바꾸고, 이번 범위 밖 화면은 '#/Soon?name=X' 로 보낸다.

쓰는 법: python3 tools/dc2jsx.py <디자인 pages 폴더> <senior-web 폴더>
"""

import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

NAMES = [
    "Login", "Home", "Schedule", "CaseList", "CaseRegister", "CaseInfo", "CaseHistory", "SessionDetail",
    "Upload", "Step1Record", "Step2Signals", "Step3Summary", "Step4Next",
]
# 디자인 안의 옛 파일 이름 → 이 앱의 화면 이름
PAGE_MAP = {
    "Login": "Login", "Main": "Home", "Schedule": "Schedule", "CaseList": "CaseList", "CaseRegister": "CaseRegister",
    "CaseDetail": "CaseInfo", "CaseHistory": "CaseHistory", "SessionDetail": "SessionDetail", "UploadModal": "Upload",
    "SttReview": "Step1Record", "SignalReview": "Step2Signals", "NoteWrite": "Step3Summary", "FollowupQ": "Step4Next",
}

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
ATTR = {
    "class": "className", "for": "htmlFor", "tabindex": "tabIndex", "readonly": "readOnly", "maxlength": "maxLength",
    "minlength": "minLength", "inputmode": "inputMode", "colspan": "colSpan", "rowspan": "rowSpan",
    "autocomplete": "autoComplete", "autofocus": "autoFocus", "spellcheck": "spellCheck", "enterkeyhint": "enterKeyHint",
    "datetime": "dateTime", "viewbox": "viewBox", "contenteditable": "contentEditable", "novalidate": "noValidate",
    "xlink:href": "xlinkHref", "srcset": "srcSet", "crossorigin": "crossOrigin", "accesskey": "accessKey",
}
BOOL = {"disabled", "checked", "readonly", "required", "multiple", "selected", "hidden", "open", "novalidate", "autofocus"}
BIND = re.compile(r"\{\{\s*(.*?)\s*\}\}")


def link(m: re.Match) -> str:
    name, frag = m.group(1), m.group(2)
    if name in PAGE_MAP:
        return f"#/{PAGE_MAP[name]}" + (f"?sec={frag}" if frag else "")
    return f"#/Soon?name={name}"


def fix_links(text: str) -> str:
    return re.sub(r"([A-Za-z0-9_]+)\.dc\.html(?:#([\w-]+))?", link, text)


def camel(name: str) -> str:
    head, *rest = name.split("-")
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


class Node:
    def __init__(self, tag, attrs):
        self.tag, self.attrs, self.children = tag, attrs, []


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


class Emit:
    def __init__(self):
        self.loops = []

    def expr(self, path: str) -> str:
        if path in ("true", "false", "null") or re.fullmatch(r"-?\d+(\.\d+)?", path):
            return path
        root = path.split(".")[0]
        return path if root in self.loops else f"v.{path}"

    def value(self, raw: str) -> str:
        """속성 값 → JSX 식(바인딩 하나면 그대로, 섞였으면 템플릿 문자열)."""
        m = BIND.fullmatch(raw.strip())
        if m:
            return self.expr(m.group(1))
        if BIND.search(raw):
            parts = BIND.split(raw)
            out = "`"
            for i, p in enumerate(parts):
                out += ("${" + self.expr(p) + "}") if i % 2 else p.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            return out + "`"
        return json.dumps(raw, ensure_ascii=False)

    @staticmethod
    def lit(raw: str) -> str:
        """JSX 속성 글자(따옴표 · 역슬래시 · 줄바꿈이 있으면 {"..."} 로)."""
        enc = json.dumps(raw, ensure_ascii=False)
        return enc if enc[1:-1] == raw else "{" + enc + "}"

    def style(self, raw: str) -> str:
        items = []
        for decl in re.split(r";(?![^(]*\))", raw):
            if ":" not in decl:
                continue
            prop, val = decl.split(":", 1)
            prop, val = prop.strip(), val.strip()
            key = json.dumps(prop) if prop.startswith("--") else camel(prop)
            if prop.startswith("-ms-"):
                key = "ms" + camel(prop[4:])[:1].upper() + camel(prop[4:])[1:]
            elif prop.startswith("-webkit-"):
                key = "Webkit" + camel(prop[8:])[:1].upper() + camel(prop[8:])[1:]
            items.append(f"{key}: {self.value(val)}")
        return "{{ " + ", ".join(items) + " }}"

    def attrs(self, node: Node) -> str:
        names = {k for k, _ in node.attrs}
        controlled = "sc-camel-on-change" in names or "sc-camel-on-input" in names
        out = []
        for k, raw in node.attrs:
            raw = "" if raw is None else raw
            if k.startswith("hint-"):
                continue
            if k.startswith("sc-camel-"):
                out.append(f"{camel(k[9:])}={{{self.value(raw)}}}")
                continue
            if k == "style":
                out.append(f"style={self.style(raw)}")
                continue
            if k in ("value", "checked") and node.tag in ("input", "textarea", "select") and not controlled:
                k = "defaultValue" if k == "value" else "defaultChecked"
            name = ATTR.get(k, k if k.startswith(("aria-", "data-")) else (camel(k) if "-" in k else k))
            if k == "href":
                raw = fix_links(raw)
            if k in BOOL and raw == "":
                out.append(f"{name}")
            elif BIND.search(raw):
                out.append(f"{name}={{{self.value(raw)}}}")
            else:
                out.append(f"{name}={self.lit(raw)}")
        if node.tag == "form" and "sc-camel-on-submit" not in names:
            out.append("onSubmit={(e) => e.preventDefault()}")
        return (" " + " ".join(out)) if out else ""

    def text(self, data: str) -> str:
        if not data.strip():
            return " " if "\n" not in data and data else ""
        out = []
        for i, p in enumerate(BIND.split(data)):
            if i % 2:
                out.append("{" + self.expr(p) + "}")
            elif p:
                if re.search(r"[{}<>]", p) or p != p.strip():
                    out.append("{" + json.dumps(p, ensure_ascii=False) + "}")
                else:
                    out.append(p)
        return "".join(out)

    def node(self, node, ind: int) -> str:
        pad = "  " * ind
        if isinstance(node, str):
            t = self.text(node)
            return (pad + t + "\n") if t.strip() else ""
        tag = node.tag
        a = dict(node.attrs)
        if tag == "sc-if":
            cond = self.value(a.get("value", "false"))
            inner = "".join(self.node(c, ind + 2) for c in node.children)
            return f"{pad}{{{cond} ? (\n{pad}  <>\n{inner}{pad}  </>\n{pad}) : null}}\n"
        if tag == "sc-for":
            lst, var = self.value(a["list"]), a.get("as", "item")
            self.loops.append(var)
            inner = "".join(self.node(c, ind + 2) for c in node.children)
            self.loops.pop()
            return (
                f"{pad}{{({lst} || []).map(({var}, i_{var}) => (\n{pad}  <Fragment key={{i_{var}}}>\n{inner}"
                f"{pad}  </Fragment>\n{pad}))}}\n"
            )
        if tag.startswith("sc-raw-"):
            tag = tag[7:]
            node = Node(tag, node.attrs)
            node.children = [c for c in Node.__dict__.get("children", [])] if False else []
        if tag in ("helmet", "x-dc"):
            return "".join(self.node(c, ind) for c in getattr(node, "children", []))
        attrs = self.attrs(node)
        kids = getattr(node, "children", [])
        if tag == "textarea" and kids:
            text = "".join(k for k in kids if isinstance(k, str))
            key = "value" if "onChange=" in attrs else "defaultValue"
            if BIND.fullmatch(text.strip() or "x"):
                attrs += f" {key}={{{self.value(text)}}}"
            elif text.strip():
                attrs += f" {key}={self.lit(text)}"
            kids = []
        if tag in VOID or not kids:
            return f"{pad}<{tag}{attrs} />\n"
        inner = "".join(self.node(c, ind + 1) for c in kids)
        if not inner.strip():
            return f"{pad}<{tag}{attrs} />\n"
        return f"{pad}<{tag}{attrs}>\n{inner}{pad}</{tag}>\n"


def raw_children_fix(tree_root):
    """sc-raw-* 는 Node 를 새로 만들지 않고 태그 이름만 바꾼다."""
    stack = [tree_root]
    while stack:
        n = stack.pop()
        if isinstance(n, Node):
            if n.tag.startswith("sc-raw-"):
                n.tag = n.tag[7:]
            stack.extend(n.children)


# ------------------------------------------------------------------ CSS


def rules(css: str):
    out, depth, cur = [], 0, ""
    for ch in css:
        cur += ch
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                out.append(cur.strip())
                cur = ""
    return out


def split_top(sel: str):
    parts, depth, cur = [], 0, ""
    for ch in sel:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def scope(rule: str, cls: str) -> str:
    head, body = rule.split("{", 1)
    head = head.strip()
    if head.startswith("@media") or head.startswith("@supports"):
        inner = body.rsplit("}", 1)[0]
        return head + "{" + "".join(scope(r, cls) for r in rules(inner)) + "}"
    if head.startswith("@"):
        return rule
    sels = []
    for s in split_top(head):
        if re.match(r"^(html|body|:root)\b", s):
            sels.append(s)
        else:
            sels.append(f".{cls} {s}")
    return ",".join(sels) + "{" + body


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    (dst / "src/pages").mkdir(parents=True, exist_ok=True)
    (dst / "src/design").mkdir(parents=True, exist_ok=True)
    (dst / "src/styles").mkdir(parents=True, exist_ok=True)
    per, count = {}, Counter()
    for name in NAMES:
        s = (src / f"{name}.dc.html").read_text(encoding="utf-8")
        css = "".join(re.findall(r"<style>(.*?)</style>", s, re.S))
        per[name] = rules(css)
        count.update(set(per[name]))

        a, b = s.find("</helmet>") + len("</helmet>"), s.find('<script type="text/x-dc"')
        tree = Tree()
        tree.feed(s[a:b])
        raw_children_fix(tree.root)
        body = "".join(Emit().node(c, 3) for c in tree.root.children)
        view = (
            f"// {name} 화면 마크업 — tools/dc2jsx.py 가 디자인({name}.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.\n"
            "/* eslint-disable */\n"
            "import { Fragment } from 'react';\n"
            f"import './{name}.css';\n\n"
            "export default function View({ v }) {\n"
            "  return (\n"
            f"    <div className=\"pg-{name}\">\n{body}    </div>\n"
            "  );\n"
            "}\n"
        )
        (dst / f"src/pages/{name}.view.jsx").write_text(view, encoding="utf-8")

        script = re.search(r'<script type="text/x-dc"[^>]*>(.*?)</script>', s, re.S).group(1)
        script = fix_links(script).replace("class Component extends DCLogic", "export default class DesignLogic extends DCLogic", 1)
        (dst / f"src/design/{name}.logic.js").write_text(
            f"// {name} 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/{name}.jsx)이 이어받아 데이터만 바꾼다.\n"
            "/* eslint-disable */\nimport { DCLogic } from '../dc';\n\n" + script.strip() + "\n",
            encoding="utf-8",
        )

    common = [r for r in per[NAMES[0]] if count[r] == len(NAMES)]
    (dst / "src/styles/design.css").write_text(
        "/* 13화면 공통 규칙 — tools/dc2jsx.py 가 디자인에서 뽑음 */\n" + "\n".join(common) + "\n", encoding="utf-8"
    )
    common_set = set(common)
    for name in NAMES:
        own = [scope(r, f"pg-{name}") for r in per[name] if r not in common_set]
        (dst / f"src/pages/{name}.css").write_text(
            f"/* {name} 화면에만 있는 규칙(.pg-{name} 아래) — tools/dc2jsx.py */\n" + "\n".join(own) + "\n", encoding="utf-8"
        )
    print("ok", len(common), {n: len(per[n]) - len([r for r in per[n] if r in common_set]) for n in NAMES})


if __name__ == "__main__":
    main()
