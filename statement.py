r"""Main-Agent Weekly Statement (PDF + HTML), modelled on the Dubai club's document,
for one of Paul's super-agent GROUPS (e.g. Cohiba) - or any list of member ids.

Data: output/managers_raw_<start>_<end>.csv (Rake = Eligible Rake, P&L = Poker P&L).
Tipsback chips = Tips x group pct (the pct itself is NOT printed). Settlement = P&L + tipsback
(RON, 1 chip = 1 RON). Terminology on the document: Tips / Tipsback (matches the sheets). Amount receivable/payable = sum of full settlements, shown in RON and converted
to USD at the live rate (open.er-api.com; fallback 4.55).

  python statement.py --group cohiba 2026-08-24 2026-08-30 [--logo path.png] [--handler CASH]
  python statement.py --group cohiba 2026-08-31 2026-09-06 --open
  python statement.py --group cashvick|premium ...   # the other Paul statements (weekly: all three)

Output: output/statements/<Group>_<start>_<end>.{html,pdf}
Logo: --logo, else assets/romanianclub_logo.png if present, else a monogram.
"""
import argparse
import base64
import csv
import json
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

import managers_config as mc

ROOT = Path(__file__).parent
OUT = ROOT / "output" / "statements"
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
DEFAULT_LOGO = ROOT / "assets" / "romanianclub_logo.png"


def usd_ron():
    try:
        with urllib.request.urlopen("https://open.er-api.com/v6/latest/USD", timeout=8) as r:
            d = json.load(r)
        return float(d["rates"]["RON"]), "live"
    except Exception:
        return 4.55, "fallback"


# single super agents under Paul that also get a statement (key -> id, printed name);
# pct comes from PAUL_SA_RAKEBACK. Groups come from PAUL_SA_GROUPS.
SINGLE_SAS = {"premium": ("9583-9412", "Premium89")}


def group_def(key):
    for g in mc.PAUL_SA_GROUPS:
        if g["key"] == key:
            return g
    if key in SINGLE_SAS:
        pid, name = SINGLE_SAS[key]
        return {"key": key, "name": name, "pct": mc.PAUL_SA_RAKEBACK[pid], "ids": [pid]}
    known = [g["key"] for g in mc.PAUL_SA_GROUPS] + list(SINGLE_SAS)
    raise SystemExit(f"unknown group {key!r}; known: {known}")


def load_rows(start, end, ids):
    raw = ROOT / "output" / f"managers_raw_{start}_{end}.csv"
    if not raw.exists():
        raise SystemExit(f"no collected data for {start}..{end}: {raw}")
    by = {r["id"]: r for r in csv.DictReader(raw.open(encoding="utf-8"))}
    rows, missing = [], []
    for i in ids:
        r = by.get(i)
        if not r or r.get("rake") in ("", "ERR", None):
            missing.append(i)
            continue
        rows.append({"id": i, "name": mc.NAME_OVERRIDES.get(i) or r["name"] or i, "rake": float(r["rake"]),
                     "pnl": float(r["profit_loss"]), "role": "sa"})
    return rows, missing


def expand_downline(rows, head_id, start, end):
    """If downline_report.py collected <head_id>'s downline for this week, list every
    downline member as its own row (players: own stats; agents: Agent Statistics total)
    and turn the head's Super Agent Statistics aggregate into 'direct' = aggregate - downline.
    Members that are already rows (e.g. SAs of the group) are not added twice."""
    f = ROOT / "output" / f"downline_{head_id}_{start}_{end}.csv"
    if not f.exists():
        return rows, None
    head = next((r for r in rows if r["id"] == head_id), None)
    if head is None:
        return rows, None
    have = {r["id"] for r in rows}
    added, bad = [], []
    for r in csv.DictReader(f.open(encoding="utf-8")):
        if r["role"] == "ERR" or r["rake"] in ("", "ERR"):
            bad.append(r["id"]); continue
        if r["id"] in have:
            continue
        added.append({"id": r["id"], "name": r["name"] or r["id"], "rake": float(r["rake"]),
                      "pnl": float(r["profit_loss"]), "role": r["role"]})
    head["rake"] = round(head["rake"] - sum(a["rake"] for a in added), 2)
    head["pnl"] = round(head["pnl"] - sum(a["pnl"] for a in added), 2)
    head["role"] = "direct"
    return rows + added, {"n": len(added), "bad": bad}


def fmt(n, dec=2):
    s = f"{abs(n):,.{dec}f}"
    return ("-" if n < 0 else "") + s


def logo_data_uri(path):
    p = Path(path) if path else None
    if p and p.exists():
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return None


def build_html(title, head_name, handler, start, end, rows, pct, rate, rate_src, logo, club="Romanian Poker Club"):
    def ro(d): return f"{d.day} {d.strftime('%B %Y')}"
    subs = [r for r in rows if r.get("role") in ("sa", "agent", "super")]
    tot_rake = sum(r["rake"] for r in rows)
    tot_pnl = sum(r["pnl"] for r in rows)
    tot_rb = sum(r["rake"] * pct / 100 for r in rows)
    tot_full = tot_pnl + tot_rb
    usd = tot_full / rate
    recv = tot_full >= 0
    week_no = start.isocalendar()[1]
    doc_no = f"RPC / {head_name.split()[0].upper()} / {start.year}-S{week_no:02d}"
    logo_html = (f'<img class="logo" src="{logo}" alt="">' if logo else '<div class="logo mono">RPC</div>')

    def under(r):
        same = r["name"].lower().replace(" ", "") == head_name.lower().replace(" ", "")
        role = r.get("role", "")
        if same or role == "direct":
            return f"{head_name} &rarr; direct (own play)"
        if role in ("agent", "super"):
            return f"{head_name} &rarr; {r['name']} <small>agent, downline total</small>"
        if role == "player":
            return f"{head_name} &rarr; {r['name']} <small>player</small>"
        return f"{head_name} &rarr; {r['name']}"

    trs = []
    for r in sorted(rows, key=lambda x: -x["rake"]):
        rb = r["rake"] * pct / 100
        full = r["pnl"] + rb
        z = "zero" if r["rake"] == 0 and r["pnl"] == 0 else ""
        trs.append(
            f"<tr class='{z}'><td class='nm'>{r['name']}</td><td class='under'>{under(r)}</td>"
            f"<td class='num'>{fmt(r['rake'])}</td>"
            f"<td class='num {'neg' if r['pnl']<0 else ''}'>{fmt(r['pnl'])}</td>"
            f"<td class='num'>{fmt(rb)}</td>"
            f"<td class='num fin {'neg' if full<0 else ''}'>{fmt(full)}</td></tr>")
    active = sum(1 for r in rows if r['rake'] or r['pnl'])
    label = 'Amount receivable' if recv else 'Amount payable'
    label_en = 'all super agents, agents & players combined'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=Source+Sans+3:wght@400;600;700&display=swap">
<style>
@page{{size:A4;margin:0}}
:root{{--ink:#15110C;--red:#9E1B1B;--gold:#B8902F;--paper:#F8F3E9;--paper2:#F1E9D9;--rule:#D9CDB3;--mute:#6B6357;--bl:#002B7F;--yl:#F2C319;--rd:#CE1126}}
html,body{{margin:0;background:#fff}}
body{{font-family:"Source Sans 3","Segoe UI",Arial,sans-serif;color:var(--ink);font-size:11px;font-variant-numeric:tabular-nums}}
.page{{width:210mm;min-height:297mm;box-sizing:border-box;padding:14mm 14mm 12mm;background:var(--paper);position:relative}}
.tri{{height:3px;background:linear-gradient(90deg,var(--bl) 0 33.3%,var(--yl) 33.3% 66.6%,var(--rd) 66.6%)}}
.mast{{display:flex;align-items:center;gap:16px;padding:12px 0 14px;border-bottom:1px solid var(--ink)}}
.logo{{width:64px;height:64px;object-fit:contain;border-radius:8px}}
.logo.mono{{background:var(--ink);color:var(--gold);display:flex;align-items:center;justify-content:center;font:700 20px "Cormorant Garamond",Georgia,serif}}
.mast .t{{flex:1}}
.mast .club{{font:600 10.5px "Source Sans 3",sans-serif;letter-spacing:.32em;text-transform:uppercase;color:var(--red)}}
.mast h1{{margin:2px 0 0;font:600 32px/1 "Cormorant Garamond",Georgia,"Times New Roman",serif;letter-spacing:-.01em}}
.mast .en{{font:italic 500 12.5px "Cormorant Garamond",Georgia,serif;color:var(--mute);margin-top:3px}}
.mast .doc{{text-align:right;font-size:10px;color:var(--mute);line-height:1.5}}
.mast .doc b{{display:block;color:var(--ink);font-weight:700;letter-spacing:.04em}}
.meta{{display:grid;grid-template-columns:1fr 1fr;gap:0 28px;padding:14px 0 12px;border-bottom:1px solid var(--rule)}}
.meta .f{{display:flex;justify-content:space-between;gap:10px;padding:5px 0;border-bottom:1px dotted var(--rule)}}
.meta .k{{color:var(--mute);font-size:10px;letter-spacing:.06em;text-transform:uppercase}}
.meta .k i{{display:block;font:italic 10.5px "Cormorant Garamond",Georgia,serif;text-transform:none;letter-spacing:0;color:#9a917f}}
.meta .v{{font-weight:700;text-align:right}}
.sec{{margin:18px 0 6px;display:flex;align-items:baseline;gap:10px}}
.sec h2{{margin:0;font:600 17px "Cormorant Garamond",Georgia,serif}}
.sec span{{font:italic 11px "Cormorant Garamond",Georgia,serif;color:var(--mute)}}
table{{width:100%;border-collapse:collapse}}
thead th{{text-align:left;padding:7px 6px 6px;border-top:2px solid var(--ink);border-bottom:1px solid var(--ink);font-weight:700;font-size:10px;letter-spacing:.03em;vertical-align:bottom}}
thead th small{{display:block;font:italic 10px "Cormorant Garamond",Georgia,serif;color:var(--mute);font-weight:500}}
thead th.num,thead th.num small{{text-align:right}}
tbody td{{padding:6px 6px;border-bottom:1px solid var(--rule);font-size:10.5px}}
tbody tr.zero td{{color:#9a917f}}
td.num{{text-align:right;white-space:nowrap}}
td.nm{{font-weight:700}} td.under{{color:var(--mute)}}
.neg{{color:var(--red)}}
td.fin{{font-weight:700}}
tfoot td{{padding:8px 6px;border-top:1px solid var(--ink);border-bottom:3px double var(--ink);font-weight:700;font-size:10.5px}}
tfoot td.num{{text-align:right}}
.settle{{margin:20px 0 16px;display:grid;grid-template-columns:1.25fr 1fr;gap:14px;align-items:stretch}}
.stamp{{border:1px solid var(--ink);padding:16px 18px 14px 22px;position:relative;background:#fff}}
.stamp::before{{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(180deg,var(--bl) 0 33.3%,var(--yl) 33.3% 66.6%,var(--rd) 66.6%)}}
.stamp .l1{{font:700 10px "Source Sans 3",sans-serif;letter-spacing:.22em;text-transform:uppercase;color:var(--red)}}
.stamp .l2{{font:italic 11.5px "Cormorant Garamond",Georgia,serif;color:var(--mute);margin-top:2px}}
.stamp .amt{{font:700 34px/1 "Cormorant Garamond",Georgia,serif;margin-top:10px;letter-spacing:-.01em}}
.stamp .amt small{{font-size:15px;font-weight:600;color:var(--mute);margin-right:6px;letter-spacing:.06em}}
.stamp .usd{{margin-top:8px;font-size:12px}}
.stamp .usd b{{font-size:14px}}
.stamp .rate{{color:var(--mute);font-size:9.5px;margin-top:4px}}
.aside{{background:var(--paper2);border:1px solid var(--rule);padding:12px 14px;font-size:10px;color:var(--ink)}}
.aside h3{{margin:0 0 6px;font:700 10px "Source Sans 3",sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--red)}}
.aside .r{{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px dotted var(--rule)}}
.aside .r:last-child{{border-bottom:0}}
.notes{{font-size:9.5px;color:var(--mute);line-height:1.55;padding-top:10px;border-top:1px solid var(--rule)}}
.notes b{{color:var(--ink);font:700 10px "Source Sans 3",sans-serif;letter-spacing:.2em;text-transform:uppercase}}
.notes ol{{margin:4px 0 0;padding-left:16px}}
.foot{{position:absolute;left:14mm;right:14mm;bottom:9mm;display:flex;justify-content:space-between;align-items:center;font:italic 10px "Cormorant Garamond",Georgia,serif;color:var(--mute)}}
.foot .tri{{width:60px;height:3px}}
</style></head><body><div class="page">
<div class="tri"></div>
<div class="mast">{logo_html}
 <div class="t"><div class="club">{club}</div><h1>Main Agent Weekly Statement</h1><div class="en">weekly settlement &middot; super agent, agents &amp; players</div></div>
 <div class="doc"><b>{doc_no}</b>issued {ro(date.today())}</div>
</div>
<div class="meta">
 <div class="f"><span class="k">Main agent<i>statement for</i></span><span class="v">{head_name}</span></div>
 <div class="f"><span class="k">Week<i>Monday &ndash; Sunday</i></span><span class="v">{ro(start)} &ndash; {ro(end)}</span></div>
 <div class="f"><span class="k">Handler<i>settlement method</i></span><span class="v">{handler}</span></div>
 <div class="f"><span class="k">Structure<i>accounts reporting up</i></span><span class="v">1 super agent &middot; {len(subs)} sub-agents &middot; {len(rows)} accounts</span></div>
 <div class="f"><span class="k">Statement<i>type</i></span><span class="v">Weekly tipsback settlement</span></div>
 <div class="f"><span class="k">Currency<i>chip value</i></span><span class="v">RON &nbsp;(1 chip = 1 RON)</span></div>
</div>
<div class="sec"><h2>Account breakdown</h2><span>super agent, agents &amp; players</span></div>
<table>
<thead><tr><th>Nickname<small>account</small></th><th>Under<small>super agent &rarr; agent</small></th><th class="num">Tips<small>chips</small></th><th class="num">Poker P&amp;L<small>chips</small></th><th class="num">Tipsback<small>chips</small></th><th class="num">Settlement<small>RON</small></th></tr></thead>
<tbody>{''.join(trs)}</tbody>
<tfoot><tr><td colspan="2">GRAND TOTAL</td><td class="num">{fmt(tot_rake)}</td><td class="num {'neg' if tot_pnl<0 else ''}">{fmt(tot_pnl)}</td><td class="num">{fmt(tot_rb)}</td><td class="num {'neg' if tot_full<0 else ''}">{fmt(tot_full)}</td></tr></tfoot>
</table>
<div class="settle">
 <div class="stamp">
  <div class="l1">{label}</div>
  <div class="l2">{label_en}</div>
  <div class="amt"><small>RON</small>{fmt(abs(tot_full))}</div>
  <div class="usd">equivalent &nbsp;<b>USD {fmt(abs(usd))}</b></div>
  <div class="rate">1 USD = {rate:.4f} RON &middot; {rate_src} rate, {ro(date.today())}</div>
 </div>
 <div class="aside"><h3>Summary</h3>
  <div class="r"><span>Total tips</span><b>{fmt(tot_rake)}</b></div>
  <div class="r"><span>Total poker P&amp;L</span><b class="{'neg' if tot_pnl<0 else ''}">{fmt(tot_pnl)}</b></div>
  <div class="r"><span>Tipsback granted</span><b>{fmt(tot_rb)}</b></div>
  <div class="r"><span>Active accounts / total</span><b>{active} / {len(rows)}</b></div>
 </div>
</div>
<div class="notes"><b>Important notes</b><ol>
<li>Tips and poker P&amp;L are the members' statistics for the stated week (Monday 00:00 to Sunday 23:59), as collected from the club.</li>
<li>Tipsback is applied to each account's eligible tips per its agreement. Settlement = poker P&amp;L + tipsback. 1 chip = 1 RON.</li>
<li>The final amount is the sum of every account's settlement; the USD figure is an indicative conversion at the rate shown.</li>
<li>This is a system-generated statement and does not require a signature.</li>
</ol></div>
<div class="foot"><span>{club} &mdash; weekly settlement statement</span><span class="tri"></span><span>{doc_no}</span></div>
</div></body></html>"""


def to_pdf(html_path, pdf_path):
    exe = next((e for e in EDGE if Path(e).exists()), None)
    if not exe:
        print("Edge not found - HTML only"); return False
    import tempfile
    prof = Path(tempfile.gettempdir()) / "clubgg_edge_pdf_profile"   # own profile: works even while Edge is open
    cmd = [exe, f"--user-data-dir={prof}", "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           f"--print-to-pdf={Path(pdf_path).resolve()}", Path(html_path).resolve().as_uri()]
    subprocess.run(cmd, capture_output=True, timeout=90)
    return Path(pdf_path).exists()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start"); ap.add_argument("end")
    ap.add_argument("--group", default="cohiba")
    ap.add_argument("--handler", default="CASH")
    ap.add_argument("--logo", default=None)
    ap.add_argument("--club", default="Romanian Poker Club")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    g = group_def(a.group)
    head = g["name"].split("(")[0].strip()            # "Cohiba Lover (+group)" -> "Cohiba Lover"
    rows, missing = load_rows(start, end, g["ids"])
    rows, dl = expand_downline(rows, g["ids"][0], start, end)
    if dl:
        print(f"downline of {head}: {dl['n']} member row(s) added; head row = own play (aggregate - downline)"
              + (f"; UNREADABLE members skipped: {dl['bad']}" if dl['bad'] else ""))
    rate, src = usd_ron()
    logo = logo_data_uri(a.logo or (DEFAULT_LOGO if DEFAULT_LOGO.exists() else None))
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{head.replace(' ', '')}_{start}_{end}"
    html_path, pdf_path = OUT / f"{stem}.html", OUT / f"{stem}.pdf"
    html_path.write_text(build_html(f"{head} statement {start}..{end}", head, a.handler, start, end,
                                    rows, g["pct"], rate, src, logo, a.club), encoding="utf-8")
    ok = to_pdf(html_path, pdf_path)
    tot = sum(r["pnl"] + r["rake"] * g["pct"] / 100 for r in rows)
    print(f"accounts: {len(rows)}  (skipped, not in this week's data: {missing or 'none'})")
    print(f"total full settlement: RON {tot:,.2f}  = USD {tot/rate:,.2f} @ {rate:.4f} ({src})")
    print(f"saved {html_path}"); print(f"saved {pdf_path}" if ok else "PDF FAILED")
    if a.open and ok:
        subprocess.Popen(["cmd", "/c", "start", "", str(pdf_path)])


if __name__ == "__main__":
    main()
