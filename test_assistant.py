import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import ask_helper as A

fails = []
def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (('   ' + str(extra)) if (extra and not cond) else ''))
    if not cond: fails.append(name)

# ---------------- tag parsing and validation ----------------
c, a = A.split_reply("Flying to Mars and speeding time up. [[GO:Mars]] [[SPEED:fast]] [[PLAY]]")
check("multi command reply", c == "Flying to Mars and speeding time up." and [x['type'] for x in a] == ['go', 'speed', 'play'], (c, a))
check("speed value", a[1]['value'] == 'fast')

c, a = A.split_reply("Hiding both. [[ORBITS:off]] [[BELTS:off]]")
check("toggles off", a == [{'type': 'orbits', 'on': False}, {'type': 'belts', 'on': False}], a)

c, a = A.split_reply("Sure. [[ orbits : show ]]")
check("loose spacing + alias show->on", a == [{'type': 'orbits', 'on': True}], a)

c, a = A.split_reply("Jupiter has no ground. [[SURFACE:Jupiter]]")
check("surface on gas giant downgraded to go", a == [{'type': 'go', 'body': 'Jupiter'}], a)
c, a = A.split_reply("Landing. [[SURFACE:mars]]")
check("surface on Mars (case-insens)", a == [{'type': 'surface', 'body': 'Mars'}], a)

c, a = A.split_reply("x [[GO:Narnia]] [[DELETE_EVERYTHING]] [[SPEED:warp]] [[DATE:2026-13-45]] [[VOLUME:999]] [[WEIGHT:-5]] [[ZOOM:sideways]]")
check("garbage / unknown commands dropped", a == [], a)

c, a = A.split_reply("Back. [[CLOSE_SURFACE]] [[PANORAMA:next]] [[PANORAMA:3]] [[PANORAMA:prev]]")
check("surface controls", [x['type'] for x in a] == ['close_surface', 'panorama', 'panorama', 'panorama'] and a[2]['which'] == 3, a)

c, a = A.split_reply("ok [[DATE:1986-02-09]] [[DATE:+10y]] [[DATE:-6m]] [[DATE:now]] [[DATE:tomorrow]]")
check("dates: iso, relative, now; junk dropped", [x['value'] for x in a] == ['1986-02-09', '+10y', '-6m', 'now'], a)

c, a = A.split_reply("ok [[VOLUME:40]] [[VOLUME:up]] [[WEIGHT:55]] [[WEIGHT:62.5kg]] [[ROTATE:left]] [[ZOOM:in]]")
c2, a2 = A.split_reply("ok [[MODE:voice]] [[SENSITIVITY:high]] [[TAB:info]] [[HELP:open]] [[KEEPLISTEN:on]] [[INTERRUPT:off]]")
check("volume/weight/rotate/zoom", [x['type'] for x in a] == ['volume', 'volume', 'weight', 'weight', 'rotate', 'zoom'] and a[3]['kg'] == 62.5, a)
check("mode/sensitivity/tab/help/keeplisten/interrupt", [x['type'] for x in a2] == ['mode', 'sensitivity', 'tab', 'help', 'keeplisten', 'interrupt'] and a2[5]['on'] is False, a2)

c, a = A.split_reply("ok " + " ".join("[[GO:%s]]" % b for b in A.BODY_NAMES[:12]))
check("max 6 actions per reply", len(a) == A.MAX_ACTIONS, len(a))

c, a = A.split_reply("Hi [[PLAY]] there [[PLAY]]\n\n\n\nbye *bold*")
check("duplicates removed, tags stripped mid-text, asterisks and blank lines cleaned", a == [{'type': 'play'}] and '[[' not in c and '*' not in c and '\n\n\n' not in c, (c, a))

# ---------------- detail detection ----------------
yes = ["Give me a detailed explanation of black holes", "explain Saturn's rings in depth", "tell me more", "Can you elaborate?",
       "walk me through how stars form", "give me a thorough answer", "I want a full explanation of the Moon", "explain it step by step",
       "go deeper on Europa", "teach me about Mars", "tell me everything about Jupiter", "a long answer please", "do a deep dive on Titan"]
no = ["Take me to Mars", "Why is Venus so hot?", "Which planet has the longest day?", "how big is the Sun", "pause", "what time is it on Earth", "hide the orbits"]
for q in yes: check("detail requested: " + q, bool(A._DETAIL.search(q)))
for q in no:  check("NOT detail: " + q, not A._DETAIL.search(q))

# ---------------- end-to-end with a fake Gemini ----------------
sent = []
def fake_call_factory(text_out):
    def fake(url, payload, key):
        sent.append(payload)
        return 200, {"output_text": text_out}
    return fake
A._key = lambda: "test-key"
A._winner[0] = None

# 1. normal short question
A._call = fake_call_factory("Venus traps heat with a thick carbon dioxide atmosphere.")
r, st = A.chat_gemini({"message": "Why is Venus so hot?", "voice": True, "ui": "time paused; orbits on"})
p = sent[-1]
mt = p.get("generation_config", p.get("generationConfig", {}))
check("short voice question: normal budget", st == 200 and mt.get("max_output_tokens", mt.get("maxOutputTokens")) == 450 and r["detail"] is False, (st, mt))
check("short voice question: told to keep it to two sentences", "at most two short sentences" in p["system_instruction"] and "DETAILED ANSWER" not in p["system_instruction"])
check("controls state reaches the model", "Controls state: time paused; orbits on" in p["input"])

# 2. detailed question in voice mode
long_text = " ".join(["Black holes form when massive stars collapse at the end of their lives."] * 40)
A._call = fake_call_factory(long_text + " [[GO:Sun]]")
r, st = A.chat_gemini({"message": "Give me a detailed explanation of how the Sun works", "voice": True})
p = sent[-1]; mt = p["generation_config"]
check("detailed voice question: big budget", mt["max_output_tokens"] == 1100, mt)
check("detailed voice question: prompt asks for full answer, no 2-sentence cap", "THE USER ASKED FOR A DETAILED ANSWER" in p["system_instruction"] and "at most two short sentences" not in p["system_instruction"])
check("detailed answer is not chopped to 1200 chars", len(r['answer']) > 1500 and r['answer'].endswith('.'), len(r['answer']))
check("detailed answer still carries its command", r['actions'] == [{'type': 'go', 'body': 'Sun'}] and r['detail'] is True)

# 3. detailed text-mode
r, st = A.chat_gemini({"message": "tell me more about Mars", "voice": False})
p = sent[-1]
check("detailed text question: biggest budget", p["generation_config"]["max_output_tokens"] == 1500)

# 4. over-long reply is trimmed at a sentence end, never mid-sentence
A._call = fake_call_factory("This is a sentence that goes on. " * 400)
r, st = A.chat_gemini({"message": "explain in detail", "voice": False})
check("hard cap trims at a sentence end", len(r['answer']) <= 6000 and r['answer'].endswith('.'), len(r['answer']))

# 5. reply that is only commands
A._call = fake_call_factory("[[PAUSE]]")
r, st = A.chat_gemini({"message": "pause", "voice": True})
check("command-only reply gets a spoken confirmation", r['answer'] == 'Done.' and r['actions'] == [{'type': 'pause'}], r)

# 6. old-style single action still exposed for anything that reads 'action'
check("legacy 'action' field = first action", r['action'] == {'type': 'pause'})

# 7. prompt sanity
check("prompt lists every command", all(k in A.ASSIST_SYSTEM for k in ["[[GO:", "[[SURFACE:", "[[CLOSE_SURFACE]]", "[[PANORAMA:", "[[DATE:", "[[PLAY]]", "[[PAUSE]]", "[[SPEED:", "[[RESET]]", "[[ORBITS:", "[[BELTS:", "[[FLY:", "[[GESTURES:", "[[ZOOM:", "[[ROTATE:", "[[MUSIC:", "[[VOLUME:", "[[WEIGHT:", "[[HELP:", "[[TAB:", "[[MODE:", "[[KEEPLISTEN:", "[[INTERRUPT:", "[[SENSITIVITY:"]))
print("\n%d failure(s)" % len(fails)); sys.exit(1 if fails else 0)
