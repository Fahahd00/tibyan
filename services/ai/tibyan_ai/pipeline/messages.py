"""User-facing texts in every interface language. Kept in one place for the governance lead to review.

Each payload object keeps its Arabic and English texts (`message_ar` / `message_en`) and adds `message`: the text in
the language of the question, which is what is shown and spoken."""

from __future__ import annotations

import re

REASONS: dict[str, dict[str, str]] = {
    "no_source": {
        "ar": "لم نجد مرجعًا كافيًا للإجابة. لم يُعثر على نص في المصادر المعتمدة يتناول هذا السؤال.",
        "en": "We could not find a sufficient reference. No text in the approved sources addresses this question.",
        "ur": "ہمیں جواب کے لیے کافی حوالہ نہیں ملا۔ منظور شدہ مصادر میں اس سوال سے متعلق کوئی متن نہیں ملا۔",
        "hi": "उत्तर के लिए पर्याप्त संदर्भ नहीं मिला। स्वीकृत स्रोतों में इस प्रश्न से संबंधित कोई पाठ नहीं मिला।",
        "tr": "Cevap için yeterli bir kaynak bulamadık. Onaylı kaynaklarda bu soruyu ele alan bir metin bulunamadı.",
        "id": "Kami tidak menemukan rujukan yang memadai untuk menjawab. Tidak ada teks dalam sumber yang disetujui yang membahas pertanyaan ini.",
        "bn": "উত্তরের জন্য পর্যাপ্ত সূত্র পাইনি। অনুমোদিত উৎসে এই প্রশ্ন সম্পর্কিত কোনো পাঠ পাওয়া যায়নি।",
        "ms": "Kami tidak menemui rujukan yang mencukupi untuk menjawab. Tiada teks dalam sumber yang diluluskan yang membincangkan soalan ini.",
        "uz": "Javob uchun yetarli manba topmadik. Tasdiqlangan manbalarda bu savolga oid matn topilmadi.",
        "kk": "Жауап беру үшін жеткілікті дереккөз таппадық. Бекітілген дереккөздерде бұл сұраққа қатысты мәтін табылмады.",
        "ha": "Ba mu sami isasshen tushe don amsawa ba. Ba a sami wani rubutu a majiyoyin da aka amince da ya shafi wannan tambayar ba.",
    },
    "weak_evidence": {
        "ar": "لم نجد مرجعًا كافيًا للإجابة. النصوص الأقرب في المصادر المعتمدة لا تجيب عن السؤال نفسه إجابة مباشرة.",
        "en": "We could not find a sufficient reference. The closest texts in the approved sources do not directly answer this question.",
        "ur": "ہمیں جواب کے لیے کافی حوالہ نہیں ملا۔ منظور شدہ مصادر کے قریب ترین متون اس سوال کا براہِ راست جواب نہیں دیتے۔",
        "hi": "उत्तर के लिए पर्याप्त संदर्भ नहीं मिला। स्वीकृत स्रोतों के निकटतम पाठ इस प्रश्न का सीधा उत्तर नहीं देते।",
        "tr": "Cevap için yeterli bir kaynak bulamadık. Onaylı kaynaklardaki en yakın metinler bu soruya doğrudan cevap vermiyor.",
        "id": "Kami tidak menemukan rujukan yang memadai untuk menjawab. Teks terdekat dalam sumber yang disetujui tidak menjawab pertanyaan ini secara langsung.",
        "bn": "উত্তরের জন্য পর্যাপ্ত সূত্র পাইনি। অনুমোদিত উৎসের নিকটতম পাঠগুলো এই প্রশ্নের সরাসরি উত্তর দেয় না।",
        "ms": "Kami tidak menemui rujukan yang mencukupi untuk menjawab. Teks terdekat dalam sumber yang diluluskan tidak menjawab soalan ini secara langsung.",
        "uz": "Javob uchun yetarli manba topmadik. Tasdiqlangan manbalardagi eng yaqin matnlar bu savolga bevosita javob bermaydi.",
        "kk": "Жауап беру үшін жеткілікті дереккөз таппадық. Бекітілген дереккөздердегі ең жақын мәтіндер бұл сұраққа тікелей жауап бермейді.",
        "ha": "Ba mu sami isasshen tushe don amsawa ba. Rubutun da suka fi kusa a majiyoyin da aka amince ba su amsa wannan tambayar kai tsaye ba.",
    },
    "verification_failed": {
        "ar": "لم نجد مرجعًا كافيًا للإجابة. تعذّر التحقق من أن الإجابة مدعومة بنص المصدر حرفيًا، فامتنعنا بدل عرض إجابة غير موثقة.",
        "en": "We could not find a sufficient reference. The answer could not be verified against the source text, so we abstained rather than show an unverified answer.",
        "ur": "ہمیں جواب کے لیے کافی حوالہ نہیں ملا۔ جواب کی مصدر کے متن سے تصدیق نہ ہو سکی، اس لیے غیر مصدقہ جواب دکھانے کے بجائے ہم نے توقف کیا۔",
        "hi": "उत्तर के लिए पर्याप्त संदर्भ नहीं मिला। उत्तर की स्रोत के पाठ से पुष्टि नहीं हो सकी, इसलिए अपुष्ट उत्तर दिखाने के बजाय हमने उत्तर नहीं दिया।",
        "tr": "Cevap için yeterli bir kaynak bulamadık. Cevap kaynak metinle doğrulanamadı; bu yüzden doğrulanmamış bir cevap göstermek yerine cevap vermedik.",
        "id": "Kami tidak menemukan rujukan yang memadai untuk menjawab. Jawaban tidak dapat diverifikasi dengan teks sumber, sehingga kami tidak menampilkan jawaban yang belum terverifikasi.",
        "bn": "উত্তরের জন্য পর্যাপ্ত সূত্র পাইনি। উত্তরটি উৎসের পাঠের সঙ্গে যাচাই করা যায়নি, তাই অযাচাইকৃত উত্তর দেখানোর বদলে আমরা বিরত থেকেছি।",
        "ms": "Kami tidak menemui rujukan yang mencukupi untuk menjawab. Jawapan tidak dapat disahkan dengan teks sumber, jadi kami tidak memaparkan jawapan yang belum disahkan.",
        "uz": "Javob uchun yetarli manba topmadik. Javobni manba matni bilan tasdiqlab bo‘lmadi, shuning uchun tasdiqlanmagan javobni ko‘rsatmadik.",
        "kk": "Жауап беру үшін жеткілікті дереккөз таппадық. Жауапты дереккөз мәтінімен растау мүмкін болмады, сондықтан расталмаған жауапты көрсетпедік.",
        "ha": "Ba mu sami isasshen tushe don amsawa ba. Ba a iya tantance amsar da rubutun tushe ba, don haka ba mu nuna amsar da ba a tantance ba.",
    },
    "unresolved_conflict": {
        "ar": "لم نجد مرجعًا كافيًا للإجابة. ظهر في المصادر ما يبدو تعارضًا في هذه المسألة لا نملك صلاحية الترجيح فيه.",
        "en": "We could not find a sufficient reference. The sources appear to differ on this matter and we are not authorized to weigh between them.",
        "ur": "ہمیں جواب کے لیے کافی حوالہ نہیں ملا۔ اس مسئلے میں مصادر کے درمیان اختلاف نظر آتا ہے، اور ہمیں ان میں ترجیح دینے کا اختیار نہیں۔",
        "hi": "उत्तर के लिए पर्याप्त संदर्भ नहीं मिला। इस विषय पर स्रोतों में मतभेद प्रतीत होता है, और हमें उनमें से किसी को प्राथमिकता देने का अधिकार नहीं है।",
        "tr": "Cevap için yeterli bir kaynak bulamadık. Kaynaklar bu meselede farklı görüşte görünüyor ve aralarında tercih yapma yetkimiz yok.",
        "id": "Kami tidak menemukan rujukan yang memadai untuk menjawab. Sumber-sumber tampak berbeda pendapat dalam masalah ini dan kami tidak berwenang menguatkan salah satunya.",
        "bn": "উত্তরের জন্য পর্যাপ্ত সূত্র পাইনি। এই বিষয়ে উৎসগুলোর মধ্যে মতভেদ দেখা যাচ্ছে, এবং কোনোটিকে অগ্রাধিকার দেওয়ার এখতিয়ার আমাদের নেই।",
        "ms": "Kami tidak menemui rujukan yang mencukupi untuk menjawab. Sumber-sumber kelihatan berbeza pendapat dalam masalah ini dan kami tidak berwenang mentarjihkan salah satunya.",
        "uz": "Javob uchun yetarli manba topmadik. Bu masalada manbalar turlicha fikrda ko‘rinadi va ularning birini ustun qo‘yishga vakolatimiz yo‘q.",
        "kk": "Жауап беру үшін жеткілікті дереккөз таппадық. Бұл мәселеде дереккөздердің пікірі әртүрлі сияқты, ал біздің олардың бірін басым деп тануға құзыретіміз жоқ.",
        "ha": "Ba mu sami isasshen tushe don amsawa ba. Da alama majiyoyi sun saɓa a kan wannan mas'ala, kuma ba mu da ikon fifita ɗaya daga cikinsu.",
    },
    "out_of_scope": {
        "ar": "تِبْيان يجيب عن الأسئلة الشرعية من مصادر معتمدة فقط. اكتب سؤالك الشرعي وسنبحث لك عن مرجعه.",
        "en": "Tibyan answers Islamic-knowledge questions from approved sources only. Please ask a religious question.",
        "ur": "تبیان صرف منظور شدہ مصادر سے شرعی سوالات کے جواب دیتا ہے۔ اپنا شرعی سوال لکھیں، ہم اس کا حوالہ تلاش کریں گے۔",
        "hi": "तिबयान केवल स्वीकृत स्रोतों से धार्मिक प्रश्नों के उत्तर देता है। अपना धार्मिक प्रश्न लिखें, हम उसका संदर्भ खोजेंगे।",
        "tr": "Tibyan yalnızca onaylı kaynaklardan dinî soruları cevaplar. Dinî sorunuzu yazın, kaynağını bulalım.",
        "id": "Tibyan hanya menjawab pertanyaan keislaman dari sumber yang disetujui. Tuliskan pertanyaan agama Anda, kami akan mencarikan rujukannya.",
        "bn": "তিবইয়ান কেবল অনুমোদিত উৎস থেকে ধর্মীয় প্রশ্নের উত্তর দেয়। আপনার ধর্মীয় প্রশ্ন লিখুন, আমরা তার সূত্র খুঁজে দেব।",
        "ms": "Tibyan hanya menjawab soalan keislaman daripada sumber yang diluluskan. Tuliskan soalan agama anda, kami akan mencarikan rujukannya.",
        "uz": "Tibyan faqat tasdiqlangan manbalardan diniy savollarga javob beradi. Diniy savolingizni yozing, uning manbasini izlab topamiz.",
        "kk": "Tibyan тек бекітілген дереккөздерден діни сұрақтарға жауап береді. Діни сұрағыңызды жазыңыз, оның дереккөзін іздеп табамыз.",
        "ha": "Tibyan yana amsa tambayoyin addini ne kawai daga majiyoyin da aka amince. Rubuta tambayarka ta addini, za mu nemo maka tushenta.",
    },
    "personal_case": {
        "ar": "سؤالك يتعلق بحالة شخصية تحتاج إلى معرفة تفاصيلها والحكم فيها من جهة مختصة، لذلك لا نقدّم فيها فتوى.",
        "en": "Your question concerns a personal case whose details must be heard and judged by a qualified authority, so we do not issue a ruling.",
        "ur": "آپ کا سوال ایک ذاتی معاملے سے متعلق ہے جس کی تفصیلات جان کر کسی مجاز ادارے کو فیصلہ کرنا چاہیے، اس لیے ہم اس میں فتویٰ نہیں دیتے۔",
        "hi": "आपका प्रश्न एक व्यक्तिगत मामले से संबंधित है, जिसके विवरण सुनकर किसी सक्षम संस्था को निर्णय देना चाहिए, इसलिए हम इसमें फ़तवा नहीं देते।",
        "tr": "Sorunuz, ayrıntılarının yetkili bir merci tarafından dinlenip hükme bağlanması gereken kişisel bir durumla ilgili; bu yüzden bu konuda fetva vermiyoruz.",
        "id": "Pertanyaan Anda menyangkut kasus pribadi yang rinciannya harus didengar dan diputuskan oleh pihak yang berwenang, sehingga kami tidak memberikan fatwa.",
        "bn": "আপনার প্রশ্নটি একটি ব্যক্তিগত বিষয়ে, যার বিস্তারিত শুনে কোনো উপযুক্ত কর্তৃপক্ষের সিদ্ধান্ত দেওয়া উচিত; তাই আমরা এতে ফতোয়া দিই না।",
        "ms": "Soalan anda berkaitan kes peribadi yang butirannya perlu didengar dan diputuskan oleh pihak berkuasa, jadi kami tidak memberikan fatwa.",
        "uz": "Savolingiz shaxsiy holatga oid bo‘lib, uning tafsilotlarini vakolatli idora eshitib hukm qilishi kerak, shuning uchun bu borada fatvo bermaymiz.",
        "kk": "Сұрағыңыз жеке жағдайға қатысты, оның мән-жайын құзырлы орган тыңдап, шешім шығаруы керек, сондықтан бұл туралы пәтуа бермейміз.",
        "ha": "Tambayarka ta shafi wani al'amari na kai wanda ya kamata hukuma mai iko ta saurari bayanansa ta yanke hukunci, don haka ba ma ba da fatawa a kai.",
    },
    "high_risk": {
        "ar": "هذه مسألة عالية الخطورة لا يُجاب عنها آليًا. يُرجى الرجوع إلى جهة رسمية مختصة. وإن كنت في خطر أو تفكر في إيذاء نفسك أو غيرك فتواصل فورًا مع خدمات الطوارئ في بلدك أو شخص تثق به.",
        "en": "This is a high-risk matter that is not answered automatically. Please contact an official authority. If you or someone else is in danger, contact your local emergency services or someone you trust immediately.",
        "ur": "یہ ایک انتہائی حساس معاملہ ہے جس کا خودکار جواب نہیں دیا جاتا۔ براہِ کرم کسی سرکاری مجاز ادارے سے رجوع کریں۔ اگر آپ یا کوئی اور خطرے میں ہے تو فوراً اپنے ملک کی ہنگامی خدمات یا کسی قابلِ اعتماد شخص سے رابطہ کریں۔",
        "hi": "यह एक अत्यंत गंभीर मामला है जिसका स्वचालित उत्तर नहीं दिया जाता। कृपया किसी आधिकारिक सक्षम संस्था से संपर्क करें। यदि आप या कोई और ख़तरे में है, तो तुरंत अपने देश की आपातकालीन सेवाओं या किसी भरोसेमंद व्यक्ति से संपर्क करें।",
        "tr": "Bu, otomatik olarak cevaplanmayan yüksek riskli bir konudur. Lütfen yetkili resmî bir mercie başvurun. Siz veya bir başkası tehlikedeyse hemen ülkenizdeki acil yardım hizmetlerine ya da güvendiğiniz birine ulaşın.",
        "id": "Ini adalah masalah berisiko tinggi yang tidak dijawab secara otomatis. Silakan hubungi lembaga resmi yang berwenang. Jika Anda atau orang lain dalam bahaya, segera hubungi layanan darurat di negara Anda atau orang yang Anda percayai.",
        "bn": "এটি একটি অত্যন্ত ঝুঁকিপূর্ণ বিষয়, যার স্বয়ংক্রিয় উত্তর দেওয়া হয় না। অনুগ্রহ করে কোনো সরকারি উপযুক্ত কর্তৃপক্ষের সঙ্গে যোগাযোগ করুন। আপনি বা অন্য কেউ বিপদে থাকলে অবিলম্বে আপনার দেশের জরুরি সেবা বা বিশ্বস্ত কারও সঙ্গে যোগাযোগ করুন।",
        "ms": "Ini masalah berisiko tinggi yang tidak dijawab secara automatik. Sila hubungi badan rasmi yang berkuasa. Jika anda atau orang lain dalam bahaya, segera hubungi perkhidmatan kecemasan di negara anda atau orang yang anda percayai.",
        "uz": "Bu avtomatik javob berilmaydigan o‘ta xavfli masala. Iltimos, vakolatli rasmiy idoraga murojaat qiling. Agar siz yoki boshqa birov xavf ostida bo‘lsa, darhol mamlakatingizdagi favqulodda xizmatlarga yoki ishonchli odamga murojaat qiling.",
        "kk": "Бұл автоматты түрде жауап берілмейтін аса қауіпті мәселе. Құзырлы ресми органға жүгініңіз. Егер сіз немесе басқа біреу қауіпте болса, дереу еліңіздегі төтенше қызметтерге немесе сенімді адамға хабарласыңыз.",
        "ha": "Wannan mas'ala ce mai haɗari sosai da ba a amsa ta ta atomatik. Don Allah ka tuntuɓi hukuma mai iko ta gwamnati. Idan kai ko wani yana cikin haɗari, nan take ka tuntuɓi hukumomin agajin gaggawa na ƙasarka ko wani amintacce.",
    },
    "provider_error": {
        "ar": "لم نجد مرجعًا كافيًا للإجابة. تعذّر إكمال التحقق من الإجابة بسبب خطأ تقني، فامتنعنا احتياطًا.",
        "en": "We could not find a sufficient reference. Verification could not be completed due to a technical error, so we abstained as a precaution.",
        "ur": "ہمیں جواب کے لیے کافی حوالہ نہیں ملا۔ تکنیکی خرابی کی وجہ سے جواب کی تصدیق مکمل نہ ہو سکی، اس لیے احتیاطاً ہم نے توقف کیا۔",
        "hi": "उत्तर के लिए पर्याप्त संदर्भ नहीं मिला। तकनीकी त्रुटि के कारण उत्तर की पुष्टि पूरी नहीं हो सकी, इसलिए सावधानी के तौर पर हमने उत्तर नहीं दिया।",
        "tr": "Cevap için yeterli bir kaynak bulamadık. Teknik bir hata nedeniyle doğrulama tamamlanamadı; bu yüzden tedbiren cevap vermedik.",
        "id": "Kami tidak menemukan rujukan yang memadai untuk menjawab. Verifikasi tidak dapat diselesaikan karena kesalahan teknis, sehingga kami tidak menjawab sebagai langkah kehati-hatian.",
        "bn": "উত্তরের জন্য পর্যাপ্ত সূত্র পাইনি। প্রযুক্তিগত ত্রুটির কারণে যাচাই সম্পন্ন করা যায়নি, তাই সতর্কতা হিসেবে আমরা উত্তর দিইনি।",
        "ms": "Kami tidak menemui rujukan yang mencukupi untuk menjawab. Pengesahan tidak dapat diselesaikan kerana ralat teknikal, jadi kami tidak menjawab sebagai langkah berhati-hati.",
        "uz": "Javob uchun yetarli manba topmadik. Texnik xato tufayli tekshiruv yakunlanmadi, shuning uchun ehtiyot yuzasidan javob bermadik.",
        "kk": "Жауап беру үшін жеткілікті дереккөз таппадық. Техникалық қателікке байланысты тексеру аяқталмады, сондықтан сақтық үшін жауап бермедік.",
        "ha": "Ba mu sami isasshen tushe don amsawa ba. Ba a iya kammala tantancewa ba saboda matsalar fasaha, don haka ba mu amsa ba don yin taka-tsantsan.",
    },
}

SENSITIVE_NOTICE = {
    "ar": "هذه معلومات عامة من المصادر المعتمدة. المسائل المتعلقة بـ{topics} تختلف أحكامها باختلاف تفاصيل كل حالة؛ فإن كانت لديك حالة خاصة فاعرضها على جهة مختصة.",
    "en": "This is general information from approved sources. Rulings on {topics} depend on the details of each case; if you have a specific case, please refer it to a qualified authority.",
    "ur": "یہ منظور شدہ مصادر سے عمومی معلومات ہیں۔ {topics} سے متعلق مسائل کے احکام ہر معاملے کی تفصیلات کے مطابق مختلف ہوتے ہیں؛ اگر آپ کا کوئی خاص معاملہ ہے تو اسے کسی مجاز ادارے کے سامنے پیش کریں۔",
    "hi": "यह स्वीकृत स्रोतों से सामान्य जानकारी है। {topics} से संबंधित मामलों के नियम हर मामले के विवरण के अनुसार बदलते हैं; यदि आपका कोई विशेष मामला है, तो उसे किसी सक्षम संस्था के सामने रखें।",
    "tr": "Bu, onaylı kaynaklardan genel bir bilgidir. {topics} ile ilgili hükümler her durumun ayrıntılarına göre değişir; size özel bir durum varsa bunu yetkili bir mercie danışın.",
    "id": "Ini adalah informasi umum dari sumber yang disetujui. Hukum terkait {topics} bergantung pada rincian setiap kasus; jika Anda memiliki kasus khusus, silakan ajukan kepada pihak yang berwenang.",
    "bn": "এটি অনুমোদিত উৎস থেকে সাধারণ তথ্য। {topics} সম্পর্কিত বিধান প্রতিটি বিষয়ের বিস্তারিত অনুযায়ী ভিন্ন হয়; আপনার কোনো বিশেষ বিষয় থাকলে তা উপযুক্ত কর্তৃপক্ষের কাছে উপস্থাপন করুন।",
    "ms": "Ini maklumat umum daripada sumber yang diluluskan. Hukum berkaitan {topics} bergantung pada butiran setiap kes; jika anda mempunyai kes khusus, sila rujuk kepada pihak berkuasa.",
    "uz": "Bu tasdiqlangan manbalardan olingan umumiy ma’lumot. {topics} bilan bog‘liq hukmlar har bir holatning tafsilotlariga qarab farq qiladi; sizda alohida holat bo‘lsa, uni vakolatli idoraga taqdim eting.",
    "kk": "Бұл бекітілген дереккөздердегі жалпы ақпарат. {topics} мәселелеріне қатысты үкімдер әр жағдайдың мән-жайына қарай өзгереді; егер сізде жеке жағдай болса, оны құзырлы органға ұсыныңыз.",
    "ha": "Wannan bayani ne na gaba ɗaya daga majiyoyin da aka amince. Hukunce-hukuncen da suka shafi {topics} suna bambanta gwargwadon bayanan kowane al'amari; idan kana da wani al'amari na musamman, ka gabatar da shi ga hukuma mai iko.",
}

ESCALATION_MESSAGE = {
    "ar": "يُنصح بعرض المسألة بتفاصيلها على جهة الإفتاء الرسمية أو الجهة المختصة. الجهات أدناه رسمية وتحققنا من مواقعها:",
    "en": "Please present your case with its details to the official fatwa authority or the competent body. The bodies below are official and their websites were verified:",
    "ur": "بہتر ہے کہ آپ اپنا مسئلہ تفصیل کے ساتھ سرکاری دار الافتاء یا متعلقہ مجاز ادارے کے سامنے پیش کریں۔ نیچے دیے گئے ادارے سرکاری ہیں اور ہم نے ان کی ویب سائٹس کی تصدیق کی ہے:",
    "hi": "कृपया अपना मामला पूरे विवरण के साथ आधिकारिक फ़तवा संस्था या संबंधित सक्षम संस्था के सामने रखें। नीचे दी गई संस्थाएँ आधिकारिक हैं और हमने उनकी वेबसाइटों की पुष्टि की है:",
    "tr": "Durumunuzu ayrıntılarıyla resmî fetva makamına veya yetkili kuruma sunmanız tavsiye edilir. Aşağıdaki kurumlar resmîdir ve internet siteleri tarafımızdan doğrulanmıştır:",
    "id": "Sebaiknya Anda menyampaikan kasus Anda beserta rinciannya kepada lembaga fatwa resmi atau pihak yang berwenang. Lembaga-lembaga berikut adalah lembaga resmi dan situs webnya telah kami verifikasi:",
    "bn": "আপনার বিষয়টি বিস্তারিতসহ সরকারি ফতোয়া প্রতিষ্ঠান বা সংশ্লিষ্ট উপযুক্ত কর্তৃপক্ষের কাছে উপস্থাপন করা উচিত। নিচের প্রতিষ্ঠানগুলো সরকারি এবং আমরা তাদের ওয়েবসাইট যাচাই করেছি:",
    "ms": "Sebaiknya anda kemukakan kes anda beserta butirannya kepada badan fatwa rasmi atau pihak berkuasa yang berkenaan. Badan-badan berikut adalah rasmi dan laman webnya telah kami sahkan:",
    "uz": "Masalangizni tafsilotlari bilan rasmiy fatvo idorasiga yoki tegishli vakolatli idoraga taqdim etishingiz tavsiya etiladi. Quyidagi idoralar rasmiy bo‘lib, ularning saytlari biz tomonimizdan tekshirilgan:",
    "kk": "Мәселеңізді мән-жайымен ресми пәтуа органына немесе тиісті құзырлы органға ұсынған жөн. Төмендегі органдар ресми және олардың сайттары біз тарапынан тексерілген:",
    "ha": "Ana ba da shawarar ka gabatar da mas'alarka tare da bayananta ga hukumar fatawa ta gwamnati ko hukuma mai iko da abin ya shafa. Hukumomin da ke ƙasa na gwamnati ne kuma mun tantance shafukansu:",
}

NO_VERIFIED_BODIES = {
    "ar": "لم نتحقق بعد من بيانات تواصل رسمية لهذه المسألة، لذلك لا نعرض أي رقم أو رابط غير موثق. يُرجى مراجعة جهة الإفتاء الرسمية في بلدك.",
    "en": "We have not yet verified official contact details for this matter, so we show no unverified numbers or links. Please consult the official fatwa authority in your country.",
    "ur": "ہم نے ابھی تک اس مسئلے کے لیے سرکاری رابطے کی معلومات کی تصدیق نہیں کی، اس لیے کوئی غیر مصدقہ نمبر یا لنک نہیں دکھاتے۔ براہِ کرم اپنے ملک کے سرکاری دار الافتاء سے رجوع کریں۔",
    "hi": "हमने अभी तक इस मामले के लिए आधिकारिक संपर्क विवरण की पुष्टि नहीं की है, इसलिए हम कोई अपुष्ट नंबर या लिंक नहीं दिखाते। कृपया अपने देश की आधिकारिक फ़तवा संस्था से संपर्क करें।",
    "tr": "Bu konu için resmî iletişim bilgilerini henüz doğrulamadık; bu yüzden doğrulanmamış hiçbir numara veya bağlantı göstermiyoruz. Lütfen ülkenizdeki resmî fetva makamına başvurun.",
    "id": "Kami belum memverifikasi kontak resmi untuk masalah ini, sehingga kami tidak menampilkan nomor atau tautan yang belum terverifikasi. Silakan hubungi lembaga fatwa resmi di negara Anda.",
    "bn": "এই বিষয়ের জন্য আমরা এখনো সরকারি যোগাযোগের তথ্য যাচাই করিনি, তাই কোনো অযাচাইকৃত নম্বর বা লিংক দেখাই না। অনুগ্রহ করে আপনার দেশের সরকারি ফতোয়া প্রতিষ্ঠানের সঙ্গে যোগাযোগ করুন।",
    "ms": "Kami belum mengesahkan maklumat hubungan rasmi untuk masalah ini, jadi kami tidak memaparkan sebarang nombor atau pautan yang belum disahkan. Sila rujuk badan fatwa rasmi di negara anda.",
    "uz": "Bu masala uchun rasmiy aloqa ma’lumotlarini hali tekshirmadik, shuning uchun tekshirilmagan raqam yoki havolani ko‘rsatmaymiz. Iltimos, mamlakatingizdagi rasmiy fatvo idorasiga murojaat qiling.",
    "kk": "Бұл мәселе бойынша ресми байланыс деректерін әлі тексерген жоқпыз, сондықтан тексерілмеген нөмір немесе сілтеме көрсетпейміз. Еліңіздегі ресми пәтуа органына жүгініңіз.",
    "ha": "Ba mu riga mun tantance bayanan tuntuɓar hukuma na wannan mas'ala ba, don haka ba ma nuna wata lamba ko mahaɗi da ba a tantance ba. Don Allah ka tuntuɓi hukumar fatawa ta gwamnati a ƙasarka.",
}

# Closes a reply to a general (non-religious) message.
INVITE = {
    "ar": "ما المسألة الشرعية التي تودّ السؤال عنها؟",
    "en": "What religious question would you like to ask?",
    "ur": "آپ کون سا شرعی مسئلہ پوچھنا چاہیں گے؟",
    "hi": "आप कौन-सा धार्मिक प्रश्न पूछना चाहेंगे?",
    "tr": "Hangi dinî meseleyi sormak istersiniz?",
    "id": "Masalah agama apa yang ingin Anda tanyakan?",
    "bn": "আপনি কোন ধর্মীয় বিষয়ে জিজ্ঞাসা করতে চান?",
    "ms": "Masalah agama apakah yang ingin anda tanyakan?",
    "uz": "Qaysi diniy masala haqida so‘ramoqchisiz?",
    "kk": "Қандай діни мәселе туралы сұрағыңыз келеді?",
    "ha": "Wace mas'ala ta addini kake son tambaya?",
}

# A longer reply is not shown (the standard out-of-scope text is used instead).
MAX_GENERAL_REPLY = 400
_QUESTION_SENTENCE = re.compile(r"[^.!?؟।۔]*[?؟]\s*")


def localized(texts: dict[str, str], language: str) -> dict:
    return {"message_ar": texts["ar"], "message_en": texts["en"], "message": texts.get(language, texts["en"])}


def reason(code: str, detail: str | None = None, language: str = "ar") -> dict:
    return {"code": code, **localized(REASONS[code], language), "detail": detail}


def general_reply(text: str, language: str) -> dict:
    """A short conversational reply to a non-religious message (no ruling, no source), then the invitation to ask."""
    text = _QUESTION_SENTENCE.sub("", text).strip()  # the invitation is the only question
    if not text or len(text) > MAX_GENERAL_REPLY:
        return reason("out_of_scope", language=language)
    message = f"{text} {INVITE.get(language, INVITE['en'])}"
    return {
        "code": "out_of_scope",
        "message_ar": message,
        "message_en": message,
        "message": message,
        "detail": "general_reply",
    }
