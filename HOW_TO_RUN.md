# تشغيل المشروع — SecuStore

## الخطوات الأساسية

```bash
# 1) تفعيل البيئة الافتراضية
source .venv/bin/activate              # Linux/Mac
.venv\Scripts\activate                 # Windows

# 2) تثبيت المتطلبات
pip install -r requirements.txt

# 3) تطبيق الـ migrations
python manage.py makemigrations
python manage.py migrate

# 4) إنشاء سوبر يوزر للأدمن
python manage.py createsuperuser

# 5) تشغيل السيرفر
python manage.py runserver
```

---

## ✨ التحديثات الجديدة في هذه النسخة

### 1. Signup — تأكيد الإيميل أولاً (3 خطوات)

```
Step 1: /Accounts/signup/                  →  المستخدم يدخل الإيميل فقط
Step 2: /Accounts/signup/verify_otp/       →  يدخل الـ OTP اللي وصله
Step 3: /Accounts/signup/details/          →  بعد التحقق، يكمل الاسم + اليوزرنيم + الباسوورد
```

**التغيير:** قبل ما يعبي كامل الفورم، يتأكد إيميله شغّال. لو الإيميل غلط، يكتشف فوراً بدون ما يضيع وقته بتعبئة باقي الحقول.

### 2. Auto-approve للملفات الصغيرة

- الملفات ≤ **10 MB** → تتقبل تلقائياً، جاهزة للتحميل فوراً.
- الملفات > **10 MB** → تحتاج موافقة الأدمن (Status = Pending).
- صفحة الرفع تعرض للمستخدم مقدّماً هل ملفه راح يتقبل تلقائياً أو يحتاج مراجعة.

**لتغيير الحد:**
```bash
# في .env أو متغيرات النظام
AUTO_APPROVE_SIZE_MB=5     # 5 MB instead of 10
```

> ⚠️ **مهم:** قيمة الـ JS في `templates/pages/home.html` (المتغير `AUTO_APPROVE_BYTES`) لازم تتطابق مع `AUTO_APPROVE_SIZE_MB`. إذا غيّرت الحد، عدّل الـ JS بنفس القيمة.

### 3. Dark Mode — إصلاحات شاملة

تم إعادة تصميم كل التمبليتس الـ auth و الـ home لاستخدام Design Tokens (`var(--text)`, `var(--surface)`, ...) بدل الألوان المثبتة. كمان أضفنا في `base.html` overrides للـ Bootstrap utilities (`text-dark`, `text-muted`, modals, alerts) عشان تشتغل تلقائياً في الوضع المظلم.

التمبليتس اللي تم إعادة تصميمها:
- `pages/signup.html` (Step 1)
- `pages/verify_signup_otp.html` (Step 2)
- `pages/signup_details.html` (Step 3 — جديد)
- `pages/verify_otp.html` (login OTP)
- `pages/password_change.html`
- `pages/password_change_verify_otp.html`
- `pages/password_changed.html`
- `pages/intro.html` (الصفحة الرئيسية للمستخدم — تصميم جديد كامل)
- `pages/home.html` (صفحة الرفع — تصميم جديد)

### 4. صفحة Home (`intro.html`) — تصميم جديد

التصميم القديم كان فيه `color: #000000` يختفي في الوضع المظلم. الجديد:
- **Hero section** بـ gradient وأزرار CTA (Upload / Browse Files).
- **Stats grid**: عدد الملفات، الستوريج المستخدم، نوع التشفير، Audit Trail.
- **Feature cards** بـ 4 ميزات أمنية أساسية.
- **Quick action bar** لزر الرفع السريع.
- يشتغل تماماً في Light + Dark Mode.

---

## ⚙️ إعدادات البيئة المهمة

```bash
# في ملف .env
EMAIL_HOST_USER=your_gmail@gmail.com
EMAIL_HOST_PASSWORD=app_specific_password_16_chars
SITE_URL=http://127.0.0.1:8000
AUTO_APPROVE_SIZE_MB=10              # اختياري — الافتراضي 10 MB
EXPIRATION_WARNING_DAYS=3            # اختياري — الافتراضي 3 أيام
AUTO_EXTENSION_DAYS=10               # اختياري — الافتراضي 10 أيام
USER_STORAGE_QUOTA_MB=500            # اختياري — الافتراضي 500 MB
```

---

## 🧪 سيناريوهات اختبار سريعة

### Signup الجديد (3 خطوات)
1. روح على `/Accounts/signup/` — اكتب إيميلك بس → اضغط Send Verification Code.
2. شيك إيميلك → ادخل الكود الـ 6 أرقام → Verify Email.
3. الآن عبّي الاسم + اليوزرنيم + الباسوورد → Create Account.
4. روح للوغين.

### Upload — auto-approve
1. ارفع ملف **5 MB** → يطلع لك مباشرة كـ "Approved" بدون انتظار.
2. ارفع ملف **15 MB** → يطلع كـ "Pending" بانتظار الأدمن.

### Dark Mode
1. اضغط على أيقونة القمر/الشمس فوق يمين.
2. تأكد إنه كل النصوص بقت ظاهرة في الوضع الجديد — مفيش نص أسود على خلفية مظلمة.

---

## 🔄 سير حياة الملف الكامل (Expiration — موجود مسبقاً)

1. **قبل التاريخ بـ 3 أيام** → إيميل warning للمستخدم مع رابط تعديل.
2. **وصل التاريخ ولا في تمديد يدوي** → النظام يمدد +10 أيام تلقائياً + إيميل.
3. **وصل التاريخ المُمدّد** → حذف نهائي + إيميل تأكيد.

تشغيل دوري (cron / scheduled task):
```bash
0 3 * * * cd /path/to/project && /path/to/venv/bin/python manage.py delete_expired
```
