# hall_booking.py
# نظام حجز قاعة واحدة - Flask + SQLite (ملف واحد)
# تشغيل: pip install -r requirements.txt
# ثم:    python hall_booking.py  -> http://127.0.0.1:5000

from __future__ import annotations
from datetime import datetime, timedelta
import re
import pytz
from dateutil.parser import parse as dtparse

from flask import Flask, request, redirect, url_for, render_template_string, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

APP_TZ = pytz.timezone("Asia/Qatar")

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me-later-for-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///hall_booking.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ------- Model -------
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=True)
    start_at = db.Column(db.DateTime, nullable=False)  # تخزين محلي Asia/Qatar (naive)
    end_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return dict(
            id=self.id,
            title=self.title,
            name=self.name,
            email=self.email or "",
            start_at=self.start_at.strftime("%Y-%m-%d %H:%M"),
            end_at=self.end_at.strftime("%Y-%m-%d %H:%M"),
        )

with app.app_context():
    db.create_all()

# ------- Helpers -------
def _parse_local(dt_str: str) -> datetime:
    """
    يستقبل نص تاريخ/وقت مثل '2025-09-24 14:30' ويعيد datetime (naive) بالتوقيت المحلي Asia/Qatar.
    """
    # dtparse يقبل صيغ متعددة؛ نضمن yyyy-mm-dd hh:mm
    dt = dtparse(dt_str)
    # نجعلها naive محلية (بدون tzinfo) بما أن النظام يعمل محلياً
    return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)

def has_conflict(start_at: datetime, end_at: datetime, exclude_id: int | None = None) -> bool:
    """
    التعارض: (start < existing.end) AND (end > existing.start)
    """
    q = Booking.query.filter(
        Booking.start_at < end_at,
        Booking.end_at > start_at
    )
    if exclude_id:
        q = q.filter(Booking.id != exclude_id)
    return db.session.query(q.exists()).scalar()

def valid_email(email: str) -> bool:
    if not email:
        return True
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

# ------- Templates (Jinja inline) -------
BASE = r"""
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>حجز القاعة</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- تصميم بسيط -->
  <style>
    :root { --bg:#f7f7fb; --fg:#111; --muted:#666; --brand:#7b3fe4; --ok:#1b9c85; --err:#e63946; --card:#fff; }
    body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", "Helvetica Neue", Arial; background: var(--bg); color: var(--fg);}
    header { display:flex; align-items:center; justify-content:space-between; padding:16px 20px; background: #fff; box-shadow: 0 1px 8px rgba(0,0,0,.05); position:sticky; top:0; z-index:1;}
    .header-title { display: flex; align-items: center; gap: 12px; }
    h1 { font-size:20px; margin:0; }
    .container { max-width: 980px; margin: 20px auto; padding: 0 16px; }
    .grid { display:grid; grid-template-columns: 1fr 360px; gap:20px; }
    .card { background: var(--card); border-radius: 16px; box-shadow: 0 8px 30px rgba(0,0,0,.06); padding: 24px; }
    .cal-head { display:flex; align-items:center; gap:10px; margin-bottom: 10px;}
    .cal-head a, .btn, button { text-decoration:none; display:inline-block; padding:10px 14px; border-radius: 12px; background:#eee; color:#111; border: none; cursor:pointer; font-weight:600;}
    .btn-primary { background: var(--brand); color:#fff; }
    .btn-danger { background: var(--err); color:#fff; }
    .btn-ghost  { background: transparent; color: var(--brand); font-size: 12px; padding: 4px 8px; }
    .muted { color: var(--muted); font-size: 13px; }
    .flash { padding:12px 14px; border-radius:12px; margin:8px 0; font-weight:600;}
    .flash.err { background:#fde7ea; color:#b00020;}
    .flash.ok  { background:#e8fff5; color:#087f5b;}
    form .row { display:flex; gap:10px; }
    label { font-size: 13px; color:#333; display:block; margin: 8px 0 4px; }
    input[type=text], input[type=datetime-local], input[type=email], textarea {
      width:100%; padding:11px 12px; border-radius:12px; border:1px solid #ddd; background:#fff; font-size:14px; box-sizing: border-box;
    }
    table { width:100%; border-collapse: collapse; }
    th, td { padding:10px 8px; border-bottom:1px solid #eee; text-align: right;}
    th { background:#fafafa; font-size: 13px; color:#555;}
    .tag { display:inline-block; padding:4px 8px; border-radius:999px; font-size: 12px; background:#f1f0ff; color:#4328b7; }
    .empty { text-align:center; padding:24px; color:#777; }
    .footer { text-align:center; color:#999; font-size:12px; padding: 20px 0 40px; }
    .kpi { display:flex; gap: 10px; flex-wrap: wrap; margin-bottom: 8px;}
    .kpi .pill { background:#eef9ff; color:#065b7a; padding:6px 10px; border-radius:999px; font-size:12px; }
    @media (max-width: 960px){ .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="header-title">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-calendar"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
        <h1>نظام حجز القاعة</h1>
    </div>
    <div><a class="btn" href="{{ url_for('index') }}">اليوم</a></div>
  </header>
  <div class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for cat, msg in messages %}
          <div class="flash {{ 'ok' if cat=='ok' else 'err' }}">{{ msg|safe }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    {{ body|safe }}
  </div>
  <div class="footer">©️ {{ now.year }} — قاعة واحدة | Asia/Qatar</div>
</body>
</html>
"""

INDEX = r"""
{% set d = selected_date %}
<div class="grid">
  <section class="card">
    <div class="cal-head">
      <a class="btn" href="{{ url_for('index', date=(d - delta).strftime('%Y-%m-%d')) }}">◀️ اليوم السابق</a>
      <div style="font-weight:700">جدول يوم {{ d.strftime('%A, %Y-%m-%d') }}</div>
      <a class="btn" href="{{ url_for('index', date=(d + delta).strftime('%Y-%m-%d')) }}">اليوم التالي ▶️</a>
    </div>

    <div class="kpi">
      <div class="pill">إجمالي الحجوزات اليوم: {{ todays_count }}</div>
      <div class="pill">ساعات محجوزة: {{ hours_booked }}</div>
    </div>

    {% if bookings %}
    <table>
      <thead>
        <tr>
          <th>العنوان</th>
          <th>الاسم</th>
          <th>البداية</th>
          <th>النهاية</th>
          <th>إجراء</th>
        </tr>
      </thead>
      <tbody>
        {% for b in bookings %}
        <tr>
          <td>{{ b.title }}</td>
          <td>{{ b.name }}</td>
          <td><span class="tag">{{ b.start_at.strftime('%H:%M') }}</span></td>
          <td><span class="tag">{{ b.end_at.strftime('%H:%M') }}</span></td>
          <td>
            <a class="btn-ghost" href="{{ url_for('booking_json', booking_id=b.id) }}" target="_blank">JSON</a>
            <a class="btn-danger" href="{{ url_for('delete_booking', booking_id=b.id) }}" onclick="return confirm('هل أنت متأكد من حذف هذا الحجز؟');">حذف</a>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
      <div class="empty">لا توجد حجوزات في هذا اليوم.</div>
    {% endif %}
  </section>

  <aside class="card">
    <h3 style="margin:0 0 8px 0;">إنشاء حجز جديد</h3>
    <div class="muted">القاعة: الرئيسية (قاعة واحدة)</div>
    <form method="post" action="{{ url_for('create_booking') }}">
      <label>عنوان الاجتماع</label>
      <input required type="text" name="title" placeholder="مثال: اجتماع الفريق الأسبوعي">

      <div class="row">
        <div style="flex:1">
          <label>الاسم</label>
          <input required type="text" name="name" placeholder="اسم منظم الاجتماع">
        </div>
        <div style="flex:1">
          <label>البريد الإلكتروني (اختياري)</label>
          <input type="email" name="email" placeholder="example@domain.qa">
        </div>
      </div>

      <label>وقت البداية</label>
      <input required type="datetime-local" name="start_at" value="{{ default_start }}">

      <label>وقت النهاية</label>
      <input required type="datetime-local" name="end_at" value="{{ default_end }}">

      <div class="muted" style="margin-top:6px">* لا يُسمح بتداخل المواعيد. الحد الأقصى لمدة الحجز هو 6 ساعات.</div>
      <div style="margin-top:16px">
        <button class="btn-primary" type="submit">تأكيد الحجز</button>
        <a class="btn" href="{{ url_for('index') }}">إلغاء</a>
      </div>
    </form>
  </aside>
</div>
"""

def render(body_html: str, **ctx):
    return render_template_string(
        BASE,
        body=body_html,
        now=datetime.now(),
        **ctx
    )

# ------- Routes -------
@app.get("/")
def index():
    # يوم محدد أو اليوم
    date_q = request.args.get("date")
    if date_q:
        try:
            selected_date = datetime.strptime(date_q, "%Y-%m-%d")
        except Exception:
            selected_date = datetime.now(APP_TZ)
    else:
        selected_date = datetime.now(APP_TZ)

    day_start = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end   = day_start + timedelta(days=1)

    bookings = (Booking.query
               .filter(Booking.start_at < day_end,
                       Booking.end_at > day_start)
               .order_by(Booking.start_at.asc())
               .all())

    # KPIs بسيطة
    total_minutes = 0
    for b in bookings:
        # قص للحدود داخل اليوم لقياس أدق
        s = max(b.start_at, day_start)
        e = min(b.end_at, day_end)
        total_minutes += max(0, int((e - s).total_seconds() // 60))
    hours_booked = round(total_minutes / 60, 2)

    # افتراضات وقت افتراضي في النموذج
    now_local = datetime.now(APP_TZ).replace(second=0, microsecond=0)
    default_start = now_local.strftime("%Y-%m-%dT%H:%M")
    default_end = (now_local + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")

    body = render_template_string(
        INDEX,
        selected_date=day_start,
        delta=timedelta(days=1),
        bookings=bookings,
        todays_count=len(bookings),
        hours_booked=hours_booked,
        default_start=default_start,
        default_end=default_end
    )
    return render(body)

@app.post("/book")
def create_booking():
    title = (request.form.get("title") or "").strip()
    name  = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    start_raw = request.form.get("start_at") or ""
    end_raw   = request.form.get("end_at") or ""

    # تحقق أساسي
    if not title or not name or not start_raw or not end_raw:
        flash("الرجاء تعبئة جميع الحقول المطلوبة.", "err")
        return redirect(url_for("index"))

    if not valid_email(email):
        flash("صيغة البريد الإلكتروني غير صحيحة.", "err")
        return redirect(url_for("index"))

    try:
        start_at = _parse_local(start_raw.replace("T", " "))
        end_at   = _parse_local(end_raw.replace("T", " "))
    except Exception:
        flash("صيغة الوقت غير صحيحة.", "err")
        return redirect(url_for("index"))

    if end_at <= start_at:
        flash("وقت النهاية يجب أن يكون بعد وقت البداية.", "err")
        return redirect(url_for("index"))

    # سياسة مدة قصوى (مثلاً 6 ساعات)
    if (end_at - start_at) > timedelta(hours=6):
        flash("المدة القصوى للحجز 6 ساعات.", "err")
        return redirect(url_for("index"))

    # منع التداخل
    if has_conflict(start_at, end_at):
        flash("عذرًا، هناك تعارض مع حجز آخر في نفس الفترة.", "err")
        return redirect(url_for("index", date=start_at.strftime("%Y-%m-%d")))

    # إنشاء الحجز
    b = Booking(title=title, name=name, email=email or None,
                start_at=start_at, end_at=end_at)
    db.session.add(b)
    db.session.commit()

    flash("تم إنشاء الحجز بنجاح ✅", "ok")
    return redirect(url_for("index", date=start_at.strftime("%Y-%m-%d")))

@app.get("/booking/<int:booking_id>/json")
def booking_json(booking_id: int):
    b = Booking.query.get_or_404(booking_id)
    return jsonify(b.to_dict())

@app.get("/booking/<int:booking_id>/delete")
def delete_booking(booking_id: int):
    b = Booking.query.get_or_404(booking_id)
    start_date = b.start_at.strftime("%Y-%m-%d")
    db.session.delete(b)
    db.session.commit()
    flash("تم حذف الحجز.", "ok")
    # العودة لليوم المرتبط بالحجز المحذوف
    return redirect(url_for("index", date=start_date))

# نقطة صحّة بسيطة
@app.get("/health")
def health():
    return {"ok": True, "now": datetime.now().isoformat(timespec="seconds")}

if __name__ == "__main__":
    app.run(debug=True)
