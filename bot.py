#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════
#   MASTER FF GEN — TELEGRAM BOT  (v2.1  ·  MEMORY-SAFE)
#   Owner : Kanha
# ══════════════════════════════════════════════════════════════════════════

# ── OOM GUARD: shrink thread stack BEFORE importing threading ──
import threading
try:
    threading.stack_size(256 * 1024)   # 256 KB per thread (default = 8 MB)
except Exception:
    pass

import sys, os, gc, time, json, random, string, hmac, hashlib
import asyncio, base64, codecs, logging, signal, atexit
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── diagnostics ──
def diag(msg):
    print(f"[DIAG] {msg}", flush=True)

def mem_mb():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return -1

diag(f"boot · py={sys.version.split()[0]} · pid={os.getpid()} · rss={mem_mb():.1f}MB")

# ── third-party ──
try:
    import requests
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    import urllib3
    urllib3.disable_warnings()
    diag(f"imports (net) done · rss={mem_mb():.1f}MB")
except Exception as e:
    diag(f"FATAL import (net): {e}")
    sys.exit(1)

try:
    from aiogram import Bot, Dispatcher, F
    from aiogram.types import (
        Message, CallbackQuery, BufferedInputFile,
        InlineKeyboardMarkup, InlineKeyboardButton,
    )
    from aiogram.filters import Command
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.fsm.storage.memory import MemoryStorage
    diag(f"imports (aiogram) done · rss={mem_mb():.1f}MB")
except Exception as e:
    diag(f"FATAL import (aiogram): {e}")
    sys.exit(1)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ffgen")

def _on_exit():
    diag(f"exit · rss={mem_mb():.1f}MB · uptime={time.time()-_BOOT:.1f}s")

_BOOT = time.time()
atexit.register(_on_exit)

def _sigterm(signum, frame):
    diag(f"signal {signum} received — shutting down")
    sys.exit(0)

for s in (signal.SIGTERM, signal.SIGINT):
    try: signal.signal(s, _sigterm)
    except Exception: pass

# ══════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════
BOT_TOKEN       = "9041420292:AAHilI1-Ij1OYB6t13DzXn1pp2lX5w_MEKg"
API_URL         = "https://tesnewmajor1.vercel.app/api/v2/gen"
ACTIVATION_API  = "https://rg-act-ofc.vercel.app/jxe/act"

NAME_PREFIX     = "MASTER"
PASS_PREFIX     = "MASTER"
DEFAULT_THREADS = 5          # LOW on purpose — prevents OOM
MAX_THREADS     = 30         # hard cap
MAX_ACCOUNTS    = 2000
MAX_DUP_RETRIES = 4
STALL_TIMEOUT   = 90

OUTPUT_DIR  = "output"
STATS_FILE  = os.path.join(OUTPUT_DIR, "stats.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEX_KEY = bytes.fromhex(
    "32656534343831396539623435393838343531343130363762323831363231383734643064356437616639643866376530306331653534373135623764316533"
)
AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

REGION_LANG = {"ME":"ar","IND":"hi","ID":"id","VN":"vi","TH":"th",
               "BD":"bn","PK":"ur","TW":"zh","CIS":"ru","SAC":"es","BR":"pt"}
REGIONS = ["IND","ME","ID","VN","TH","BD","PK","TW","CIS","SAC","BR"]

# ══════════════════════════════════════════════════════════════════════════
# CRYPTO / PROTO HELPERS
# ══════════════════════════════════════════════════════════════════════════
FIELD_22 = bytes.fromhex(
    "4747524501010100620200001052aa0d669c6a368f08338060d2ee0690053af84a41edcd3558556ec10f24f4"
    "6c93ac64ca41a16732c46a2cb071246a79b8929032f9e1b6f4ef331bd53cabf29b09b97349a46e9863c0314e"
    "1a0d80819fef8aabf03876b3d037db354a7ccb5c1bce96411fb3753f6f50e44c69c4ed617fa30efb8ffc0517"
    "ff2f636739be1f304d999cfd6fd48bf69454199794c3dc88f55a4bdbd66534d5a061359cdfd1fb680cd37918"
    "df9fdb3cf7d80067b0a3506c90063cf62b2ccec11e23913a2fd7c4ef091331967bb518a5ad1e551146b90821"
    "be800883abadde39d6c80a5d798611466c748f075481806c5842ce45e6bd4e3368ec08fe2ec41ceb880cd862"
    "49eb71693f79f0bccf9e590c3fae12519fe08c7a1905d0927690109e0df28574bb14847225db1a59230e6662"
    "ed7730e15ff9a6c815cb41b420edeada735a4b03e181037c37c2c850257311df2f07b0a56e759372cbd0268e"
    "3f13a292ee4373e38ab5096e0342a5e0d7fec6da2bbc265d74baadd2b24ee4f74862f82c21d6694bac53f8ce"
    "80312a30068a6276a641c19b11d0305c6fe2f531ac7de578b29f543697f5c73663e6f23aa15277b6122dcd4d"
    "4171e38f9ac0b173f39c58416a16c5c1f4a35acd065ce78f449cf538a249339e763272d458e4ed86c976591a"
    "9c066b3a37111e44091eb6b5a795249f3e5145db022a6055f2cc675936391312f688f89627845df222a91156"
    "555225be36f9714a0ba50246d0f003bda3c9c1292ab73b4f79635ddd023218eda93a302d79e023404c143965"
    "44a930b98ed54771aca7fec10d095587685b473e81a9619764fad9256529dcd6e911f4f4629612287d4ee3ec"
    "5389f6ec4ec020b0e2aac017232a9197be9e46239ce690fe5d4872b2e98e651510c971667f3aca8b59f3e9d5"
    "0e43"
)

def encode_f14(s):
    ks = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
          0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
    return bytes(ord(c) ^ ks[i % len(ks)] for i, c in enumerate(s))

def encode_varint(n):
    if n < 0: return b''
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def build_proto(fields):
    parts = []
    for k, v in fields.items():
        if isinstance(v, dict):
            n = build_proto(v)
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(n)) + n)
        elif isinstance(v, int):
            parts.append(encode_varint((k << 3) | 0) + encode_varint(v))
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(ev)) + ev)
    return b''.join(parts)

def aes_encrypt(hex_data):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(bytes.fromhex(hex_data), AES.block_size))

def encrypt_api(plain_hex):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(bytes.fromhex(plain_hex), AES.block_size)).hex()

# ══════════════════════════════════════════════════════════════════════════
# DEVICE / WAF
# ══════════════════════════════════════════════════════════════════════════
UAS = [
    "GarenaMSDK/4.0.42(SM-A525F ;Android)",
    "GarenaMSDK/4.0.41(SM-S918B;Android 14;en;IN;)",
    "GarenaMSDK/4.0.42(OnePlus 11;Android 13;en;US;)",
    "GarenaMSDK/4.0.41(Pixel 7 Pro;Android 14;en;US;)",
    "GarenaMSDK/4.0.43(realme 9 Pro;Android 12;en;TH;)",
]
DEVICE_MODELS = [
    ("SM-A525F","ARMv8 VFPv4 NEON VMH | 2200 | 8","Adreno (TM) 618"),
    ("SM-S918B","ARMv8 VFPv4 NEON VMH | 3200 | 8","Adreno (TM) 740"),
    ("Pixel 7 Pro","ARMv8 VFPv4 NEON VMH | 2800 | 8","Mali-G710"),
    ("OnePlus 11","ARMv8 VFPv4 NEON VMH | 3200 | 8","Adreno (TM) 740"),
]
ANDROID_VERSIONS = [
    ("Android OS 12 / API-31 (SP1A.210812.016)","12","31"),
    ("Android OS 13 / API-33 (TQ3A.230805.001)","13","33"),
    ("Android OS 14 / API-34 (UP1A.231005.007)","14","34"),
]
OPERATORS = ["Telkomsel","Indosat","XL Axiata","Airtel","Jio","Vodafone","Jazz"]
NETWORKS  = ["WIFI","4G","5G"]
SDK_VER   = ["4.0.41","4.0.42","4.0.43"]

def _rh(n): return ''.join(random.choices("0123456789abcdef", k=n))
def _uuid(): return f"{_rh(8)}-{_rh(4)}-{_rh(4)}-{_rh(4)}-{_rh(12)}"

def make_device():
    model, cpu, gpu = random.choice(DEVICE_MODELS)
    af, av, api = random.choice(ANDROID_VERSIONS)
    return {
        "model": model, "cpu": cpu, "gpu": gpu, "android_full": af,
        "android_version": av, "api_level": api,
        "operator": random.choice(OPERATORS), "network": random.choice(NETWORKS),
        "sdk": random.choice(SDK_VER), "device_id": _rh(32),
        "android_id": _rh(16), "uuid": _uuid(), "imei": _rh(15),
    }

_tls = threading.local()
ACT_LOCK = threading.Lock()
LAST_ACT_TIME = [0.0]

def get_session():
    if not hasattr(_tls, "session"):
        _tls.session = requests.Session()
    return _tls.session

def get_device():
    if not hasattr(_tls, "device"):
        _tls.device = make_device()
    return _tls.device

def reset_thread():
    old = getattr(_tls, "session", None)
    if old is not None:
        try: old.close()
        except Exception: pass
    _tls.session = requests.Session()
    _tls.device  = make_device()

def hdrs(base=None):
    dev = get_device()
    h = dict(base or {})
    h.setdefault("X-Device-Id", dev["device_id"])
    h.setdefault("X-Android-Id", dev["android_id"])
    h.setdefault("X-Device-Model", dev["model"])
    h.setdefault("X-OS-Version", dev["android_version"])
    h.setdefault("X-API-Level", dev["api_level"])
    h.setdefault("X-SDK-Version", dev["sdk"])
    return h

def req(method, url, retries=2, **kw):
    s = get_session()
    for attempt in range(retries + 1):
        try:
            kw.setdefault("timeout", 20)
            kw["headers"] = hdrs(kw.get("headers"))
            kw["verify"] = False
            time.sleep(random.uniform(0.1, 0.35))
            r = s.request(method, url, **kw)
            if r.status_code in (403, 429, 500, 502, 503, 504):
                if attempt < retries:
                    reset_thread(); s = get_session()
                    time.sleep(0.4 * (2 ** attempt))
                    continue
            return r
        except Exception:
            if attempt < retries:
                reset_thread(); s = get_session()
                time.sleep(0.4 * (attempt + 1))
                continue
            return None
    return None

# ══════════════════════════════════════════════════════════════════════════
# FF CORE
# ══════════════════════════════════════════════════════════════════════════
def gen_name(): return NAME_PREFIX + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def api_get_one(region):
    try:
        params = {"count": 1, "name": NAME_PREFIX, "password": PASS_PREFIX, "region": region.upper()}
        r = requests.get(API_URL, params=params, timeout=20, verify=False)
        if r.status_code == 200:
            d = r.json()
            if d.get("success") and d.get("accounts"):
                a = d["accounts"][0]
                uid = str(a.get("uid","")).strip()
                aid = str(a.get("account_id","N/A")).strip()
                if uid and aid and aid != "N/A":
                    return {
                        "uid": uid, "password": a.get("password",""),
                        "name": a.get("name", NAME_PREFIX),
                        "account_id": aid, "region": region.upper(),
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
    except Exception:
        pass
    return None

def create_account_direct(region):
    try:
        rand_part = "".join(random.choices("0123456789ABCDEF", k=16))
        password  = f"{PASS_PREFIX}_{rand_part}"
        url = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
        payload = {"app_id":100067,"client_type":2,"password":password,"source":2}
        body_json = json.dumps(payload, separators=(",",":"))
        sig = hmac.new(HEX_KEY, body_json.encode("utf-8"), hashlib.sha256).hexdigest()
        headers = hdrs({
            "User-Agent": random.choice(UAS),
            "Accept": "application/json",
            "Authorization": f"Signature {sig}",
            "Content-Type": "application/json; charset=utf-8",
            "Host": "100067.connect.garena.com",
        })
        r = req("POST", url, headers=headers, data=body_json)
        if r and r.status_code == 200:
            res = r.json()
            if "data" in res and "uid" in res["data"]:
                return _get_token(str(res["data"]["uid"]), password, region)
    except Exception:
        pass
    return None

def _get_token(uid, password, region):
    try:
        url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        headers = hdrs({"Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": random.choice(UAS)})
        body = {"uid":uid,"password":password,"response_type":"token",
                "client_type":"2","client_secret":HEX_KEY,"client_id":"100067"}
        r = req("POST", url, headers=headers, data=body)
        if r and r.status_code == 200 and 'open_id' in r.json():
            j = r.json()
            open_id = j['open_id']; at = j["access_token"]
            ks = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
                  0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
            encoded = "".join(chr(ord(open_id[i]) ^ ks[i % len(ks)]) for i in range(len(open_id)))
            field = codecs.decode(
                ''.join(c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}' for c in encoded),
                'unicode_escape'
            ).encode('latin1')
            return _major_register(at, open_id, field, uid, password, region)
    except Exception:
        pass
    return None

def _major_register(at, open_id, field, uid, password, region):
    try:
        base_url = ("https://loginbp.ppmainecoonghj.com/MajorRegister"
                    if region.upper() not in ["ME","TH"]
                    else "https://loginbp.common.ggbluefox.com/MajorRegister")
        name = gen_name()
        headers = hdrs({
            'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Accept': '*/*', 'Authorization': 'Bearer', 'X-GA': 'v1 1',
            'ReleaseVersion': "OB55",
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Unity-Version': '2018.4.12f1',
        })
        lang = REGION_LANG.get(region.upper(), "en")
        reg_msg = {1:name, 2:at, 3:open_id, 5:102000007, 6:4, 7:1, 13:1,
                   14:encode_f14(open_id), 15:lang, 16:2, 20:"2.132.4", 21:1, 22:FIELD_22}
        encrypted = aes_encrypt(build_proto(reg_msg).hex())
        req("POST", base_url, headers=headers, data=encrypted)
        lg = _major_login(uid, password, at, open_id, region)
        aid = lg.get("account_id","N/A")
        if aid != "N/A":
            return {
                "uid": uid, "password": password, "name": name,
                "account_id": aid, "region": region.upper(),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
    except Exception:
        pass
    return None

def _major_login(uid, password, at, open_id, region):
    try:
        lang = REGION_LANG.get(region.upper(), "en")
        dev = get_device()
        open_b = open_id.encode() if isinstance(open_id, str) else open_id
        at_b   = at.encode() if isinstance(at, str) else at
        payload = {
            3: datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            4: b'free fire', 5: 1, 7: "2.132.4", 8: dev["android_full"],
            9: b'Handheld', 10: dev["operator"], 11: dev["network"],
            12: 1280, 13: 720, 14: b'240', 15: dev["cpu"],
            16: 6000, 17: dev["gpu"], 18: f"{dev['gpu']}|OpenGL ES 3.2",
            19: f'Google|{dev["uuid"]}',
            20: f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}",
            21: lang, 22: open_b, 23: b'4', 24: b'Handheld', 25: dev["model"],
            26: lang, 29: at_b, 30: 1, 41: dev["operator"], 42: dev["network"],
            57: b'1ac4b80ecf0478a44203bf8fac6120f5',
            60: 30000, 61: 30000, 62: 2519, 63: 243, 64: 32357, 65: 34308,
            66: 32357, 67: 34308, 73: 1,
            74: b'/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/lib/arm',
            76: 2,
            77: b'428775ab8c8845bd341b5357ec61d15e|/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/base.apk',
            78: 2, 79: 1, 81: b'32', 83: b'2019118525', 85: 3,
            86: b'OpenGLES3', 87: 4095, 88: 4,
            92: 20000, 93: b'android_max',
            94: b'KqsHT2gyPt7vUCc9SCjv2ioi3WEZSEL86ErvXB38suVVK/Z4IVt78ESl/r2S15C1pqu/j6ZmgFL7HbwoFiiVconX08ooKiisQffvEAPCo/C+Lahr',
            96: b'{"cur_rate":null,"support_etc2":true}', 97: 1, 98: 1, 99: b'4', 100: b'4', 102: b'',
            104: 77149, 105: 1,
            106: b'https://dl.cdn.freefiremobile.com/live/ABHotUpdates/|https://dl-core.cdn.freefiremobile.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462',
            107: b'c8e41b7a93f02d56e1a94c7b8203f5d1',
        }
        data = build_proto(payload)
        url = ("https://loginbp.ppmainecoonghj.com/MajorLogin"
               if region.upper() not in ["ME","TH"]
               else "https://loginbp.common.ggbluefox.com/MajorLogin")
        headers = hdrs({
            'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Accept': '*/*', 'Authorization': 'Bearer', 'X-GA': 'v1 1',
            'X-Ga-Sv': '1789534056', 'ReleaseVersion': "OB55",
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Unity-Version': '2018.4.12f1',
        })
        enc_hex = encrypt_api(data.hex())
        r = req("POST", url, headers=headers, data=bytes.fromhex(enc_hex))
        if r and r.status_code == 200 and len(r.text) > 10:
            j = r.text.find("eyJ")
            if j != -1:
                jwt = r.text[j:]
                sd = jwt.find(".", jwt.find(".")+1)
                if sd != -1:
                    jwt = jwt[:sd+44]
                    try:
                        parts = jwt.split('.')
                        if len(parts) >= 2:
                            pp = parts[1]; padding = 4 - len(pp) % 4
                            if padding != 4: pp += '=' * padding
                            claims = json.loads(base64.urlsafe_b64decode(pp))
                            aid = claims.get('account_id') or claims.get('external_id')
                            if aid:
                                return {"account_id": str(aid), "jwt_token": jwt}
                    except Exception:
                        pass
    except Exception:
        pass
    return {"account_id": "N/A", "jwt_token": ""}

def activate_account(uid, password):
    uid = str(uid).strip(); password = str(password).strip()
    if not uid or not password:
        return {"activated": False, "status": "INVALID"}
    try:
        with ACT_LOCK:
            now = time.time()
            w = 1.5 - (now - LAST_ACT_TIME[0])
            if w > 0: time.sleep(w)
            LAST_ACT_TIME[0] = time.time()
        r = requests.get(ACTIVATION_API, params={"uid": uid, "password": password},
                         timeout=10, verify=False,
                         headers={"User-Agent": random.choice(UAS)})
        if 200 <= r.status_code < 300:
            return {"activated": True, "status": "ACTIVATED"}
        return {"activated": False, "status": f"HTTP_{r.status_code}"}
    except Exception:
        return {"activated": False, "status": "ERROR"}

def generate_one(region, do_activate):
    acc = api_get_one(region) or create_account_direct(region)
    if not acc: return None
    if do_activate:
        a = activate_account(acc["uid"], acc["password"])
        acc["activated"] = a["activated"]; acc["status"] = a["status"]
    else:
        acc["activated"] = False; acc["status"] = "SKIPPED"
    return acc

# ══════════════════════════════════════════════════════════════════════════
# JOB (dedup, streaming write)
# ══════════════════════════════════════════════════════════════════════════
class GenJob:
    def __init__(self, user_id, region, count, threads):
        self.user_id    = user_id
        self.region     = region
        self.count      = count
        self.threads    = threads
        self.accounts   = []
        self.seen_uids  = set()
        self.seen_aids  = set()
        self.done       = 0
        self.activated  = 0
        self.failed     = 0
        self.duplicates = 0
        self.lock       = threading.Lock()
        self.stop       = threading.Event()
        self.start_time = time.time()
        self.last_update = time.time()

    def try_record(self, acc):
        with self.lock:
            if not acc:
                self.failed += 1; self.last_update = time.time(); return False
            uid = acc.get("uid",""); aid = acc.get("account_id","")
            if not uid or not aid or aid == "N/A":
                self.failed += 1; self.last_update = time.time(); return False
            if uid in self.seen_uids or aid in self.seen_aids:
                self.duplicates += 1; self.last_update = time.time(); return False
            self.seen_uids.add(uid); self.seen_aids.add(aid)
            self.accounts.append(acc)
            self.done += 1
            if acc.get("activated"): self.activated += 1
            self.last_update = time.time()
            if self.done >= self.count: self.stop.set()
            return True

    def remaining(self):
        with self.lock: return self.count - self.done

    def elapsed(self): return time.time() - self.start_time

def _worker(job):
    region = "BD" if job.region == "GHOST" else job.region
    while not job.stop.is_set():
        if job.remaining() <= 0: break
        got = False
        for _ in range(MAX_DUP_RETRIES):
            if job.stop.is_set(): break
            try: acc = generate_one(region, True)
            except Exception: acc = None
            if job.try_record(acc):
                got = True; break
        if not got: time.sleep(0.25)
    # cleanup thread-local session
    old = getattr(_tls, "session", None)
    if old is not None:
        try: old.close()
        except Exception: pass

def run_generation(job):
    reset_thread()
    diag(f"gen start · threads={job.threads} · rss={mem_mb():.1f}MB")
    with ThreadPoolExecutor(max_workers=job.threads) as ex:
        futs = [ex.submit(_worker, job) for _ in range(job.threads)]
        for f in as_completed(futs):
            try: f.result()
            except Exception: pass
    gc.collect()
    diag(f"gen end · done={job.done} · rss={mem_mb():.1f}MB")

def build_txt(job):
    export = []
    for a in job.accounts:
        export.append({
            "uid": a.get("uid",""),
            "password": a.get("password",""),
            "name": a.get("name",""),
            "account_id": a.get("account_id",""),
            "region": a.get("region",""),
            "created_at": a.get("created_at") or a.get("created",""),
        })
    return json.dumps(export, indent=4, ensure_ascii=False).encode("utf-8")

# ══════════════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════════════
_stats_lock = threading.Lock()

def load_stats():
    if not os.path.exists(STATS_FILE): return {}
    try:
        with open(STATS_FILE, encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def save_stats(s):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f: json.dump(s, f, indent=2)
    except Exception: pass

def bump_stat(user_id, generated, activated):
    with _stats_lock:
        s = load_stats(); k = str(user_id)
        s.setdefault(k, {"generated":0,"activated":0,"sessions":0,
                         "first_seen":datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        s[k]["generated"] += generated
        s[k]["activated"] += activated
        s[k]["sessions"]  += 1
        save_stats(s)

# ══════════════════════════════════════════════════════════════════════════
# BOT
# ══════════════════════════════════════════════════════════════════════════
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

class SG(StatesGroup):
    count   = State()
    threads = State()

ACTIVE_JOBS = {}

def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Generate Accounts", callback_data="gen")],
        [InlineKeyboardButton(text="📊 My Stats", callback_data="stats"),
         InlineKeyboardButton(text="ℹ️ About", callback_data="about")],
        [InlineKeyboardButton(text="🆔 My ID", callback_data="myid")],
    ])

def kb_regions():
    rows = []
    chunk = REGIONS[:]
    while chunk:
        rows.append([InlineKeyboardButton(text=r, callback_data=f"region:{r}") for r in chunk[:3]])
        chunk = chunk[3:]
    rows.append([InlineKeyboardButton(text="👻 GHOST", callback_data="region:GHOST")])
    rows.append([InlineKeyboardButton(text="🔙 Back", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_cancel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])

def kb_after():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Generate Again", callback_data="gen")],
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back")],
    ])

@dp.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer(
        "🔥 <b>MASTER FF GEN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bulk Free Fire guest account generator\n"
        "with auto-activation & dedup.\n\n"
        "👑 <b>Owner</b> : Kanha\n"
        f"📦 <b>Version</b> : v2.1 memory-safe\n"
        f"⚡ <b>Max bulk</b> : {MAX_ACCOUNTS}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Pick an option below 👇",
        reply_markup=kb_main(), parse_mode="HTML"
    )

@dp.callback_query(F.data == "back")
async def cb_back(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    await cq.message.edit_text(
        "🔥 <b>MASTER FF GEN</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\nPick an option 👇",
        reply_markup=kb_main(), parse_mode="HTML"
    )
    await cq.answer()

@dp.callback_query(F.data == "about")
async def cb_about(cq: CallbackQuery):
    await cq.message.edit_text(
        "ℹ️ <b>About</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👑 <b>Owner</b>     : Kanha\n"
        "📦 <b>Engine</b>    : v2.1 (OOM-safe)\n"
        f"🌍 <b>Regions</b>   : {len(REGIONS)}\n"
        f"⚡ <b>Threads</b>   : up to {MAX_THREADS}\n"
        f"👥 <b>Max bulk</b>  : {MAX_ACCOUNTS}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "• Bulk guest generation\n"
        "• Auto-activation\n"
        "• Duplicate removal (uid + aid)\n"
        "• Instant .txt (JSON) export\n"
        "• Memory-safe architecture\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=kb_main(), parse_mode="HTML"
    )
    await cq.answer()

@dp.callback_query(F.data == "myid")
async def cb_myid(cq: CallbackQuery):
    await cq.answer(f"Your ID: {cq.from_user.id}", show_alert=True)

@dp.callback_query(F.data == "stats")
async def cb_stats(cq: CallbackQuery):
    s = load_stats().get(str(cq.from_user.id), {})
    await cq.message.edit_text(
        "📊 <b>Your Stats</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <code>{cq.from_user.id}</code> · {cq.from_user.first_name or '-'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 Generated  : {s.get('generated', 0)}\n"
        f"✅ Activated  : {s.get('activated', 0)}\n"
        f"🔁 Sessions   : {s.get('sessions', 0)}\n"
        f"📅 First seen : {s.get('first_seen','-')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=kb_main(), parse_mode="HTML"
    )
    await cq.answer()

@dp.callback_query(F.data == "cancel")
async def cb_cancel(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    job = ACTIVE_JOBS.get(cq.from_user.id)
    if job:
        job.stop.set(); ACTIVE_JOBS.pop(cq.from_user.id, None)
    await cq.message.edit_text("❌ Cancelled.\n\nBack to menu:", reply_markup=kb_main())
    await cq.answer("Cancelled")

@dp.callback_query(F.data == "gen")
async def cb_gen(cq: CallbackQuery, state: FSMContext):
    if cq.from_user.id in ACTIVE_JOBS:
        await cq.answer("⚠️ Job already running!", show_alert=True); return
    await state.clear()
    await cq.message.edit_text(
        "🌍 <b>Select Region</b>",
        reply_markup=kb_regions(), parse_mode="HTML"
    )
    await cq.answer()

@dp.callback_query(F.data.startswith("region:"))
async def cb_region(cq: CallbackQuery, state: FSMContext):
    region = cq.data.split(":", 1)[1]
    await state.update_data(region=region)
    await state.set_state(SG.count)
    await cq.message.edit_text(
        f"🌍 Region: <b>{region}</b>\n"
        f"Send count (1 – {MAX_ACCOUNTS}):",
        reply_markup=kb_cancel(), parse_mode="HTML"
    )
    await cq.answer()

@dp.message(SG.count)
async def sg_count(m: Message, state: FSMContext):
    t = (m.text or "").strip()
    if not t.isdigit() or not (1 <= int(t) <= MAX_ACCOUNTS):
        await m.answer(f"❌ Send 1 – {MAX_ACCOUNTS}.", reply_markup=kb_cancel()); return
    await state.update_data(count=int(t))
    await state.set_state(SG.threads)
    await m.answer(
        f"✅ Count: <b>{t}</b>\n"
        f"Threads (1 – {MAX_THREADS}) or /skip for default {DEFAULT_THREADS}:",
        reply_markup=kb_cancel(), parse_mode="HTML"
    )

@dp.message(SG.threads)
async def sg_threads(m: Message, state: FSMContext):
    t = (m.text or "").strip().lower()
    if t in ("/skip","skip",""):
        threads = DEFAULT_THREADS
    elif t.isdigit() and 1 <= int(t) <= MAX_THREADS:
        threads = int(t)
    else:
        await m.answer(f"❌ Send 1 – {MAX_THREADS} or /skip.", reply_markup=kb_cancel()); return
    d = await state.get_data()
    await state.clear()
    await start_job(m, m.from_user.id, d["region"], d["count"], threads)

async def start_job(m: Message, user_id, region, count, threads):
    job = GenJob(user_id, region, count, threads)
    ACTIVE_JOBS[user_id] = job

    status = await m.answer(
        "⚙️ <b>Starting job…</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌍 Region   : <b>{region}</b>\n"
        f"🔢 Count    : <b>{count}</b>\n"
        f"⚡ Threads  : <b>{threads}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )

    loop = asyncio.get_running_loop()
    gen_future = loop.run_in_executor(None, run_generation, job)

    last_done = 0
    last_change = time.time()
    while not gen_future.done():
        await asyncio.sleep(3)
        with job.lock:
            done = job.done; act = job.activated
            fail = job.failed; dup = job.duplicates
        if done != last_done:
            last_done = done; last_change = time.time()
        if time.time() - last_change > STALL_TIMEOUT and not gen_future.done():
            job.stop.set(); break
        pct = int((done / count) * 100) if count else 0
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        try:
            await status.edit_text(
                f"⚙️ <b>Generating…</b>  {pct}%\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<code>{bar}</code>\n"
                f"📦 Done       : <b>{done}/{count}</b>\n"
                f"✅ Activated  : <b>{act}</b>\n"
                f"❌ Failed     : <b>{fail}</b>\n"
                f"♻️ Duplicates : <b>{dup}</b>\n"
                f"⏱ Elapsed    : <b>{job.elapsed():.1f}s</b>\n"
                f"🧠 RSS        : <b>{mem_mb():.0f}MB</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode="HTML"
            )
        except Exception:
            pass

    try: await gen_future
    except Exception as e: diag(f"job future: {e}")

    with job.lock:
        total = len(job.accounts); act = job.activated; dup = job.duplicates
    elapsed = job.elapsed()
    ACTIVE_JOBS.pop(user_id, None)
    bump_stat(user_id, total, act)

    if total == 0:
        await status.edit_text(
            "❌ <b>No accounts generated.</b>\nTry again.",
            parse_mode="HTML", reply_markup=kb_after()
        ); return

    data  = build_txt(job)
    fname = f"ff_{region}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    file  = BufferedInputFile(data, filename=fname)

    try:
        await status.edit_text(
            "✅ <b>Job Complete</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Generated : <b>{total}/{count}</b>\n"
            f"✅ Activated : <b>{act}</b>\n"
            f"♻️ Dupes cut : <b>{dup}</b>\n"
            f"⏱ Elapsed   : <b>{elapsed:.1f}s</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n📤 Sending file…",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await m.answer_document(
        document=file,
        caption=(
            f"📁 <b>{fname}</b>\n"
            f"🌍 {region}  ·  📦 {total}  ·  ✅ {act}\n"
            f"👑 Kanha"
        ),
        parse_mode="HTML",
        reply_markup=kb_after()
    )

# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════
async def main():
    diag(f"main() entered · rss={mem_mb():.1f}MB")
    try:
        me = await bot.get_me()
        diag(f"logged in · @{me.username} ({me.id}) · rss={mem_mb():.1f}MB")
    except Exception as e:
        diag(f"get_me FAILED: {type(e).__name__}: {e}")
        raise

    diag("starting polling…")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        diag("polling stopped · closing session")
        try: await bot.session.close()
        except Exception: pass

if __name__ == "__main__":
    diag("== booting ==")
    try:
        asyncio.run(main())
    except Exception as e:
        import traceback
        diag(f"FATAL: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)