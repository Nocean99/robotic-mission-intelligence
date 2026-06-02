from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote


def build_report_viewer(report_path: str | Path, output_path: str | Path | None = None) -> Path:
    report_path = Path(report_path)
    data = json.loads(report_path.read_text(encoding="utf-8"))
    if output_path is None:
        output_path = report_path.with_name("vision_report_viewer.html")
    output_path = Path(output_path)
    output_path.write_text(render_html(data, report_path.parent), encoding="utf-8")
    return output_path


def render_html(data: dict, base_dir: Path) -> str:
    summary = data.get("summary") or {}
    evaluation = data.get("evaluation") or {}
    vision_plan = data.get("vision_plan") or {}
    false_positives = evaluation.get("false_positives") or []
    false_negatives = evaluation.get("false_negatives") or []
    shortlist = summary.get("shortlist") or []
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Vision Benchmark Report</title>
    <style>{CSS}</style>
  </head>
  <body>
    <main class="shell">
      <header class="top">
        <div>
          <p class="eyebrow">Drone Vision Benchmark</p>
          <h1>{esc(data.get("mission_request", "Vision report"))}</h1>
        </div>
        <div class="meta">
          <span>{esc(data.get("timestamp", ""))}</span>
          <span>{esc(data.get("proposal_mode", ""))}</span>
          <span>{esc(data.get("scorer", ""))}</span>
        </div>
      </header>

      <section class="metrics">
        {metric("Processed", summary.get("processed"))}
        {metric("Detections", summary.get("detections"))}
        {metric("Shortlist", summary.get("shortlist_count"))}
        {metric("Precision", evaluation.get("precision"))}
        {metric("Recall", evaluation.get("recall"))}
        {metric("F1", evaluation.get("f1"))}
        {metric("False Positives", evaluation.get("false_positive"))}
        {metric("False Negatives", evaluation.get("false_negative"))}
      </section>

      <section class="panel">
        <h2>Vision Plan</h2>
        <div class="chips">
          {chips("Colors", vision_plan.get("important_colors"))}
          {chips("Categories", vision_plan.get("possible_categories"))}
          {chips("Context", vision_plan.get("context_hints"))}
          {chips("Proposal Modes", vision_plan.get("proposal_modes"))}
        </div>
      </section>

      <section class="split">
        <article class="panel">
          <h2>False Positives</h2>
          {cards(false_positives, base_dir) or '<p class="muted">None recorded.</p>'}
        </article>
        <article class="panel">
          <h2>False Negatives</h2>
          {cards(false_negatives, base_dir) or '<p class="muted">None recorded.</p>'}
        </article>
      </section>

      <section class="panel">
        <h2>Review Shortlist</h2>
        {cards(shortlist, base_dir) or '<p class="muted">No shortlist entries.</p>'}
      </section>
    </main>
  </body>
</html>
"""


def metric(label: str, value) -> str:
    shown = "n/a" if value is None else str(value)
    return f'<div class="metric"><span>{esc(label)}</span><strong>{esc(shown)}</strong></div>'


def chips(label: str, values) -> str:
    values = values or []
    if not values:
        return f'<div><h3>{esc(label)}</h3><span class="chip empty">none</span></div>'
    rendered = "".join(f'<span class="chip">{esc(value)}</span>' for value in values)
    return f"<div><h3>{esc(label)}</h3>{rendered}</div>"


def cards(items: list[dict], base_dir: Path) -> str:
    rendered = []
    for item in items:
        image_path = item.get("debug_path") or item.get("crop_path") or item.get("image_path")
        img = image_tag(image_path, base_dir) if image_path else ""
        label = item.get("label") or {}
        rendered.append(
            f"""
            <article class="card">
              {img}
              <div class="card-body">
                <h3>{esc(Path(item.get("image_path", "")).name)}</h3>
                <p>{esc(label.get("label", "unlabeled"))}</p>
                <dl>
                  <div><dt>Score</dt><dd>{esc(item.get("score"))}</dd></div>
                  <div><dt>Decision</dt><dd>{esc(item.get("decision"))}</dd></div>
                  <div><dt>Detector</dt><dd>{esc(item.get("detector_confidence"))}</dd></div>
                  <div><dt>BBox</dt><dd>{esc(item.get("bbox"))}</dd></div>
                </dl>
              </div>
            </article>
            """
        )
    return "\n".join(rendered)


def image_tag(path_value: str, base_dir: Path) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        candidate = Path.cwd() / path
        if candidate.exists():
            path = candidate
        else:
            path = base_dir / path
    if not path.exists():
        return '<div class="missing">image unavailable</div>'
    return f'<img src="file://{quote(str(path))}" alt="{esc(path.name)}" loading="lazy" />'


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


CSS = """
:root {
  color-scheme: dark;
  --bg: #101417;
  --panel: #182024;
  --panel2: #202a2f;
  --line: #324147;
  --text: #eef5f2;
  --muted: #a9bbb4;
  --accent: #63cdda;
  --warn: #f6c85f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.shell { width: min(1500px, calc(100% - 28px)); margin: 0 auto; padding: 22px 0 32px; }
.top { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; margin-bottom: 16px; }
.eyebrow { margin: 0 0 6px; color: var(--accent); font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; }
h1, h2, h3, p { margin: 0; }
h1 { max-width: 950px; font-size: clamp(1.4rem, 3vw, 2.6rem); line-height: 1.05; }
h2 { margin-bottom: 12px; font-size: 1rem; }
h3 { margin-bottom: 8px; font-size: .92rem; }
.meta { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.meta span, .chip {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel2);
  padding: 0 10px;
  color: var(--muted);
  font-size: .8rem;
}
.metrics { display: grid; grid-template-columns: repeat(8, minmax(120px, 1fr)); gap: 10px; margin-bottom: 12px; }
.metric, .panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
}
.metric { padding: 12px; }
.metric span { display: block; color: var(--muted); font-size: .78rem; }
.metric strong { display: block; margin-top: 4px; font-size: 1.25rem; }
.panel { padding: 14px; margin-bottom: 12px; }
.split { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.chips { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.chips h3 { color: var(--muted); font-size: .8rem; }
.chip { margin: 0 6px 6px 0; color: var(--text); }
.chip.empty { color: var(--muted); }
.card {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  gap: 12px;
  min-height: 180px;
  border-top: 1px solid var(--line);
  padding: 12px 0;
}
.card:first-of-type { border-top: 0; padding-top: 0; }
.card img, .missing {
  width: 230px;
  height: 170px;
  object-fit: contain;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #0d1113;
}
.missing { display: grid; place-items: center; color: var(--muted); }
.card-body p, .muted { color: var(--muted); }
dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; margin: 12px 0 0; }
dl div { min-width: 0; }
dt { color: var(--muted); font-size: .76rem; }
dd { margin: 2px 0 0; overflow-wrap: anywhere; }
@media (max-width: 980px) {
  .top, .split { display: block; }
  .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chips { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .card { grid-template-columns: 1fr; }
  .card img, .missing { width: 100%; height: auto; min-height: 170px; }
}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an HTML viewer for a vision_report.json file")
    parser.add_argument("report_path")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = build_report_viewer(args.report_path, args.output)
    print(f"Vision report viewer saved: {path}")


if __name__ == "__main__":
    main()
