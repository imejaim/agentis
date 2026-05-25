# -*- coding: utf-8 -*-
"""
build-html.py — Agentis 씨드(seed/agentis.md)를 단일 HTML 뷰어로 변환해
  docs/agentis-view.html 로 내보낸다. (Cline 룰 토큰 절약을 위해 LIVE 룰은
  .clinerules/agentis.md 마크다운을 쓰고, HTML 은 사람이 읽는 뷰어 전용이다.)

  python seed/build-html.py              # seed/agentis.md -> docs/agentis-view.html
  python seed/build-html.py IN OUT       # 입력/출력 경로 직접 지정

특징
  - 외부 의존성 없음 (Python 표준 라이브러리만). 사내망/오프라인 OK.
  - 결정론적: 같은 씨드 -> 같은 HTML. 씨드가 바뀌면 다시 실행하면 된다.
  - 에디토리얼 톤 + 다크/라이트 토글 + 사이드바 sticky TOC + 키네틱 타이포.
"""
import sys
import re
import html
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────
# 인라인 변환:  **굵게**  *기울임*  `코드`  [텍스트](링크)
# ─────────────────────────────────────────────────────────────────────────
def fmt(text):
    s = html.escape(text, quote=False)            # 1) &, <, > 이스케이프
    codes = []                                     # 2) 코드 스팬을 자리표시자로 보호
    def grab_code(m):
        codes.append(m.group(1))
        return '\x00%d\x00' % (len(codes) - 1)
    s = re.sub(r'`([^`]+)`', grab_code, s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)   # 3) 굵게
    s = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', s)               # 4) 기울임
    s = re.sub(                                                  # 5) 링크
        r'\[([^\]]+)\]\(([^)]+)\)',
        lambda m: '<a href="%s">%s</a>' % (html.escape(m.group(2), quote=True), m.group(1)),
        s,
    )
    s = re.sub(r'\x00(\d+)\x00',                                 # 6) 코드 스팬 복원
               lambda m: '<code>%s</code>' % codes[int(m.group(1))], s)
    return s


# ─────────────────────────────────────────────────────────────────────────
# 헤딩 슬러그 (GitHub 방식 근사) — 중복 시 -2, -3 … 부여
# ─────────────────────────────────────────────────────────────────────────
_used_slugs = set()

def slugify(text):
    s = re.sub(r'[`*]', '', text).strip().lower()
    s = ''.join(ch for ch in s if ch.isalnum() or ch in (' ', '-'))
    return s.replace(' ', '-')

def unique_slug(text):
    base = slugify(text) or 'section'
    slug = base
    k = 1
    while slug in _used_slugs:
        k += 1
        slug = '%s-%d' % (base, k)
    _used_slugs.add(slug)
    return slug


# ─────────────────────────────────────────────────────────────────────────
# 표 헬퍼
# ─────────────────────────────────────────────────────────────────────────
def is_separator(line):
    s = line.strip()
    if '|' not in s or '-' not in s:
        return False
    return re.match(r'^\|?[\s:|-]+\|?$', s) is not None

def split_row(line):
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    return [c.strip() for c in s.split('|')]

def render_table(header, rows):
    out = ['<table>', '<thead><tr>']
    out += ['<th>%s</th>' % fmt(c) for c in header]
    out.append('</tr></thead>')
    out.append('<tbody>')
    for row in rows:
        cells = (row + [''] * len(header))[:len(header)]
        out.append('<tr>' + ''.join('<td>%s</td>' % fmt(c) for c in cells) + '</tr>')
    out.append('</tbody></table>')
    return '\n'.join(out)


# ─────────────────────────────────────────────────────────────────────────
# 인용구 — `>` 줄 하나당 한 줄로 (씨드는 줄 단위로 의도해서 쓰여 있음)
# ─────────────────────────────────────────────────────────────────────────
def render_blockquote(qlines):
    parts = ['<p>%s</p>' % fmt(l) for l in qlines if l.strip()]
    return '<blockquote>%s</blockquote>' % '\n'.join(parts)


# ─────────────────────────────────────────────────────────────────────────
# 리스트 — 항목 내부(중첩 리스트/코드/인용)는 재귀로 파싱
# ─────────────────────────────────────────────────────────────────────────
def parse_list(lines, i, headings):
    n = len(lines)
    m = re.match(r'^(\s*)([-*+]|\d+[.)])(\s+)(.*)$', lines[i])
    base_indent = len(m.group(1))
    ordered = m.group(2)[0].isdigit()
    content_col = base_indent + len(m.group(2)) + len(m.group(3))
    items = []

    while i < n:
        line = lines[i]
        if line.strip() == '':                       # 빈 줄: 리스트가 이어지는지 판단
            j = i + 1
            while j < n and lines[j].strip() == '':
                j += 1
            if j >= n:
                break
            nxt = lines[j]
            indent = len(nxt) - len(nxt.lstrip(' '))
            mm = re.match(r'^(\s*)([-*+]|\d+[.)])\s+', nxt)
            if (mm and len(mm.group(1)) == base_indent) or indent >= content_col:
                if items:
                    items[-1].append('')
                i += 1
                continue
            break

        mm = re.match(r'^(\s*)([-*+]|\d+[.)])(\s+)(.*)$', line)
        if mm and len(mm.group(1)) == base_indent:   # 같은 레벨의 새 항목
            items.append([mm.group(4)])
            i += 1
            continue

        indent = len(line) - len(line.lstrip(' '))   # 현재 항목의 연속 줄
        if items and indent > base_indent:
            items[-1].append(line[content_col:] if indent >= content_col else line.lstrip(' '))
            i += 1
            continue
        break                                        # 리스트 종료

    tag = 'ol' if ordered else 'ul'
    out = ['<%s>' % tag]
    for item in items:
        while item and item[-1] == '':
            item.pop()
        inner = '\n'.join(parse_blocks(item, headings, list_item=True))
        out.append('<li>%s</li>' % inner)
    out.append('</%s>' % tag)
    return '\n'.join(out), i


# ─────────────────────────────────────────────────────────────────────────
# 블록 파서 — 프래그먼트(문자열) 리스트를 돌려준다
# ─────────────────────────────────────────────────────────────────────────
_BLOCK_FENCE = re.compile(r'^(\s*)(`{3,}|~{3,})(.*)$')
_HEADING = re.compile(r'^(#{1,6})\s+(.*)$')
_LIST = re.compile(r'^(\s*)([-*+]|\d+[.)])\s+')
_HR = re.compile(r'^(-{3,}|\*{3,})\s*$')

def parse_blocks(lines, headings, list_item=False):
    out = []
    i, n = 0, len(lines)
    first = True                                     # 리스트 항목의 첫 블록인지

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped == '':                           # 빈 줄
            i += 1
            continue

        if stripped.startswith('<!--'):              # HTML 주석 (@section 앵커 등) -> 버림
            if '-->' in line:
                i += 1
            else:
                i += 1
                while i < n and '-->' not in lines[i]:
                    i += 1
                if i < n:
                    i += 1
            continue

        mh = _HEADING.match(line)                    # 헤딩
        if mh:
            level = len(mh.group(1))
            text = mh.group(2).rstrip()
            slug = unique_slug(text)
            headings.append((level, text, slug))
            if level == 2:
                # h2 에 선행 "N." 패턴이 있으면 섹션 라벨용 data-num 부여
                mn = re.match(r'^(\d+)\.\s+', text)
                if mn:
                    out.append('<h2 id="%s" data-num="%s">%s</h2>'
                               % (slug, mn.group(1).zfill(2), fmt(text)))
                else:
                    out.append('<h2 id="%s">%s</h2>' % (slug, fmt(text)))
            else:
                out.append('<h%d id="%s">%s</h%d>'
                           % (level, slug, fmt(text), level))
            i += 1
            first = False
            continue

        if _HR.match(line):                          # 가로줄
            out.append('<hr>')
            i += 1
            first = False
            continue

        mf = _BLOCK_FENCE.match(line)                # 코드 펜스
        if mf:
            base, fence = mf.group(1), mf.group(2)
            tick = fence[0]
            i += 1
            code = []
            while i < n:
                cl = lines[i]
                cs = cl.strip()
                if cs.startswith(tick * 3) and cs.rstrip(tick) == '':
                    i += 1
                    break
                code.append(cl[len(base):] if cl.startswith(base) else cl)
                i += 1
            out.append('<pre><code>%s</code></pre>'
                       % html.escape('\n'.join(code), quote=False))
            first = False
            continue

        if stripped.startswith('|') and i + 1 < n and is_separator(lines[i + 1]):
            header = split_row(line)                 # 표
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith('|'):
                rows.append(split_row(lines[i]))
                i += 1
            out.append(render_table(header, rows))
            first = False
            continue

        if stripped.startswith('>'):                 # 인용구
            q = []
            while i < n and lines[i].strip().startswith('>'):
                ql = lines[i].lstrip()[1:]
                if ql.startswith(' '):
                    ql = ql[1:]
                q.append(ql)
                i += 1
            out.append(render_blockquote(q))
            first = False
            continue

        if _LIST.match(line):                        # 리스트
            block, i = parse_list(lines, i, headings)
            out.append(block)
            first = False
            continue

        para = []                                    # 문단 — 다음 블록 시작 전까지
        while i < n:
            pl = lines[i]
            ps = pl.strip()
            if (ps == '' or ps.startswith('<!--') or ps.startswith('>')
                    or _HEADING.match(pl) or _HR.match(pl)
                    or _BLOCK_FENCE.match(pl) or _LIST.match(pl)
                    or (ps.startswith('|') and i + 1 < n and is_separator(lines[i + 1]))):
                break
            para.append(ps)
            i += 1
        body = '<br>\n'.join(fmt(p) for p in para)
        out.append(body if (list_item and first) else '<p>%s</p>' % body)
        first = False

    return out


# ─────────────────────────────────────────────────────────────────────────
# 상단 배너 — 파일 맨 앞 HTML 주석(박스)에서 추출
# ─────────────────────────────────────────────────────────────────────────
_BOX_CHARS = set('╔╗╚╝═║─│┌┐└┘━┃┏┓┗┛╭╮╯╰')

def extract_banner(lines):
    if not lines or not lines[0].lstrip().startswith('<!--'):
        return None, lines
    end = next((idx for idx, l in enumerate(lines) if '-->' in l), None)
    if end is None:
        return None, lines
    return lines[1:end], lines[end + 1:]

def build_banner(comment_lines):
    cleaned = []
    for raw in comment_lines:
        t = ''.join(ch for ch in raw if ch not in _BOX_CHARS).strip()
        if t:
            cleaned.append(t)
    if not cleaned:
        return '', 'Agentis 씨드'
    title = cleaned[0]
    parts = ['<header class="seed-banner">',
             '<div class="seed-banner-title">%s</div>' % html.escape(title, quote=False)]
    for line in cleaned[1:]:
        if re.match(r'^https?://\S+$', line):
            parts.append('<p><a href="%s">%s</a></p>'
                         % (html.escape(line, quote=True), html.escape(line, quote=False)))
        else:
            parts.append('<p>%s</p>' % html.escape(line, quote=False))
    parts.append('</header>')
    return '\n'.join(parts), title


# ─────────────────────────────────────────────────────────────────────────
# 목차 (h2 / h3)
# ─────────────────────────────────────────────────────────────────────────
def build_toc(headings):
    items = [h for h in headings if h[0] in (2, 3)]
    if not items:
        return ''
    out = ['<nav class="toc">', '<div class="toc-title">목차</div>', '<ul>']
    started = False
    open_sub = False
    for level, text, slug in items:
        disp = html.escape(re.sub(r'[`*]', '', text), quote=False)
        if level == 2:
            if open_sub:
                out.append('</ul>')
                open_sub = False
            if started:
                out.append('</li>')
            out.append('<li><a href="#%s">%s</a>' % (slug, disp))
            started = True
        else:
            if not started:
                out.append('<li><a href="#%s">%s</a></li>' % (slug, disp))
                started = True
                continue
            if not open_sub:
                out.append('<ul>')
                open_sub = True
            out.append('<li><a href="#%s">%s</a></li>' % (slug, disp))
    if open_sub:
        out.append('</ul>')
    if started:
        out.append('</li>')
    out += ['</ul>', '</nav>']
    return '\n'.join(out)


# ─────────────────────────────────────────────────────────────────────────
# 템플릿 / 스타일 — 하얀 바탕, 깔끔하게
# ─────────────────────────────────────────────────────────────────────────
CSS = """
/* ── Tokens — Light (default) ───────────────────── */
:root {
  --bg: #ffffff;
  --bg-soft: #fafafa;
  --bg-code: #f4f4f6;
  --text: #0a0a0a;
  --text-muted: #5a5e66;
  --text-faint: #989ea5;
  --border: #ececef;
  --accent: #5b4dfa;
  --accent-soft: #ece9ff;
  --accent-hover: #4338ca;
  --code-text: #2d2a4a;
  --sans: 'Pretendard Variable', 'Pretendard', -apple-system, BlinkMacSystemFont,
          'Segoe UI', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
  --mono: 'JetBrains Mono', 'D2Coding', 'Cascadia Code', Consolas, 'Courier New', monospace;
}

/* ── Tokens — Dark ──────────────────────────────── */
[data-theme="dark"] {
  --bg: #0e0e10;
  --bg-soft: #17171a;
  --bg-code: #1e1e22;
  --text: #fafafa;
  --text-muted: #a8aab2;
  --text-faint: #6a6c75;
  --border: #2a2a2f;
  --accent: #8b7dff;
  --accent-soft: #2a2348;
  --accent-hover: #b1a4ff;
  --code-text: #d6cfff;
}

/* ── Reset ──────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: 18px;
  line-height: 1.78;
  font-weight: 400;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
  font-feature-settings: 'kern' 1, 'liga' 1;
  transition: background-color 0.3s ease, color 0.3s ease;
}
::selection { background: var(--accent-soft); color: var(--text); }

.page { max-width: 760px; margin: 0 auto; padding: 88px 28px 120px; }

/* ── Theme toggle ───────────────────────────────── */
.theme-toggle {
  position: fixed; top: 22px; right: 22px; z-index: 100;
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 999px;
  cursor: pointer;
  padding: 0;
  transition: background 0.2s ease, color 0.2s ease,
              transform 0.15s ease, border-color 0.2s ease;
}
.theme-toggle:hover {
  transform: scale(1.06);
  background: var(--bg-soft);
  border-color: var(--accent);
  color: var(--accent);
}
.theme-toggle svg { width: 18px; height: 18px; }
.theme-toggle .icon-sun { display: none; }
.theme-toggle .icon-moon { display: block; }
[data-theme="dark"] .theme-toggle .icon-sun { display: block; }
[data-theme="dark"] .theme-toggle .icon-moon { display: none; }

/* ── Sidebar TOC (wide screens) ─────────────────── */
.sidebar { display: none; }
@media (min-width: 1280px) {
  body {
    display: grid;
    grid-template-columns: 280px 1fr;
    align-items: start;
  }
  .sidebar {
    display: block;
    position: sticky;
    top: 0;
    align-self: start;
    height: 100vh;
    overflow-y: auto;
    padding: 96px 24px 40px 40px;
    border-right: 1px solid var(--border);
  }
  .sidebar .toc {
    margin: 0; padding: 0; background: transparent;
    border: 0; border-radius: 0;
  }
  .page nav.toc { display: none; }
}

/* ── Banner ─────────────────────────────────────── */
.seed-banner {
  margin: 0 0 64px;
  padding: 0 0 36px;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--border);
  border-radius: 0;
}
.seed-banner-title {
  font-size: 1.5rem; font-weight: 800;
  letter-spacing: -0.022em; line-height: 1.3;
  color: var(--text); margin-bottom: 18px;
}
.seed-banner p {
  margin: 5px 0; font-size: 0.95rem; line-height: 1.7;
  color: var(--text-muted);
}
.seed-banner p:first-of-type {
  display: inline-block;
  font-family: var(--mono);
  font-size: 0.76rem;
  padding: 4px 11px;
  background: var(--accent-soft);
  color: var(--accent-hover);
  border-radius: 999px;
  margin: 0 0 16px;
  letter-spacing: 0.02em;
  font-weight: 500;
}

/* ── Headings ───────────────────────────────────── */
h1, h2, h3, h4 {
  font-family: var(--sans);
  font-weight: 800; color: var(--text);
  letter-spacing: -0.025em;
}
h1 {
  font-size: 2.5rem; line-height: 1.18;
  margin: 0 0 1.4rem; padding: 0; border: 0;
  letter-spacing: -0.035em;
}
h2 {
  font-size: 1.7rem; line-height: 1.3;
  margin: 4.2rem 0 1.1rem; padding: 0; border: 0;
  letter-spacing: -0.028em;
}
h2[data-num]::before {
  content: '§ ' attr(data-num);
  display: block;
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--accent);
  letter-spacing: 0.22em;
  margin-bottom: 12px;
  text-transform: uppercase;
}
h3 {
  font-size: 1.22rem; line-height: 1.42;
  margin: 2.6rem 0 0.85rem; font-weight: 700;
}
h4 {
  font-size: 1.02rem; line-height: 1.5;
  margin: 2rem 0 0.6rem; font-weight: 700; color: var(--text);
}

/* ── Body text ──────────────────────────────────── */
p { margin: 1.1rem 0; }
strong { font-weight: 700; color: var(--text); }
em { font-style: italic; color: var(--text); }

/* ── Links — drawing underline ──────────────────── */
a {
  color: var(--accent);
  text-decoration: none;
  background-image:
    linear-gradient(var(--accent), var(--accent)),
    linear-gradient(var(--accent-soft), var(--accent-soft));
  background-size: 0 1px, 100% 1px;
  background-repeat: no-repeat, no-repeat;
  background-position: 0 100%, 0 100%;
  padding-bottom: 1px;
  border-bottom: 0;
  transition: background-size 0.4s cubic-bezier(0.22, 1, 0.36, 1), color 0.2s;
}
a:hover { background-size: 100% 1px, 100% 1px; }

/* ── Code ───────────────────────────────────────── */
code {
  font-family: var(--mono); font-size: 0.86em;
  background: var(--bg-code); color: var(--code-text);
  padding: 0.16em 0.42em; border-radius: 5px;
  font-weight: 500;
}
pre {
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 10px; padding: 20px 24px;
  margin: 1.6rem 0; overflow-x: auto; line-height: 1.62;
}
pre code {
  background: none; padding: 0; color: var(--text);
  font-size: 0.88em; font-weight: 400; white-space: pre;
}

/* ── Blockquote — agent voice ──────────────────── */
blockquote {
  margin: 1.75rem 0; padding: 0.4rem 0 0.4rem 1.4rem;
  border-left: 3px solid var(--accent);
  background: transparent; border-radius: 0;
}
blockquote p { margin: 0.5rem 0; color: var(--text-muted); }

/* ── Lists ──────────────────────────────────────── */
ul, ol { padding-left: 1.6rem; margin: 1rem 0; }
li { margin: 0.5rem 0; }
li::marker { color: var(--text-faint); }
li > ul, li > ol { margin: 0.5rem 0; }

/* ── Tables — minimal editorial lines ──────────── */
table {
  border-collapse: collapse; width: 100%;
  margin: 1.8rem 0; font-size: 0.95rem; line-height: 1.62;
}
th, td {
  padding: 14px 16px; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--border);
}
th {
  font-weight: 700; color: var(--text);
  border-bottom: 2px solid var(--text);
  background: transparent; font-size: 0.92rem;
}
tbody tr:hover { background: var(--bg-soft); }

hr { border: 0; border-top: 1px solid var(--border); margin: 4.5rem 0; }

/* ── TOC ────────────────────────────────────────── */
.toc {
  margin: 2.5rem 0 5rem;
  padding: 26px 30px 30px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: 12px;
}
.toc-title {
  font-weight: 700; font-size: 0.76rem;
  text-transform: uppercase; letter-spacing: 0.18em;
  margin-bottom: 18px; color: var(--text-muted);
}
.toc ul { list-style: none; padding-left: 0; margin: 0; }
.toc ul ul {
  padding-left: 14px; margin: 0.4rem 0 0.85rem;
  border-left: 1px solid var(--border);
}
.toc li { margin: 0.35rem 0; }
.toc a {
  color: var(--text-muted); font-size: 0.94rem;
  display: inline-block; padding: 1px 0;
  background-image: linear-gradient(var(--accent), var(--accent));
  background-size: 0 1px;
  background-repeat: no-repeat;
  background-position: 0 100%;
  padding-bottom: 1px;
  border-bottom: 0;
  transition: background-size 0.35s cubic-bezier(0.22, 1, 0.36, 1),
              color 0.2s ease;
}
.toc a:hover { color: var(--accent); background-size: 100% 1px; }
.toc > ul > li > a {
  color: var(--text); font-weight: 600; font-size: 0.97rem;
}

/* ── Overrides — banner / footer (no drawing) ───── */
.seed-banner a {
  background-image: none;
  padding-bottom: 0;
  color: var(--accent); font-weight: 500;
  border-bottom: 1px solid transparent;
  transition: border-color 0.15s ease;
}
.seed-banner a:hover { border-bottom-color: var(--accent); }

/* ── Footer ─────────────────────────────────────── */
.page-footer {
  margin-top: 6rem; padding-top: 2rem;
  border-top: 1px solid var(--border);
  font-size: 0.86rem; color: var(--text-faint);
}
.page-footer code {
  font-size: 0.92em; background: var(--bg-code); color: var(--text-muted);
}
.page-footer a {
  background-image: none;
  padding-bottom: 0;
  color: var(--text-muted);
  border-bottom: 1px solid var(--text-faint);
  transition: color 0.15s, border-color 0.15s;
}
.page-footer a:hover { color: var(--accent); border-bottom-color: var(--accent); }

/* ── Kinetic typography (aino-inspired) ─────────── */
.kinetic-char {
  display: inline-block;
  opacity: 0;
  transform: translateY(28px) rotate(-4deg);
  transform-origin: 50% 100%;
  transition: opacity 0.7s cubic-bezier(0.22, 1, 0.36, 1),
              transform 0.7s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: opacity, transform;
}
.kinetic-char.lit { opacity: 1; transform: translateY(0) rotate(0); }

.reveal {
  opacity: 0;
  transform: translateY(22px);
  transition: opacity 0.8s cubic-bezier(0.22, 1, 0.36, 1),
              transform 0.8s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: opacity, transform;
}
.reveal.in-view { opacity: 1; transform: translateY(0); }

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  .kinetic-char, .reveal {
    opacity: 1 !important; transform: none !important; transition: none !important;
  }
  body, .theme-toggle { transition: none !important; }
}

/* ── Responsive ─────────────────────────────────── */
@media (max-width: 720px) {
  body { font-size: 16.5px; line-height: 1.76; }
  .page { padding: 48px 20px 80px; }
  h1 { font-size: 2rem; }
  h2 { font-size: 1.42rem; margin: 3rem 0 0.9rem; }
  h2[data-num]::before { font-size: 0.66rem; margin-bottom: 8px; }
  h3 { font-size: 1.13rem; margin: 2rem 0 0.7rem; }
  h4 { font-size: 1rem; }
  pre { padding: 16px 18px; border-radius: 8px; }
  .toc { padding: 20px 22px; }
  .seed-banner-title { font-size: 1.25rem; }
  table { font-size: 0.9rem; }
  th, td { padding: 10px 12px; }
  .theme-toggle { top: 14px; right: 14px; width: 36px; height: 36px; }
}
""".strip()


JS = """
(function () {
  // ── Theme toggle (always active, even with reduced motion) ──
  var toggle = document.querySelector('.theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var root = document.documentElement;
      var current = root.getAttribute('data-theme') || 'light';
      var next = (current === 'dark') ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('theme', next); } catch (e) {}
    });
  }

  // ── Animations gated by prefers-reduced-motion ──
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // H1 — letter-by-letter reveal (글자가 솟아오르듯)
  var h1 = document.querySelector('main h1');
  if (h1 && !h1.querySelector('*')) {
    var text = h1.textContent;
    h1.textContent = '';
    Array.from(text).forEach(function (ch, i) {
      var span = document.createElement('span');
      span.className = 'kinetic-char';
      span.textContent = (ch === ' ') ? String.fromCharCode(160) : ch;
      span.style.transitionDelay = (i * 32) + 'ms';
      h1.appendChild(span);
    });
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        h1.querySelectorAll('.kinetic-char').forEach(function (s) {
          s.classList.add('lit');
        });
      });
    });
  }

  // Scroll-triggered reveal for major blocks (main only)
  var scope = document.querySelector('main') || document;
  var targets = scope.querySelectorAll(
    'h2, h3, blockquote, table, pre, hr, .toc, .seed-banner'
  );
  targets.forEach(function (el) { el.classList.add('reveal'); });
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('in-view');
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    targets.forEach(function (el) { io.observe(el); });
  } else {
    targets.forEach(function (el) { el.classList.add('in-view'); });
  }
})();
""".strip()


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap">
<script>
/* Theme bootstrap — FOUC 방지용. 본문 그리기 전에 data-theme 부착 */
(function () {
  try {
    var saved = localStorage.getItem('theme');
    var sys = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', saved || (sys ? 'dark' : 'light'));
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();
</script>
<style>
{{CSS}}
</style>
</head>
<body>
<button class="theme-toggle" type="button" aria-label="라이트/다크 모드 전환">
  <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
  <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4"></circle>
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
  </svg>
</button>
<aside class="sidebar">{{TOC}}</aside>
<main class="page">
{{BODY}}
</main>
<script>
{{JS}}
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────
def main():
    here = Path(__file__).resolve().parent
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else here / 'agentis.md'
    # 기본 출력은 docs/agentis-view.html (사람이 읽는 뷰어). Cline 룰은 .clinerules/agentis.md 마크다운.
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else here.parent / 'docs' / 'agentis-view.html'

    md = src.read_text(encoding='utf-8').lstrip('﻿')
    lines = md.split('\n')

    comment_lines, rest = extract_banner(lines)
    if comment_lines is not None:
        banner_html, title = build_banner(comment_lines)
    else:
        banner_html, title = '', 'Agentis 씨드'

    headings = []
    frags = parse_blocks(rest, headings)

    toc_html = build_toc(headings)
    if toc_html:
        for idx, frag in enumerate(frags):
            if frag.startswith('<h1'):
                frags.insert(idx + 1, toc_html)
                break
        else:
            frags.insert(0, toc_html)

    footer = ('<footer class="page-footer">이 페이지는 <code>seed/agentis.md</code> 에서 '
              '자동 생성되었습니다. 다시 만들려면 <code>python seed/build-html.py</code>.</footer>')

    body = '\n'.join(filter(None, [banner_html, '\n'.join(frags), footer]))
    out = (HTML_TEMPLATE
           .replace('{{TITLE}}', html.escape(title, quote=False))
           .replace('{{CSS}}', CSS)
           .replace('{{JS}}', JS)
           .replace('{{TOC}}', toc_html or '')
           .replace('{{BODY}}', body))

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding='utf-8')

    print('OK  ->', dst)
    print('  source  :', src.name, '(%d lines)' % len(lines))
    print('  blocks  :', len(frags))
    print('  headings:', len(headings))
    print('  output  : %d bytes' % len(out.encode('utf-8')))


if __name__ == '__main__':
    main()
