import json, os, re, subprocess, unicodedata
from datetime import datetime, timezone, timedelta

ROOT = "MarkLens-Themes"
INDEX = os.path.join(ROOT, "index.json")
OUT = os.environ.get("GITHUB_OUTPUT", "/dev/null")

BLOCKED = ["fuck", "shit", "bitch", "cunt", "dick", "pussy", "slut", "whore", "nigg", "fag", "retard", "rape",
           "nazi", "porn", "sex", "kill", "hitler", "bastard", "asshole", "penis", "vagina", "boob", "cock"]
ALLOWED = ["essex", "sussex", "classic", "class", "grape", "scunthorpe", "assess", "passion", "glass", "brass",
           "bass", "cocktail", "peacock", "dickens", "skill", "kiln"]
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})


def say(key, value):
    with open(OUT, "a") as f:
        f.write(f"{key}={value}\n")


def finish(message, added=False, final=False, name=""):
    say("message", message.replace("\n", " "))
    say("added", "true" if added else "false")
    say("final", "true" if final else "false")
    say("name", name)
    raise SystemExit(0)


def clean(text):
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c)).translate(LEET)
    t = re.sub(r"[^a-z]", "", t)
    return re.sub(r"(.)\1{2,}", r"\1\1", t)


def offensive(text):
    t = clean(text)
    for safe in ALLOWED:
        t = t.replace(safe, "")
    return any(word in t for word in BLOCKED)


def lum(c):
    def ch(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c["r"]) + 0.7152 * ch(c["g"]) + 0.0722 * ch(c["b"])


def contrast(a, b):
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def field(body, label):
    m = re.search(r"\*\*" + label + r":\*\*\s*(.*)", body)
    return m.group(1).strip() if m else ""


body = os.environ.get("ISSUE_BODY", "")
user = os.environ.get("ISSUE_USER", "")
owner = os.environ.get("REPO_OWNER", "")

m = re.search(r"```json\s*(\{.*\})\s*```", body, re.S)
if not m:
    finish("I couldn’t find a theme in this issue. Please send it again from MarkLens with Theme Gallery › Share a Theme.")
raw = m.group(1)
if len(raw) > 60_000:
    finish("This theme file is too large.", final=True)
try:
    data = json.loads(raw)
except Exception:
    finish("The theme file in this issue isn’t valid. Please send it again from MarkLens.")

theme = data.get("editor") if isinstance(data, dict) else None
if not isinstance(theme, dict) or not isinstance(theme.get("page"), dict):
    finish("This doesn’t look like a MarkLens editor theme.", final=True)

name = str(theme.get("name", "")).strip()[:30]
author = field(body, "Author")[:30] or user
tags = [t.strip().lower() for t in re.split(r"[,#]", field(body, "Tags")) if t.strip()][:5]
tags = [re.sub(r"[^a-z0-9-]", "", t)[:16] for t in tags if t]
if not name or not re.fullmatch(r"[\w .'&-]{2,30}", name):
    finish("Please give the theme a short name using letters, numbers and spaces.", final=True)
for text in [name, author] + tags:
    if offensive(text):
        finish("Please choose a different name or tags.", final=True)

if user != owner:
    info = json.loads(subprocess.run(["gh", "api", f"users/{user}"], capture_output=True, text=True).stdout or "{}")
    created = info.get("created_at")
    if not created or datetime.now(timezone.utc) - datetime.fromisoformat(created.replace("Z", "+00:00")) < timedelta(days=30):
        finish("Thanks! To keep the gallery free of spam, themes can only be shared from GitHub accounts older than 30 days.", final=True)

with open(INDEX) as f:
    index = json.load(f)

week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
recent = [t for t in index["themes"] if t.get("submittedBy") == user and t.get("added", "") > week_ago]
if user != owner and len(recent) >= 3:
    finish("You’ve shared 3 themes this week already. Try again in a few days.")

page = theme["page"]
dark = lum(page) < 0.18
text = (theme.get("style") or {}).get("textDark" if dark else "textLight")
text = text or ({"r": 1, "g": 1, "b": 1} if dark else {"r": 0, "g": 0, "b": 0})
if contrast(text, page) < 4.5:
    finish("The text in this theme is hard to read. Open it in MarkLens, press Fix It on the Readability badge, then share it again.")
accent = theme.get("customAccent")
if isinstance(accent, dict) and contrast(accent, {"r": 1, "g": 1, "b": 1}) < 2.5:
    finish("The accent colour is too light for buttons. Press Fix It in MarkLens and share it again.")


def fingerprint(t):
    cs = [t.get("page"), t.get("customAccent")] + list((t.get("glow") or [])[:3])
    return [c.get(k, 0) for c in cs if isinstance(c, dict) for k in ("r", "g", "b")]


mine = fingerprint(theme)
for entry in index["themes"]:
    path = os.path.join(ROOT, entry["file"])
    if not os.path.exists(path):
        continue
    with open(path) as f:
        other = json.load(f).get("editor") or {}
    theirs = fingerprint(other)
    if len(theirs) == len(mine) and mine and sum((a - b) ** 2 for a, b in zip(mine, theirs)) < 0.02:
        finish(f"This looks almost the same as “{entry['name']}”, which is already in the gallery.", final=True)

slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "theme"
base, n = slug, 2
while any(t["id"] == slug for t in index["themes"]):
    slug, n = f"{base}-{n}", n + 1

theme["name"] = name
data = {"format": "MarkLens Theme", "version": 1, "kind": "editor", "editor": theme}
os.makedirs(os.path.join(ROOT, "themes"), exist_ok=True)
with open(os.path.join(ROOT, "themes", slug + ".mltheme"), "w") as f:
    json.dump(data, f, indent=2)

index["themes"].append({
    "id": slug, "name": name, "author": author, "tags": tags or (["dark"] if dark else ["light"]),
    "file": f"themes/{slug}.mltheme", "version": 1, "summary": "",
    "submittedBy": user, "added": datetime.now(timezone.utc).isoformat()
})
with open(INDEX, "w") as f:
    json.dump(index, f, indent=2)

finish(f"Thanks, {author}! “{name}” is now in the MarkLens Theme Gallery. It shows up the next time someone opens the gallery.",
       added=True, name=name)
