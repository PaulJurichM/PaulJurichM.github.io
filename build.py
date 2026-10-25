#!/usr/bin/env python3
"""Собирает malari.me из папки src/ в папку docs/ (её публикует GitHub Pages).

Новая заметка в блог: положить src/blog/ГГГГ-ММ-ДД-адрес.md и запустить  python3 build.py
(или просто закоммитить файл: GitHub Actions соберёт сайт сам).
"""
import html, json, os, re, shutil

SRC, OUT = "src", "docs"
NAME = "Павел Мальков"
PEN = "Павел Юрич"
MONTHS = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()

NAV = [("/blog/", "Блог"), ("/work/", "Работа"), ("/creative/", "Творчество")]


# ---------- чтение и разметка ----------

def read(path):
    raw = open(path, encoding="utf-8").read()
    meta, body = {}, raw
    m = re.match(r"---\n(.*?)\n---\n?(.*)", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    return meta, body.strip()


def load(name, default):
    p = os.path.join(SRC, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def inline(text):
    t = html.escape(text, quote=False)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" loading="lazy">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", t)
    t = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", t)
    return t


def table(lines):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]
    head, body = rows[0], [r for r in rows[2:]]
    th = "".join(f"<th>{inline(c)}</th>" for c in head)
    tb = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="table"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'


def md(body):
    """Небольшой Markdown: абзацы, ## и ### заголовки, списки «- » и «1. », цитаты «> », ссылки,
    картинки, курсив, `код`, таблицы «| a | b |», блоки ```, метка статуса «@ текст»
    и треки «♪ [Название](/ссылка/) | /путь.mp3 | подпись»."""
    fences = []

    def keep(m):
        fences.append(m.group(1))
        return f"\n\n\x00{len(fences) - 1}\x00\n\n"

    body = re.sub(r"^```[^\n]*\n(.*?)\n```\s*$", keep, body.strip(), flags=re.S | re.M)
    out = []
    for block in re.split(r"\n\s*\n", body.strip()):
        lines = block.strip("\n").split("\n")
        if not block.strip():
            continue
        m = re.fullmatch(r"\x00(\d+)\x00", block.strip())
        if m:
            out.append(f"<pre><code>{html.escape(fences[int(m.group(1))], quote=False)}</code></pre>")
            continue
        while lines and (re.match(r"#{2,3} ", lines[0]) or lines[0].startswith("@ ")):
            if lines[0].startswith("@ "):
                out.append(f'<p class="tag">{inline(lines[0][2:].strip())}</p>')
            else:
                lvl = 3 if lines[0].startswith("### ") else 2
                out.append(f"<h{lvl}>{inline(lines[0][lvl + 1:].strip())}</h{lvl}>")
            lines = lines[1:]
        if not lines:
            continue
        if all(l.startswith("♪ ") for l in lines):
            # треки: «♪ [Название](/ссылка/) | /путь.mp3 | подпись»
            cards = []
            for l in lines:
                parts = [x.strip() for x in l[2:].split("|")]
                name, src = parts[0], parts[1] if len(parts) > 1 else ""
                note = parts[2] if len(parts) > 2 else ""
                cards.append(f'<li><div class="tt">{inline(name)}</div>'
                             + (f'<p>{inline(note)}</p>' if note else "")
                             + f'<audio controls preload="none" src="{html.escape(src)}"></audio></li>')
            out.append('<ul class="tracks">' + "".join(cards) + "</ul>")
            continue
        if len(lines) >= 2 and all(l.strip().startswith("|") for l in lines) and re.fullmatch(r"[|\s:-]+", lines[1].strip()):
            out.append(table(lines))
        elif all(l.startswith("- ") for l in lines):
            out.append("<ul>" + "".join(f"<li>{inline(l[2:])}</li>" for l in lines) + "</ul>")
        elif all(re.match(r"\d+\. ", l) for l in lines):
            items = [inline(re.sub(r"^\d+\. ", "", l)) for l in lines]
            out.append("<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>")
        elif all(l.startswith(">") for l in lines):
            out.append("<blockquote><p>" + "<br>".join(inline(re.sub(r"^>\s?", "", l)) for l in lines) + "</p></blockquote>")
        else:
            out.append("<p>" + " ".join(inline(l.strip()) for l in lines) + "</p>")
    return "\n".join(out)


def plural(n, one, few, many):
    w = one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many
    return f"{n} {w}"


def rudate(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def esc(s):
    return html.escape(s or "")


# ---------- каркас страницы ----------

def page(path, title, content, here="", desc="", extra=""):
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{u}"{cur if here == u else ""}>{t}</a>' for u, t in NAV)
    full = f"{title} — {NAME}" if title else NAME
    doc = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full)}</title>
<meta name="description" content="{esc(desc)}">
<script>(function(){{try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=PT+Sans:wght@400;700&family=PT+Serif:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
</head>
<body>
<header class="top">
  <a class="brand" href="/">{NAME}</a>
  <nav>{nav}<button class="ctl" id="theme" type="button" aria-label="Переключить тему">Тёмная</button></nav>
</header>
<main>
{content}
</main>
{extra}
<footer>© {NAME}, 2026 · проза под именем {PEN} · <a href="https://t.me/MalariNeo">Телеграм</a></footer>
<script src="/assets/site.js"></script>
<script data-goatcounter="https://malari.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
</body>
</html>
"""
    dest = os.path.join(OUT, path.strip("/"), "index.html") if not path.endswith(".html") else os.path.join(OUT, path.strip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "w", encoding="utf-8").write(doc)


def crumbs(*items):
    return '<p class="crumbs">' + " · ".join(f'<a href="{u}">{t}</a>' for u, t in items) + "</p>"


def empty(text):
    return f'<p class="empty">{text}</p>'


# ---------- разделы ----------

def build_about(posts):
    meta, body = read(os.path.join(SRC, "about.md"))
    photo, cap = meta.get("photo", ""), meta.get("caption", "")
    pic = (f'<figure class="hero"><img src="{esc(photo)}" alt="{esc(meta.get("alt", NAME))}">'
           + (f'<figcaption>{esc(cap)}</figcaption>' if cap else "") + "</figure>") if photo else ""
    head = pic + f'<h1>{NAME}</h1><p class="alias">в прозе — {PEN}</p>'
    cards = ('<p class="label">Разделы</p><div class="cards">'
             '<a class="card" href="/blog/"><b>Блог</b><span>Новости и мысли: о работе, о книгах, о том, что получилось и что нет.</span></a>'
             '<a class="card" href="/work/"><b>Работа</b><span>Как я встраиваю ИИ в работу системного аналитика. Проекты и пет-проекты.</span></a>'
             '<a class="card" href="/creative/"><b>Творчество</b><span>Проза, хронотопы чужих книг, видео и музыка.</span></a>'
             '</div>')
    last = ""
    if posts:
        p = posts[0]
        last = ('<p class="label">Последняя заметка</p><ul class="list">'
                f'<li><a href="/blog/{p["slug"]}/"><b>{esc(p["title"])}</b><small>{rudate(p["date"])}</small></a></li></ul>')
    page("/", "", head + f'<div class="prose">{md(body)}</div>' + cards + last,
         desc=meta.get("description", ""))


def build_blog():
    d = os.path.join(SRC, "blog")
    posts = []
    for f in sorted(os.listdir(d), reverse=True) if os.path.isdir(d) else []:
        if not f.endswith(".md") or f.startswith("_"):
            continue
        meta, body = read(os.path.join(d, f))
        if meta.get("draft"):
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.md$", f)
        if not m:
            continue
        posts.append({"date": m.group(1), "slug": m.group(2), "title": meta.get("title", m.group(2)),
                      "summary": meta.get("summary", ""), "body": body})
    for p in posts:
        page(f"/blog/{p['slug']}/", p["title"],
             crumbs(("/blog/", "Блог")) + f'<article class="prose"><h1>{esc(p["title"])}</h1>'
             f'<p class="meta">{rudate(p["date"])}</p>{md(p["body"])}</article>',
             here="/blog/", desc=p["summary"])
    items = "".join(f'<li><a href="/blog/{p["slug"]}/"><b>{esc(p["title"])}</b><small>{rudate(p["date"])}</small>'
                    + (f'<span>{esc(p["summary"])}</span>' if p["summary"] else "") + "</a></li>" for p in posts)
    page("/blog/", "Блог",
         '<h1>Блог</h1><p class="lead">Новости и мысли.</p>'
         + (f'<ul class="list">{items}</ul>' if posts else empty("Первые заметки появятся здесь совсем скоро.")),
         here="/blog/", desc="Блог Павла Малькова")
    return posts


def project_list(items):
    if not items:
        return empty("Скоро здесь будет список.")
    return '<ul class="list">' + "".join(
        f'<li><a href="{esc(i["url"])}"><b>{esc(i["title"])}</b>'
        + (f'<small>{esc(i["tag"])}</small>' if i.get("tag") else "")
        + f'<span>{esc(i.get("about", ""))}</span></a></li>' for i in items) + "</ul>"


def build_work_articles():
    """Статьи раздела «Работа»: src/work/адрес.md -> /work/адрес/. «_» в начале имени и draft: yes прячут файл."""
    d = os.path.join(SRC, "work")
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".md") or f.startswith("_"):
            continue
        meta, body = read(os.path.join(d, f))
        if meta.get("draft"):
            continue
        slug, title = f[:-3], meta.get("title", f[:-3])
        tag = f'<p class="meta">{esc(meta["tag"])}</p>' if meta.get("tag") else ""
        page(f"/work/{slug}/", title,
             crumbs(("/work/", "Работа")) + f'<article class="prose"><h1>{esc(title)}</h1>{tag}{md(body)}</article>',
             here="/work/", desc=meta.get("summary", ""))


MONTHS_NOM = "январь февраль март апрель май июнь июль август сентябрь октябрь ноябрь декабрь".split()
MORE = "<!--more-->"
GRUMBLER = "Заметки ворчуна"


def build_grumbler():
    """«Заметки ворчуна»: src/work/vorchun/ГГГГ-ММ-ДД-адрес.md -> /work/vorchun/адрес/.
    В ленте показывается текст до метки <!--more--> (нет метки — первый абзац), дальше «Читать дальше».
    month: yes в шапке — точная дата неизвестна, показывать только месяц и год."""
    d = os.path.join(SRC, "work", "vorchun")
    notes = []
    for f in sorted(os.listdir(d), reverse=True) if os.path.isdir(d) else []:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})-(.+)\.md$", f)
        if not m or f.startswith("_"):
            continue
        meta, body = read(os.path.join(d, f))
        if meta.get("draft"):
            continue
        y, mo, day, slug = m.groups()
        when = f"{MONTHS_NOM[int(mo) - 1]} {y}" if meta.get("month") else rudate(f"{y}-{mo}-{day}")
        if MORE in body:
            teaser, rest = (s.strip() for s in body.split(MORE, 1))
        else:
            teaser, _, rest = body.partition("\n\n")
        notes.append({"slug": slug, "title": meta.get("title", slug), "when": when,
                      "teaser": teaser, "full": f"{teaser}\n\n{rest}".strip()})
    base = "/work/vorchun/"
    for n in notes:
        page(f"{base}{n['slug']}/", n["title"],
             crumbs(("/work/", "Работа"), (base, GRUMBLER)) + f'<article class="prose"><h1>{esc(n["title"])}</h1>'
             f'<p class="meta">{n["when"]}</p>{md(n["full"])}'
             f'<p class="sans more"><a href="{base}">← Все заметки ворчуна</a></p></article>',
             here="/work/", desc=re.sub(r"[*_`\[\]]", "", n["teaser"])[:200])
    feed = "".join(
        f'<article class="note"><p class="meta">{n["when"]}</p>'
        f'<h2><a href="{base}{n["slug"]}/">{esc(n["title"])}</a></h2>'
        f'<div class="prose">{md(n["teaser"])}</div>'
        f'<p class="sans more"><a href="{base}{n["slug"]}/">Читать дальше →</a></p></article>' for n in notes)
    page(base, GRUMBLER,
         crumbs(("/work/", "Работа")) + f'<h1>{GRUMBLER}</h1>'
         '<p class="lead">Мысли разной степени причёсанности о том, что знакомо каждому в айти: '
         'созвоны, менеджеры, переработки, собеседования. Никого не хочу обидеть, зову поспорить.</p>'
         + (f'<div class="notes">{feed}</div>' if notes else empty("Заметки скоро появятся.")),
         here="/work/", desc="Заметки ворчуна — колонка Павла Малькова об айтишных порядках")
    return notes


def build_work(grumbler=()):
    meta, body = read(os.path.join(SRC, "work.md"))
    data = load("work.json", {"ai": [], "pet": []})
    gr = project_list([{"title": GRUMBLER, "url": "/work/vorchun/",
                        "tag": plural(len(grumbler), "заметка", "заметки", "заметок"),
                        "about": "Ворчливая колонка об айтишных порядках: созвоны, менеджеры, переработки, собеседования."}]) if grumbler else ""
    page("/work/", "Работа",
         f'<h1>Работа</h1><div class="prose">{md(body)}</div>'
         '<p class="label">ИИ в работе аналитика</p>' + project_list(data.get("ai", []))
         + (f'<p class="label">{GRUMBLER}</p>' + gr if gr else "")
         + '<p class="label">Пет-проекты</p>' + project_list(data.get("pet", [])),
         here="/work/", desc=meta.get("description", ""))


def build_creative():
    meta, body = read(os.path.join(SRC, "creative.md"))
    cards = ('<div class="cards two">'
             '<a class="card" href="/books/"><b>Литература</b><span>Сборники рассказов и повестей. Читать бесплатно, без регистрации.</span><i>Читать →</i></a>'
             '<a class="card" href="/creative/hronotopy/"><b>Хронотопы</b><span>Интерактивные атласы чужих книг: кто, где и когда.</span><i>Открыть →</i></a>'
             '<a class="card" href="/creative/video/"><b>Видео</b><span>Ролики, которые я смонтировал.</span><i>Смотреть →</i></a>'
             '<a class="card" href="/creative/music/"><b>Музыка</b><span>Песни, сделанные в Suno, по альбомам.</span><i>Слушать →</i></a>'
             '</div>')
    page("/creative/", "Творчество", f'<h1>Творчество</h1><div class="prose">{md(body)}</div>' + cards,
         here="/creative/", desc=meta.get("description", ""))

    back = crumbs(("/creative/", "Творчество"))
    hr = load("creative/hronotopy.json", [])
    page("/creative/hronotopy/", "Хронотопы",
         back + '<h1>Хронотопы</h1><p class="lead">Атласы чужих книг: события на общей шкале времени, '
         'с фильтрами по циклам и по степени достоверности. Каждый атлас открывается отдельной страницей.</p>'
         + project_list(hr), here="/creative/", desc="Интерактивные хронотопы книг")

    vids = load("creative/video.json", [])
    vhtml = "".join(
        f'<figure class="video"><div class="frame"><iframe src="https://www.youtube-nocookie.com/embed/{esc(v["id"])}" '
        f'title="{esc(v["title"])}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
        f'gyroscope; picture-in-picture" allowfullscreen></iframe></div><h3>{esc(v["title"])}</h3>'
        + (f'<p>{esc(v["about"])}</p>' if v.get("about") else "") + "</figure>" for v in vids)
    page("/creative/video/", "Видео", back + '<h1>Видео</h1><p class="lead">Ролики моего авторства. Все они есть и на моём '
         '<a href="https://www.youtube.com/@PaulJurich">канале на YouTube</a>.</p>'
         + (vhtml or empty("Ролики скоро появятся.")), here="/creative/", desc="Видео Павла Малькова")

    mus = load("creative/music.json", {"base": "", "albums": []})
    base = mus.get("base", "")
    ahtml = ""
    for a in mus.get("albums", []):
        cover = f'<img src="{esc(a["cover"])}" alt="" loading="lazy">' if a.get("cover") else ""
        def track(t):
            src = esc(base + a["tag"] + "/" + t["file"])
            if t.get("pending"):
                return f'<li class="soon"><span>{esc(t["title"])}</span><small>скоро</small></li>'
            return (f'<li data-src="{src}" data-title="{esc(t["title"])} — {esc(a["title"])}">'
                    f'<button type="button">{esc(t["title"])}</button><a href="{src}" download>mp3</a></li>')
        tracks = "".join(track(t) for t in a.get("tracks", []))
        info = [plural(len(a.get("tracks", [])), "трек", "трека", "треков")]
        if a.get("suno"):
            info.append(f'<a href="{esc(a["suno"])}">в Suno</a>')
        ahtml += (f'<section class="album" id="{esc(a["tag"])}"><header>{cover}<div><h2>{esc(a["title"])}</h2>'
                  f'<small>{" · ".join(info)}</small></div></header>'
                  + (f'<p class="album-about">{esc(a["about"])}</p>' if a.get("about") else "")
                  + f"<ol>{tracks}</ol></section>")
    player = '<div class="player"><div><b></b><audio controls preload="none"></audio></div></div>' if ahtml else ""
    page("/creative/music/", "Музыка", back + '<h1>Музыка</h1><p class="lead">Песни, которые я сделал в Suno. '
         'Можно слушать прямо здесь или скачать в mp3.</p>'
         + ('<nav class="toc-albums">' + "".join(f'<a href="#{esc(a["tag"])}">{esc(a["title"])}</a>' for a in mus.get("albums", [])) + "</nav>" if ahtml else "")
         + (ahtml or empty("Альбомы скоро появятся.")),
         here="/creative/", desc="Музыка Павла Малькова", extra=player)


def build_404():
    page("/404.html", "Страница не найдена",
         '<h1>Такой страницы нет</h1><p class="lead">Возможно, она переехала, или в адресе опечатка.</p>'
         '<p class="sans"><a href="/">На главную</a> · <a href="/books/">К сборникам</a></p>')


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    shutil.copytree("assets", f"{OUT}/assets")
    if os.path.isdir(os.path.join(SRC, "media")):
        shutil.copytree(os.path.join(SRC, "media"), f"{OUT}/media")
    open(f"{OUT}/.nojekyll", "w").close()
    shutil.copy("assets/favicon.ico", f"{OUT}/favicon.ico")  # для страниц без своей иконки (хронотопы и др.)
    if os.path.exists("CNAME"):
        shutil.copy("CNAME", f"{OUT}/CNAME")
    posts = build_blog()
    build_about(posts)
    build_work(build_grumbler())
    build_work_articles()
    build_creative()
    build_404()
    print(f"Готово: заметок {len(posts)} → {OUT}/")


if __name__ == "__main__":
    main()
