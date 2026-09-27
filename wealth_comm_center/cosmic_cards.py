"""Deterministic, data-driven CosmicCard resolver and escaped vector renderer.

Cards display engine-owned facts. Editorial correspondences are explicitly
attributed and never influence astronomy or scoring. No personal name is copied.
"""

from __future__ import annotations

import copy
import hashlib
import html
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"
REGISTRY_VERSION = "cosmic-registry-1"
TEMPLATE_VERSION = "cosmic-vector-1"
LOCALES = ("en", "ja", "zh-CN", "th", "ko", "vi")


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CanonicalEntity(_Schema):
    id: str
    canonical_name: str
    display_name: str
    kind: Literal["physical_body"] = "physical_body"
    archetypes: list[str] = Field(default_factory=list)
    editorial_element: str | None = None
    editorial_metal: str | None = None
    correspondence_source: str | None = None


class ChartPlacement(_Schema):
    longitude: float = Field(ge=0, lt=360)
    sign: str = Field(max_length=80)
    house: int | None = Field(default=None, ge=1, le=12)
    retrograde: bool
    degrees_in_sign: float | None = Field(default=None, ge=0, le=360)
    evidence_id: str
    frame: str


class VisualSpec(_Schema):
    template_version: str = TEMPLATE_VERSION
    width: int = 640
    height: int = 900
    motif: Literal["sun", "orbit"]
    accent: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    background: str = "#091E23"
    foreground: str = "#F8F0DF"


class Provenance(_Schema):
    schema_version: str = SCHEMA_VERSION
    registry_version: str = REGISTRY_VERSION
    template_version: str = TEMPLATE_VERSION
    engine: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    fingerprint: str = ""


class CosmicCard(_Schema):
    schema_version: str = SCHEMA_VERSION
    entity: CanonicalEntity
    locale: str
    title: str
    placement: ChartPlacement | None
    correspondences: dict
    labels: dict[str, str]
    visual: VisualSpec
    provenance: Provenance
    warnings: list[str]


_NAMES = {
    "sun": ("Sun", "太陽", "太阳", "ดวงอาทิตย์", "태양", "Mặt Trời"),
    "moon": ("Moon", "月", "月亮", "ดวงจันทร์", "달", "Mặt Trăng"),
    "mercury": ("Mercury", "水星", "水星", "ดาวพุธ", "수성", "Sao Thủy"),
    "venus": ("Venus", "金星", "金星", "ดาวศุกร์", "금성", "Sao Kim"),
    "mars": ("Mars", "火星", "火星", "ดาวอังคาร", "화성", "Sao Hỏa"),
    "jupiter": ("Jupiter", "木星", "木星", "ดาวพฤหัสบดี", "목성", "Sao Mộc"),
    "saturn": ("Saturn", "土星", "土星", "ดาวเสาร์", "토성", "Sao Thổ"),
    "uranus": ("Uranus", "天王星", "天王星", "ดาวยูเรนัส", "천왕성", "Sao Thiên Vương"),
    "neptune": ("Neptune", "海王星", "海王星", "ดาวเนปจูน", "해왕성", "Sao Hải Vương"),
    "pluto": ("Pluto", "冥王星", "冥王星", "ดาวพลูโต", "명왕성", "Sao Diêm Vương"),
}
# Registry entries, not a class hierarchy or personal chart constants.
ENTITY_REGISTRY = {
    identity: {"names": names, "motif": "sun" if identity == "sun" else "orbit",
               "accent": "#E5BC69" if identity == "sun" else "#89BCAE"}
    for identity, names in _NAMES.items()
}
_LABELS = {
    "en": ("COSMIC CARD", "SUN · SPIRIT", "Longitude", "House", "Gate · Line", "Unknown", "SYMBOLIC / NOT A PREDICTION", "Sovereignty · Vitality · Illumination", "Computed placement · custom framework", "Editorial symbols: Fire · Gold"),
    "ja": ("コズミックカード", "太陽・スピリット", "黄経", "ハウス", "ゲート・ライン", "不明", "象徴的な表現・予測ではありません", "主体性・生命力・光", "計算された配置・独自の枠組み", "編集上の象徴：火・金"),
    "zh-CN": ("宇宙卡牌", "太阳 · 精神", "黄经", "宫位", "闸门 · 爻线", "未知", "象征性表达 · 并非预测", "自主 · 活力 · 光明", "计算位置 · 自定义体系", "编辑设定的象征：火 · 金"),
    "th": ("การ์ดจักรวาล", "ดวงอาทิตย์ · จิตวิญญาณ", "ลองจิจูด", "เรือน", "เกต · ไลน์", "ไม่ทราบ", "สัญลักษณ์ ไม่ใช่คำทำนาย", "อำนาจในตน · พลังชีวิต · แสงสว่าง", "ตำแหน่งที่คำนวณ · กรอบเฉพาะ", "สัญลักษณ์ที่กำหนด: ไฟ · ทอง"),
    "ko": ("코스믹 카드", "태양 · 정신", "황경", "하우스", "게이트 · 라인", "알 수 없음", "상징적 표현 · 예측 아님", "주체성 · 활력 · 빛", "계산된 배치 · 고유 체계", "편집상의 상징: 불 · 금"),
    "vi": ("THẺ VŨ TRỤ", "MẶT TRỜI · TINH THẦN", "Kinh độ", "Nhà", "Cổng · Vạch", "Chưa biết", "BIỂU TƯỢNG / KHÔNG PHẢI DỰ ĐOÁN", "Tự chủ · Sức sống · Ánh sáng", "Vị trí đã tính · Hệ quy chiếu riêng", "Biểu tượng biên tập: Lửa · Vàng"),
}
_WARNING = {
    "en": ("No placement is available in this report.", "Nakshatra, totem, body-specific Tarot and card rank are unresolved; no personal example is substituted.", "Fire, Gold and the Sun archetypes are editorial examples from the design discussion, not astronomical facts or universal correspondences."),
    "ja": ("このレポートには配置情報がありません。", "ナクシャトラ、トーテム、天体別タロット、カードのランクは未確定です。個人の例で補完しません。", "火、金、太陽の原型は設計上の例であり、天文学的事実や普遍的対応ではありません。"),
    "zh-CN": ("此报告中没有位置信息。", "月宿、图腾、天体专属塔罗及卡牌等级尚未确定，不以个人示例代替。", "火、金和太阳原型是设计讨论中的编辑示例，并非天文学事实或普遍对应关系。"),
    "th": ("ไม่มีข้อมูลตำแหน่งในรายงานนี้", "นักษัตร โทเท็ม ไพ่ทาโรต์เฉพาะวัตถุ และลำดับไพ่ยังไม่กำหนด โดยไม่ใช้ตัวอย่างของบุคคลมาแทน", "ไฟ ทอง และต้นแบบดวงอาทิตย์เป็นตัวอย่างจากการออกแบบ ไม่ใช่ข้อเท็จจริงทางดาราศาสตร์หรือความสัมพันธ์สากล"),
    "ko": ("이 보고서에 배치 정보가 없습니다.", "나크샤트라, 토템, 천체별 타로와 카드 등급은 미정이며 개인 예시로 대체하지 않습니다.", "불, 금, 태양의 원형은 설계 논의의 편집상 예시이며 천문학적 사실이나 보편적인 대응 관계가 아닙니다."),
    "vi": ("Báo cáo chưa có thông tin vị trí.", "Tú, vật tổ, Tarot theo thiên thể và hạng thẻ chưa được xác định; không thay bằng ví dụ cá nhân.", "Lửa, Vàng và nguyên mẫu Mặt Trời là ví dụ biên tập từ thảo luận thiết kế, không phải sự thật thiên văn hay tương ứng phổ quát."),
}


def resolve_card(report: dict, entity_id: str = "sun", locale: str = "en") -> dict:
    """Resolve a public-safe card from an authorized report, without recalculation."""
    if not isinstance(report, dict):
        raise ValueError("A canonical report is required")
    if entity_id not in ENTITY_REGISTRY:
        raise ValueError("Unsupported card entity. Choose a physical body from the registry.")
    locale = locale if locale in LOCALES else "en"
    words = _LABELS[locale]
    labels = dict(zip(("heading", "sun_title", "longitude", "house", "gate", "unknown", "disclaimer", "archetypes", "placement", "editorial"), words))
    registry = ENTITY_REGISTRY[entity_id]
    canonical = registry["names"][0]
    name = registry["names"][LOCALES.index(locale)]
    is_sun = entity_id == "sun"
    entity = CanonicalEntity(
        id=f"body.{entity_id}", canonical_name=canonical, display_name=name,
        archetypes=words[7].split(" · ") if is_sun else [],
        editorial_element="Fire" if is_sun else None, editorial_metal="Gold" if is_sun else None,
        correspondence_source="Design discussion: Sun-Spirit editorial example (not canonical astronomy)" if is_sun else None,
    )
    source = next((body for body in report.get("chart", {}).get("bodies", []) if body.get("name") == canonical), None)
    evidence_id = f"chart.{entity_id}.longitude"
    valid_evidence = {e.get("id"): e for e in report.get("evidence", []) if isinstance(e, dict)}
    warnings = [_WARNING[locale][1]]
    if is_sun:
        warnings.append(_WARNING[locale][2])
    placement = None
    if source and evidence_id in valid_evidence and source.get("longitude") == valid_evidence[evidence_id].get("value"):
        placement = ChartPlacement(
            longitude=source["longitude"], sign=source.get("sign", ""), house=source.get("house"),
            retrograde=source.get("retrograde", False), degrees_in_sign=source.get("degrees_in_sign"),
            evidence_id=evidence_id, frame=str(report.get("chart", {}).get("zodiac", "engine-defined")),
        )
    else:
        warnings.insert(0, _WARNING[locale][0])
    raw_gate = report.get("systems", {}).get("gates", {}).get(canonical)
    gate = None
    if placement and isinstance(raw_gate, dict):
        number, line = raw_gate.get("gate"), raw_gate.get("line")
        if type(number) is int and 1 <= number <= 64 and type(line) is int and 1 <= line <= 6:
            gate = {"gate": number, "line": line, "source": f"systems.gates.{canonical}", "kind": "derived"}
    engine_provenance = report.get("provenance", {})
    # Profile names, birth data, generated timestamps, user IDs and other arbitrary
    # metadata cannot leak into either an exported card or its fingerprint payload.
    allowed_keys = ("engine_version", "framework_version", "upstream_commit", "swisseph_version",
                    "ephemeris_backends", "ephemeris_files_sha256", "zodiac", "houses", "time_basis")
    provenance = Provenance(
        engine={key: copy.deepcopy(engine_provenance[key]) for key in allowed_keys if key in engine_provenance},
        evidence_ids=[evidence_id] if placement else [],
    )
    card = CosmicCard(
        entity=entity, locale=locale, title=words[1] if is_sun else name,
        placement=placement, labels=labels,
        correspondences={"gate": gate, "nakshatra": None, "totem": None, "tarot": None, "card_rank": None},
        visual=VisualSpec(motif=registry["motif"], accent=registry["accent"]),
        provenance=provenance, warnings=warnings,
    )
    canonical_json = json.dumps(card.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    card.provenance.fingerprint = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return card.model_dump()


def render_svg(card: dict | CosmicCard) -> str:
    """Render a self-contained accessible SVG with no scripts or external assets."""
    model = card if isinstance(card, CosmicCard) else CosmicCard.model_validate(card)
    def e(value):
        return html.escape(str(value), quote=True)
    labels, visual = model.labels, model.visual
    placement = model.placement
    longitude = f"{placement.longitude:.4f}°" if placement else labels["unknown"]
    house = str(placement.house) if placement and placement.house else labels["unknown"]
    gate = model.correspondences.get("gate")
    gate_value = f"{gate['gate']} · {gate['line']}" if gate else labels["unknown"]
    subtitle = labels["archetypes"] if model.entity.archetypes else model.entity.display_name
    rays = "".join(
        f'<line x1="320" y1="170" x2="320" y2="196" transform="rotate({angle} 320 292)"/>'
        for angle in range(0, 360, 30)
    ) if visual.motif == "sun" else '<ellipse cx="320" cy="292" rx="126" ry="46" transform="rotate(-30 320 292)"/>'
    editorial = labels["editorial"] if model.entity.correspondence_source else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="900" viewBox="0 0 640 900" role="img" aria-labelledby="card-title card-desc" lang="{e(model.locale)}">
<title id="card-title">{e(model.title)}</title>
<desc id="card-desc">{e(labels['placement'])}. {e(labels['disclaimer'])}. {e(' '.join(model.warnings))}</desc>
<defs><linearGradient id="card-bg" x2="1" y2="1"><stop stop-color="{e(visual.background)}"/><stop offset="1" stop-color="#173B3C"/></linearGradient></defs>
<rect width="640" height="900" rx="32" fill="url(#card-bg)"/>
<rect x="20" y="20" width="600" height="860" rx="22" fill="none" stroke="{e(visual.accent)}" stroke-opacity=".5"/>
<g fill="{e(visual.foreground)}" font-family="Noto Sans, Yu Gothic, Microsoft YaHei, Leelawadee UI, Malgun Gothic, sans-serif" text-anchor="middle">
<text x="320" y="69" font-size="15" letter-spacing="2">WEALTH COMMAND CENTER</text>
<text x="320" y="105" font-size="14" fill="{e(visual.accent)}">{e(labels['heading'])} / {e(model.entity.canonical_name.upper())}</text>
<g fill="none" stroke="{e(visual.accent)}" stroke-width="2.5">{rays}<circle cx="320" cy="292" r="68"/><circle cx="320" cy="292" r="83" stroke-opacity=".4"/></g>
<circle cx="320" cy="292" r="51" fill="{e(visual.accent)}" fill-opacity=".12"/>
<text x="320" y="471" font-size="28">{e(model.title)}</text>
<text x="320" y="510" font-size="17" fill="{e(visual.accent)}">{e(subtitle)}</text>
<path d="M80 544 H560" stroke="{e(visual.accent)}" stroke-opacity=".35"/>
<text x="320" y="580" font-size="13">{e(labels['placement'])}</text>
<text x="165" y="628" font-size="13" opacity=".65">{e(labels['longitude'])}</text>
<text x="320" y="628" font-size="13" opacity=".65">{e(labels['house'])}</text>
<text x="475" y="628" font-size="13" opacity=".65">{e(labels['gate'])}</text>
<text x="165" y="662" font-size="23">{e(longitude)}</text>
<text x="320" y="662" font-size="23">{e(house)}</text>
<text x="475" y="662" font-size="23">{e(gate_value)}</text>
<text x="320" y="723" font-size="13" opacity=".75">{e(editorial)}</text>
<text x="320" y="779" font-size="12" fill="{e(visual.accent)}">{e(labels['disclaimer'])}</text>
<text x="320" y="821" font-size="11" opacity=".5">{e(model.provenance.registry_version)} · {e(model.provenance.template_version)}</text>
<text x="320" y="845" font-size="10" opacity=".5">{e(model.provenance.fingerprint[:24])}</text>
</g></svg>'''
