# server.py - HELA SMART SACCO Web Server
# Pure Python stdlib — NO fastapi/uvicorn needed. Works on any Python 3.6+.
import threading, json, hashlib, base64, time, os, logging
import hmac as _hmac, uuid as _uuid, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

log = logging.getLogger("hela.server")
_server_thread = None
_server_port   = None
_kivy_app      = None

# ── JWT ───────────────────────────────────────────────────────────────────────
_JWT_SECRET = os.environ.get("HELA_JWT_SECRET", "hela_sacco_jwt_v3")

def _b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def sign_jwt(payload, hours=24):
    p = dict(payload)
    p["exp"] = int(time.time()) + hours * 3600
    h = _b64u(json.dumps({"alg":"HS256","typ":"JWT"}).encode())
    b = _b64u(json.dumps(p, separators=(",",":")).encode())
    s = _b64u(_hmac.new(_JWT_SECRET.encode(), f"{h}.{b}".encode(), hashlib.sha256).digest())
    return f"{h}.{b}.{s}"

def verify_jwt(token):
    try:
        h, b, s = token.split(".")
        exp = _b64u(_hmac.new(_JWT_SECRET.encode(), f"{h}.{b}".encode(), hashlib.sha256).digest())
        if not _hmac.compare_digest(s, exp): return None
        p = json.loads(base64.urlsafe_b64decode(b + "=="))
        if p.get("exp", 0) < time.time(): return None
        return p
    except Exception:
        return None

# ── Helpers ───────────────────────────────────────────────────────────────────
def _hash_pw(pw, salt=None, iters=600000):
    if salt is None:
        salt = base64.b64encode(os.urandom(32)).decode()
    h = base64.b64encode(
        hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(salt), iters, 32)
    ).decode()
    return h, salt

def _norm_phone(phone):
    p = phone.strip().replace(" ","").replace("-","").replace("+","")
    if p.startswith("0"): p = "254" + p[1:]
    return p

# ── Portal HTML (embedded) ────────────────────────────────────────────────────
from api_routes import PORTAL_HTML

# ── Request Handler ───────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass  # suppress default access log

    def _send(self, code, body, content_type="application/json"):
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, b"")

    def _json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0: return {}
        return json.loads(self.rfile.read(length))

    def _auth(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "): return None
        return verify_jwt(auth[7:])

    def _db(self):
        return _kivy_app.db

    def do_GET(self):
        path = urlparse(self.path).path
        db   = self._db()

        if path == "/api/me":
            u = self._auth()
            if not u: return self._send(401, {"detail": "Not authenticated"})
            self._handle_get_me(u, db); return

        if path == "/api/me/statement":
            u = self._auth()
            if not u: return self._send(401, {"detail": "Not authenticated"})
            qs     = parse_qs(urlparse(self.path).query)
            limit  = int(qs.get("limit",  ["30"])[0])
            offset = int(qs.get("offset", ["0"])[0])
            self._handle_statement(u, db, min(limit,100), offset); return

        if path == "/api/me/loans":
            u = self._auth()
            if not u: return self._send(401, {"detail": "Not authenticated"})
            self._handle_loans(u, db); return

        if path == "/api/me/investments":
            u = self._auth()
            if not u: return self._send(401, {"detail": "Not authenticated"})
            self._handle_investments(u, db); return

        # SPA — serve portal for everything else
        self._send(200, PORTAL_HTML, "text/html; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path
        db   = self._db()

        if path == "/api/auth/login":
            self._handle_login(db); return
        if path == "/api/auth/register":
            self._handle_register(db); return
        if path == "/api/me/loan_apply":
            u = self._auth()
            if not u: return self._send(401, {"detail": "Not authenticated"})
            self._handle_loan_apply(u, db); return
        if path == "/api/me/stk_deposit":
            u = self._auth()
            if not u: return self._send(401, {"detail": "Not authenticated"})
            self._handle_stk_deposit(u, db); return
        if path in ("/mpesa/stk_callback", "/mpesa/b2c_callback"):
            self._handle_mpesa_callback(path, db); return

        self._send(404, {"detail": "Not found"})

    # ── Endpoint implementations ──────────────────────────────────────────────

    def _handle_login(self, db):
        try:
            body = self._json_body()
            phone    = str(body.get("phone","")).strip()
            password = str(body.get("password","")).strip()
            if not phone or not password:
                return self._send(400, {"detail": "Phone and password required"})
            p = _norm_phone(phone)
            member = (
                db.fetch_one(
                    "SELECT m.*, u.id as uid, u.password_hash, u.salt, u.iterations, u.role "
                    "FROM members m JOIN users u ON u.id=m.user_id "
                    "WHERE (m.phone=? OR m.phone=?) AND m.is_active=1",
                    (phone, p))
                or db.fetch_one(
                    "SELECT u.id as uid, u.id, u.username, u.password_hash, "
                    "u.salt, u.iterations, u.role, NULL as member_no "
                    "FROM users u WHERE u.username=? AND u.is_active=1", (phone,))
            )
            if not member:
                return self._send(401, {"detail": "Phone number or password is incorrect"})
            h, _ = _hash_pw(password, member["salt"], member["iterations"] or 600000)
            if h != member["password_hash"]:
                return self._send(401, {"detail": "Phone number or password is incorrect"})
            uid   = member.get("uid") or member["id"]
            role  = (member.get("role") or "member").lower()
            token = sign_jwt({"sub": uid, "role": role})
            name  = member.get("full_name") or member.get("username","")
            self._send(200, {"token": token, "role": role, "name": name})
        except Exception as e:
            log.error(f"login error: {e}")
            self._send(500, {"detail": str(e)})

    def _handle_register(self, db):
        try:
            body       = self._json_body()
            first_name = str(body.get("first_name","")).strip()
            last_name  = str(body.get("last_name","")).strip()
            phone      = str(body.get("phone","")).strip()
            id_number  = str(body.get("id_number","")).strip()
            email      = str(body.get("email","")).strip()
            password   = str(body.get("password","")).strip()

            if not first_name or not last_name:
                return self._send(400, {"detail": "Full name is required"})
            if not phone:
                return self._send(400, {"detail": "Phone number is required"})
            if not id_number:
                return self._send(400, {"detail": "National ID is required"})
            if not password or len(password) < 6:
                return self._send(400, {"detail": "Password must be at least 6 characters"})

            p = _norm_phone(phone)
            if db.fetch_one("SELECT id FROM members WHERE phone=? OR phone=?", (phone, p)):
                return self._send(409, {"detail": "A member with this phone already exists"})
            if db.fetch_one("SELECT id FROM members WHERE id_number=?", (id_number,)):
                return self._send(409, {"detail": "A member with this ID number already exists"})

            now       = datetime.datetime.now().isoformat()
            user_id   = str(_uuid.uuid4())
            member_id = str(_uuid.uuid4())
            full_name = f"{first_name} {last_name}"
            count     = (db.fetch_one("SELECT COUNT(*) as c FROM members") or {}).get("c", 0)
            member_no = f"HLS{str(count + 1).zfill(5)}"
            pw_hash, salt = _hash_pw(password)

            db.execute(
                "INSERT INTO users (id, username, password_hash, salt, iterations, "
                "role, full_name, is_active, created_at) VALUES (?,?,?,?,?,?,?,1,?)",
                (user_id, p, pw_hash, salt, 600000, "member", full_name, now))
            db.execute(
                "INSERT INTO members (id, user_id, member_no, first_name, last_name, "
                "full_name_search, phone, email, id_number, is_active, kyc_status, "
                "membership_date, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,1,\'pending\',date(\'now\'),?,?)",
                (member_id, user_id, member_no, first_name, last_name,
                 full_name.lower(), p, email, id_number, now, now))
            acc_id = str(_uuid.uuid4())
            db.execute(
                "INSERT INTO accounts (id, member_id, account_no, account_type, "
                "balance_minor, is_active, opening_date, created_at, updated_at) "
                "VALUES (?,?,?,\'savings\',0,1,date(\'now\'),?,?)",
                (acc_id, member_id, f"SAV{member_no[3:]}", now, now))

            token = sign_jwt({"sub": user_id, "role": "member"})
            self._send(200, {
                "token": token, "role": "member", "name": full_name,
                "member_no": member_no,
                "message": "Account created! Visit a branch to complete KYC verification."
            })
        except Exception as e:
            log.error(f"register error: {e}")
            self._send(500, {"detail": str(e)})

    def _get_mid(self, uid, db):
        row = db.fetch_one(
            "SELECT m.id FROM members m JOIN users u ON u.id=m.user_id WHERE u.id=?", (uid,))
        return (row or {}).get("id") or uid

    def _handle_get_me(self, u, db):
        try:
            uid = u["sub"]
            member = (
                db.fetch_one(
                    "SELECT m.*, u.username, u.role FROM members m "
                    "JOIN users u ON u.id=m.user_id WHERE u.id=?", (uid,))
                or db.fetch_one("SELECT id, username, role FROM users WHERE id=?", (uid,))
            )
            if not member: return self._send(404, {"detail": "Member not found"})
            mid = member.get("id") or uid
            acc = db.fetch_one(
                "SELECT * FROM accounts WHERE member_id=? AND account_type=\'savings\' "
                "ORDER BY opening_date LIMIT 1", (mid,))
            loans = db.fetch_all(
                "SELECT id, principal_minor, outstanding_balance_minor, status, "
                "next_due_date, monthly_installment_minor FROM loans "
                "WHERE member_id=? AND status IN (\'active\',\'disbursed\',\'overdue\') "
                "ORDER BY created_at DESC", (mid,))
            self._send(200, {
                "id":         mid,
                "name":       member.get("full_name") or member.get("username",""),
                "member_no":  member.get("member_no",""),
                "phone":      member.get("phone",""),
                "email":      member.get("email",""),
                "kyc_status": member.get("kyc_status","pending"),
                "balance":    (acc or {}).get("balance_minor", 0) / 100,
                "account_no": (acc or {}).get("account_no",""),
                "account_id": (acc or {}).get("id",""),
                "loans": [{
                    "id":          l["id"],
                    "principal":   l["principal_minor"] / 100,
                    "outstanding": l["outstanding_balance_minor"] / 100,
                    "status":      l["status"],
                    "next_due":    str(l.get("next_due_date","") or ""),
                    "installment": l.get("monthly_installment_minor",0) / 100,
                } for l in loans],
            })
        except Exception as e:
            self._send(500, {"detail": str(e)})

    def _handle_statement(self, u, db, limit, offset):
        try:
            mid  = self._get_mid(u["sub"], db)
            txns = db.fetch_all(
                "SELECT t.*, a.account_no FROM transactions t "
                "JOIN accounts a ON a.id=t.account_id "
                "WHERE a.member_id=? ORDER BY t.created_at DESC LIMIT ? OFFSET ?",
                (mid, limit, offset))
            self._send(200, {"transactions": [{
                "id":          t["id"],
                "type":        t["transaction_type"],
                "amount":      t["amount_minor"] / 100,
                "balance":     t.get("balance_after_minor",0) / 100,
                "description": t.get("description",""),
                "channel":     t.get("channel",""),
                "date":        str(t.get("created_at","")),
                "reference":   t.get("reference_number",""),
            } for t in txns]})
        except Exception as e:
            self._send(500, {"detail": str(e)})

    def _handle_loans(self, u, db):
        try:
            mid   = self._get_mid(u["sub"], db)
            loans = db.fetch_all(
                "SELECT * FROM loans WHERE member_id=? ORDER BY created_at DESC", (mid,))
            self._send(200, {"loans": [{
                "id":            l["id"],
                "amount":        l["principal_minor"] / 100,
                "outstanding":   l.get("outstanding_balance_minor",0) / 100,
                "status":        l["status"],
                "next_due":      str(l.get("next_due_date","") or ""),
                "installment":   l.get("monthly_installment_minor",0) / 100,
                "term_months":   l.get("term_months",0),
                "interest_rate": l.get("interest_rate",0),
                "purpose":       l.get("loan_purpose",""),
            } for l in loans]})
        except Exception as e:
            self._send(500, {"detail": str(e)})

    def _handle_investments(self, u, db):
        try:
            mid  = self._get_mid(u["sub"], db)
            invs = db.fetch_all(
                "SELECT * FROM investments WHERE member_id=? ORDER BY created_at DESC", (mid,))
            self._send(200, {"investments": [{
                "id":        i["id"],
                "name":      i.get("name",""),
                "type":      i.get("investment_type",""),
                "principal": i["principal_minor"] / 100,
                "interest":  i.get("interest_earned_minor",0) / 100,
                "rate":      i.get("interest_rate",0),
                "start":     str(i.get("start_date","")),
                "maturity":  str(i.get("maturity_date","")),
                "status":    i.get("status",""),
            } for i in invs]})
        except Exception as e:
            self._send(500, {"detail": str(e)})

    def _handle_loan_apply(self, u, db):
        try:
            mid     = self._get_mid(u["sub"], db)
            body    = self._json_body()
            amount  = float(body.get("amount",0))
            term    = int(body.get("term_months",12))
            purpose = str(body.get("purpose","Personal")).strip()
            if amount < 1000: return self._send(400, {"detail": "Minimum loan is KSh 1,000"})
            if not (1 <= term <= 60): return self._send(400, {"detail": "Term must be 1-60 months"})
            loan_id = str(_uuid.uuid4())
            now = datetime.datetime.now().isoformat()
            db.execute(
                "INSERT INTO loans (id, member_id, principal_minor, term_months, "
                "loan_purpose, status, created_at, updated_at) VALUES (?,?,?,?,?,\'pending\',?,?)",
                (loan_id, mid, int(amount*100), term, purpose, now, now))
            self._send(200, {"status":"submitted","loan_id":loan_id,
                             "message":"Application submitted. We will contact you within 24 hours."})
        except Exception as e:
            self._send(500, {"detail": str(e)})

    def _handle_stk_deposit(self, u, db):
        try:
            mid    = self._get_mid(u["sub"], db)
            body   = self._json_body()
            amount = float(body.get("amount",0))
            phone  = str(body.get("phone","")).strip()
            if amount < 10: return self._send(400, {"detail": "Minimum deposit is KSh 10"})
            if not phone:   return self._send(400, {"detail": "Phone number required"})
            acc = db.fetch_one(
                "SELECT * FROM accounts WHERE member_id=? AND account_type=\'savings\' LIMIT 1", (mid,))
            if not acc: return self._send(404, {"detail": "No savings account found"})
            mm  = _kivy_app.mobile_money_service
            res = mm.receive_stk_push(
                phone=phone, amount_ksh=amount,
                account_ref=acc.get("account_no", mid[:10]),
                description="HELA SACCO Deposit",
                account_id=acc["id"], member_id=mid)
            if res.get("status") not in ("pending","success"):
                return self._send(400, {"detail": res.get("message","STK Push failed")})
            self._send(200, {"status":"pending",
                             "message": res.get("message","Check your phone for the M-Pesa prompt"),
                             "checkout_id": res.get("checkout_id","")})
        except Exception as e:
            self._send(500, {"detail": str(e)})

    def _handle_mpesa_callback(self, path, db):
        try:
            body = self._json_body()
            if "stk" in path:
                res = _kivy_app.mobile_money_service.mpesa.parse_stk_callback(body)
                cid = res.get("checkout_id","")
                if res.get("status") == "success":
                    tx = db.fetch_one(
                        "SELECT * FROM mobile_money_transactions "
                        "WHERE conversation_id=? AND direction=\'inbound\' AND status=\'pending\' LIMIT 1",
                        (cid,))
                    if tx and tx.get("account_id"):
                        _kivy_app.account_service.post_transaction(
                            tx["account_id"], "deposit",
                            int(round(res.get("amount",0)*100)),
                            "M-Pesa STK deposit via web portal",
                            channel="mobile_money",
                            reference_number=res.get("mpesa_receipt",""))
                        db.execute(
                            "UPDATE mobile_money_transactions SET status=\'completed\', "
                            "mpesa_transaction_id=? WHERE conversation_id=?",
                            (res.get("mpesa_receipt",""), cid))
            else:
                result = body.get("Result",{})
                code   = result.get("ResultCode",-1)
                params = {p["Key"]:p["Value"]
                          for p in result.get("ResultParameters",{}).get("ResultParameter",[])}
                cid = result.get("ConversationID","")
                db.execute(
                    "UPDATE mobile_money_transactions SET status=?, mpesa_transaction_id=? "
                    "WHERE conversation_id=?",
                    ("completed" if code==0 else "failed",
                     params.get("TransactionReceipt",""), cid))
        except Exception as e:
            log.warning(f"mpesa cb error: {e}")
        self._send(200, {"ResultCode":0,"ResultDesc":"Accepted"})


# ── Server launcher ───────────────────────────────────────────────────────────
def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def start_server(kivy_app, port=None):
    global _server_thread, _server_port, _kivy_app
    if _server_thread and _server_thread.is_alive():
        return _server_thread
    _kivy_app = kivy_app

    def _run():
        global _server_port
        try:
            _p = port
            if _p is None:
                try:
                    row = kivy_app.db.fetch_one(
                        "SELECT value FROM system_settings WHERE key=?", ("api_port",))
                    _p = int((row or {}).get("value") or 8080)
                except Exception:
                    _p = 8080
            _server_port = _p
            httpd = ThreadingHTTPServer(("0.0.0.0", _p), Handler)
            log.warning(
                f"\nHELA SACCO Portal running:\n"
                f"  This phone: http://127.0.0.1:{_p}\n"
                f"  Same WiFi:  http://{get_local_ip()}:{_p}"
            )
            httpd.serve_forever()
        except Exception as e:
            log.error(f"HELA server error: {e}")

    _server_thread = threading.Thread(target=_run, daemon=True, name="hela-api")
    _server_thread.start()
    return _server_thread

def get_portal_url():
    return f"http://127.0.0.1:{_server_port or 8080}"

def get_lan_url():
    return f"http://{get_local_ip()}:{_server_port or 8080}"
