# Security Changes & Improvements

## Fixes (ثغرات تم حلها)

| # | الثغرة | الحل |
|---|--------|------|
| 1 | OTP مخزّن نص عادي | SHA-256 hash فقط يُخزّن في DB |
| 2 | OTP Brute-Force | `@ratelimit(5/min per IP)` على `verifyotp` |
| 3 | Email Enumeration | نفس الرسالة دايماً بغض النظر عن الإيميل |
| 4 | `random` غير آمن | استبداله بـ `secrets.randbelow` |
| 5 | Profile image بدون فحص | Extension + Size + Magic bytes |
| 6 | Magic bytes للملفات | فحص أول 8 bytes لكل ملف مرفوع |
| 7 | ClamAV Fail-Open | Fail-Closed عند `CLAMAV_REQUIRED=True` |
| 8 | Admin يرفع ملفات | Admin يُوجَّه للـ dashboard عند لوجين |
| 9 | `@login_required` ناقص | أُضيف على `password_change` |

## Admin Features الجديدة

| الميزة | URL |
|--------|-----|
| Dashboard | `/monitoring/dashboard/` |
| كل الملفات + موافقة | `/files/admin/all/` |
| Approve ملف | `/files/admin/approve/<id>/` |
| Reject ملف | `/files/admin/reject/<id>/` |
| حذف أي ملف | `/files/admin/delete/<id>/` |
| Verify Blockchain | `/files/admin/blockchain/` |
| قائمة المستخدمين | `/monitoring/users/` |
| تفعيل/تعطيل حساب | `/monitoring/users/<id>/toggle/` |
| حذف حساب | `/monitoring/users/<id>/delete/` |
| سجل النشاط | `/monitoring/activity/` |

## File Approval Workflow

بعد الرفع: status = `pending` → Admin يوافق (`approved`) أو يرفض (`rejected`)
المستخدم يقدر يحمّل الملف فقط بعد الموافقة.

## تشغيل المشروع

```bash
# 1. تفعيل البيئة الافتراضية
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/Mac

# 2. تطبيق الـ migrations
python manage.py makemigrations
python manage.py migrate

# 3. تشغيل السيرفر
python manage.py runserver
```
