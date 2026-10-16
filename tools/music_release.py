#!/usr/bin/env python3
"""Выкладывает музыку в релизы GitHub: один релиз на альбом, тег релиза = tag альбома.

Запускается из GitHub Actions (.github/workflows/music.yml) после изменения
src/creative/music.json. Для каждого трека, которого ещё нет в релизе:
скачивает видео трека с Suno, вынимает звук в mp3 (VBR ~190 кбит/с),
прописывает теги и обложку альбома, загружает файл в релиз.
Уже загруженные треки не трогает, поэтому повторный запуск безопасен.
"""
import json, os, subprocess, sys, tempfile, time, urllib.request

MUSIC = "src/creative/music.json"


def sh(*cmd, check=True, capture=False):
    r = subprocess.run(cmd, check=check, text=True, capture_output=capture)
    return r.stdout if capture else r.returncode


def fetch(url, dest, tries=4):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                f.write(r.read())
            if os.path.getsize(dest) > 10000:
                return True
        except Exception as e:
            print(f"  попытка {n + 1}: {e}")
        time.sleep(5 * (n + 1))
    return False


def assets(tag):
    out = sh("gh", "release", "view", tag, "--json", "assets", "-q", ".assets[].name", check=False, capture=True)
    return set(out.split()) if out else None


def main():
    m = json.load(open(MUSIC, encoding="utf-8"))
    artist = m.get("artist", "")
    failed = []
    for a in m["albums"]:
        tag, n = a["tag"], len(a["tracks"])
        have = assets(tag)
        if have is None:
            notes = (a.get("about", "") + "\n\n" if a.get("about") else "") + f"Плейлист в Suno: {a.get('suno', '')}"
            sh("gh", "release", "create", tag, "--title", a["title"], "--notes", notes, "--target", "main")
            have = set()
        todo = [(i, t) for i, t in enumerate(a["tracks"], 1) if t["file"] not in have]
        print(f"{a['title']}: в релизе {len(have)}, загрузить {len(todo)}")
        if not todo:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            cover = os.path.join("src", a["cover"].lstrip("/")) if a.get("cover") else ""
            ready = []
            for i, t in todo:
                mp4, mp3 = os.path.join(tmp, "src.mp4"), os.path.join(tmp, t["file"])
                if not fetch(f"https://cdn1.suno.ai/{t['clip']}.mp4", mp4):
                    failed.append(f"{a['title']} — {t['title']}")
                    continue
                cmd = ["ffmpeg", "-v", "error", "-y", "-i", mp4]
                if cover and os.path.exists(cover):
                    cmd += ["-i", cover, "-map", "0:a", "-map", "1:v", "-c:v", "mjpeg",
                            "-disposition:v", "attached_pic", "-metadata:s:v", "comment=Cover (front)"]
                else:
                    cmd += ["-map", "0:a"]
                cmd += ["-map_metadata", "-1", "-c:a", "libmp3lame", "-q:a", "2", "-id3v2_version", "3",
                        "-metadata", f"title={t['title']}", "-metadata", f"artist={artist}",
                        "-metadata", f"album={a['title']}", "-metadata", f"track={i}/{n}", mp3]
                if sh(*cmd, check=False) != 0:
                    failed.append(f"{a['title']} — {t['title']}")
                    continue
                os.remove(mp4)
                ready.append(mp3)
                print(f"  готов {t['file']}")
            for k in range(0, len(ready), 10):
                sh("gh", "release", "upload", tag, *ready[k:k + 10], "--clobber")
    if failed:
        print("Не удалось:", *failed, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
