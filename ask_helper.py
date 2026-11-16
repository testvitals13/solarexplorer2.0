"""
ask_helper.py - lets the solar system page ask Gemini a question.

THE API KEY IS NEVER STORED IN THIS PROJECT. It is read from an environment variable called
GEMINI_API_KEY, which you set once on your own computer (see the setup steps). That way you
can zip and share this folder without sharing your key.

Only the standard Python library is used, so there is nothing new to install.
"""

import http.client
import json
import os
import datetime
import re
import socket
import threading
import time
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]   # smartest free-tier model first, lighter ones as fallbacks
MIN_SECONDS_BETWEEN_QUESTIONS = 2.0      # protects the free daily limit from button mashing
MAX_ANSWER_CHARS = 1500

SYSTEM = (
    "You are a friendly guide inside a school project that shows the solar system in 3D. "
    "Answer in 2 to 4 short sentences, in plain words for a student aged 12 to 15. "
    "Use the facts given in the message when they apply. If you are not sure, say so instead of guessing. "
    "If the question is not about space or astronomy, politely say you can only talk about space."
)

_last_question = [0.0]


class _NoInternet(Exception):
    pass


def _key():
    """The key comes from the GEMINI_API_KEY environment variable, or from a one-line file called .gemini_key
    next to this script (that file is never uploaded: it is in .gitignore)."""
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gemini_key"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _models():
    custom = os.environ.get("GEMINI_MODEL", "").strip()          # optional: choose your own model
    names = [custom] if custom else []
    for name in DEFAULT_MODELS:
        if name not in names:
            names.append(name)
    return names


_local = threading.local()


def _call(url, payload, key):
    """One request over a kept-alive connection. The key travels in a header and is never printed."""
    path = url.split("googleapis.com", 1)[1]
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    for attempt in (1, 2):
        conn = getattr(_local, "conn", None)
        if conn is None:
            conn = _local.conn = http.client.HTTPSConnection("generativelanguage.googleapis.com", timeout=40)
        try:
            conn.request("POST", path, body, headers)
            response = conn.getresponse()
            raw = response.read()
            try:
                return response.status, json.loads(raw.decode("utf-8"))
            except ValueError:
                return response.status, {}
        except socket.timeout:
            _local.conn = None
            raise _NoInternet("timed out")
        except (http.client.HTTPException, OSError) as error:      # a stale kept-alive connection: reconnect once
            try:
                conn.close()
            except Exception:
                pass
            _local.conn = None
            if attempt == 2:
                raise _NoInternet(type(error).__name__ + ": " + str(error)[:120])


def _error_message(body):
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error.get("status") or "")
    return str(error or "")


def _join_text(node):
    """All the answer text inside one reply part, skipping the model's private 'thinking'."""
    found = []

    def walk(item):
        if isinstance(item, dict):
            if item.get("thought") is True or item.get("type") in ("thought", "thinking"):
                return
            if isinstance(item.get("text"), str):
                found.append(item["text"])
            for key, value in item.items():
                if key != "text":
                    walk(value)
        elif isinstance(item, list):
            for value in item:
                walk(value)

    walk(node)
    return "".join(found).strip()


def _find_text(body):
    """Works for both reply shapes Google uses (the newer 'steps' one and the older 'candidates' one)."""
    if not isinstance(body, dict):
        return ""
    for key in ("output_text", "outputText"):
        if isinstance(body.get(key), str) and body[key].strip():
            return body[key].strip()
    steps = body.get("steps")
    if isinstance(steps, list):
        for step in reversed(steps):                              # the final step holds the answer
            text = _join_text(step)
            if text:
                return text
    candidates = body.get("candidates")
    if isinstance(candidates, list) and candidates:
        text = _join_text(candidates[0])
        if text:
            return text
    return ""


def _attempts(text, system=None, max_tokens=2500):
    """The requests to try, newest style first. We move on to the next one only if Google says
    'no such model' or 'I do not understand this request' (HTTP 404 / 400)."""
    system = system or SYSTEM
    models = _models()
    tries = []
    for model in models:
        tries.append((
            "interactions " + model, API + "/interactions",
            {"model": model, "system_instruction": system, "input": text,
             "generation_config": {"max_output_tokens": max_tokens}}))
    for model in models[:2]:
        tries.append((
            "generateContent " + model, API + "/models/" + model + ":generateContent",
            {"systemInstruction": {"parts": [{"text": system}]},
             "contents": [{"role": "user", "parts": [{"text": text}]}],
             "generationConfig": {"maxOutputTokens": max_tokens}}))
    return tries


def ask_gemini(data):
    """data = {'question': ..., 'body': 'Venus', 'context': 'facts from the page'}.
    Returns (dict to send back to the page, HTTP status)."""
    key = _key()
    if not key:
        return {"error": "No Gemini key is set on this computer yet. See the setup steps."}, 503

    question = str(data.get("question", "")).strip()[:300]
    body_name = str(data.get("body", "")).strip()[:40]
    context = str(data.get("context", "")).strip()[:1500]
    if not question:
        return {"error": "Please type a question first."}, 400

    now = time.monotonic()
    if now - _last_question[0] < MIN_SECONDS_BETWEEN_QUESTIONS:
        return {"error": "One moment, then ask again."}, 429
    _last_question[0] = now

    text = ("Facts from the app about " + (body_name or "the solar system") + ": " + context +
            "\n\nStudent's question: " + question)

    slow_tries = [0]
    for label, url, payload in _attempts(text):
        try:
            status, reply = _call(url, payload, key)
        except _NoInternet as problem:
            print("[assistant] " + label + " -> could not reach Google (" + str(problem) + ")")
            if "timed out" in str(problem).lower() or "Timeout" in str(problem):
                slow_tries[0] += 1
                if slow_tries[0] < 2:
                    continue                                      # maybe just a slow model: try the next one once
            return {"error": "Could not reach Gemini. Check your internet, VPN or antivirus. The facts above still work offline."}, 503
        if 200 <= status < 300:
            answer = _find_text(reply)
            if answer:
                return {"answer": answer[:MAX_ANSWER_CHARS]}, 200
            print("[assistant] " + label + " -> empty answer. Reply keys: " +
                  (", ".join(reply.keys()) if isinstance(reply, dict) else "?"))
            return {"answer": "I could not come up with an answer to that. Try asking it another way."}, 200
        message = _error_message(reply)
        print("[assistant] " + label + " -> HTTP " + str(status) + ": " + message[:160])
        if status in (401, 403) or "api key" in message.lower():
            return {"error": "Gemini did not accept the key. Check that it was copied correctly."}, 502
        if status == 429:
            return {"error": "The free limit was reached for now. Try again in a minute."}, 429
        if status in (400, 404):
            continue                                              # try the next model / request style
        return {"error": "The assistant is having trouble right now. Try again in a moment."}, 502

    print("[assistant] none of the model names worked. Set GEMINI_MODEL to a current model name.")
    return {"error": "The assistant is not available right now."}, 502


# ====================================================================================
#  Voice / text assistant (used by the chat panel and the glowing orb)
# ====================================================================================
BODY_NAMES = ["Sun", "Mercury", "Venus", "Earth", "Moon", "Mars", "Ceres", "Jupiter", "Saturn", "Titan", "Uranus",
              "Neptune", "Pluto", "Haumea", "Makemake", "Eris", "Halley", "Io", "Europa", "Ganymede", "Callisto",
              "Triton", "Charon"]
SURFACE_BODIES = ["Mars", "Moon", "Venus"]          # places with real surface photos from space agencies

ASSIST_SYSTEM = (
    "You are the on-board guide of an interactive 3D solar system explorer. Be warm, clear and accurate, like a "
    "good science presenter. Write in plain spoken English with NO markdown, bullet lists, emoji or asterisks, because "
    "your reply may be read aloud. Use the facts given in the message when they apply. If you are not sure, say so "
    "instead of guessing. If the question is not about space, astronomy or using this app, politely say you can only talk about space.\n"
    "LENGTH: Normally reply in 1 to 3 short sentences. But when the user asks for a detailed, in-depth, thorough, complete, "
    "full or long answer, or asks you to elaborate, go deeper, tell them more, break it down or walk them through it, give a "
    "genuinely detailed answer instead: about 8 to 15 sentences (roughly 150 to 300 words) in short spoken paragraphs separated "
    "by a blank line. Cover what it is, how or why it works, the key numbers and comparisons, and one surprising fact. "
    "Never cut a detailed answer short and never pad it.\n"
    "CONTROLS: You can operate the whole app for the user, exactly like clicking its buttons. Put commands at the very end of "
    "your reply as tags like [[NAME]] or [[NAME:value]], at most 6, in the order they should happen. The tags are removed "
    "before your reply is read aloud. The commands are:\n"
    "  [[GO:Body]]  fly to a body and open its info (go to, show me, find, take me to).\n"
    "  [[SURFACE:Body]]  open the 360 degree surface view (stand on, land on, see the ground, rover view). Only Mars, Moon and "
    "Venus have real surface photos. For the Sun, Jupiter, Saturn, Uranus and Neptune explain that there is no solid surface and use [[GO:Body]] instead.\n"
    "  [[CLOSE_SURFACE]]  leave the surface view and go back to orbit.\n"
    "  [[PANORAMA:next]], [[PANORAMA:prev]] or [[PANORAMA:3]]  pick another surface photo while the surface view is open.\n"
    "  [[DATE:2026-07-04]]  jump the simulated date. [[DATE:now]] is today. Relative jumps work too: [[DATE:+10y]], [[DATE:-6m]], "
    "[[DATE:+2w]], [[DATE:+30d]] (d days, w weeks, m months, y years). Prefer relative jumps to doing date arithmetic yourself. "
    "The supported date range is in the app state.\n"
    "  [[PLAY]] and [[PAUSE]]  start or stop time moving.\n"
    "  [[SPEED:fast]]  how quickly time runs: slow, medium, fast or veryfast.\n"
    "  [[RESET]]  the Whole system button: back to the full overview of the solar system.\n"
    "  [[ORBITS:on]] or [[ORBITS:off]]  show or hide the orbit lines.\n"
    "  [[BELTS:on]] or [[BELTS:off]]  show or hide the asteroid belt, Trojans and Kuiper belt.\n"
    "  [[FLY:on]] or [[FLY:off]]  free-flight spaceship camera.\n"
    "  [[GESTURES:on]] or [[GESTURES:off]]  camera-based hand gesture control (the browser asks for camera permission).\n"
    "  [[ZOOM:in]] or [[ZOOM:out]]  move the camera closer or farther.\n"
    "  [[ROTATE:left]]  turn the view: left, right, up or down.\n"
    "  [[MUSIC:on]] or [[MUSIC:off]]  the Interstellar background music. [[VOLUME:40]] sets its volume from 0 to 100, or use [[VOLUME:up]] and [[VOLUME:down]].\n"
    "  [[WEIGHT:55]]  type a body weight in kg into the weight calculator of the selected body (send [[GO:Body]] before it if that body is not selected yet).\n"
    "  [[HELP:open]] or [[HELP:close]]  the controls help card.\n"
    "  [[TAB:info]]  show the planet info panel.\n"
    "  [[MODE:text]] or [[MODE:voice]]  switch the assistant between typing and talking.\n"
    "  [[KEEPLISTEN:on]] or [[KEEPLISTEN:off]]  keep listening after answers.  [[INTERRUPT:on]] or [[INTERRUPT:off]]  let the user "
    "interrupt by talking.  [[SENSITIVITY:high]]  how easily the user's voice interrupts: low, normal or high.\n"
    "Body must be exactly one of: " + ", ".join(BODY_NAMES) + ".\n"
    "RULES: Only send a command when the user asks you to do something in the app or it is clearly what they want. A pure question gets "
    "no command. Say naturally what you are doing, and never claim you did something you did not send a command for. If the user asks "
    "for something the app cannot do, say so briefly and offer the closest thing it can do. You may combine an explanation with commands.\n"
    "Examples:\n"
    "  User: take me to Mars and run time fast -> Flying to Mars and speeding time up. [[GO:Mars]] [[SPEED:fast]] [[PLAY]]\n"
    "  User: show me Halley's comet in 1986 -> Jumping to February 1986, when Halley's comet last passed the Sun. [[DATE:1986-02-09]] [[GO:Halley]]\n"
    "  User: hide the orbit lines and the belts -> Hiding both. [[ORBITS:off]] [[BELTS:off]]\n"
    "  User: I weigh 55 kg, what would I weigh on Mars? -> About 21 kilograms, because Mars has 0.38 times Earth's gravity. [[GO:Mars]] [[WEIGHT:55]]\n"
)

# a request for a long answer: these words switch on the big answer length and the larger token budget
_DETAIL = re.compile(
    r"\b(in[- ]depth|detail(?:ed|s)?|elaborat\w*|thorough(?:ly)?|comprehensive(?:ly)?|deep[- ]dive|go deeper|at length|in full|"
    r"full (?:explanation|story|answer|breakdown|picture)|explain (?:it |this |that )?(?:fully|more|further|properly|in depth)|"
    r"tell me (?:much )?more|tell me everything|everything (?:about|you know)|long(?:er)? (?:answer|explanation)|"
    r"step[- ]by[- ]step|break (?:it|this|that) down|walk me through|teach me)\b", re.I)

# ---- the commands: the model writes [[NAME:value]] tags, we check every one and hand the page clean, safe actions ----
_TAG = re.compile(r"\[\[\s*([A-Za-z_]+)\s*(?::\s*([^\]\n]{0,40}?))?\s*\]\]")
_ON = {"on", "true", "yes", "show", "open", "enable", "enabled", "start"}
_OFF = {"off", "false", "no", "hide", "close", "disable", "disabled", "stop"}
_SPEEDS = {"slow": "slow", "medium": "medium", "normal": "medium", "fast": "fast", "veryfast": "veryfast"}
_TOGGLES = {"ORBITS", "BELTS", "FLY", "GESTURES", "MUSIC", "HELP", "KEEPLISTEN", "INTERRUPT"}
MAX_ACTIONS = 6


def _body(arg):
    return next((b for b in BODY_NAMES if b.lower() == (arg or "").strip().lower()), None)


def _date_arg(arg):
    a = (arg or "").strip().lower().replace(" ", "")
    if a in ("now", "today"):
        return "now"
    if re.fullmatch(r"[+-]\d{1,4}[dwmy]", a):
        return a
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", a):
        try:
            datetime.date.fromisoformat(a)
            return a
        except ValueError:
            return None
    return None


def _make_action(cmd, arg):
    """One [[CMD:arg]] tag -> a checked action dict for the page, or None if it is not a real command."""
    cmd = cmd.upper().replace("-", "_")
    arg = (arg or "").strip()
    key = arg.lower().replace(" ", "").replace("_", "").replace("-", "")
    if cmd in ("GO", "SURFACE"):
        name = _body(arg)
        if not name:
            return None
        return {"type": "surface" if cmd == "SURFACE" and name in SURFACE_BODIES else "go", "body": name}
    if cmd in ("CLOSE_SURFACE", "CLOSESURFACE"):
        return {"type": "close_surface"}
    if cmd == "PANORAMA":
        if key in ("next", "prev", "previous"):
            return {"type": "panorama", "which": "prev" if key.startswith("prev") else "next"}
        if key.isdigit() and 1 <= int(key) <= 30:
            return {"type": "panorama", "which": int(key)}
        return None
    if cmd == "DATE":
        value = _date_arg(arg)
        return {"type": "date", "value": value} if value else None
    if cmd in ("PLAY", "PAUSE", "RESET"):
        return {"type": cmd.lower()}
    if cmd == "SPEED":
        return {"type": "speed", "value": _SPEEDS[key]} if key in _SPEEDS else None
    if cmd in _TOGGLES:
        if key in _ON:
            return {"type": cmd.lower(), "on": True}
        if key in _OFF:
            return {"type": cmd.lower(), "on": False}
        return None
    if cmd == "VOLUME":
        if key in ("up", "down"):
            return {"type": "volume", "value": key}
        return {"type": "volume", "value": int(key)} if key.isdigit() and 0 <= int(key) <= 100 else None
    if cmd == "TAB":
        return {"type": "tab", "value": "info"} if key == "info" else None
    if cmd == "MODE":
        return {"type": "mode", "value": key} if key in ("text", "voice") else None
    if cmd == "ZOOM":
        return {"type": "zoom", "value": key} if key in ("in", "out") else None
    if cmd == "ROTATE":
        return {"type": "rotate", "value": key} if key in ("left", "right", "up", "down") else None
    if cmd == "WEIGHT":
        try:
            kg = float(arg.lower().replace("kg", "").strip())
        except ValueError:
            return None
        return {"type": "weight", "kg": round(kg, 1)} if 1 <= kg <= 1000 else None
    if cmd == "SENSITIVITY":
        return {"type": "sensitivity", "value": key} if key in ("low", "normal", "high") else None
    return None


def split_reply(answer):
    """Model text -> (clean text to show and speak, list of checked actions in order)."""
    actions = []
    for m in _TAG.finditer(answer):
        a = _make_action(m.group(1), m.group(2))
        if a and a not in actions and len(actions) < MAX_ACTIONS:
            actions.append(a)
    clean = _TAG.sub("", answer).replace("*", "")
    clean = re.sub(r"[ \t]+\n", "\n", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return clean, actions


def _trim(text, limit):
    """Cut very long text at the end of a sentence, never in the middle of one."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind(".\n"))
    return cut[:end + 1] if end > limit * 0.5 else cut


FAST_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash", "gemini-3.8-flash"]   # quick models first
_winner = [None]            # the request style that worked last time is tried first, so there are no wasted round trips
_cache = {}                 # repeated questions are answered instantly


def _fast_attempts(text, system, max_tokens):
    custom = os.environ.get("GEMINI_MODEL", "").strip()
    models = ([custom] if custom else []) + [m for m in FAST_MODELS if m != custom]
    tries = []
    for model in models:
        base = {"model": model, "system_instruction": system, "input": text}
        tries.append(("interactions " + model + " fast", API + "/interactions",
                      dict(base, generation_config={"max_output_tokens": max_tokens, "thinking_level": "minimal"})))
        tries.append(("interactions " + model, API + "/interactions",
                      dict(base, generation_config={"max_output_tokens": max_tokens})))
    for model in models[:2]:
        gc = {"maxOutputTokens": max_tokens}
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": text}]}]}
        tries.append(("generateContent " + model + " fast", API + "/models/" + model + ":generateContent",
                      dict(body, generationConfig=dict(gc, thinkingConfig={"thinkingLevel": "minimal"}))))
        tries.append(("generateContent " + model, API + "/models/" + model + ":generateContent", dict(body, generationConfig=gc)))
    if _winner[0]:
        tries.sort(key=lambda t: t[0] != _winner[0])           # stable: winner first, the rest keep their order
    return tries


def chat_gemini(data):
    """data = {'message', 'history': [{'role': 'user'|'guide', 'text'}], 'selected': 'Mars', 'date', 'context', 'ui', 'voice'}
    Returns ({'answer': text, 'actions': [..], 'action': first action or None, 'detail': bool}, HTTP status)."""
    key = _key()
    if not key:
        return {"error": "No Gemini key is set on this computer yet. See the setup steps."}, 503

    message = str(data.get("message", "")).strip()[:500]
    if not message:
        return {"error": "Please type or say something first."}, 400

    voice = bool(data.get("voice"))
    detail = bool(_DETAIL.search(message))                       # the user asked for a long, detailed answer
    system = ASSIST_SYSTEM
    if detail:
        system += (" THE USER ASKED FOR A DETAILED ANSWER: write the full detailed answer described under LENGTH now" +
                   (", as flowing spoken paragraphs with no lists or headings, because it will be read aloud." if voice else "."))
    elif voice:
        system += " VOICE MODE: unless the user asked for a detailed answer, use at most two short sentences."
    # the budget also covers command tags and any model 'thinking', so it is generous. Short answers stay short because the prompt says so
    max_tokens = (1100 if voice else 1500) if detail else (450 if voice else 700)

    lines = []
    for turn in (data.get("history") or [])[-8:]:
        if isinstance(turn, dict) and str(turn.get("text", "")).strip():
            who = "User" if turn.get("role") == "user" else "Guide"
            lines.append(who + ": " + str(turn["text"]).strip()[:900])
    selected = str(data.get("selected") or "").strip()[:40]
    facts = str(data.get("context") or "").strip()[:1200]
    ui = str(data.get("ui") or "").strip()[:700]
    text = ("App state: selected body = " + (selected or "none") + "; simulated date = " +
            (str(data.get("date") or "now")[:40]) + ".\n" +
            (("Controls state: " + ui + ".\n") if ui else "") +
            ((("Facts about the selected body: " + facts + "\n")) if facts else "") +
            (("\nConversation so far:\n" + "\n".join(lines) + "\n") if lines else "") +
            "\nUser: " + message + "\nGuide:")

    slow_tries = [0]
    for label, url, payload in _fast_attempts(text, system, max_tokens):
        try:
            status, reply = _call(url, payload, key)
        except _NoInternet as problem:
            print("[assistant] " + label + " -> could not reach Google (" + str(problem) + ")")
            if "timed out" in str(problem).lower() or "Timeout" in str(problem):
                slow_tries[0] += 1
                if slow_tries[0] < 2:
                    continue
            return {"error": "I can't reach the internet right now, so I can't answer. The planet facts still work offline."}, 503
        if 200 <= status < 300:
            answer = _find_text(reply)
            if not answer:
                return {"answer": "I could not come up with an answer to that. Try asking it another way.", "actions": [], "action": None, "detail": detail}, 200
            clean, actions = split_reply(answer)
            if not clean and actions:
                clean = "Done."
            result = {"answer": _trim(clean, 6000 if detail else 1500), "actions": actions,
                      "action": actions[0] if actions else None, "detail": detail}
            _winner[0] = label
            return result, 200
        message_text = _error_message(reply)
        print("[assistant] " + label + " -> HTTP " + str(status) + ": " + message_text[:160])
        if status in (401, 403) or "api key" in message_text.lower():
            return {"error": "Gemini did not accept the key. Check that it was copied correctly."}, 502
        if status == 429:
            return {"error": "The free limit was reached for now. Try again in a minute."}, 429
        if status in (400, 404):
            continue
        return {"error": "The assistant is having trouble right now. Try again in a moment."}, 502

    print("[assistant] none of the model names worked. Set GEMINI_MODEL to a current model name.")
    return {"error": "The assistant is not available right now."}, 502
