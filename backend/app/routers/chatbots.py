"""
Chatbots — multiple purpose-built conversational assistants inside a profile.

Each chatbot is a front-door persona (Sales Bot, HR Bot, …) with its own memory
scope, tools, permissions and model. The agent engine (local LLM) executes; the
chatbot is *not* tied to any one chat platform. A normalized channel-adapter
ingest endpoint lets Telegram/WhatsApp/Slack/etc. hit the same engine with a
common `{profileId, chatbotId, message}` shape (the "Bot Gateway").
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import llm
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Chatbot, ChatbotChannel, ChatConversation, ChatMessage,
                      MemoryItem, Tenant, now)
from ..security import ulid

router = APIRouter(tags=["chatbots"])

CHANNEL_TYPES = ["website", "desktop", "voice", "telegram", "whatsapp", "slack",
                 "teams", "discord", "email"]


def _pub(tenant_id, action, name):
    hub.emit(tenant_id, "chatbot.changed", {"action": action, "name": name})


# ───────────────────────────── Serialization ────────────────────────────────
def channel_dto(c: ChatbotChannel):
    cfg = c.config or {}
    return {"id": c.id, "type": c.type, "status": c.status,
            "account": cfg.get("account") or cfg.get("handle"),
            "has_token": bool(cfg.get("token"))}


def chatbot_dto(db, b: Chatbot):
    chans = db.query(ChatbotChannel).filter_by(chatbot_id=b.id).all()
    return {"id": b.id, "name": b.name, "purpose": b.purpose, "department": b.department,
            "model_id": b.model_id, "persona": b.persona,
            "memory_scopes": b.memory_scopes or [], "tools": b.tools or [],
            "permissions": b.permissions or {}, "color": b.color, "status": b.status,
            "linked_pipeline_id": b.linked_pipeline_id,
            "channels": [channel_dto(c) for c in chans]}


# ───────────────────────────── Chatbot CRUD ─────────────────────────────────
@router.get("/chatbots")
def list_chatbots(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Chatbot).filter_by(tenant_id=p.tenant_id).filter(
        Chatbot.status != "archived").order_by(Chatbot.created_at).all()
    return [chatbot_dto(db, b) for b in rows]


@router.get("/chatbots/{bid}")
def get_chatbot(bid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    b = db.get(Chatbot, bid)
    if not b or b.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Chatbot not found"})
    return chatbot_dto(db, b)


class ChatbotIn(BaseModel):
    name: str
    purpose: str | None = None
    department: str | None = None
    model_id: str = "mdl_gemma9b"
    persona: str | None = None
    memory_scopes: list[str] = ["business", "knowledge"]
    tools: list[str] = []
    color: str = "violet"
    linked_pipeline_id: str | None = None


@router.post("/chatbots")
def create_chatbot(body: ChatbotIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    b = Chatbot(id=ulid("cbt"), tenant_id=p.tenant_id, name=body.name, purpose=body.purpose,
                department=body.department, model_id=body.model_id,
                persona=body.persona or f"You are {body.name}, a helpful assistant for "
                        f"the {body.department or 'company'} team. Be concise and accurate.",
                memory_scopes=body.memory_scopes, tools=body.tools, color=body.color,
                linked_pipeline_id=body.linked_pipeline_id, status="active")
    db.add(b)
    db.flush()
    # Every chatbot is reachable in-app via the Website channel by default.
    db.add(ChatbotChannel(id=ulid("chc"), chatbot_id=b.id, tenant_id=p.tenant_id,
                          type="website", status="connected", config={}))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="chatbot.create",
          target=b.id, tenant_id=p.tenant_id, meta={"name": body.name})
    db.commit()
    _pub(p.tenant_id, "create", b.name)
    return chatbot_dto(db, b)


class ChatbotPatch(BaseModel):
    name: str | None = None
    purpose: str | None = None
    department: str | None = None
    model_id: str | None = None
    persona: str | None = None
    memory_scopes: list[str] | None = None
    tools: list[str] | None = None
    color: str | None = None
    status: str | None = None
    linked_pipeline_id: str | None = None


@router.patch("/chatbots/{bid}")
def update_chatbot(bid: str, body: ChatbotPatch, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    b = db.get(Chatbot, bid)
    if not b or b.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Chatbot not found"})
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(b, f, v)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="chatbot.update",
          target=b.id, tenant_id=p.tenant_id)
    db.commit()
    _pub(p.tenant_id, "update", b.name)
    return chatbot_dto(db, b)


@router.delete("/chatbots/{bid}")
def delete_chatbot(bid: str, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    b = db.get(Chatbot, bid)
    if not b or b.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Chatbot not found"})
    b.status = "archived"
    name = b.name
    audit(db, plane="local", actor=f"user:{p.user_id}", action="chatbot.delete",
          target=bid, tenant_id=p.tenant_id)
    db.commit()
    _pub(p.tenant_id, "delete", name)
    return {"status": "archived", "message": f"Deleted chatbot “{name}”."}


# ───────────────────────────── Channels (adapter layer) ─────────────────────
@router.get("/chatbots/{bid}/channels")
def list_channels(bid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(ChatbotChannel).filter_by(chatbot_id=bid, tenant_id=p.tenant_id).all()
    present = {c.type: channel_dto(c) for c in rows}
    # surface all supported channel types, connected or not
    return [present.get(t, {"id": None, "type": t, "status": "disconnected",
                            "account": None, "has_token": False}) for t in CHANNEL_TYPES]


class ConnectChannelIn(BaseModel):
    type: str
    token: str | None = None
    account: str | None = None


@router.post("/chatbots/{bid}/channels")
def connect_channel(bid: str, body: ConnectChannelIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    b = db.get(Chatbot, bid)
    if not b or b.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Chatbot not found"})
    if body.type not in CHANNEL_TYPES:
        raise HTTPException(422, detail={"code": "VALIDATION_ERROR", "message": "Unknown channel"})
    c = db.query(ChatbotChannel).filter_by(chatbot_id=bid, type=body.type).first()
    if not c:
        c = ChatbotChannel(id=ulid("chc"), chatbot_id=bid, tenant_id=p.tenant_id, type=body.type)
        db.add(c)
    c.config = {"token": body.token, "account": body.account}
    c.status = "connected"
    audit(db, plane="local", actor=f"user:{p.user_id}", action="channel.connect",
          target=f"{bid}:{body.type}", tenant_id=p.tenant_id)
    db.commit()
    _pub(p.tenant_id, "channel", f"{b.name} · {body.type} connected")
    return {**channel_dto(c), "message": f"Connected {body.type} to {b.name}."}


@router.delete("/chatbots/{bid}/channels/{ctype}")
def disconnect_channel(bid: str, ctype: str, p: Principal = Depends(current_user),
                       db: Session = Depends(get_db)):
    b = db.get(Chatbot, bid)
    if not b or b.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Chatbot not found"})
    c = db.query(ChatbotChannel).filter_by(chatbot_id=bid, tenant_id=p.tenant_id, type=ctype).first()
    if c:
        c.status = "disconnected"
        c.config = {}
        audit(db, plane="local", actor=f"user:{p.user_id}", action="channel.disconnect",
              target=f"{bid}:{ctype}", tenant_id=p.tenant_id)
        db.commit()
        _pub(p.tenant_id, "channel", f"{b.name} · {ctype} disconnected")
    return {"status": "disconnected", "message": f"Disconnected {ctype} from {b.name}."}


# ───────────────────────────── Chat engine ──────────────────────────────────
def _retrieve(db, tenant_id, scopes, query, k=4):
    """Scoped memory retrieval for grounding (hybrid keyword + embedding)."""
    q = db.query(MemoryItem).filter_by(tenant_id=tenant_id).filter(MemoryItem.tier != "deleted")
    if scopes:
        q = q.filter(MemoryItem.memory_class.in_(scopes))
    rows = q.all()
    terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
    qvec = llm.embed(query)

    def score(m):
        text = ((m.title or "") + " " + (m.body or "")).lower()
        kw = sum(text.count(t) for t in terms)
        sem = llm.cosine(qvec, m.embedding) if (qvec and m.embedding) else 0
        return sem * 0.8 + min(kw, 5) / 5 * 0.2 if qvec else kw
    rows = sorted(rows, key=score, reverse=True)
    return [m for m in rows if score(m) > 0][:k]


def _run_chat(db, p_user_id, tenant_id, bot, message, conversation, channel):
    # store user message
    db.add(ChatMessage(id=ulid("msg"), conversation_id=conversation.id, role="user",
                       body=message, channel=channel))
    db.flush()

    docs = _retrieve(db, tenant_id, bot.memory_scopes or [], message)
    context = "\n".join(f"- {m.title}: {(m.body or '')[:280]}" for m in docs)
    history = db.query(ChatMessage).filter_by(conversation_id=conversation.id).order_by(
        ChatMessage.at.desc()).limit(7).all()
    history = list(reversed(history))[:-1]  # exclude the just-added user msg
    convo = "\n".join(f"{'User' if h.role == 'user' else bot.name}: {h.body}" for h in history)

    system = (f"{bot.persona}\n\n"
              f"You are '{bot.name}', the {bot.department or 'company'} assistant for "
              f"the company. Answer using the company context when relevant. If you don't "
              f"know, say so. Keep replies short and helpful.")
    prompt = (f"Company context:\n{context or '(no matching records)'}\n\n"
              f"Recent conversation:\n{convo or '(start)'}\n\nUser: {message}\n{bot.name}:")
    reply = llm.chat(prompt, system=system, smart=False, num_predict=350, timeout=120)
    engine = "local-llm" if reply else "template"
    if not reply:
        reply = (f"I'm {bot.name}. " +
                 (f"Here's what I found: {docs[0].title} — {(docs[0].body or '')[:160]}"
                  if docs else "I couldn't find anything on that in the company memory yet."))

    citations = [{"title": m.title, "class": m.memory_class} for m in docs]
    db.add(ChatMessage(id=ulid("msg"), conversation_id=conversation.id, role="assistant",
                       body=reply, channel=channel, citations=citations, engine=engine))
    audit(db, plane="local", actor=f"user:{p_user_id or 'channel'}", action="chatbot.message",
          target=bot.id, tenant_id=tenant_id, meta={"channel": channel})
    db.commit()
    return {"response": reply, "conversation_id": conversation.id,
            "citations": citations, "engine": engine}


class ChatIn(BaseModel):
    message: str
    conversation_id: str | None = None
    channel: str = "website"


@router.post("/chatbots/{bid}/chat")
def chat(bid: str, body: ChatIn, p: Principal = Depends(current_user),
         db: Session = Depends(get_db)):
    bot = db.get(Chatbot, bid)
    if not bot or bot.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Chatbot not found"})
    conv = db.get(ChatConversation, body.conversation_id) if body.conversation_id else None
    if not conv or conv.chatbot_id != bid:
        conv = ChatConversation(id=ulid("cvn"), chatbot_id=bid, tenant_id=p.tenant_id,
                                channel=body.channel, title=body.message[:50])
        db.add(conv)
        db.flush()
    return _run_chat(db, p.user_id, p.tenant_id, bot, body.message, conv, body.channel)


@router.get("/chatbots/{bid}/conversations")
def conversations(bid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    convs = db.query(ChatConversation).filter_by(chatbot_id=bid, tenant_id=p.tenant_id).order_by(
        ChatConversation.created_at.desc()).all()
    out = []
    for c in convs:
        msgs = db.query(ChatMessage).filter_by(conversation_id=c.id).order_by(ChatMessage.at).all()
        out.append({"id": c.id, "title": c.title, "channel": c.channel,
                    "messages": [{"role": m.role, "body": m.body, "channel": m.channel,
                                  "citations": m.citations or [], "engine": m.engine,
                                  "at": m.at.isoformat()} for m in msgs]})
    return out


# ───────────────────────────── Channel-adapter ingest (Bot Gateway) ─────────
class IngestIn(BaseModel):
    platform: str                       # telegram|whatsapp|slack|...
    bot_ref: str                        # chatbot id or name
    external_user: str
    message: str


@router.post("/channels/ingest")
def channel_ingest(body: IngestIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    """Normalized inbound from any platform → same engine (the adapter common format)."""
    bot = db.get(Chatbot, body.bot_ref)
    if not bot:
        bot = db.query(Chatbot).filter(Chatbot.tenant_id == p.tenant_id,
                                       func.lower(Chatbot.name) == body.bot_ref.lower()).first()
    if not bot or bot.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Chatbot not found"})
    conv = db.query(ChatConversation).filter_by(
        chatbot_id=bot.id, channel=body.platform, external_user=body.external_user).first()
    if not conv:
        conv = ChatConversation(id=ulid("cvn"), chatbot_id=bot.id, tenant_id=p.tenant_id,
                                channel=body.platform, external_user=body.external_user,
                                title=f"{body.platform}:{body.external_user}")
        db.add(conv)
        db.flush()
    r = _run_chat(db, None, p.tenant_id, bot, body.message, conv, body.platform)
    return {"profileId": p.tenant_id, "chatbotId": bot.id, "platform": body.platform,
            "response": r["response"]}


# ──────────────────────── voice / natural-language control ───────────────────
# A conversational resolver: broad phrasing + an LLM fallback for anything the
# patterns miss + interactive CLARIFY (it asks a question and we continue with
# the `pending` context on the next turn).
class ResolveIn(BaseModel):
    transcript: str
    pending: dict | None = None        # {action, need, slots} from a prior clarify


_CHAN = ["telegram", "whatsapp", "slack", "teams", "discord", "email", "voice", "website", "desktop"]
_CHAN_SYN = {"telegram": "telegram", "whatsapp": "whatsapp", "whats app": "whatsapp", "slack": "slack",
             "teams": "teams", "discord": "discord", "email": "email", "mail": "email",
             "voice": "voice", "website": "website", "web": "website", "desktop": "desktop"}
_CREATE = re.compile(r"\b(create|add|new|make|build|set ?up|spin ?up|launch|start|i (?:want|need|'?d like)|register)\b", re.I)
_DELETE = re.compile(r"\b(delete|remove|archive|get rid of|kill|drop|trash|deactivate|retire)\b", re.I)
_OPEN = re.compile(r"\b(open|show|switch|go to|select|talk to|view|let me see|bring up|pull up|chat with)\b", re.I)
_CONNECT = re.compile(r"\b(connect|add|enable|link|hook up|integrate|turn on|set ?up|attach)\b", re.I)
_DISCONNECT = re.compile(r"\b(disconnect|unlink|disable|turn off|remove|detach|drop)\b", re.I)
_BOTWORD = re.compile(r"\b(bot|chatbot|chat bot|assistant|agent|helpdesk)\b", re.I)
_YES = re.compile(r"\b(yes|yeah|yep|sure|ok|okay|go ahead|do it|confirm|please)\b", re.I)
_NO = re.compile(r"\b(no|nope|cancel|stop|don'?t|never ?mind)\b", re.I)


def _match_bot(db, tenant_id, text):
    low = (text or "").lower()
    best, score = None, 0
    for b in db.query(Chatbot).filter_by(tenant_id=tenant_id, status="active").all():
        nm = (b.name or "").lower()
        if nm and nm in low:                       # full-name match wins
            return b
        for w in re.findall(r"[a-z0-9]+", nm):
            if len(w) > 2 and w not in ("bot", "the") and w in low and len(w) > score:
                best, score = b, len(w)
    return best


def _match_channel(text):
    low = (text or "").lower()
    for k, v in _CHAN_SYN.items():
        if k in low:
            return v
    return None


def _bot_names(db, tenant_id):
    return [b.name for b in db.query(Chatbot).filter_by(tenant_id=tenant_id, status="active").all()]


def _clarify(action, need, question, slots=None):
    return {"action": "clarify", "need": need, "question": question, "message": question,
            "pending": {"action": action, "need": need, "slots": slots or {}}}


def _do(action, **slots):
    msg = {"create_bot": f"Creating {slots.get('name', 'a new assistant')}.",
           "delete_bot": f"Deleting {slots.get('bot_name', 'it')}.",
           "open_bot": f"Opening {slots.get('bot_name', 'it')}.",
           "connect_channel": f"Connecting {slots.get('channel', 'the channel')}.",
           "disconnect_channel": f"Disconnecting {slots.get('channel', 'the channel')}."}.get(action, "Done.")
    return {"action": action, "message": msg, **slots}


def _finalize(db, tenant_id, action, slots):
    """Turn a (possibly partial) action+slots into a concrete action or a clarify."""
    if action in ("delete_bot", "open_bot"):
        if not slots.get("bot_id"):
            names = _bot_names(db, tenant_id)
            return _clarify(action, "bot",
                            ("You don't have any chatbots yet — say \"create a sales bot\"."
                             if not names else f"Which chatbot — {', '.join(names)}?"), slots)
        return _do(action, **slots)
    if action in ("connect_channel", "disconnect_channel"):
        if not slots.get("channel"):
            return _clarify(action, "channel",
                            "Which channel — Telegram, WhatsApp, Slack, Discord, Teams or Email?", slots)
        return _do(action, **slots)
    if action == "create_bot":
        if not slots.get("name"):
            return _clarify(action, "name", "What should I call the chatbot?", slots)
        return _do(action, **slots)
    return {"action": "none", "message": "I'm not sure what to do."}


def _resolve_fresh(db, tenant_id, text):
    low = text.lower()
    chan = _match_channel(text)
    bot = _match_bot(db, tenant_id, text)
    has_botword = bool(_BOTWORD.search(text))

    # channel ops (check disconnect before connect; both share "remove"/"add")
    if chan and _DISCONNECT.search(low) and not _CREATE.search(low.replace("set up", "")):
        return _finalize(db, tenant_id, "disconnect_channel",
                         {"channel": chan, "bot_id": bot.id if bot else None, "bot_name": bot.name if bot else None})
    if chan and (_CONNECT.search(low) or has_botword is False):
        return _finalize(db, tenant_id, "connect_channel",
                         {"channel": chan, "bot_id": bot.id if bot else None, "bot_name": bot.name if bot else None})

    # delete (with a bot word OR a clearly-named bot)
    if _DELETE.search(low) and (has_botword or bot):
        return _finalize(db, tenant_id, "delete_bot",
                         {"bot_id": bot.id if bot else None, "bot_name": bot.name if bot else None})

    # create
    if _CREATE.search(low) and has_botword:
        name = None
        mn = re.search(r"\b(?:called|named|name it|titled)\s+([A-Za-z][\w ]+?)(?:\s+(?:for|to|that)\b|[.,]|$)", text, re.I)
        if mn:
            name = mn.group(1).strip().title()
        else:
            # grab the descriptor that sits right before bot/chatbot/assistant, then
            # strip any leading verb/article so "spin up an HR assistant" → "HR Bot".
            md = re.search(r"([a-z][a-z ]*?)\s+(?:bot|chatbot|chat bot|assistant)\b", text, re.I)
            if md:
                cand = re.sub(r"^(?:please\s+)?(?:create|add|make|build|set ?up|spin ?up|launch|start|new|"
                              r"register|i\s+(?:want|need|'?d like))\b\s*", "", md.group(1).strip(), flags=re.I)
                cand = re.sub(r"\b(?:a|an|the|me|some|new)\b", "", cand, flags=re.I).strip()
                if cand and len(cand) > 1:
                    name = " ".join(w.upper() if len(w) <= 3 else w.title() for w in cand.split()) + " Bot"
        purpose = None
        mp = re.search(r"\bfor\s+(.+)$", text, re.I)
        if mp:
            purpose = mp.group(1).strip(" .'\"")
        return _finalize(db, tenant_id, "create_bot", {"name": name, "purpose": purpose})

    # open / switch
    if _OPEN.search(low) or bot:
        return _finalize(db, tenant_id, "open_bot", {"bot_id": bot.id if bot else None, "bot_name": bot.name if bot else None})

    return None


def _llm_resolve(db, tenant_id, text):
    """Fallback: let the local LLM classify a free-form command into an action."""
    if not llm.available():
        return None
    names = _bot_names(db, tenant_id)
    j = llm.chat_json(
        f"Existing chatbots: {names or 'none'}. Channels: telegram, whatsapp, slack, teams, discord, email.\n"
        f"User said: \"{text}\"\n"
        "Map it to ONE action. Reply JSON only: "
        '{"action":"create_bot|delete_bot|open_bot|connect_channel|disconnect_channel|none",'
        '"name":"<for create>","purpose":"<optional>","bot":"<existing chatbot name>","channel":"<channel>"}',
        system="You map a user's request about managing chatbots to a single structured action.",
        num_predict=120, timeout=45)
    if not j or not j.get("action") or j["action"] == "none":
        return None
    action = j["action"]
    slots = {}
    if j.get("bot"):
        b = _match_bot(db, tenant_id, j["bot"])
        if b:
            slots["bot_id"], slots["bot_name"] = b.id, b.name
    if j.get("channel"):
        slots["channel"] = _match_channel(j["channel"])
    if j.get("name"):
        slots["name"] = str(j["name"]).strip().title()
    if j.get("purpose"):
        slots["purpose"] = j["purpose"]
    return _finalize(db, tenant_id, action, slots)


@router.post("/chatbots/resolve")
def chatbots_resolve(body: ResolveIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Conversational resolver — broad phrasing, LLM fallback, and clarify-then-continue."""
    text = (body.transcript or "").strip()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}

    # Continuing a clarification: interpret the answer in the context of `pending`.
    pend = body.pending or None
    if pend and pend.get("action"):
        action, need = pend["action"], pend.get("need")
        slots = dict(pend.get("slots") or {})
        if _NO.search(text.lower()) and not _match_bot(db, p.tenant_id, text):
            return {"action": "cancelled", "message": "Okay, cancelled."}
        if need == "bot":
            b = _match_bot(db, p.tenant_id, text)
            if not b:
                names = _bot_names(db, p.tenant_id)
                return _clarify(action, "bot", f"I couldn't find that one. Which chatbot — {', '.join(names)}?", slots)
            slots.update(bot_id=b.id, bot_name=b.name)
            return _finalize(db, p.tenant_id, action, slots)
        if need == "channel":
            ch = _match_channel(text)
            if not ch:
                return _clarify(action, "channel", "I didn't catch the channel. Telegram, WhatsApp, Slack, Discord, Teams or Email?", slots)
            slots["channel"] = ch
            return _finalize(db, p.tenant_id, action, slots)
        if need == "name":
            nm = re.sub(r"^(call it|name it|it'?s|its|the name is)\s+", "", text, flags=re.I).strip(" .'\"")
            slots["name"] = nm.title()
            return _finalize(db, p.tenant_id, "create_bot", slots)
        # unknown need → re-resolve fresh
    # Fresh command: patterns first, then LLM fallback, then a friendly clarify.
    r = _resolve_fresh(db, p.tenant_id, text)
    if r:
        return r
    r = _llm_resolve(db, p.tenant_id, text)
    if r:
        return r
    return _clarify("menu", "action",
                    "I can create a chatbot, open one, delete one, or connect a channel. What would you like to do?")
