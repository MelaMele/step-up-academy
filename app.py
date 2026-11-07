
import os
from datetime import datetime
from io import BytesIO
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, render_template_string, abort, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook, load_workbook

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-before-deployment")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///stepup.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="teacher")
    full_name = db.Column(db.String(120), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_code = db.Column(db.String(40), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    father_name = db.Column(db.String(80), nullable=False)
    grand_name = db.Column(db.String(80), nullable=False, default="")
    grade = db.Column(db.String(20), nullable=False)
    section = db.Column(db.String(20), nullable=False, default="A")
    gender = db.Column(db.String(20), default="")
    birth_date = db.Column(db.String(20), default="")
    guardian_name = db.Column(db.String(120), default="")
    guardian_phone = db.Column(db.String(40), default="")
    active = db.Column(db.Boolean, default=True)


class GuardianStudentLink(db.Model):
    """Explicit account-to-student link; parents only see linked children."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    user = db.relationship("User")
    student = db.relationship("Student")
    __table_args__ = (db.UniqueConstraint("user_id", "student_id", name="uq_guardian_student"),)


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name_en = db.Column(db.String(100), nullable=False)
    name_am = db.Column(db.String(100), nullable=False, default="")
    grade = db.Column(db.String(20), nullable=False)
    max_mark = db.Column(db.Float, default=100)

class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    quarter = db.Column(db.Integer, nullable=False)
    assessment = db.Column(db.String(40), nullable=False, default="Total")
    score = db.Column(db.Float, nullable=False)
    student = db.relationship("Student")
    subject = db.relationship("Subject")
    __table_args__ = (db.UniqueConstraint("student_id","subject_id","academic_year","quarter","assessment", name="uq_mark"),)

class AssessmentComponent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grade = db.Column(db.String(20), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True)
    academic_year = db.Column(db.String(20), nullable=False)
    quarter = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(60), nullable=False)
    max_score = db.Column(db.Float, nullable=False)
    subject = db.relationship("Subject")
    __table_args__ = (db.UniqueConstraint("grade", "subject_id", "academic_year", "quarter", "name", name="uq_assessment_component"),)

class GradePolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grade = db.Column(db.String(20), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    pass_mark = db.Column(db.Float, nullable=False, default=50.0)
    __table_args__ = (db.UniqueConstraint("grade", "academic_year", name="uq_grade_policy"),)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    quarter = db.Column(db.Integer, nullable=False)
    present = db.Column(db.Integer, default=0)
    absent = db.Column(db.Integer, default=0)
    student = db.relationship("Student")

def current_user():
    return User.query.get(session.get("user_id")) if session.get("user_id") else None

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user(): return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            u = current_user()
            if not u: return redirect(url_for("login"))
            if u.role not in roles: abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco

BASE = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Step Up Academy</title><style>
:root{--navy:#173d68;--blue:#276aa5;--gold:#e4b64d;--bg:#f4f7fb;--ink:#203047}
*{box-sizing:border-box}body{margin:0;font:15px Arial,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--navy);color:white;padding:16px 22px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
header strong{font-size:20px;letter-spacing:.4px}.brand{display:flex;align-items:center;gap:12px}.brand img{width:64px;height:64px;object-fit:contain;background:#fff;border-radius:8px;padding:3px}nav{background:#fff;padding:12px 22px;display:flex;gap:16px;flex-wrap:wrap;border-bottom:1px solid #dce4ee}
a{color:var(--blue);text-decoration:none}nav a{font-weight:600}.wrap{max-width:1200px;margin:24px auto;padding:0 16px}
.card{background:white;border:1px solid #e0e7ef;border-radius:12px;padding:18px;margin-bottom:16px;box-shadow:0 2px 8px #173d680d}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.stat{font-size:28px;font-weight:700;color:var(--navy);margin-top:8px}
input,select{padding:10px;border:1px solid #cbd5e1;border-radius:7px;width:100%;margin:5px 0 12px;background:white}
label{font-weight:600;font-size:13px}button,.btn{background:var(--blue);color:white;border:0;border-radius:7px;padding:10px 15px;cursor:pointer;display:inline-block}
button:hover,.btn:hover{background:var(--navy);color:white}table{border-collapse:collapse;width:100%;background:white}
th,td{padding:10px;border-bottom:1px solid #e5eaf0;text-align:left}th{background:#edf3f9}
.notice{padding:10px;border-radius:7px;background:#fff7df;margin:10px 0}.muted{color:#64748b;font-size:13px}
.row{display:flex;gap:12px;flex-wrap:wrap}.row>*{flex:1;min-width:160px}
.report{text-align:center;border:2px solid var(--navy);padding:20px;background:white}
@media print{header,nav,.no-print{display:none!important}.report{break-after:page;page-break-after:always}body{background:white}.wrap{margin:0;max-width:none}.card{box-shadow:none;border:0}}
</style></head><body>
<header><div class="brand"><img src="{{ url_for('static', filename='step_up_academy_logo.jpeg') }}" alt="Step Up Academy logo"><div><strong>STEP UP ACADEMY</strong><div class="muted" style="color:#dce8f5">Student & Academic Management</div></div></div>
<div>{% if user %}{{ user.full_name }} · {{ user.role }} · <a style="color:#fff" href="{{ url_for('logout') }}">Logout</a>{% endif %}</div></header>
{% if user %}<nav><a href="{{ url_for('dashboard') }}">Dashboard</a><a href="{{ url_for('students') }}">Students</a>{% if user.role in ['admin','registrar'] %}<a href="{{ url_for('import_students') }}">Excel Import</a>{% endif %}<a href="{{ url_for('subjects') }}">Subjects</a><a href="{{ url_for('marks') }}">Marks</a>{% if user.role in ['admin','registrar'] %}<a href="{{ url_for('assessment_settings') }}">Assessment Settings</a>{% endif %}<a href="{{ url_for('reports') }}">Report Cards</a><a href="{{ url_for('annual_results') }}">Annual Results & Ranking</a>{% if user.role=='admin' %}<a href="{{ url_for('users') }}">Users</a>{% endif %}{% if user.role in ['admin','registrar'] %}<a href="{{ url_for('parent_links') }}">Parent Links</a>{% endif %}{% if user.role=='parent' %}<a href="{{ url_for('parent_portal') }}">Parent Portal</a>{% endif %}{% if user.role in ['admin','registrar','teacher'] %}<a href="{{ url_for('class_summary') }}">Class Summary</a><a href="{{ url_for('bulk_reports') }}">Bulk Reports</a>{% endif %}</nav>{% endif %}
<div class="wrap">{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="notice">{{m}}</div>{% endfor %}{% endwith %}{{ body|safe }}</div>
</body></html>
"""

def page(body, **ctx):
    return render_template_string(BASE, body=render_template_string(body, **ctx), user=current_user())

@app.route("/")
def home(): return redirect(url_for("dashboard") if current_user() else url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(username=request.form["username"].strip()).first()
        if u and u.check_password(request.form["password"]):
            session["user_id"]=u.id
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.")
    return page("""<div class="card" style="max-width:420px;margin:50px auto"><h2>Sign in / ግባ</h2><form method="post"><label>Username</label><input name="username" required><label>Password</label><input type="password" name="password" required><button>Login</button></form><p class="muted">Initial admin: admin / StepUp@123 (change immediately)</p></div>""")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    return page("""<h2>Dashboard / ዋና ገጽ</h2><div class="grid">
    <div class="card">Total Students<div class="stat">{{students}}</div></div>
    <div class="card">Subjects<div class="stat">{{subjects}}</div></div>
    <div class="card">Marks Entered<div class="stat">{{marks}}</div></div>
    <div class="card">Active Users<div class="stat">{{users}}</div></div></div>
    <div class="card"><h3>Academic structure</h3>KG – Grade 8 · Quarter 1, 2, 3, 4 · Marks out of 100 · Amharic / English</div>""",
    students=Student.query.filter_by(active=True).count(),subjects=Subject.query.count(),marks=Mark.query.count(),users=User.query.count())

@app.route("/students", methods=["GET","POST"])
@login_required
def students():
    if request.method=="POST":
        if current_user().role not in ("admin","registrar"): abort(403)
        s=Student(student_code=request.form["code"].strip(),first_name=request.form["first"].strip(),
        father_name=request.form["father"].strip(),grand_name=request.form.get("grand","").strip(),
        grade=request.form["grade"],section=request.form.get("section","A"),gender=request.form.get("gender",""),
        guardian_name=request.form.get("guardian",""),guardian_phone=request.form.get("phone",""))
        db.session.add(s)
        try: db.session.commit(); flash("Student registered successfully.")
        except: db.session.rollback(); flash("Student ID already exists. Use a unique ID.")
        return redirect(url_for("students"))
    return page("""<h2>Students / ተማሪዎች</h2>
    {% if user.role in ['admin','registrar'] %}<div class="card"><h3>Register student</h3><form method="post">
    <div class="row"><div><label>Student ID</label><input name="code" required placeholder="SUA-0001"></div><div><label>First name</label><input name="first" required></div><div><label>Father name</label><input name="father" required></div></div>
    <div class="row"><div><label>Grandfather name</label><input name="grand"></div><div><label>Grade</label><select name="grade">{% for g in grades %}<option>{{g}}</option>{% endfor %}</select></div><div><label>Section</label><input name="section" value="A"></div></div>
    <div class="row"><div><label>Gender</label><select name="gender"><option></option><option>Female</option><option>Male</option></select></div><div><label>Guardian name</label><input name="guardian"></div><div><label>Guardian phone</label><input name="phone"></div></div><button>Save student</button></form></div>{% endif %}
    <div class="card"><form method="get"><div class="row"><input name="q" placeholder="Search name or ID" value="{{q}}"><select name="grade"><option value="">All grades</option>{% for g in grades %}<option {% if grade==g %}selected{% endif %}>{{g}}</option>{% endfor %}</select><button>Filter</button></div></form>
    <table><tr><th>ID</th><th>Student</th><th>Grade</th><th>Section</th><th>Card</th></tr>{% for s in data %}<tr><td>{{s.student_code}}</td><td>{{s.first_name}} {{s.father_name}} {{s.grand_name}}</td><td>{{s.grade}}</td><td>{{s.section}}</td><td><a href="{{url_for('student_card',sid=s.id)}}">Open card</a></td></tr>{% endfor %}</table><p class="muted">Showing up to 250 records. Use search and grade filters for larger lists.</p></div>""",
    data=student_list_query(request.args.get("q",""), request.args.get("grade","")).limit(500).all(),
    q=request.args.get("q",""),grade=request.args.get("grade",""),grades=["KG"]+[f"Grade {i}" for i in range(1,9)])


def student_list_query(q="", grade=""):
    query = Student.query.filter_by(active=True)
    if grade:
        query = query.filter(Student.grade == grade)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(db.or_(Student.student_code.ilike(term), Student.first_name.ilike(term),
                                    Student.father_name.ilike(term), Student.grand_name.ilike(term)))
    return query.order_by(Student.grade, Student.section, Student.first_name)


@app.route("/students/template")
@roles_required("admin", "registrar")
def student_import_template():
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append(["student_code", "first_name", "father_name", "grand_name", "grade", "section", "gender", "guardian_name", "guardian_phone"])
    ws.append(["SUA-0001", "Abebe", "Kebede", "Tesfaye", "Grade 1", "A", "Male", "Kebede Abebe", "0911000000"])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col, width in {"A":18,"B":20,"C":20,"D":20,"E":15,"F":12,"G":12,"H":24,"I":18}.items():
        ws.column_dimensions[col].width = width
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="Step_Up_Students_Template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/students/import", methods=["GET", "POST"])
@roles_required("admin", "registrar")
def import_students():
    grades = ["KG"] + [f"Grade {i}" for i in range(1, 9)]
    if request.method == "POST":
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename.lower().endswith(".xlsx"):
            flash("እባክዎ .xlsx Excel ፋይል ይምረጡ።")
            return redirect(url_for("import_students"))
        try:
            wb = load_workbook(uploaded, read_only=True, data_only=True)
            ws = wb.active
            rows = ws.iter_rows(values_only=True)
            headers = [str(x).strip().lower() if x is not None else "" for x in next(rows)]
            required = ["student_code", "first_name", "father_name", "grade"]
            missing = [h for h in required if h not in headers]
            if missing:
                flash("የሚያስፈልጉ አምዶች የሉም: " + ", ".join(missing))
                return redirect(url_for("import_students"))
            index = {h: headers.index(h) for h in headers if h}
            prepared, errors, seen = [], [], set()
            for line_no, row in enumerate(rows, start=2):
                if not row or all(v is None or str(v).strip() == "" for v in row):
                    continue
                def val(key):
                    i = index.get(key)
                    return str(row[i]).strip() if i is not None and i < len(row) and row[i] is not None else ""
                code, first, father, grade = val("student_code"), val("first_name"), val("father_name"), val("grade")
                if not code or not first or not father or not grade:
                    errors.append(f"Row {line_no}: student_code, first_name, father_name, grade አያሟሉም")
                    continue
                if grade not in grades:
                    errors.append(f"Row {line_no}: የክፍል ስም ትክክል አይደለም ({grade})")
                    continue
                if code in seen or Student.query.filter_by(student_code=code).first():
                    errors.append(f"Row {line_no}: የተማሪ መለያ ተደግሟል ({code})")
                    continue
                seen.add(code)
                gender = val("gender")
                if gender and gender.lower() not in ("male", "female", "ወንድ", "ሴት"):
                    errors.append(f"Row {line_no}: gender Male/Female ወይም ወንድ/ሴት ይሁን")
                    continue
                prepared.append(Student(student_code=code, first_name=first, father_name=father,
                    grand_name=val("grand_name"), grade=grade, section=val("section") or "A",
                    gender=gender, guardian_name=val("guardian_name"), guardian_phone=val("guardian_phone")))
            wb.close()
            if errors:
                preview = " | ".join(errors[:8])
                flash(f"ምንም ተማሪ አልተጨመረም። {len(errors)} ስህተት ተገኝቷል: {preview}")
            elif not prepared:
                flash("በፋይሉ ውስጥ ለመጨመር ተማሪ አልተገኘም።")
            else:
                db.session.add_all(prepared)
                db.session.commit()
                flash(f"በተሳካ ሁኔታ {len(prepared)} ተማሪዎች ተመዝግበዋል።")
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("Student Excel import failed")
            flash("ፋይሉን ማንበብ አልተቻለም። የተሰጠውን Excel template ይጠቀሙ።")
        return redirect(url_for("import_students"))
    return page("""<h2>Excel Student Import / ተማሪዎችን በExcel ማስገባት</h2>
    <div class=\"card\"><p>1. መጀመሪያ የExcel ናሙና ፋይሉን ያውርዱ።</p>
    <p><a class=\"btn\" href=\"{{url_for('student_import_template')}}\">Download Excel Template</a></p>
    <p>2. የተማሪዎችን መረጃ በናሙናው ውስጥ ያስገቡ። የstudent_code መለያ ለእያንዳንዱ ተማሪ ልዩ መሆን አለበት።</p>
    <p>3. የተሞላውን .xlsx ፋይል ከዚህ በታች ይጫኑ። ስህተት ካለ ሙሉ ዝርዝሩ እስኪስተካከል ድረስ ምንም ተማሪ አይጨመርም።</p>
    <form method=\"post\" enctype=\"multipart/form-data\"><label>Excel file (.xlsx)</label><input type=\"file\" name=\"file\" accept=\".xlsx\" required><button>Import Students</button></form>
    <p class=\"muted\">Required columns: student_code, first_name, father_name, grade. Optional: grand_name, section, gender, guardian_name, guardian_phone. Maximum file size: 5 MB.</p></div>""")

@app.route("/subjects", methods=["GET","POST"])
@login_required
def subjects():
    if request.method=="POST":
        if current_user().role not in ("admin","registrar"): abort(403)
        db.session.add(Subject(name_en=request.form["en"],name_am=request.form.get("am",""),grade=request.form["grade"],max_mark=100))
        db.session.commit(); flash("Subject added."); return redirect(url_for("subjects"))
    return page("""<h2>Subjects / ትምህርቶች</h2>{% if user.role in ['admin','registrar'] %}<div class="card"><form method="post"><div class="row"><div><label>Subject English</label><input name="en" required></div><div><label>Subject Amharic</label><input name="am"></div><div><label>Grade</label><select name="grade">{% for g in grades %}<option>{{g}}</option>{% endfor %}</select></div></div><button>Add subject</button></form></div>{% endif %}
    <div class="card"><table><tr><th>Grade</th><th>English</th><th>Amharic</th><th>Out of</th></tr>{% for s in data %}<tr><td>{{s.grade}}</td><td>{{s.name_en}}</td><td>{{s.name_am}}</td><td>{{s.max_mark}}</td></tr>{% endfor %}</table></div>""",
    grades=["KG"]+[f"Grade {i}" for i in range(1,9)],data=Subject.query.order_by(Subject.grade,Subject.name_en).all())

@app.route("/assessment-settings", methods=["GET", "POST"])
@roles_required("admin", "registrar")
def assessment_settings():
    grades = ["KG"] + [f"Grade {i}" for i in range(1, 9)]
    if request.method == "POST":
        grade = request.form.get("grade", "")
        subject_raw = request.form.get("subject_id", "")
        subject_id = int(subject_raw) if subject_raw else None
        year = request.form.get("year", "").strip()
        quarter = int(request.form.get("quarter", "1"))
        name = request.form.get("name", "").strip()
        try: maximum = float(request.form.get("max_score", ""))
        except ValueError: maximum = 0
        if grade not in grades or not year or not name or quarter not in range(1, 5) or maximum <= 0 or maximum > 100:
            flash("እባክዎ ትክክለኛ መረጃ ያስገቡ፤ ከፍተኛ ማርክ ከ0 በላይ እና 100 ወይም ከዚያ በታች መሆን አለበት።")
            return redirect(url_for("assessment_settings"))
        if subject_id and not Subject.query.filter_by(id=subject_id, grade=grade).first():
            flash("የተመረጠው ትምህርት ከክፍሉ ጋር አይዛመድም።")
            return redirect(url_for("assessment_settings"))
        item = AssessmentComponent.query.filter_by(grade=grade, subject_id=subject_id, academic_year=year, quarter=quarter, name=name).first()
        if item: item.max_score = maximum
        else: db.session.add(AssessmentComponent(grade=grade, subject_id=subject_id, academic_year=year, quarter=quarter, name=name, max_score=maximum))
        db.session.commit(); flash("የማርክ ክፍፍሉ ተቀምጧል።")
        return redirect(url_for("assessment_settings"))
    items = AssessmentComponent.query.order_by(AssessmentComponent.academic_year.desc(), AssessmentComponent.grade, AssessmentComponent.quarter, AssessmentComponent.name).all()
    return page("""<h2>Assessment Settings / የማርክ ክፍፍል ማስተካከያ</h2>
    <div class="card"><p>የማርክ ክፍፍሉን በክፍል፣ በትምህርት (አማራጭ)፣ በዓመትና በኳርተር ያዘጋጁ። ትምህርት ካልመረጡ ለዚያ ክፍል አጠቃላይ ይሆናል።</p>
    <form method="post"><div class="row"><div><label>Grade</label><select name="grade">{% for g in grades %}<option>{{g}}</option>{% endfor %}</select></div>
    <div><label>Subject (optional)</label><select name="subject_id"><option value="">All subjects in grade</option>{% for x in subjects %}<option value="{{x.id}}">{{x.grade}} – {{x.name_en}}</option>{% endfor %}</select></div>
    <div><label>Academic year E.C.</label><input name="year" value="2019" required></div><div><label>Quarter</label><select name="quarter">{% for q in range(1,5) %}<option value="{{q}}">Quarter {{q}}</option>{% endfor %}</select></div></div>
    <div class="row"><div><label>Assessment name</label><input name="name" placeholder="Quiz / Assignment / Mid Exam" required></div><div><label>Maximum score</label><input name="max_score" type="number" min="0.01" max="100" step="0.01" required></div></div><button>Save / Update component</button></form></div>
    <div class="card"><h3>Configured components</h3><table><tr><th>Year</th><th>Grade</th><th>Subject scope</th><th>Quarter</th><th>Assessment</th><th>Out of</th></tr>{% for x in items %}<tr><td>{{x.academic_year}}</td><td>{{x.grade}}</td><td>{{x.subject.name_en if x.subject else 'All subjects'}}</td><td>{{x.quarter}}</td><td>{{x.name}}</td><td>{{x.max_score}}</td></tr>{% endfor %}</table></div>""", grades=grades, subjects=Subject.query.order_by(Subject.grade,Subject.name_en).all(), items=items)

@app.route("/marks", methods=["GET","POST"])
@login_required
def marks():
    if request.method == "POST":
        if current_user().role not in ("admin", "teacher"): abort(403)
        student = Student.query.get_or_404(int(request.form["student_id"]))
        subject = Subject.query.get_or_404(int(request.form["subject_id"]))
        year = request.form["year"].strip(); q = int(request.form["quarter"]); assessment = request.form.get("assessment", "").strip()
        config = AssessmentComponent.query.filter_by(grade=student.grade, subject_id=subject.id, academic_year=year, quarter=q, name=assessment).first()
        if not config:
            config = AssessmentComponent.query.filter_by(grade=student.grade, subject_id=None, academic_year=year, quarter=q, name=assessment).first()
        if not config or subject.grade != student.grade:
            flash("ለዚህ ተማሪና ትምህርት የተዘጋጀ የማርክ ክፍፍል የለም። Admin በAssessment Settings ያዘጋጅ።")
            return redirect(url_for("marks"))
        try: score = float(request.form["score"])
        except ValueError: score = -1
        if score < 0 or score > config.max_score:
            flash(f"ማርኩ ከ0 እስከ {config.max_score} መሆን አለበት።")
            return redirect(url_for("marks"))
        m = Mark.query.filter_by(student_id=student.id, subject_id=subject.id, academic_year=year, quarter=q, assessment=assessment).first()
        if m: m.score = score
        else: db.session.add(Mark(student_id=student.id, subject_id=subject.id, academic_year=year, quarter=q, assessment=assessment, score=score))
        db.session.commit(); flash("ማርኩ ተቀምጧል።"); return redirect(url_for("marks"))
    year = request.args.get("year", "2019"); q = int(request.args.get("quarter", "1")); subject_id = request.args.get("subject_id", type=int)
    subject = Subject.query.get(subject_id) if subject_id else None
    configs = []
    if subject:
        configs = AssessmentComponent.query.filter_by(grade=subject.grade, subject_id=subject.id, academic_year=year, quarter=q).all()
        if not configs: configs = AssessmentComponent.query.filter_by(grade=subject.grade, subject_id=None, academic_year=year, quarter=q).all()
    return page("""<h2>Mark Entry / የማርክ ማስገቢያ</h2><div class="card"><p class="muted">ከመጀመሪያ Assessment Settings ውስጥ የማርክ ክፍፍል ያዘጋጁ። ከዚያ ተማሪ፣ ትምህርት፣ ዓመትና ኳርተር ይምረጡ።</p>
    <form method="get"><div class="row"><div><label>Academic year</label><input name="year" value="{{year}}"></div><div><label>Quarter</label><select name="quarter">{% for n in range(1,5) %}<option value="{{n}}" {% if q==n %}selected{% endif %}>Quarter {{n}}</option>{% endfor %}</select></div><div><label>Subject (to load components)</label><select name="subject_id"><option value="">Choose subject</option>{% for x in subjects %}<option value="{{x.id}}" {% if subject and subject.id==x.id %}selected{% endif %}>{{x.grade}} – {{x.name_en}}</option>{% endfor %}</select></div></div><button>Load assessment list</button></form>
    {% if subject %}<hr><form method="post"><div class="row"><div><label>Student</label><select name="student_id" required>{% for x in students if x.grade==subject.grade %}<option value="{{x.id}}">{{x.student_code}} – {{x.first_name}} {{x.father_name}} ({{x.grade}} {{x.section}})</option>{% endfor %}</select></div><div><label>Subject</label><input value="{{subject.name_en}}" disabled><input type="hidden" name="subject_id" value="{{subject.id}}"></div></div>
    <input type="hidden" name="year" value="{{year}}"><input type="hidden" name="quarter" value="{{q}}"><div class="row"><div><label>Assessment</label><select name="assessment" required>{% for c in configs %}<option value="{{c.name}}">{{c.name}} (out of {{c.max_score}})</option>{% endfor %}</select></div><div><label>Score</label><input name="score" type="number" min="0" max="100" step="0.01" required></div></div>{% if configs %}<button>Save mark</button>{% else %}<div class="notice">ለዚህ ምርጫ የተዘጋጀ assessment የለም።</div>{% endif %}</form>{% endif %}</div>
    <div class="card"><h3>Recent marks</h3><table><tr><th>Student</th><th>Subject</th><th>Year</th><th>Quarter</th><th>Assessment</th><th>Score</th></tr>{% for m in recent %}<tr><td>{{m.student.first_name}} {{m.student.father_name}}</td><td>{{m.subject.name_en}}</td><td>{{m.academic_year}}</td><td>{{m.quarter}}</td><td>{{m.assessment}}</td><td>{{m.score}}</td></tr>{% endfor %}</table></div>""", year=year, q=q, subject=subject, configs=configs, subjects=Subject.query.order_by(Subject.grade,Subject.name_en).all(), students=Student.query.filter_by(active=True).order_by(Student.grade,Student.first_name).all(), recent=Mark.query.order_by(Mark.id.desc()).limit(30).all())

@app.route("/reports")
@login_required
def reports():
    return page("""<h2>Report Cards / የውጤት ካርዶች</h2><div class="card"><form method="get"><div class="row"><div><label>Student ID</label><input name="code" value="{{code}}" placeholder="SUA-0001"></div><div><label>Academic year</label><input name="year" value="{{year}}"></div><div><label>Quarter</label><select name="quarter">{% for q in range(1,5) %}<option value="{{q}}" {% if quarter==q|string %}selected{% endif %}>Quarter {{q}}</option>{% endfor %}</select></div><button>Generate</button></div></form>
    {% if student %}<a class="btn no-print" href="{{url_for('student_card',sid=student.id,year=year,quarter=quarter)}}">Open printable report card</a>{% endif %}</div>
    {% if not student and code %}<div class="notice">No student found with that ID.</div>{% endif %}""",
    student=Student.query.filter_by(student_code=request.args.get("code","")).first() if request.args.get("code") else None,code=request.args.get("code",""),year=request.args.get("year","2019"),quarter=request.args.get("quarter","1"))

@app.route("/student/<int:sid>/card")
@login_required
def student_card(sid):
    s=Student.query.get_or_404(sid); year=request.args.get("year","2019"); q=int(request.args.get("quarter","1"))
    marks=Mark.query.filter_by(student_id=s.id,academic_year=year,quarter=q).all()
    # One report line per subject: assessment rows are summed only if configured as component scores;
    # Total assessment is displayed as entered.
    grouped={}
    for m in marks: grouped.setdefault(m.subject_id,{"subject":m.subject,"scores":[]}).get("scores").append(m)
    rows=[]
    for item in grouped.values():
        total_rows=[x for x in item["scores"] if x.assessment=="Total"]
        if total_rows:
            score = total_rows[-1].score
        else:
            weighted = 0.0
            for mark in item["scores"]:
                cfg = AssessmentComponent.query.filter_by(grade=s.grade, subject_id=item["subject"].id, academic_year=year, quarter=q, name=mark.assessment).first()
                if not cfg:
                    cfg = AssessmentComponent.query.filter_by(grade=s.grade, subject_id=None, academic_year=year, quarter=q, name=mark.assessment).first()
                if cfg and cfg.max_score > 0:
                    weighted += (mark.score / cfg.max_score) * cfg.max_score
            configured_total = sum(c.max_score for c in AssessmentComponent.query.filter_by(grade=s.grade, subject_id=item["subject"].id, academic_year=year, quarter=q).all())
            if configured_total == 0:
                configured_total = sum(c.max_score for c in AssessmentComponent.query.filter_by(grade=s.grade, subject_id=None, academic_year=year, quarter=q).all())
            score = round((weighted / configured_total) * 100, 2) if configured_total else 0
        rows.append((item["subject"],score))
    avg=round(sum(x[1] for x in rows)/len(rows),2) if rows else 0
    return page("""<div class="report"><img src="{{ url_for('static', filename='step_up_academy_logo.jpeg') }}" alt="Step Up Academy logo" style="width:115px;height:115px;object-fit:contain"><h1>STEP UP ACADEMY</h1><h2>STUDENT REPORT CARD</h2><h3>Academic Year {{year}} E.C. · Quarter {{q}}</h3>
    <hr><div style="text-align:left"><b>Student:</b> {{s.first_name}} {{s.father_name}} {{s.grand_name}}<br><b>Student ID:</b> {{s.student_code}}<br><b>Grade / Section:</b> {{s.grade}} / {{s.section}}</div>
    <table style="margin-top:20px"><tr><th>Subject</th><th>Mark / 100</th><th>Letter</th></tr>{% for subject,score in rows %}<tr><td>{{subject.name_en}}{% if subject.name_am %} / {{subject.name_am}}{% endif %}</td><td>{{"%.2f"|format(score)}}</td><td>{{letter(score)}}</td></tr>{% endfor %}</table>
    <h3>Average: {{avg}}% · Subjects recorded: {{rows|length}}</h3><p style="text-align:left">Teacher's comment: __________________________________________</p>
    <div style="display:flex;justify-content:space-between;margin-top:55px"><span>Class Teacher: ______________</span><span>Principal: ______________</span></div>
    <p style="margin-top:30px;color:#64748b">STEP UP ACADEMY · LEARN TODAY, LEAD TOMORROW</p></div><p class="no-print"><button onclick="window.print()">Print / Save as PDF</button></p>""",s=s,year=year,q=q,rows=rows,avg=avg,letter=letter_grade)

def letter_grade(score):
    if score>=90:return "A+"
    if score>=80:return "A"
    if score>=70:return "B"
    if score>=60:return "C"
    if score>=50:return "D"
    return "F"

def configured_components(grade, subject_id, year, quarter):
    specific = AssessmentComponent.query.filter_by(grade=grade, subject_id=subject_id,
        academic_year=year, quarter=quarter).order_by(AssessmentComponent.id).all()
    if specific:
        return specific
    return AssessmentComponent.query.filter_by(grade=grade, subject_id=None,
        academic_year=year, quarter=quarter).order_by(AssessmentComponent.id).all()


def quarter_subject_score(student, subject, year, quarter):
    """Return normalized /100 score only when every configured component is marked."""
    components = configured_components(student.grade, subject.id, year, quarter)
    if not components:
        return None
    marks_by_name = {m.assessment: m for m in Mark.query.filter_by(
        student_id=student.id, subject_id=subject.id, academic_year=year,
        quarter=quarter).all()}
    if any(c.name not in marks_by_name for c in components):
        return None
    earned = sum(marks_by_name[c.name].score for c in components)
    possible = sum(c.max_score for c in components)
    if possible <= 0:
        return None
    return round(earned / possible * 100, 2)


@app.route("/annual-results", methods=["GET", "POST"])
@login_required
def annual_results():
    grades = ["KG"] + [f"Grade {i}" for i in range(1, 9)]
    if request.method == "POST":
        if current_user().role not in ("admin", "registrar"):
            abort(403)
        grade = request.form.get("grade", "")
        year = request.form.get("year", "").strip()
        try:
            threshold = float(request.form.get("pass_mark", "50"))
        except ValueError:
            threshold = -1
        if grade not in grades or not year or not 0 <= threshold <= 100:
            flash("እባክዎ ትክክለኛ ክፍል፣ ዓመትና ከ0 እስከ 100 የማለፊያ ማርክ ያስገቡ።")
        else:
            policy = GradePolicy.query.filter_by(grade=grade, academic_year=year).first()
            if policy:
                policy.pass_mark = threshold
            else:
                db.session.add(GradePolicy(grade=grade, academic_year=year, pass_mark=threshold))
            db.session.commit()
            flash("የማለፊያ ማርክ ተቀምጧል።")
        return redirect(url_for("annual_results", year=year, grade=grade,
                                 section=request.form.get("section", "")))

    year = request.args.get("year", "2019").strip()
    grade = request.args.get("grade", "Grade 1")
    section = request.args.get("section", "")
    if grade not in grades:
        grade = "Grade 1"
    policy = GradePolicy.query.filter_by(grade=grade, academic_year=year).first()
    pass_mark = policy.pass_mark if policy else 50.0
    students_q = Student.query.filter_by(active=True, grade=grade)
    if section:
        students_q = students_q.filter_by(section=section)
    students_list = students_q.order_by(Student.section, Student.first_name, Student.father_name).all()
    subjects_list = Subject.query.filter_by(grade=grade).order_by(Subject.name_en).all()
    results = []
    for student in students_list:
        quarter_avgs = []
        subject_annual = []
        complete = bool(subjects_list)
        for qtr in range(1, 5):
            scores = [quarter_subject_score(student, subj, year, qtr) for subj in subjects_list]
            if not scores or any(score is None for score in scores):
                quarter_avgs.append(None)
                complete = False
            else:
                quarter_avgs.append(round(sum(scores) / len(scores), 2))
        for subj in subjects_list:
            qs = [quarter_subject_score(student, subj, year, qtr) for qtr in range(1, 5)]
            if any(score is None for score in qs):
                complete = False
            else:
                subject_annual.append(round(sum(qs) / 4, 2))
        annual = round(sum(subject_annual) / len(subject_annual), 2) if complete and subject_annual and len(subject_annual) == len(subjects_list) else None
        results.append({"student": student, "quarters": quarter_avgs, "annual": annual,
                        "status": ("Pass" if annual is not None and annual >= pass_mark else
                                   "Needs review" if annual is not None else "Incomplete")})
    rank_map = {}
    by_section = {}
    for item in results:
        if item["annual"] is not None:
            by_section.setdefault(item["student"].section, []).append(item)
    for section_name, section_results in by_section.items():
        ranked = sorted(section_results, key=lambda r: r["annual"], reverse=True)
        last_score = None
        last_rank = 0
        for index, item in enumerate(ranked, start=1):
            if item["annual"] != last_score:
                last_rank = index
                last_score = item["annual"]
            rank_map[item["student"].id] = last_rank
    for item in results:
        item["rank"] = rank_map.get(item["student"].id, "—")
    results.sort(key=lambda r: (r["student"].section, r["rank"] if isinstance(r["rank"], int) else 99999,
                                r["student"].first_name))
    sections = [x[0] for x in db.session.query(Student.section).filter_by(active=True, grade=grade).distinct().order_by(Student.section).all()]
    return page("""<h2>Annual Results & Ranking / የዓመት ውጤትና ደረጃ</h2>
    <div class="card"><form method="get"><div class="row"><div><label>Academic year E.C.</label><input name="year" value="{{year}}"></div><div><label>Grade</label><select name="grade">{% for g in grades %}<option value="{{g}}" {% if grade==g %}selected{% endif %}>{{g}}</option>{% endfor %}</select></div><div><label>Section</label><select name="section"><option value="">All sections</option>{% for x in sections %}<option value="{{x}}" {% if section==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select></div></div><button>Generate annual results</button></form></div>
    {% if user.role in ['admin','registrar'] %}<div class="card"><h3>Promotion policy / የማለፊያ መስፈርት</h3><form method="post"><input type="hidden" name="grade" value="{{grade}}"><input type="hidden" name="year" value="{{year}}"><input type="hidden" name="section" value="{{section}}"><label>Minimum annual average to pass (0–100)</label><input name="pass_mark" type="number" min="0" max="100" step="0.01" value="{{pass_mark}}" required><button>Save pass mark</button></form><p class="muted">ይህ መስፈርት ለተመረጠው ክፍልና ዓመት ብቻ ይሠራል።</p></div>{% endif %}
    <div class="card"><p><b>Pass mark:</b> {{pass_mark}}% · <b>Students:</b> {{results|length}} · <b>Rank:</b> በክፍልና በሴክሽን ውስጥ በተሟላ ዓመታዊ ውጤት ይሰላል።</p>
    <div style="overflow-x:auto"><table><tr><th>Rank</th><th>Student ID</th><th>Student</th><th>Section</th><th>Q1 Avg</th><th>Q2 Avg</th><th>Q3 Avg</th><th>Q4 Avg</th><th>Annual Avg</th><th>Decision</th></tr>{% for r in results %}<tr><td>{{r.rank}}</td><td>{{r.student.student_code}}</td><td>{{r.student.first_name}} {{r.student.father_name}}</td><td>{{r.student.section}}</td>{% for v in r.quarters %}<td>{{'%.2f'|format(v) if v is not none else '—'}}</td>{% endfor %}<td><b>{{'%.2f'|format(r.annual) if r.annual is not none else '—'}}</b></td><td>{{r.status}}</td></tr>{% endfor %}</table></div>
    <p class="muted">Incomplete = አንድ ወይም ከዚያ በላይ ኳርተር/ትምህርት ውጤት የጎደለው። የዓመት አማካይ ለመስላት ሁሉም 4 ኳርተሮች እና ሁሉም የክፍሉ ትምህርቶች የተሟላ ውጤት ሊኖራቸው ይገባል።</p></div>""", year=year, grade=grade, section=section, grades=grades,
        sections=sections, pass_mark=pass_mark, results=results)


@app.route("/users", methods=["GET","POST"])
@roles_required("admin")
def users():
    if request.method=="POST":
        u=User(username=request.form["username"].strip(),full_name=request.form["name"].strip(),role=request.form["role"])
        u.set_password(request.form["password"]); db.session.add(u)
        try: db.session.commit(); flash("User created.")
        except: db.session.rollback(); flash("Username already exists.")
        return redirect(url_for("users"))
    return page("""<h2>User Accounts / የተጠቃሚ መለያዎች</h2><div class="card"><form method="post"><div class="row"><div><label>Full name</label><input name="name" required></div><div><label>Username</label><input name="username" required></div><div><label>Temporary password</label><input name="password" type="password" required minlength="8"></div><div><label>Role</label><select name="role"><option value="teacher">Teacher</option><option value="registrar">Registrar</option><option value="parent">Parent</option><option value="student">Student</option><option value="admin">Admin</option></select></div></div><button>Create account</button></form></div><div class="card"><table><tr><th>Name</th><th>Username</th><th>Role</th></tr>{% for u in data %}<tr><td>{{u.full_name}}</td><td>{{u.username}}</td><td>{{u.role}}</td></tr>{% endfor %}</table></div>""",data=User.query.order_by(User.full_name).all())


@app.route("/parent-links", methods=["GET", "POST"])
@roles_required("admin", "registrar")
def parent_links():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        code = request.form.get("student_code", "").strip()
        account = User.query.filter_by(username=username, role="parent").first()
        student = Student.query.filter_by(student_code=code, active=True).first()
        if not account or not student:
            flash("የወላጅ መለያውንና የተማሪ መለያውን ያረጋግጡ።")
        elif GuardianStudentLink.query.filter_by(user_id=account.id, student_id=student.id).first():
            flash("ይህ ግንኙነት አስቀድሞ ተመዝግቧል።")
        else:
            db.session.add(GuardianStudentLink(user_id=account.id, student_id=student.id))
            db.session.commit()
            flash("የወላጅና ተማሪ ግንኙነት ተመዝግቧል።")
        return redirect(url_for("parent_links"))
    links = GuardianStudentLink.query.join(User).join(Student).order_by(User.full_name, Student.first_name).all()
    return page("""<h2>Parent–Student Links / የወላጅ ግንኙነት</h2>
    <div class="card"><p>መጀመሪያ Users ውስጥ Role = Parent የሆነ መለያ ይፍጠሩ። ከዚያ ከታች ከተማሪው ጋር ያገናኙት።</p>
    <form method="post"><div class="row"><div><label>Parent username</label><input name="username" required></div><div><label>Student ID</label><input name="student_code" required></div></div><button>Link account</button></form></div>
    <div class="card"><h3>Existing links</h3><table><tr><th>Parent</th><th>Username</th><th>Student ID</th><th>Student</th><th>Grade</th></tr>{% for x in links %}<tr><td>{{x.user.full_name}}</td><td>{{x.user.username}}</td><td>{{x.student.student_code}}</td><td>{{x.student.first_name}} {{x.student.father_name}}</td><td>{{x.student.grade}} {{x.student.section}}</td></tr>{% endfor %}</table></div>""", links=links)


@app.route("/parent-portal")
@roles_required("parent")
def parent_portal():
    year = request.args.get("year", "2019").strip()
    qtr = request.args.get("quarter", "1")
    try: qtr = int(qtr)
    except ValueError: qtr = 1
    if qtr not in (1, 2, 3, 4): qtr = 1
    links = GuardianStudentLink.query.filter_by(user_id=current_user().id).all()
    children = []
    for link in links:
        student = link.student
        subjects = Subject.query.filter_by(grade=student.grade).order_by(Subject.name_en).all()
        rows = []
        for subject in subjects:
            score = quarter_subject_score(student, subject, year, qtr)
            rows.append({"subject": subject, "score": score})
        complete = [r["score"] for r in rows if r["score"] is not None]
        average = round(sum(complete)/len(complete), 2) if complete and len(complete)==len(rows) else None
        children.append({"student": student, "rows": rows, "average": average})
    return page("""<h2>Parent Portal / የወላጅ መመልከቻ</h2>
    <div class="card"><form method="get"><div class="row"><div><label>Academic year E.C.</label><input name="year" value="{{year}}"></div><div><label>Quarter</label><select name="quarter">{% for n in range(1,5) %}<option value="{{n}}" {% if n==qtr %}selected{% endif %}>Quarter {{n}}</option>{% endfor %}</select></div></div><button>View results</button></form></div>
    {% if not children %}<div class="notice">የተመደበ ተማሪ የለም። እባክዎ ትምህርት ቤቱን ያነጋግሩ።</div>{% endif %}
    {% for child in children %}<div class="card"><h3>{{child.student.first_name}} {{child.student.father_name}} {{child.student.grand_name}}</h3><p><b>ID:</b> {{child.student.student_code}} · <b>Grade:</b> {{child.student.grade}} / {{child.student.section}}</p>
    <table><tr><th>Subject</th><th>Mark / 100</th><th>Grade</th></tr>{% for r in child.rows %}<tr><td>{{r.subject.name_en}}{% if r.subject.name_am %} / {{r.subject.name_am}}{% endif %}</td><td>{{'%.2f'|format(r.score) if r.score is not none else 'Incomplete'}}</td><td>{{letter(r.score) if r.score is not none else '—'}}</td></tr>{% endfor %}</table>
    <h3>Quarter Average: {{'%.2f'|format(child.average) if child.average is not none else 'Incomplete'}}</h3></div>{% endfor %}""", year=year, qtr=qtr, children=children, letter=letter_grade)


@app.route("/class-summary")
@roles_required("admin", "registrar", "teacher")
def class_summary():
    year = request.args.get("year", "2019").strip()
    grade = request.args.get("grade", "Grade 1")
    section = request.args.get("section", "")
    qtr = request.args.get("quarter", "1")
    try: qtr = int(qtr)
    except ValueError: qtr = 1
    if qtr not in (1,2,3,4): qtr = 1
    grades = ["KG"] + [f"Grade {i}" for i in range(1,9)]
    if grade not in grades: grade = "Grade 1"
    sq = Student.query.filter_by(active=True, grade=grade)
    if section: sq = sq.filter_by(section=section)
    pupils = sq.order_by(Student.section, Student.first_name).all()
    subjects = Subject.query.filter_by(grade=grade).order_by(Subject.name_en).all()
    summaries=[]
    for pupil in pupils:
        vals=[quarter_subject_score(pupil, sub, year, qtr) for sub in subjects]
        complete=[v for v in vals if v is not None]
        avg=round(sum(complete)/len(complete),2) if vals and len(complete)==len(vals) else None
        summaries.append({"student":pupil,"average":avg,"status":"Complete" if avg is not None else "Incomplete"})
    valid=[x["average"] for x in summaries if x["average"] is not None]
    class_avg=round(sum(valid)/len(valid),2) if valid else None
    sections=[x[0] for x in db.session.query(Student.section).filter_by(active=True,grade=grade).distinct().order_by(Student.section).all()]
    return page("""<h2>Class Summary / የክፍል ውጤት ማጠቃለያ</h2><div class="card"><form method="get"><div class="row"><div><label>Year</label><input name="year" value="{{year}}"></div><div><label>Grade</label><select name="grade">{% for g in grades %}<option {% if g==grade %}selected{% endif %}>{{g}}</option>{% endfor %}</select></div><div><label>Section</label><select name="section"><option value="">All sections</option>{% for s in sections %}<option {% if s==section %}selected{% endif %}>{{s}}</option>{% endfor %}</select></div><div><label>Quarter</label><select name="quarter">{% for n in range(1,5) %}<option value="{{n}}" {% if n==qtr %}selected{% endif %}>Q{{n}}</option>{% endfor %}</select></div></div><button>Generate</button></form></div>
    <div class="grid"><div class="card">Students<div class="stat">{{summaries|length}}</div></div><div class="card">Class average<div class="stat">{{'%.2f'|format(class_avg) if class_avg is not none else '—'}}</div></div><div class="card">Complete results<div class="stat">{{valid_count}}</div></div><div class="card">Incomplete<div class="stat">{{summaries|length-valid_count}}</div></div></div>
    <div class="card"><button class="no-print" onclick="window.print()">Print summary</button><table><tr><th>No.</th><th>Student ID</th><th>Name</th><th>Section</th><th>Average</th><th>Status</th></tr>{% for x in summaries %}<tr><td>{{loop.index}}</td><td>{{x.student.student_code}}</td><td>{{x.student.first_name}} {{x.student.father_name}}</td><td>{{x.student.section}}</td><td>{{'%.2f'|format(x.average) if x.average is not none else '—'}}</td><td>{{x.status}}</td></tr>{% endfor %}</table></div>""", year=year, grade=grade, section=section, qtr=qtr, grades=grades, sections=sections, summaries=summaries, class_avg=class_avg, valid_count=len(valid))


@app.route("/reports/bulk")
@roles_required("admin", "registrar", "teacher")
def bulk_reports():
    year=request.args.get("year","2019").strip()
    grade=request.args.get("grade","Grade 1")
    section=request.args.get("section","")
    qtr=request.args.get("quarter","1")
    try: qtr=int(qtr)
    except ValueError: qtr=1
    if qtr not in (1,2,3,4): qtr=1
    grades=["KG"]+[f"Grade {i}" for i in range(1,9)]
    if grade not in grades: grade="Grade 1"
    sq=Student.query.filter_by(active=True,grade=grade)
    if section: sq=sq.filter_by(section=section)
    pupils=sq.order_by(Student.section,Student.first_name).limit(300).all()
    cards=[]
    for pupil in pupils:
        rows=[]
        for subject in Subject.query.filter_by(grade=pupil.grade).order_by(Subject.name_en).all():
            rows.append((subject,quarter_subject_score(pupil,subject,year,qtr)))
        vals=[v for _,v in rows if v is not None]
        avg=round(sum(vals)/len(vals),2) if rows and len(vals)==len(rows) else None
        cards.append({"student":pupil,"rows":rows,"average":avg})
    sections=[x[0] for x in db.session.query(Student.section).filter_by(active=True,grade=grade).distinct().order_by(Student.section).all()]
    return page("""<h2>Bulk Report Cards / የብዙ ተማሪዎች ሪፖርት</h2><div class="card no-print"><form method="get"><div class="row"><div><label>Year</label><input name="year" value="{{year}}"></div><div><label>Grade</label><select name="grade">{% for g in grades %}<option {% if g==grade %}selected{% endif %}>{{g}}</option>{% endfor %}</select></div><div><label>Section</label><select name="section"><option value="">All sections</option>{% for s in sections %}<option {% if s==section %}selected{% endif %}>{{s}}</option>{% endfor %}</select></div><div><label>Quarter</label><select name="quarter">{% for n in range(1,5) %}<option value="{{n}}" {% if n==qtr %}selected{% endif %}>Q{{n}}</option>{% endfor %}</select></div></div><button>Load report cards</button></form><p>እስከ 300 ተማሪዎች ይጫናሉ። Print በመጫን ወደ PDF ማስቀመጥ ይችላሉ።</p><button onclick="window.print()">Print / Save all as PDF</button></div>
    {% for card in cards %}<div class="report" style="margin:18px 0;page-break-after:always"><h1>STEP UP ACADEMY</h1><h2>STUDENT REPORT CARD</h2><h3>{{year}} E.C. · Quarter {{qtr}}</h3><p style="text-align:left"><b>Student:</b> {{card.student.first_name}} {{card.student.father_name}} {{card.student.grand_name}}<br><b>ID:</b> {{card.student.student_code}}<br><b>Grade / Section:</b> {{card.student.grade}} / {{card.student.section}}</p><table><tr><th>Subject</th><th>Mark / 100</th><th>Letter</th></tr>{% for subject,score in card.rows %}<tr><td>{{subject.name_en}}{% if subject.name_am %} / {{subject.name_am}}{% endif %}</td><td>{{'%.2f'|format(score) if score is not none else 'Incomplete'}}</td><td>{{letter(score) if score is not none else '—'}}</td></tr>{% endfor %}</table><h3>Average: {{'%.2f'|format(card.average) if card.average is not none else 'Incomplete'}}</h3><p style="text-align:left">Teacher's comment: __________________________________</p><div style="display:flex;justify-content:space-between;margin-top:35px"><span>Class Teacher: __________</span><span>Principal: __________</span></div><p>STEP UP ACADEMY · LEARN TODAY, LEAD TOMORROW</p></div>{% endfor %}""", year=year,grade=grade,section=section,qtr=qtr,grades=grades,sections=sections,cards=cards,letter=letter_grade)


@app.cli.command("init-db")
def init_db():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        u=User(username="admin",full_name="System Administrator",role="admin")
        u.set_password(os.environ.get("INITIAL_ADMIN_PASSWORD","StepUp@123")); db.session.add(u); db.session.commit()
    print("Database initialized. Initial login: admin / StepUp@123")

if __name__=="__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            u=User(username="admin",full_name="System Administrator",role="admin"); u.set_password("StepUp@123"); db.session.add(u); db.session.commit()
    app.run(debug=True)
