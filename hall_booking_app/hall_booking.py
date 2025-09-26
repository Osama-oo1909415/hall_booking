# hall_booking.py
# MOVO Hall Booking System - Flask + SQLite (Single File)
# Run: pip install -r requirements.txt
# Then:  python hall_booking.py  -> http://127.0.0.1:5000

from __future__ import annotations
from datetime import datetime, timedelta
import os
import re
import pytz
from dateutil.parser import parse as dtparse

from flask import Flask, request, redirect, url_for, render_template_string, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

# Application Timezone
APP_TZ = pytz.timezone("Asia/Qatar")

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me-later-for-production"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{app.instance_path}/hall_booking.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# ------- Model -------
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=True)
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(APP_TZ).replace(tzinfo=None))

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
    os.makedirs(app.instance_path, exist_ok=True)
    db.create_all()


# ------- Helpers -------
def _parse_local(dt_str: str) -> datetime:
    """Parses a datetime string like '2025-09-24 14:30' into a naive datetime object."""
    dt = dtparse(dt_str)
    return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)

def get_conflict(start_at: datetime, end_at: datetime, exclude_id: int | None = None) -> Booking | None:
    """Finds and returns the first booking that conflicts with the given time range."""
    q = Booking.query.filter(
        Booking.start_at < end_at,
        Booking.end_at > start_at
    )
    if exclude_id:
        q = q.filter(Booking.id != exclude_id)
    return q.first()

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
  <title>MOVO | حجز القاعة</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap" rel="stylesheet">
  <!-- MOVO Brand Styling -->
  <style>
    :root {
      --brand-purple: #7400FF;
      --brand-ruby: #EB0045;
      --brand-navy: #243746;
      --brand-raven: #1D1D1B;
      --success: #1b9c85;
      --bg: #f8f9fa;
      --card-bg: #ffffff;
      --font-family: 'Manrope', system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
    }
    body {
      margin: 0;
      font-family: var(--font-family);
      background: var(--bg);
      color: var(--brand-raven);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 24px;
      background: var(--card-bg);
      box-shadow: 0 2px 8px rgba(0,0,0,.06);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .header-title {
      display: flex;
      align-items: center;
      gap: 12px;
      font-weight: 700;
    }
    .container {
      max-width: 1024px;
      margin: 24px auto;
      padding: 0 16px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 380px;
      gap: 24px;
    }
    .card {
      background: var(--card-bg);
      border-radius: 16px;
      box-shadow: 0 8px 30px rgba(0,0,0,.07);
      padding: 24px;
    }
    .cal-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    }
    .cal-head .date-display {
      font-weight: 700;
      font-size: 18px;
      color: var(--brand-navy);
    }
    .btn, button {
      text-decoration: none;
      display: inline-block;
      padding: 10px 18px;
      border-radius: 12px;
      background: #e9ecef;
      color: var(--brand-raven);
      border: none;
      cursor: pointer;
      font-weight: 600;
      font-family: var(--font-family);
      transition: all 0.2s ease;
    }
    .btn:hover, button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,.1);
    }
    .btn-primary {
      background: var(--brand-purple);
      color: #fff;
    }
    .btn-danger {
      background: var(--brand-ruby);
      color: #fff;
    }
    .btn-ghost {
      background: transparent;
      color: var(--brand-purple);
      font-size: 13px;
      padding: 4px 8px;
      box-shadow: none;
      transform: none;
    }
    .flash {
      padding: 14px 18px;
      border-radius: 12px;
      margin: 16px 0;
      font-weight: 600;
      border: 1px solid transparent;
    }
    .flash.err {
      background: #fff5f5;
      color: #c53030;
      border-color: #fed7d7;
    }
    .flash.ok {
      background: #f0fff4;
      color: #2f855a;
      border-color: #c6f6d5;
    }
    form .row { display: flex; gap: 12px; }
    label {
      font-size: 14px;
      color: var(--brand-navy);
      display: block;
      margin: 12px 0 6px;
      font-weight: 600;
    }
    input[type=text], input[type=datetime-local], input[type=email] {
      width: 100%;
      padding: 12px 14px;
      border-radius: 10px;
      border: 1px solid #dee2e6;
      background: #fff;
      font-size: 14px;
      box-sizing: border-box;
      font-family: var(--font-family);
    }
    input:focus {
        outline: none;
        border-color: var(--brand-purple);
        box-shadow: 0 0 0 3px rgba(116, 0, 255, 0.1);
    }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 12px 8px; border-bottom: 1px solid #f1f3f5; text-align: right; vertical-align: middle; }
    th { background: #f8f9fa; font-size: 13px; color: #495057; text-transform: uppercase; }
    .tag { display: inline-block; padding: 5px 10px; border-radius: 8px; font-size: 13px; background: #f3f0ff; color: var(--brand-purple); font-weight: 600; }
    .empty { text-align: center; padding: 32px; color: #868e96; }
    .footer { text-align: center; color: #adb5bd; font-size: 12px; padding: 24px 0 40px; }
    .kpi { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
    .kpi .pill { background: #eef9ff; color: #065b7a; padding: 6px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; }
    @media (max-width: 960px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="header-title">
        <img src="https://i.postimg.cc/VsG3CBzs/Logo.jpg" alt="شعار MOVO" style="height: 36px; width: auto;">
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
  <div class="footer">©️ {{ now.year }} — Operated by Movo Systems</div>
</body>
</html>
"""

INDEX = r"""
{% set d = selected_date %}
<div class="grid">
  <section class="card">
    <div class="cal-head">
      <a class="btn" href="{{ url_for('index', date=(d - delta).strftime('%Y-%m-%d')) }}">◀️ السابق</a>
      <div class="date-display">{{ d.strftime('%A, %d %B %Y') }}</div>
      <a class="btn" href="{{ url_for('index', date=(d + delta).strftime('%Y-%m-%d')) }}">التالي ▶️</a>
    </div>

    <div class="kpi">
      <div class="pill">إجمالي الحجوزات اليوم: {{ todays_count }}</div>
      <div class="pill">مجموع الساعات المحجوزة: {{ hours_booked }}</div>
    </div>

    {% if bookings %}
    <table>
      <thead>
        <tr>
          <th>العنوان</th>
          <th>الاسم</th>
          <th>الوقت</th>
          <th style="width: 120px;">إجراء</th>
        </tr>
      </thead>
      <tbody>
        {% for b in bookings %}
        <tr>
          <td><strong>{{ b.title }}</strong></td>
          <td>{{ b.name }}</td>
          <td><span class="tag">{{ b.start_at.strftime('%H:%M') }} - {{ b.end_at.strftime('%H:%M') }}</span></td>
          <td>
            <a class="btn-ghost" href="{{ url_for('delete_booking', booking_id=b.id) }}" onclick="return confirm('هل أنت متأكد من حذف هذا الحجز؟');">حذف</a>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
      <div class="empty">لا توجد حجوزات في هذا اليوم.</div>
    {% endif %}
  </section>

  <aside>
    <div class="card">
        <h3 style="margin:0 0 16px 0;">إنشاء حجز جديد</h3>
        <form method="post" action="{{ url_for('create_booking') }}">
          <label for="title">عنوان الاجتماع</label>
          <input id="title" required type="text" name="title" placeholder="مثال: اجتماع الفريق الأسبوعي">

          <div class="row">
            <div style="flex:1">
              <label for="name">الاسم</label>
              <input id="name" required type="text" name="name" placeholder="اسم المنظم">
            </div>
            <div style="flex:1">
              <label for="email">البريد الإلكتروني (اختياري)</label>
              <input id="email" type="email" name="email" placeholder="example@domain.com">
            </div>
          </div>

          <label for="start_at">وقت البداية</label>
          <input id="start_at" required type="datetime-local" name="start_at" value="{{ default_start }}">

          <label for="end_at">وقت النهاية</label>
          <input id="end_at" required type="datetime-local" name="end_at" value="{{ default_end }}">

          <div class="muted" style="margin-top:8px; font-size: 12px;">* الحد الأقصى لمدة الحجز هو 6 ساعات.</div>
          <div style="margin-top:20px">
            <button class="btn-primary" type="submit" style="width:100%;">تأكيد الحجز</button>
          </div>
        </form>
    </div>
  </aside>
</div>
"""

def render(body_html: str, **ctx):
    return render_template_string(
        BASE,
        body=body_html,
        now=datetime.now(APP_TZ),
        **ctx
    )


# ------- Routes -------
@app.get("/")
def index():
    date_q = request.args.get("date")
    today_in_qatar = datetime.now(APP_TZ).date()

    if date_q:
        try:
            selected_date = datetime.strptime(date_q, "%Y-%m-%d").date()
        except Exception:
            selected_date = today_in_qatar
    else:
        selected_date = today_in_qatar

    day_start = datetime(selected_date.year, selected_date.month, selected_date.day)
    day_end   = day_start + timedelta(days=1)

    bookings = (Booking.query
               .filter(Booking.start_at < day_end,
                       Booking.end_at > day_start)
               .order_by(Booking.start_at.asc())
               .all())

    total_minutes = 0
    for b in bookings:
        s = max(b.start_at, day_start)
        e = min(b.end_at, day_end)
        total_minutes += max(0, int((e - s).total_seconds() // 60))
    hours_booked = round(total_minutes / 60, 2)

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

    if not all([title, name, start_raw, end_raw]):
        flash("الرجاء تعبئة جميع الحقول المطلوبة.", "err")
        return redirect(url_for("index"))

    if not valid_email(email):
        flash("صيغة البريد الإلكتروني غير صحيحة.", "err")
        return redirect(url_for("index"))

    try:
        start_at = _parse_local(start_raw)
        end_at   = _parse_local(end_raw)
    except Exception:
        flash("صيغة الوقت غير صحيحة.", "err")
        return redirect(url_for("index"))

    # [FIX] Automatically handle overnight bookings. If the end time on the same
    # day is earlier than the start time, it implies the booking crosses midnight.
    if end_at.date() == start_at.date() and end_at.time() < start_at.time():
        end_at += timedelta(days=1)

    now_in_qatar = datetime.now(APP_TZ).replace(tzinfo=None, second=0, microsecond=0)
    if start_at < now_in_qatar:
        flash("لا يمكن إنشاء حجز في وقت قد مضى.", "err")
        return redirect(url_for("index"))

    if end_at <= start_at:
        flash("وقت النهاية يجب أن يكون بعد وقت البداية.", "err")
        return redirect(url_for("index"))

    if (end_at - start_at) > timedelta(hours=6):
        flash("المدة القصوى للحجز 6 ساعات.", "err")
        return redirect(url_for("index"))

    conflicting_booking = get_conflict(start_at, end_at)
    if conflicting_booking:
        msg = (f"عذرًا، هناك تعارض مع حجز آخر: "
               f"<strong>'{conflicting_booking.title}'</strong> "
               f"({conflicting_booking.start_at.strftime('%H:%M')} - {conflicting_booking.end_at.strftime('%H:%M')})")
        flash(msg, "err")
        return redirect(url_for("index", date=start_at.strftime("%Y-%m-%d")))

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
    start_date_str = b.start_at.strftime("%Y-%m-%d")
    
    db.session.delete(b)
    db.session.commit()
    
    flash("تم حذف الحجز.", "ok")
    return redirect(url_for("index", date=start_date_str))

@app.get("/health")
def health():
    return {"ok": True, "now": datetime.now().isoformat(timespec="seconds")}

if __name__ == "__main__":
    app.run(debug=True)

