#!/usr/bin/env python3
"""生成石头三个月健康管理复盘的客户发送版 PDF 与 HTML 预览。"""

from __future__ import annotations

import html
from pathlib import Path


OUT_DIR = Path("客户减肥指导/石头/交付")
HTML_PATH = OUT_DIR / "石头-3个月健康管理阶段复盘-客户版.html"
PDF_PATH = OUT_DIR / "石头-3个月健康管理阶段复盘-客户版.pdf"


def esc(value: str) -> str:
    return html.escape(value)


def bullet(items: list[str]) -> str:
    return "".join(f"<li>{esc(item)}</li>" for item in items)


def page(number: int, section: str, title: str, body: str, *, extra: str = "") -> str:
    return f"""
    <section class="page {extra}">
      <div class="topline"><span>{esc(section)}</span><span>STONE · HEALTH REVIEW</span></div>
      <div class="page-title">{esc(title)}</div>
      {body}
      <div class="page-footer"><span>石头｜3个月健康管理阶段复盘</span><span>{number:02d}</span></div>
    </section>
    """


def build_html() -> str:
    cover = """
    <section class="page cover">
      <div class="cover-shape shape-one"></div>
      <div class="cover-shape shape-two"></div>
      <div class="cover-inner">
        <div class="eyebrow">DANDAN NUTRITION & HEALTH MANAGEMENT</div>
        <div class="cover-title">3个月健康管理<br><span>阶段复盘</span></div>
        <div class="cover-subtitle">为 石头 定制</div>
        <div class="cover-period">2026.04.27 — 2026.07.31</div>
        <div class="cover-line"></div>
        <p class="cover-note">不只看体重，也看身体状态、生活节奏和下一步怎么走。</p>
        <div class="cover-advisor">营养师｜丹丹</div>
      </div>
      <div class="page-footer light"><span>CLIENT REVIEW</span><span>01</span></div>
    </section>
    """

    p2 = page(
        2,
        "01",
        "先看结论",
        """
        <div class="lead-box">
          <div class="lead-label">这三个月，最值得记住的变化</div>
          <div class="lead-text">你的身体变轻了，情绪和睡眠也更稳定了。</div>
        </div>
        <div class="stat-grid four">
          <div class="stat-card"><div class="stat-value">-2.4<span>kg</span></div><div class="stat-label">体重变化</div><div class="stat-sub">56.6kg → 54.2kg</div></div>
          <div class="stat-card"><div class="stat-value">-3<span>cm</span></div><div class="stat-label">腰围变化</div><div class="stat-sub">70cm → 67cm</div></div>
          <div class="stat-card"><div class="stat-value">-3<span>cm</span></div><div class="stat-label">臀围变化</div><div class="stat-sub">95cm → 92cm</div></div>
          <div class="stat-card"><div class="stat-value">-2<span>cm</span></div><div class="stat-label">腿围变化</div><div class="stat-sub">54cm → 52cm</div></div>
        </div>
        <div class="two-col">
          <div class="soft-card">
            <div class="card-kicker">身体状态</div>
            <ul>""" + bullet([
                "情绪更稳定",
                "睡眠质量变好",
                "经期水肿几乎消失",
                "情绪性想吃零食的情况明显减少",
            ]) + """</ul>
          </div>
          <div class="soft-card accent-card">
            <div class="card-kicker">过程判断</div>
            <p>你不是靠一段时间的极端控制变瘦，而是在工作很忙、运动空间有限的情况下，靠稳定的饮食动作，把体重和围度一点点带了下来。</p>
          </div>
        </div>
        """,
    )

    p3 = page(
        3,
        "02",
        "你已经做出的改变",
        """
        <div class="section-intro">真正有效的改变，已经发生在每天的具体选择里。</div>
        <div class="action-grid">
          <div class="action-card">
            <div class="action-number">01</div>
            <h3>外食时主动加一份蔬菜</h3>
            <p>你让一顿外食不再只有主食和肉，餐盘结构更完整，吃完后的饱腹感也更稳定。</p>
          </div>
          <div class="action-card">
            <div class="action-number">02</div>
            <h3>不方便点菜时，自己带蔬菜</h3>
            <p>你没有等环境变理想，而是提前准备好选择，忙碌的工作日也能保留自己的饮食节奏。</p>
          </div>
          <div class="action-card">
            <div class="action-number">03</div>
            <h3>随身准备高蛋白加餐</h3>
            <p>你没有等到特别饿才随手找零食，减少了饿过头后情绪性进食的机会。</p>
          </div>
          <div class="action-card">
            <div class="action-number">04</div>
            <h3>开始观察食材和身体的关系</h3>
            <p>你会尝试新食材，也会留意腹胀、腹泻和经期变化，逐渐找到更适合自己的吃法。</p>
          </div>
        </div>
        <div class="quote-box">你做的不是短期节食，而是在高压工作里，建立了一套更适合自己身体的饮食方式。</div>
        """,
    )

    p4 = page(
        4,
        "03",
        "我们面对的小难题",
        """
        <div class="section-intro">这些不是失败，而是下一阶段需要把方案调得更贴合现实的地方。</div>
        <div class="challenge-list">
          <div class="challenge-row">
            <div class="challenge-icon">01</div>
            <div><h3>工作节奏很满，运动难以固定</h3><p>工作强度高，占用了大部分时间和精力。下一阶段不追求大运动量，先保留低门槛活动入口。</p></div>
          </div>
          <div class="challenge-row">
            <div class="challenge-icon">02</div>
            <div><h3>蔬菜目标和消化舒适度还没有平衡</h3><p>蔬菜量经常在250—399g之间，同时出现过腹胀、腹泻。接下来先提高耐受度，再逐步接近400g。</p></div>
          </div>
          <div class="challenge-row">
            <div class="challenge-icon">03</div>
            <div><h3>放松和恢复还没有固定下来</h3><p>每天10分钟的放松动作还没有稳定进入日程。接下来要把一部分精力分给睡眠、情绪和恢复。</p></div>
          </div>
        </div>
        <div class="lead-box compact">
          <div class="lead-label">我们怎么看</div>
          <div class="lead-text small">不是你不够自律，而是下一阶段要让动作更低门槛、更容易嵌入你的工作日。</div>
        </div>
        """,
    )

    p5 = page(
        5,
        "04",
        "最新检查报告",
        """
        <div class="section-intro">这次复查的重点，不是继续把饮食收得更紧，而是确认下一步如何巩固。</div>
        <table class="lab-table">
          <thead><tr><th>项目</th><th>4月12日</th><th>7月31日</th><th>变化</th></tr></thead>
          <tbody>
            <tr><td>TPOAb</td><td>80.8 IU/mL</td><td>60.1 IU/mL</td><td><span class="good">下降</span></td></tr>
            <tr><td>TgAb</td><td>367.9 IU/mL</td><td>291.3 IU/mL</td><td><span class="good">下降</span></td></tr>
            <tr><td>25-羟维生素D</td><td>19.83 µg/L</td><td>24.46 µg/L</td><td><span class="warn">上升，但仍低于目标30</span></td></tr>
            <tr><td>TSH</td><td>3.286 mIU/L</td><td>3.833 mIU/L</td><td>需要持续观察</td></tr>
            <tr><td>FT4</td><td>10.59 pmol/L</td><td>8.70 pmol/L</td><td>下降，仍在报告范围内</td></tr>
          </tbody>
        </table>
        <div class="two-col">
          <div class="soft-card">
            <div class="card-kicker">报告里的积极变化</div>
            <p>两项甲状腺抗体数值较4月下降，维生素D也从19.83升到了24.46。当前方向值得继续观察。</p>
          </div>
          <div class="soft-card accent-card">
            <div class="card-kicker">需要继续跟进的地方</div>
            <p>维生素D还没有达到报告目标；甲状腺相关指标需要结合身体状态、用药和医生意见持续跟踪。</p>
          </div>
        </div>
        <div class="notice">这份报告给我们的方向是：不再增加饮食禁忌，先把营养吃够、肠胃照顾好、复查跟上。</div>
        """,
    )

    p6 = page(
        6,
        "05",
        "下一阶段怎么做",
        """
        <div class="section-intro">接下来不追求更狠，只把已经有效的事情继续做稳。</div>
        <div class="next-grid">
          <div class="next-card">
            <div class="next-tag">动作 1</div>
            <h3>保持现有饮食框架</h3>
            <p>每餐保留蛋白质、适量主食和身体能够接受的蔬菜。</p>
            <div class="standard">标准：不新增禁食清单，不把食物越吃越少。</div>
          </div>
          <div class="next-card">
            <div class="next-tag">动作 2</div>
            <h3>让蔬菜吃得更舒服</h3>
            <p>熟蔬菜分到2—3餐，先稳定每日约300g，再根据消化情况逐步接近400g。</p>
            <div class="standard">标准：每周记录3天蔬菜量和消化情况。</div>
          </div>
          <div class="next-card">
            <div class="next-tag">动作 3</div>
            <h3>核对补充剂和复查计划</h3>
            <p>把维生素D、硒、锌及其他补充剂清单带给医生确认，不自行加量。</p>
            <div class="standard">标准：下次复查前完成一次清单核对。</div>
          </div>
        </div>
        <div class="bonus-box">
          <strong>低门槛活动加分项</strong>
          <span>每周2次，每次10分钟。快走、拉伸或轻力量都可以，完成比强度更重要。</span>
        </div>
        """,
    )

    p7 = page(
        7,
        "06",
        "给这一阶段的你",
        """
        <div class="closing">
          <div class="closing-mark">“</div>
          <p>这三个月，你完成的不是把自己管得更紧，<br>而是在忙碌、疲惫和身体敏感的情况下，<br>慢慢找到了一套适合自己的方法。</p>
          <div class="closing-line"></div>
          <p class="closing-small">接下来不追求更狠，<br>只把已经有效的事情继续做稳。</p>
        </div>
        <div class="disclaimer">检查报告部分仅用于营养管理沟通，不替代医生诊疗、处方或药物调整。如有持续腹胀、腹泻或其他不适，请及时咨询医生。</div>
        """,
        extra="closing-page",
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>石头-3个月健康管理阶段复盘-客户版</title>
<style>
@page {{ size: A4; margin: 0; }}
:root {{ --font-cjk:"ClientHeiti","Adobe Heiti Std","STHeiti",sans-serif; }}
@font-face {{ font-family:"ClientHeiti"; src:url("file:///Library/Fonts/AdobeHeitiStd-Regular.otf"); font-weight:400; }}
@font-face {{ font-family:"ClientHeiti"; src:url("file:///Library/Fonts/AdobeFanHeitiStd-Bold.otf"); font-weight:700 900; }}
:root {{
  --forest:#285943; --deep:#1d4535; --sage:#aec8b7; --mint:#e8f0e9;
  --cream:#f7f4ea; --coral:#d66d4e; --ink:#26352f; --muted:#718078;
  --line:#d8e3dc; --white:#fff;
}}
* {{ box-sizing:border-box; }}
html,body {{ margin:0; padding:0; background:#e9eee9; color:var(--ink); font-family:var(--font-cjk); }}
body {{ font-size:14px; line-height:1.65; }}
.page {{ width:210mm; height:297mm; position:relative; padding:17mm 18mm 17mm; background:var(--white); page-break-after:always; overflow:hidden; }}
.page:last-child {{ page-break-after:auto; }}
.topline {{ display:flex; justify-content:space-between; color:var(--muted); font-size:9px; letter-spacing:1.2px; border-bottom:1px solid var(--line); padding-bottom:6px; }}
.topline span:first-child {{ color:var(--coral); font-weight:700; letter-spacing:1.5px; }}
.page-title {{ color:var(--deep); font-size:29px; font-weight:800; letter-spacing:1px; margin-top:15mm; margin-bottom:10mm; }}
.page-title::before {{ content:""; display:block; width:42px; height:4px; background:var(--coral); margin-bottom:8px; }}
.page-footer {{ position:absolute; left:18mm; right:18mm; bottom:9mm; display:flex; justify-content:space-between; color:var(--muted); font-size:9px; border-top:1px solid var(--line); padding-top:5px; }}
.cover {{ background:var(--cream); padding:0; }}
.cover-inner {{ position:absolute; left:22mm; top:54mm; z-index:3; }}
.eyebrow {{ color:var(--forest); font-size:10px; letter-spacing:1.4px; font-weight:700; }}
.cover-title {{ color:var(--deep); font-size:44px; line-height:1.25; font-weight:800; margin-top:17mm; letter-spacing:2px; }}
.cover-title span {{ color:var(--coral); }}
.cover-subtitle {{ color:var(--forest); font-size:18px; margin-top:13mm; font-weight:600; }}
.cover-period {{ color:var(--muted); font-size:11px; letter-spacing:1.6px; margin-top:5mm; }}
.cover-line {{ width:60px; height:4px; background:var(--coral); margin:10mm 0 7mm; }}
.cover-note {{ color:var(--muted); font-size:14px; max-width:80mm; line-height:1.9; }}
.cover-advisor {{ color:var(--forest); font-size:12px; margin-top:25mm; letter-spacing:1px; }}
.cover-shape {{ position:absolute; transform:rotate(-28deg); }}
.shape-one {{ width:120mm; height:65mm; right:-55mm; top:28mm; background:var(--forest); opacity:.95; z-index:1; }}
.shape-two {{ width:190mm; height:90mm; left:-58mm; bottom:-28mm; background:var(--sage); opacity:.8; }}
.page-footer.light {{ color:#f5faf6; border-color:rgba(255,255,255,.4); z-index:3; }}
.lead-box {{ background:var(--mint); border-left:6px solid var(--forest); padding:7mm 8mm; margin-bottom:8mm; }}
.lead-box.compact {{ margin-top:9mm; padding:5mm 7mm; }}
.lead-label,.card-kicker {{ color:var(--coral); font-size:10px; font-weight:800; letter-spacing:1px; }}
.lead-text {{ color:var(--deep); font-size:22px; font-weight:800; line-height:1.45; margin-top:4px; }}
.lead-text.small {{ font-size:16px; }}
.stat-grid {{ display:grid; gap:4mm; }}
.stat-grid.four {{ grid-template-columns:repeat(4,1fr); }}
.stat-card {{ background:var(--cream); padding:5mm 4mm; min-height:35mm; border-top:3px solid var(--sage); }}
.stat-value {{ color:var(--forest); font-size:27px; line-height:1.1; font-weight:800; }}
.stat-value span {{ font-size:14px; margin-left:2px; }}
.stat-label {{ color:var(--deep); font-size:12px; font-weight:700; margin-top:3mm; }}
.stat-sub {{ color:var(--muted); font-size:10px; margin-top:1mm; }}
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:5mm; margin-top:7mm; }}
.soft-card {{ background:var(--cream); padding:5mm 6mm; min-height:44mm; }}
.soft-card.accent-card {{ background:var(--mint); }}
.soft-card p {{ margin:3mm 0 0; }}
ul {{ margin:3mm 0 0; padding-left:5mm; }}
li {{ margin:1.6mm 0; }}
.section-intro {{ color:var(--muted); font-size:15px; margin-top:-5mm; margin-bottom:7mm; }}
.action-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:5mm; }}
.action-card {{ border:1px solid var(--line); border-top:4px solid var(--forest); padding:5mm 6mm; min-height:55mm; }}
.action-number,.challenge-icon {{ color:var(--coral); font-weight:800; font-size:12px; letter-spacing:1px; }}
h3 {{ color:var(--forest); font-size:16px; line-height:1.35; margin:2mm 0 2mm; }}
p {{ margin:2mm 0; }}
.quote-box,.notice {{ margin-top:8mm; background:var(--forest); color:#f4fbf5; padding:5mm 7mm; font-size:15px; font-weight:600; line-height:1.65; }}
.challenge-list {{ border-top:1px solid var(--line); }}
.challenge-row {{ display:grid; grid-template-columns:16mm 1fr; gap:4mm; padding:5mm 0; border-bottom:1px solid var(--line); }}
.challenge-row h3 {{ margin:0 0 1mm; }}
.challenge-row p {{ color:var(--muted); margin:0; }}
.lab-table {{ width:100%; border-collapse:collapse; margin:5mm 0 7mm; font-size:11.5px; }}
.lab-table th {{ background:var(--deep); color:#fff; text-align:left; padding:3mm 3.3mm; }}
.lab-table td {{ border:1px solid var(--line); padding:3mm 3.3mm; vertical-align:top; }}
.lab-table tr:nth-child(even) td {{ background:var(--cream); }}
.good {{ color:var(--forest); font-weight:700; }}
.warn {{ color:#b95c36; font-weight:700; }}
.notice {{ background:var(--cream); color:var(--deep); border-left:5px solid var(--coral); font-size:14px; }}
.next-grid {{ display:grid; grid-template-columns:1fr; gap:4mm; }}
.next-card {{ border-left:5px solid var(--forest); background:var(--cream); padding:4mm 6mm; }}
.next-tag {{ color:var(--coral); font-size:10px; font-weight:800; letter-spacing:1px; }}
.next-card h3 {{ margin:1mm 0; }}
.next-card p {{ margin:1mm 0; }}
.standard {{ color:var(--forest); font-size:11px; font-weight:700; margin-top:2mm; }}
.bonus-box {{ display:flex; gap:5mm; align-items:center; margin-top:7mm; padding:4mm 6mm; background:var(--mint); }}
.bonus-box strong {{ color:var(--forest); white-space:nowrap; }}
.bonus-box span {{ color:var(--muted); }}
.closing-page {{ background:var(--cream); }}
.closing {{ margin-top:35mm; padding-left:8mm; border-left:5px solid var(--coral); }}
.closing-mark {{ color:var(--coral); font-family:Georgia,serif; font-size:64px; line-height:.5; }}
.closing p {{ color:var(--deep); font-size:21px; line-height:1.9; font-weight:700; margin:9mm 0; }}
.closing-line {{ width:45mm; height:3px; background:var(--sage); }}
.closing p.closing-small {{ color:var(--forest); font-size:17px; line-height:1.8; }}
.disclaimer {{ position:absolute; bottom:28mm; left:26mm; right:26mm; background:rgba(255,255,255,.72); border-top:1px solid var(--line); padding-top:4mm; color:var(--muted); font-size:10px; line-height:1.6; }}
@media screen {{ body {{ padding:10mm 0; }} .page {{ margin:0 auto 10mm; box-shadow:0 8px 30px rgba(29,69,53,.12); }} }}
@media print {{ body {{ background:#fff; }} }}
</style>
</head>
<body>
{cover}{p2}{p3}{p4}{p5}{p6}{p7}
</body>
</html>"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(build_html(), encoding="utf-8")
    from weasyprint import HTML

    HTML(filename=str(HTML_PATH), base_url=str(HTML_PATH.parent)).write_pdf(str(PDF_PATH))
    print(HTML_PATH)
    print(PDF_PATH)


if __name__ == "__main__":
    main()
