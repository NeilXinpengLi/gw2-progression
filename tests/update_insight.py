"""Update insight screen."""

with open("D:\\Projects\\gw2-progression\\src\\gw2_progression\\static\\index.html", encoding="utf-8") as f:
    html = f.read()

marker = '<div id="insight-screen" style="display:none">'
start = html.find(marker)
if start < 0:
    print("ERROR: marker not found")
    exit(1)

end = html.find('<div id="action-center"', start)
if end < 0:
    print("ERROR: action-center not found")
    exit(1)

old = html[start:end]
new = """      <div id="insight-screen" style="display:none">
        <div id="insight-hero" style="background:linear-gradient(135deg,#1a2a1a,#2a1a2a);border:1px solid #3a2a3a;border-radius:12px;padding:24px;text-align:center;margin-bottom:12px"></div>
        <div id="insight-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:12px"></div>
        <div id="insight-key" style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:16px;text-align:center">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">KEY INSIGHT</div>
          <div id="insight-key-text" style="font-size:14px;color:var(--gold)"></div>
        </div>
        <div style="text-align:center">
          <button id="insight-dismiss-btn" class="btn-sm" onclick="dismissInsight()">Continue to Action Center</button>
        </div>
      </div>
      """

html = html.replace(old, new)
with open("D:\\Projects\\gw2-progression\\src\\gw2_progression\\static\\index.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Done")
