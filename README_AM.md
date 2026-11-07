# Step Up Academy – Student & Academic Management (Version 3)

ይህ የማስፋፊያ ስሪት ለKG–Grade 8፣ አራት ኳርተሮች፣ 100 የመጨረሻ ውጤት እና አማርኛ/English መሠረት ተዘጋጅቷል። የማርክ ክፍፍል በትምህርት ቤቱ ፍላጎት ሊዋቀር ይችላል።

## ማስነሳት
1. Python 3.10+ ይጫኑ።
2. `pip install -r requirements.txt`
3. `python app.py`
4. Browser ላይ `http://127.0.0.1:5000` ይክፈቱ።
5. የመጀመሪያ መግቢያ: `admin` / `StepUp@123`

**አስፈላጊ:** ከእውነተኛ የተማሪ መረጃ በፊት የadmin የይለፍ ቃል ይቀይሩ። በኢንተርኔት ላይ ለማስቀመጥ ጠንካራ `SECRET_KEY` እና PostgreSQL `DATABASE_URL` ያዘጋጁ። ይህ ገና production-ready አይደለም።

## ባህሪያት
- KG–Grade 8 ተማሪ መመዝገብ።
- ብዙ ተማሪዎችን በExcel (.xlsx) ማስገባት።
- የክፍል ትምህርቶችን መመዝገብ።
- በዓመትና በኳርተር የማርክ ክፍፍል ማዋቀር።
- ማርክን በተዋቀረው ከፍተኛ ማርክ መሠረት ማስገባት።
- የኳርተር ውጤትን ከ100 ማስላት እና የግል ሪፖርት ካርድ ማተም።

## የማርክ ክፍፍል ማዋቀር
1. Admin ወይም Registrar ሆነው ይግቡ።
2. **Assessment Settings** ይክፈቱ።
3. Grade፣ academic year፣ quarter፣ assessment name እና maximum score ያስገቡ።
4. ለአንድ ትምህርት ብቻ ከሆነ Subject ይምረጡ፤ ለክፍሉ ሁሉ ከሆነ All subjects ይተዉ።
5. የክፍፍሉ ድምር 100 መሆን አለበት፤ አሁን ሲስተሙ የተጠቃሚውን የተወሰኑ ክፍሎች ከአጠቃላይ ድምር ጋር በመያያዝ ወደ 100 ይቀይራል። ትምህርት ቤቱ ከ100 የማይደርስ ወይም ከ100 የሚበልጥ ክፍፍል ካዘጋጀ የሚታየው ውጤት እንደ መቶኛ ይnormalize ይደረጋል።
6. ከዚያ Marks ውስጥ year፣ quarter እና subject ይምረጡ፣ በተጫነው assessment list መሠረት ማርክ ያስገቡ።

## የሚቀጥሉ አስፈላጊ ሥራዎች
- የአራቱ ኳርተሮች አመታዊ ውጤት፣ ranking እና promotion።
- የመምህራን ክፍል/ሴክሽን መመደብ እና የውሂብ መዳረሻ ገደብ።
- የወላጅ/ተማሪ መለያዎች ለተመደበላቸው ተማሪ ብቻ መዳረሻ።
- የይለፍ ቃል መቀየሪያ፣ audit log፣ CSRF protection፣ backup/restore እና የደህንነት ሙከራ።
- የት/ቤቱን ኦሪጅናል ሎጎ ማካተት።

**ማስታወሻ:** የነባር ዳታቤዝ ላይ አዲሱ `assessment_component` ሰንጠረዥ በ`db.create_all()` ይፈጠራል፤ ለወደፊት የዳታቤዝ መዋቅር ለውጦች migration መጠቀም ይመከራል።


## Version 4 – የዓመት ውጤትና ደረጃ
- Annual Results ገጽ በዓመት፣ በክፍልና በሴክሽን ይፈልጋል።
- የእያንዳንዱ ኳርተር አማካይና የዓመት አማካይ ያሳያል።
- የዓመት ውጤት ለመስላት በአራቱም ኳርተሮች ሁሉም የክፍሉ ትምህርቶች የተሟላ ውጤት ያስፈልጋል፤ ካልተሟላ “Incomplete” ይላል።
- Admin/Registrar ለእያንዳንዱ ክፍልና ዓመት የማለፊያ ዝቅተኛ አማካይ (ነባሪ 50/100) ሊያስተካክል ይችላል።
- Ranking በክፍልና በሴክሽን ውስጥ በተሟላ የዓመት አማካይ ይሰላል። እኩል ውጤት እኩል ደረጃ ይወስዳል።

**ማስፈላለጊያ:** የአራቱ ኳርተሮች የAssessment Settings ክፍፍል እና ሁሉም ማርኮች መግባታቸውን አረጋግጡ። ይህ የመነሻ ስሪት ነው፤ ለProduction ከመጠቀም በፊት የተጠቃሚ መዳረሻ ገደብ፣ CSRF፣ backup፣ የውጤት ማረጋገጫና ሙሉ ሙከራ ያስፈልጋሉ።

## Version 5 – Parent Portal, Class Summary & Bulk Report Cards

### አዲስ ባህሪያት
- **Parent Links:** Admin/Registrar በUsers ውስጥ `parent` role ያለውን መለያ ከተማሪ ID ጋር ያገናኛል።
- **Parent Portal:** ወላጅ በራሱ መለያ ገብቶ ከተገናኙት ልጆቹ የተመረጠውን ኳርተር ውጤት ብቻ ያያል። ያልተገናኘ ሌላ ተማሪ ውጤት አይታይም።
- **Class Summary:** በክፍል፣ ሴክሽን፣ ዓመትና ኳርተር የክፍል አማካይ፣ የተሟሉና ያልተሟሉ ውጤቶችን ያሳያል።
- **Bulk Report Cards:** እስከ 300 የክፍል/ሴክሽን ተማሪዎች ሪፖርት ካርድ በአንድ ገጽ ያዘጋጃል፤ Browser Print → Save as PDF በመጠቀም አንድ PDF ማውጣት ይቻላል።

### የመጀመሪያ አጠቃቀም
1. `pip install -r requirements.txt`
2. `flask --app app init-db`
3. `flask --app app run`
4. Admin በመግባት Users ውስጥ Parent መለያ ይፍጠሩ።
5. Parent Links ውስጥ የወላጁን username ከተማሪ ID ጋር ያገናኙ።
6. ወላጁ በራሱ username/password ገብቶ Parent Portal ይመለከታል።

### አስፈላጊ የደህንነት ማስታወሻ
ይህ አሁንም MVP/የልማት ስሪት ነው። በት/ቤቱ እውነተኛ መረጃ ላይ ከመጠቀም በፊት HTTPS፣ ጠንካራ `SECRET_KEY`፣ የመጀመሪያ የAdmin ይለፍ ቃል መቀየር፣ የBackup/Restore፣ CSRF ጥበቃ፣ የመምህራን የክፍል ፈቃድ ገደብና ሙሉ የQA/የደህንነት ሙከራ ያስፈልጋሉ። የተጨመረው Parent Portal በግልጽ የተመዘገበ የParent–Student Link ብቻ ይጠቀማል።


## Version 6 – Official school logo
- Supplied Step Up Academy logo included at `static/step_up_academy_logo.jpeg`.
- Displayed in the main header and printable student report cards.
- Keep the image in the `static` folder when deploying.
