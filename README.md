# شو عندي اليوم

برنامج صغير على GitHub Actions: كل صبح بيجيب تقويم Moodle، بيبني صفحة بمواعيد اليوم والأسبوع، وبيبعت إشعار على الجوال.

## الإعداد (من الجوال)

1. **الأسرار (Secrets):** من الريبو → Settings → Secrets and variables → Actions → New repository secret
   - `CALENDAR_URL` = رابط تقويم Moodle
   - `NTFY_TOPIC` = اسم طويل وعشوائي تختاره (مثلاً `study-x7k29fq-ahmad`)، هو اللي بيحمي إشعاراتك
2. **تطبيق ntfy:** نزّله من Google Play أو F-Droid، واشترك بنفس اسم الـ topic.
3. **تفعيل الصفحة:** Settings → Pages → Source = **GitHub Actions**
4. **أول تشغيل:** تبويب Actions → Daily study brief → Run workflow
5. **جدول المحاضرات (اختياري):** عدّل `schedule.json` (أيام: sun mon tue wed thu fri sat)

## ملاحظات

- لا تحط رابط التقويم أو أي كلمة سر داخل أي ملف بالريبو. بس بالـ Secrets.
- صفحة GitHub Pages بتكون علنية لمين ما معه الرابط (فيها عناوين ومواعيد، مش بيانات دخول).
- GitHub بيوقف المهام المجدولة بالريبو العلني بعد 60 يوم بدون نشاط. إذا وقفت، شغّلها يدوياً من تبويب Actions.
- وقت الإشعار الافتراضي 7 الصبح. تغييره: متغير `NOTIFY_HOUR` بالـ workflow.
