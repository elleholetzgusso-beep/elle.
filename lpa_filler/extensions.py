"""Preserva tudo o que o openpyxl descarta ao gravar um .xlsm.

Ao gravar, o openpyxl perde: imagens, gráficos (charts), desenhos (drawings),
``printerSettings``, as extensões x14 (dropdowns / formatação condicional) e
algumas entradas de Content_Types. Macros e PivotTable sobrevivem como *partes*,
mas as referências podem ficar inconsistentes.

Estratégia (``preserve``): usar o ficheiro do openpyxl como base (estilos, dados,
fórmulas e mesclas corretos) e, sobre ele:

1. Enxertar a "cauda" original de cada worksheet — de ``<pageMargins>`` até
   ``</worksheet>`` — que traz ``pageSetup``, ``headerFooter``, ``<drawing>`` e o
   ``<extLst>`` (dropdowns/formatação condicional), tudo com os r:id originais.
2. Restaurar verbatim as partes auxiliares originais (drawings, charts, media,
   printerSettings, pivotTables, pivotCache e os respetivos _rels).
3. Repor as entradas em falta em ``[Content_Types].xml``.
4. Garantir ``xmlns:r`` no elemento raiz das worksheets onde foi enxertada cauda.
5. (Opcional) expandir os intervalos ``<xm:sqref>`` para cobrir as linhas geradas.

Partes legitimamente substituídas (``sharedStrings``, ``calcChain``) não são
restauradas — o openpyxl/Excel tratam delas.
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

_R_NS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
_DROP = {"xl/sharedStrings.xml", "xl/calcChain.xml"}
_FORCE_ORIGINAL_PREFIXES = (
    "xl/worksheets/_rels/",
    "xl/drawings/",
    "xl/charts/",
    "xl/media/",
    "xl/printerSettings/",
    "xl/pivotTables/",
    "xl/pivotCache/",
)


def _attr(tag: str, name: str) -> str | None:
    m = re.search(rf'\b{re.escape(name)}="([^"]*)"', tag)
    return m.group(1) if m else None


def _sheet_name_to_path(z: zipfile.ZipFile) -> dict[str, str]:
    """Mapeia nome de aba -> caminho do XML (robusto à ordem dos atributos)."""
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    rid_to_target: dict[str, str] = {}
    for tag in re.findall(r"<Relationship\b[^>]*/?>", rels):
        rid, target = _attr(tag, "Id"), _attr(tag, "Target")
        if rid and target:
            rid_to_target[rid] = target
    out: dict[str, str] = {}
    for tag in re.findall(r"<sheet\b[^>]*/?>", wb):
        name, rid = _attr(tag, "name"), _attr(tag, "r:id")
        target = rid_to_target.get(rid) if rid else None
        if name and target:
            target = target.lstrip("/")
            out[name] = target if target.startswith("xl/") else f"xl/{target}"
    return out


def _merge_root_ns(out_xml: str, tpl_xml: str) -> str:
    """Garante que o root <worksheet> do output declara todos os namespaces
    (xmlns:*, mc:Ignorable) usados pela cauda original — senão a extLst com
    `xr:uid`/`x14`/`mc` gera "unbound prefix"."""
    i = out_xml.index("<worksheet")
    j = out_xml.index(">", i)
    out_root = out_xml[i:j]
    t_i = tpl_xml.index("<worksheet")
    t_root = tpl_xml[t_i : tpl_xml.index(">", t_i)]
    additions = ""
    for attr in re.findall(r'(?:xmlns(?::\w+)?|mc:Ignorable)="[^"]*"', t_root):
        key = attr.split("=", 1)[0]
        if re.search(rf"\b{re.escape(key)}=", out_root) is None:
            additions += " " + attr
    if not additions:
        return out_xml
    return out_xml[:j] + additions + out_xml[j:]


def _expand_sqref(xml: str, max_row: int) -> str:
    def repl(m: re.Match) -> str:
        ranges = []
        for token in m.group(1).split():
            mm = re.fullmatch(r"([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?", token)
            if not mm:
                ranges.append(token)
                continue
            c1, r1, c2, _ = mm.groups()
            ranges.append(f"{c1}{r1}:{c2 or c1}{max(max_row, int(r1))}")
        return "<xm:sqref>" + " ".join(ranges) + "</xm:sqref>"

    return re.sub(r"<xm:sqref>(.*?)</xm:sqref>", repl, xml, flags=re.S)


def _merge_content_types(out_ct: str, tpl_ct: str, parts: set[str]) -> str:
    additions = []
    have_ext = set(re.findall(r'<Default[^>]*Extension="([^"]+)"', out_ct))
    for m in re.finditer(r"<Default[^>]*?/>", tpl_ct):
        ext = re.search(r'Extension="([^"]+)"', m.group(0))
        if ext and ext.group(1) not in have_ext:
            additions.append(m.group(0))
    have_part = set(re.findall(r'<Override[^>]*PartName="([^"]+)"', out_ct))
    for m in re.finditer(r"<Override[^>]*?/>", tpl_ct):
        part = re.search(r'PartName="([^"]+)"', m.group(0))
        if not part:
            continue
        pn = part.group(1)
        if pn in have_part:
            continue
        if pn.lstrip("/") in _DROP:
            continue
        if pn.lstrip("/") in parts:
            additions.append(m.group(0))
    if not additions:
        return out_ct
    return out_ct.replace("</Types>", "".join(additions) + "</Types>", 1)


def _pivot_refresh_on_load(xml: bytes) -> bytes:
    """Marca a PivotTable para atualizar automaticamente ao abrir o ficheiro."""
    m = re.search(rb"<pivotCacheDefinition\b[^>]*>", xml)
    if not m or b"refreshOnLoad" in m.group(0):
        return xml
    tag = m.group(0)[:-1] + b' refreshOnLoad="1">'
    return xml[: m.start()] + tag + xml[m.end() :]


def preserve(output: str | Path, template: str | Path, row_overrides: dict[str, int] | None = None) -> None:
    output, template = Path(output), Path(template)
    row_overrides = row_overrides or {}

    with zipfile.ZipFile(template) as zt:
        t_parts = {n: zt.read(n) for n in zt.namelist()}
        t_name_to_path = _sheet_name_to_path(zt)
    with zipfile.ZipFile(output) as zo:
        o_parts = {i.filename: zo.read(i.filename) for i in zo.infolist()}
        o_name_to_path = _sheet_name_to_path(zo)

    # 1. Enxertar a cauda original em cada worksheet (por nome de aba).
    for name, t_path in t_name_to_path.items():
        o_path = o_name_to_path.get(name)
        if not o_path or o_path not in o_parts or t_path not in t_parts:
            continue
        o_xml = o_parts[o_path].decode("utf-8")
        t_xml = t_parts[t_path].decode("utf-8")
        if "<pageMargins" not in o_xml or "<pageMargins" not in t_xml:
            continue
        body = o_xml[: o_xml.index("<pageMargins")]
        tail = t_xml[t_xml.index("<pageMargins") : t_xml.rindex("</worksheet>")]
        merged = _merge_root_ns(body + tail + "</worksheet>", t_xml)
        if name in row_overrides:
            merged = _expand_sqref(merged, row_overrides[name])
        o_parts[o_path] = merged.encode("utf-8")

    # 2. Restaurar partes auxiliares originais (verbatim).
    for n, data in t_parts.items():
        if n in _DROP or n == "[Content_Types].xml":
            continue
        if n.startswith(_FORCE_ORIGINAL_PREFIXES):
            # Forçar refreshOnLoad na PivotTable para atualizar sozinha ao abrir.
            if "pivotCacheDefinition" in n:
                data = _pivot_refresh_on_load(data)
            o_parts[n] = data
        elif n not in o_parts:
            o_parts[n] = data

    # 3. Merge de Content_Types.
    if "[Content_Types].xml" in o_parts and "[Content_Types].xml" in t_parts:
        o_parts["[Content_Types].xml"] = _merge_content_types(
            o_parts["[Content_Types].xml"].decode("utf-8"),
            t_parts["[Content_Types].xml"].decode("utf-8"),
            set(o_parts.keys()),
        ).encode("utf-8")

    # 4. Reescrever o ficheiro.
    tmp = output.with_suffix(output.suffix + ".tmp")
    ordered = ["[Content_Types].xml"] + [k for k in o_parts if k != "[Content_Types].xml"]
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ordered:
            z.writestr(name, o_parts[name])
    shutil.move(str(tmp), str(output))
