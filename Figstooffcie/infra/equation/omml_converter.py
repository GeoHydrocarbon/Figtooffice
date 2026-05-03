from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from latex2mathml.converter import convert as latex_to_mathml
from lxml import etree


DEFAULT_XSL_CANDIDATES = [
    Path(r"C:\Program Files\Microsoft Office\Office16\MML2OMML.XSL"),
    Path(r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL"),
    Path(r"C:\Program Files (x86)\Microsoft Office\Office16\MML2OMML.XSL"),
    Path(r"C:\Program Files (x86)\Microsoft Office\root\Office16\MML2OMML.XSL"),
]


def find_mml2omml_xsl() -> Path:
    for candidate in DEFAULT_XSL_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "未找到 MML2OMML.XSL。请在本机安装 Microsoft Word。"
    )


class OmmlConverter:
    def __init__(self, xsl_path: Path | None = None) -> None:
        actual_path = xsl_path or find_mml2omml_xsl()
        self.transform = etree.XSLT(etree.parse(str(actual_path)))

    def to_omml(self, latex: str):
        mathml = latex_to_mathml(latex)
        mathml_root = etree.fromstring(mathml.encode("utf-8"))
        omml_tree = self.transform(mathml_root)
        return deepcopy(omml_tree.getroot())
