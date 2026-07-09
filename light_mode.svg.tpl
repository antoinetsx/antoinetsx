<svg width="820" height="460" viewBox="0 0 820 460" xmlns="http://www.w3.org/2000/svg" font-family="'Courier New', monospace">
  <style>
    .bg { fill: #ffffff; }
    .title { fill: #0969da; font-weight: bold; }
    .label { fill: #cf222e; }
    .value { fill: #24292f; }
    .dim { fill: #57606a; }
    .rule { stroke: #d0d7de; stroke-width: 1; }
    text { font-size: 14px; }
  </style>
  <rect class="bg" width="820" height="460" rx="12"/>

  <text x="30" y="40" class="title" font-size="16">{{USERNAME}}@github</text>
  <line class="rule" x1="30" y1="52" x2="790" y2="52"/>

  <text x="30" y="82"><tspan class="label">Uptime: </tspan><tspan class="value">{{UPTIME}}</tspan></text>
  <text x="30" y="108"><tspan class="label">Repos: </tspan><tspan class="value">{{REPOS}}</tspan></text>
  <text x="30" y="134"><tspan class="label">Stars: </tspan><tspan class="value">{{STARS}}</tspan></text>
  <text x="30" y="160"><tspan class="label">Commits: </tspan><tspan class="value">{{COMMITS}}</tspan></text>
  <text x="30" y="186"><tspan class="label">Followers: </tspan><tspan class="value">{{FOLLOWERS}}</tspan></text>

  <text x="30" y="226" class="title">Lines of Code</text>
  <line class="rule" x1="30" y1="234" x2="790" y2="234"/>
  <text x="30" y="260"><tspan class="label">Net total: </tspan><tspan class="value">{{LOC_NET}}</tspan></text>
  <text x="30" y="286"><tspan class="dim">( +{{LOC_ADDED}}, -{{LOC_DELETED}} )</tspan></text>

  <text x="430" y="82" class="title">Top Languages</text>
  <line class="rule" x1="430" y1="90" x2="790" y2="90"/>
  <text x="430" y="116" class="value">{{TOP_LANG_1}}</text>
  <text x="430" y="142" class="value">{{TOP_LANG_2}}</text>
  <text x="430" y="168" class="value">{{TOP_LANG_3}}</text>
  <text x="430" y="194" class="value">{{TOP_LANG_4}}</text>
  <text x="430" y="220" class="value">{{TOP_LANG_5}}</text>

  <text x="30" y="430" class="dim" font-size="11">Last updated: {{LAST_UPDATED}}</text>
</svg>
