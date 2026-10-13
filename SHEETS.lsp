;;; ==========================================================================
;;;  SHEETS.lsp Ч форматы листов со штампом (√ќ—“ – 21.101, формы 3, 4, 5, 6),
;;;  ведомость листов, ведомость спецификаций, ведомость ссылочных и прилагаемых документов.
;;;  ¬ерси€ s0.12 (s0.12 Ч перевод листов —ѕƒ— в SHEETS: SHEET_FROM_SPDS;
;;;  s0.11 Ч окна в виде штампа: Ђƒанные комплектаї, Ђƒанные бокового штампаї,
;;;  Ђ¬се пол€ штампаї с кнопками Ђƒл€ этого листаї / Ђƒл€ всех листовї, шаблоны данных комплекта;
;;;  s0.10 Ч формы 4 и 5, лист без бокового штампа, ведомость ссылочных и прилагаемых
;;;  документов SHEET_REFS, документы форм 4 и 5 со своей нумерацией; пробна€ SHEET_TBLTEST убрана;
;;;  s0.9.1 Ч пробна€ команда SHEET_TBLTEST: способы убрать рамку заголовка таблицы;
;;;  s0.9 Ч заголовок ведомостей без рамки: Ђбез границї на всю строку заголовка;
;;;  s0.8 Ч окно всех команд SHT, автозагрузка при открытии чертежа;
;;;  s0.7 Ч подписи и логотип в штампе: SHEET_SIGN, шаг плана s0.4;
;;;  s0.6.2 Ч ведомость листов вставл€етс€ по верху заголовка, как ведомость спецификаций;
;;;  s0.6.1 Ч ведомость спецификаций обновл€етс€ сразу после правки заголовка / переноса таблицы;
;;;  s0.6 Ч ведомость спецификаций: таблицы AutoCAD Ђ—пецификаци€Еї по листам, SHEET_SPEC;
;;;  s0.5.1 Ч заголовок ведомости без рамки; удалили лист Ч ведомость сразу;
;;;  s0.5 Ч ведомость рабочих чертежей: таблица AutoCAD, Ђѕримечаниеї по изменени€м,
;;;  ЂЋистовї на первом листе, автообновление при сохранении и печати;
;;;  s0.3.2 Ч печать в PDF: один файл комплекта или отдельные листы, по номерам листов;
;;;  s0.2.2 Ч тонкий текст, вписывание, короткий штамп, окно листа, формат в Ђ—войствахї), 2026-10-05
;;;  AutoCAD 2021 / 2024.
;;;  ¬ј∆Ќќ: файл хранитс€ в кодировке Windows-1251 (ANSI). ¬ UTF-8 кириллица
;;;  в окнах и в чертеже превращаетс€ в Ђкракоз€брыї.
;;;   оманды: SHEET_NEW Ч новый лист; SHEET_EDIT Ч изменить лист (и двойной щелчок по листу);
;;;  SHEET_DATA Ч данные комплекта (во все листы); SHEET_UPDATE Ч вписать тексты во всех листах;
;;;  SHEET_DBLCLICK Ч двойной щелчок: окно листа / обычный редактор; SHEET_PROBE Ч разбор объекта;
;;;  SHEET_APPLY Ч перестроить листы, у которых в Ђ—войствахї помен€ли FORMAT / ORIENT (запускаетс€ сама);
;;;  SHEET_PLOT Ч печать листов в PDF (s0.3); SHEET_LIST Ч ведомость рабочих чертежей (s0.5);
;;;  SHEET_SPEC Ч ведомость спецификаций (s0.6); SHEET_SIGN Ч подписи и логотип (s0.7);
;;;  SHT Ч окно всех команд + автозагрузка (s0.8); SHEET_REFS Ч ведомость ссылочных и прилагаемых
;;;  документов (s0.10); SHEET_STAMP Ч все пол€ штампа листа, SHEET_SIDE Ч данные бокового штампа (s0.11);
;;;  SHEET_FROM_SPDS Ч перевод листов (рамок) —ѕƒ— в листы SHEETS (s0.12).
;;;
;;;  ќкна (DCL) встроены в этот файл: при запуске пишутс€ во временный файл
;;;  и удал€ютс€ после закрыти€. »стори€ и план работ Ч claude/sheets_state.md
;;; ==========================================================================

(vl-load-com)

;;; --------------------------------------------------------------------------
;;;  1. Ќј—“–ќ… » » —ѕ–ј¬ќ„Ќ» » (размеры Ч мм листа; в модели Ч x масштаб)
;;; --------------------------------------------------------------------------

(setq *sht:Version* "s0.14.4")
(setq *sht:BlkVer* "5")          ; s0.12.1: форма 3 Ч тексты 2,5, объект на всю графу; верси€ описаний блоков листа: помен€лась Ч блоки переопредел€ютс€
                                 ; s0.2: тексты 0,25, атрибуты на слое листа, форма 6;
                                 ; s0.2.2: формат (графа 26) Ч атрибут FORMAT, ориентаци€ Ч ORIENT

;;  одировка временного DCL-файла (как в PYLON_BASE): nil Ч ANSI, проверено на 2021/2024
(setq *sht:DclEncoding* nil)

(setq *sht:LayFmt*   "0000_‘ормат"      ; листы
      *sht:LayFmtP*  "0000_‘ормат_ѕ"    ; рамка сквозного номера (стади€ ѕ) Ч выключаетс€ дл€ –
      *sht:LayProps* '(("0000_‘ормат" 7 50) ("0000_‘ормат_ѕ" 7 50) ("0000_“аблицы" 7 -3))
      *sht:Style*    "√ќ—“ 2.304"       ; стиль текста штампа (как в образце —ѕƒ—)
      *sht:StyleFont* "CS_Gost2304.shx"
      *sht:SetKey*   "SHT_SET"          ; словарь чертежа: данные комплекта
      *sht:LwThick*  60                 ; основные линии 0,6
      *sht:LwThin*   25                 ; тонкие 0,25 (и обрезна€ рамка)
      *sht:LwText*   25                 ; толщина текстов и атрибутов (как в образце; не Ђжирныеї, s0.2)
      *sht:MinWf*    0.5                ; сжатие длинного текста не сильнееЕ
      *sht:MinH*     1.8                ; Едальше уменьшаетс€ высота, но не ниже 1,8 мм листа
      *sht:LineSp*   1.667)             ; шаг строк многострочного текста, в высотах

;; ѕол€ листа: слева, снизу, справа, сверху (подшивка Ч слева)
(setq *sht:Margins* '(20.0 5.0 5.0 5.0))

;; ‘орматы Ч из ЂDWG To PDF.pmpї јртЄма: (им€ кратность коротка€ длинна€), мм.
;;  ратность 1 Ч основной формат. A4 горизонтальный пока не используетс€ (решение јртЄма).
(setq *sht:Formats*
  '(("A4" 1 210.0 297.0) ("A4" 3 297.0 630.0) ("A4" 4 297.0 841.0) ("A4" 5 297.0 1051.0)
    ("A4" 6 297.0 1261.0) ("A4" 7 297.0 1471.0) ("A4" 8 297.0 1682.0) ("A4" 9 297.0 1892.0)
    ("A3" 1 297.0 420.0) ("A3" 3 420.0 891.0) ("A3" 4 420.0 1189.0) ("A3" 5 420.0 1486.0)
    ("A3" 6 420.0 1783.0) ("A3" 7 420.0 2080.0)
    ("A2" 1 420.0 594.0) ("A2" 3 594.0 1261.0) ("A2" 4 594.0 1682.0) ("A2" 5 594.0 2102.0)
    ("A1" 1 594.0 841.0) ("A1" 3 841.0 1783.0) ("A1" 4 841.0 2378.0)
    ("A0" 1 841.0 1189.0) ("A0" 2 1189.0 1682.0) ("A0" 3 1189.0 2523.0)))
(setq *sht:FmtNames* '("A4" "A3" "A2" "A1" "A0"))
(setq *sht:OnlyPortrait* '(("A4" . 1)))   ; только вертикальный

;; ‘ормы штампа (s0.10, образец јртЄма Ђ‘орматы.dxfї): "3" Ч основна€ надпись 185 x 55 (чертежи
;; основного комплекта); "4" Ч 185 x 55 (чертежи строительных изделий); "5" Ч 185 x 40 (первый лист
;; текстовых документов, эскизов изделий); "6" Ч коротка€ 185 x 15 (последующие листы, ЂЎтамп“екстї).
;; Ѕуква "N" после номера Ч лист без бокового штампа (пол€ подшивки): "3N", "4N" Е
(setq *sht:Forms*     '("3" "4" "5" "6")
      *sht:FormsAll*  '("3" "4" "5" "6" "3N" "4N" "5N" "6N")
      *sht:FormNames* '("‘орма 3 - чертежи основного комплекта (185 x 55)"
                        "‘орма 4 - чертежи строительных изделий (185 x 55)"
                        "‘орма 5 - текстовые документы, 1-й лист (185 x 40)"
                        "‘орма 6 - последующие листы (185 x 15)"))

;; Ќомер формы без "N"; есть ли боковой штамп; форма из номера и признака
(defun sht:fbase (form) (substr form 1 1))
(defun sht:fside-p (form) (not (wcmatch form "*N")))
(defun sht:fmake (base side) (if side base (strcat base "N")))
;; Ћист документа формы 4 / 5 (s0.10): в графе 1 Ч своЄ обозначение (атрибут OBOZN, не общий шифр),
;; нумераци€ Ч сво€ внутри документа
(defun sht:fdoc-p (form) (member (sht:fbase form) '("4" "5")))

;; √еометри€ Ч по образцам јртЄма (—ѕƒ— GraphiCS: ЂЎтампы и таблица.dxfї Ч форма 3,
;; ЂЎтамп“екст.dxfї Ч форма 6). “очки Ч от угла рамки пол€: "BR" правый нижний (штамп),
;; "BL" левый нижний (доп. графы), "TR" правый верхний (рамка сквозного номера).
;; Ћинии: (угол x1 y1 x2 y2 вес слой); слой nil Ч 0, "P" Ч *sht:LayFmtP*.
(setq *sht:Lines3*
  '(;; основна€ надпись (форма 3, 185 x 55)
    ("BR" -185.0 0.0 0.0 0.0 60 nil) ("BR" -185.0 55.0 0.0 55.0 60 nil) ("BR" -185.0 30.0 0.0 30.0 60 nil)
    ("BR" -185.0 35.0 -120.0 35.0 60 nil) ("BR" -120.0 15.0 0.0 15.0 60 nil) ("BR" -120.0 45.0 0.0 45.0 60 nil)
    ("BR" -50.0 25.0 0.0 25.0 60 nil)
    ("BR" -185.0 0.0 -185.0 55.0 60 nil) ("BR" -165.0 0.0 -165.0 55.0 60 nil) ("BR" -145.0 0.0 -145.0 55.0 60 nil)
    ("BR" -130.0 0.0 -130.0 55.0 60 nil) ("BR" -120.0 0.0 -120.0 55.0 60 nil) ("BR" 0.0 0.0 0.0 55.0 60 nil)
    ("BR" -175.0 30.0 -175.0 55.0 60 nil) ("BR" -155.0 30.0 -155.0 55.0 60 nil)
    ("BR" -50.0 0.0 -50.0 30.0 60 nil) ("BR" -35.0 15.0 -35.0 30.0 60 nil) ("BR" -20.0 15.0 -20.0 30.0 60 nil)
    ("BR" -185.0 5.0 -120.0 5.0 25 nil) ("BR" -185.0 10.0 -120.0 10.0 25 nil) ("BR" -185.0 15.0 -120.0 15.0 25 nil)
    ("BR" -185.0 20.0 -120.0 20.0 25 nil) ("BR" -185.0 25.0 -120.0 25.0 25 nil) ("BR" -185.0 40.0 -120.0 40.0 25 nil)
    ("BR" -185.0 45.0 -120.0 45.0 25 nil) ("BR" -185.0 50.0 -120.0 50.0 25 nil)))
(setq *sht:Lines6*
  '(;; коротка€ (форма 6, 185 x 15): 2 строки изменений + шапка, графа 1 (110), ЂЋистї 10 x (7 + 8)
    ("BR" -185.0 15.0 0.0 15.0 60 nil) ("BR" -185.0 0.0 -185.0 15.0 60 nil) ("BR" -175.0 0.0 -175.0 15.0 60 nil)
    ("BR" -165.0 0.0 -165.0 15.0 60 nil) ("BR" -155.0 0.0 -155.0 15.0 60 nil) ("BR" -145.0 0.0 -145.0 15.0 60 nil)
    ("BR" -130.0 0.0 -130.0 15.0 60 nil) ("BR" -120.0 0.0 -120.0 15.0 60 nil) ("BR" -10.0 0.0 -10.0 15.0 60 nil)
    ("BR" -10.0 8.0 0.0 8.0 60 nil) ("BR" 0.0 0.0 0.0 15.0 60 nil)
    ("BR" -185.0 5.0 -120.0 5.0 25 nil) ("BR" -185.0 10.0 -120.0 10.0 25 nil)))
(setq *sht:Lines4*
  '(;; форма 4 (185 x 55, Ђ‘орматы.dxfї): слева Ч как у формы 3; справа графа 1 (y 40Е55), графа 5
    ;; 70 x 25, Ђ—тади€ / ћасса / ћасштабї (шапка y 35Е40), ЂЋист / Ћистовї в одну строку (y 15Е20),
    ;; внизу графы 23 (70 x 15) и 9 (50 x 15)
    ("BR" -185.0 0.0 0.0 0.0 60 nil) ("BR" -185.0 55.0 0.0 55.0 60 nil) ("BR" -185.0 30.0 -120.0 30.0 60 nil)
    ("BR" -185.0 35.0 -120.0 35.0 60 nil) ("BR" -120.0 40.0 0.0 40.0 60 nil) ("BR" -120.0 15.0 0.0 15.0 60 nil)
    ("BR" -50.0 35.0 0.0 35.0 60 nil) ("BR" -50.0 20.0 0.0 20.0 60 nil)
    ("BR" -185.0 0.0 -185.0 55.0 60 nil) ("BR" -165.0 0.0 -165.0 55.0 60 nil) ("BR" -145.0 0.0 -145.0 55.0 60 nil)
    ("BR" -130.0 0.0 -130.0 55.0 60 nil) ("BR" -120.0 0.0 -120.0 55.0 60 nil) ("BR" 0.0 0.0 0.0 55.0 60 nil)
    ("BR" -175.0 30.0 -175.0 55.0 60 nil) ("BR" -155.0 30.0 -155.0 55.0 60 nil)
    ("BR" -50.0 0.0 -50.0 40.0 60 nil) ("BR" -35.0 20.0 -35.0 40.0 60 nil) ("BR" -20.0 20.0 -20.0 40.0 60 nil)
    ("BR" -30.0 15.0 -30.0 20.0 60 nil)
    ("BR" -185.0 5.0 -120.0 5.0 25 nil) ("BR" -185.0 10.0 -120.0 10.0 25 nil) ("BR" -185.0 15.0 -120.0 15.0 25 nil)
    ("BR" -185.0 20.0 -120.0 20.0 25 nil) ("BR" -185.0 25.0 -120.0 25.0 25 nil) ("BR" -185.0 40.0 -120.0 40.0 25 nil)
    ("BR" -185.0 45.0 -120.0 45.0 25 nil) ("BR" -185.0 50.0 -120.0 50.0 25 nil)))
(setq *sht:Lines5*
  '(;; форма 5 (185 x 40): 2 строки изменений (y 30Е40), шапка (y 25Е30), 5 строк подписей;
    ;; справа графа 1 (y 25Е40), графа 5 70 x 25, Ђ—тади€ / Ћист / Ћистовї (шапка y 20Е25, значени€
    ;; y 15Е20), графа 9 (50 x 15)
    ("BR" -185.0 0.0 0.0 0.0 60 nil) ("BR" -185.0 40.0 0.0 40.0 60 nil) ("BR" -185.0 30.0 -120.0 30.0 60 nil)
    ("BR" -185.0 25.0 0.0 25.0 60 nil) ("BR" -50.0 15.0 0.0 15.0 60 nil) ("BR" -50.0 20.0 0.0 20.0 60 nil)
    ("BR" -185.0 0.0 -185.0 40.0 60 nil) ("BR" -165.0 0.0 -165.0 40.0 60 nil) ("BR" -145.0 0.0 -145.0 40.0 60 nil)
    ("BR" -130.0 0.0 -130.0 40.0 60 nil) ("BR" -120.0 0.0 -120.0 40.0 60 nil) ("BR" 0.0 0.0 0.0 40.0 60 nil)
    ("BR" -175.0 25.0 -175.0 40.0 60 nil) ("BR" -155.0 25.0 -155.0 40.0 60 nil)
    ("BR" -50.0 0.0 -50.0 25.0 60 nil) ("BR" -35.0 15.0 -35.0 25.0 60 nil) ("BR" -20.0 15.0 -20.0 25.0 60 nil)
    ("BR" -185.0 5.0 -120.0 5.0 25 nil) ("BR" -185.0 10.0 -120.0 10.0 25 nil) ("BR" -185.0 15.0 -120.0 15.0 25 nil)
    ("BR" -185.0 20.0 -120.0 20.0 25 nil) ("BR" -185.0 35.0 -120.0 35.0 25 nil)))
(setq *sht:LinesCommon*
  '(;; дополнительные графы на поле подшивки (инв. є подл., подп. и дата, взам. инв. є, согласовано)
    ("BL" 0.0 0.0 0.0 150.0 60 nil) ("BL" -12.0 0.0 0.0 0.0 60 nil) ("BL" -12.0 0.0 -12.0 85.0 60 nil)
    ("BL" -7.0 0.0 -7.0 85.0 60 nil) ("BL" -12.0 25.0 0.0 25.0 60 nil) ("BL" -12.0 60.0 0.0 60.0 60 nil)
    ("BL" -15.0 85.0 0.0 85.0 60 nil) ("BL" -15.0 85.0 -15.0 150.0 60 nil) ("BL" -10.0 85.0 -10.0 150.0 60 nil)
    ("BL" -15.0 150.0 0.0 150.0 60 nil) ("BL" -10.0 105.0 0.0 105.0 60 nil) ("BL" -10.0 125.0 0.0 125.0 60 nil)
    ("BL" -10.0 140.0 0.0 140.0 60 nil) ("BL" -5.0 85.0 -5.0 150.0 25 nil)
    ;; рамка 10 x 7 Ч сквозной номер листа (стади€ ѕ)
    ("TR" -10.0 -7.0 0.0 -7.0 60 "P") ("TR" -10.0 -7.0 -10.0 0.0 60 "P")
    ("TR" -10.0 0.0 0.0 0.0 60 "P") ("TR" 0.0 -7.0 0.0 0.0 60 "P")))

;; ѕосто€нные надписи: (угол x y текст высота сжатие поворот-град выравн-гор выравн-верт)
;; выравнивание: гор. 0 Ч влево, 1 Ч по центру; верт. 0 Ч по базовой линии, 2 Ч по середине
(setq *sht:Texts3*
  '(("BR" -180.0 32.5 "»зм." 2.5 1.0 0.0 1 2) ("BR" -170.0 32.5 " ол. уч." 2.5 0.742 0.0 1 2)
    ("BR" -160.0 32.5 "Ћист" 2.5 1.0 0.0 1 2) ("BR" -150.0 32.5 "є док." 2.5 0.889 0.0 1 2)
    ("BR" -137.5 32.5 "ѕодп." 2.5 1.0 0.0 1 2) ("BR" -125.0 32.5 "ƒата" 2.5 1.0 0.0 1 2)
    ("BR" -42.5 27.5 "—тади€" 2.5 1.0 0.0 1 2) ("BR" -27.5 27.5 "Ћист" 2.5 1.0 0.0 1 2)
    ("BR" -10.0 27.5 "Ћистов" 2.5 1.0 0.0 1 2)))
;; форма 6: в образце подписей граф нет Ч по √ќ—“ (шапка внизу, ЂЋистї в верхней части клетки)
(setq *sht:Texts6*
  '(("BR" -180.0 2.5 "»зм." 2.5 1.0 0.0 1 2) ("BR" -170.0 2.5 " ол. уч." 2.5 0.742 0.0 1 2)
    ("BR" -160.0 2.5 "Ћист" 2.5 1.0 0.0 1 2) ("BR" -150.0 2.5 "є док." 2.5 0.889 0.0 1 2)
    ("BR" -137.5 2.5 "ѕодп." 2.5 1.0 0.0 1 2) ("BR" -125.0 2.5 "ƒата" 2.5 1.0 0.0 1 2)
    ("BR" -5.0 11.5 "Ћист" 2.5 1.0 0.0 1 2)))
;; формы 4 и 5 (s0.10): подписи граф в образце сдвинуты Ч по √ќ—“, в середине клеток
(setq *sht:Texts4*
  '(("BR" -180.0 32.5 "»зм." 2.5 1.0 0.0 1 2) ("BR" -170.0 32.5 " ол. уч." 2.5 0.742 0.0 1 2)
    ("BR" -160.0 32.5 "Ћист" 2.5 1.0 0.0 1 2) ("BR" -150.0 32.5 "є док." 2.5 0.889 0.0 1 2)
    ("BR" -137.5 32.5 "ѕодп." 2.5 1.0 0.0 1 2) ("BR" -125.0 32.5 "ƒата" 2.5 1.0 0.0 1 2)
    ("BR" -42.5 37.5 "—тади€" 2.5 1.0 0.0 1 2) ("BR" -27.5 37.5 "ћасса" 2.5 1.0 0.0 1 2)
    ("BR" -10.0 37.5 "ћасштаб" 2.5 1.0 0.0 1 2)
    ("BR" -48.5 17.5 "Ћист" 2.5 1.0 0.0 0 2) ("BR" -28.5 17.5 "Ћистов" 2.5 1.0 0.0 0 2)))
(setq *sht:Texts5*
  '(("BR" -180.0 27.5 "»зм." 2.5 1.0 0.0 1 2) ("BR" -170.0 27.5 " ол. уч." 2.5 0.742 0.0 1 2)
    ("BR" -160.0 27.5 "Ћист" 2.5 1.0 0.0 1 2) ("BR" -150.0 27.5 "є док." 2.5 0.889 0.0 1 2)
    ("BR" -137.5 27.5 "ѕодп." 2.5 1.0 0.0 1 2) ("BR" -125.0 27.5 "ƒата" 2.5 1.0 0.0 1 2)
    ("BR" -42.5 22.5 "—тади€" 2.5 1.0 0.0 1 2) ("BR" -27.5 22.5 "Ћист" 2.5 1.0 0.0 1 2)
    ("BR" -10.0 22.5 "Ћистов" 2.5 1.0 0.0 1 2)))
(setq *sht:TextsCommon*
  '(("BR" -32.5 -3.75 "‘ормат" 2.5 1.0 0.0 1 0)
    ("BL" -9.5 12.5 "»нв. є подл." 3.0 1.0 90.0 1 2) ("BL" -9.5 42.5 "ѕодп. и дата" 3.0 1.0 90.0 1 2)
    ("BL" -9.5 72.5 "¬зам. инв. є" 3.0 0.992 90.0 1 2) ("BL" -11.21 87.0 "—огласовано" 3.0 1.0 90.0 0 0)))
;; им€ формата под рамкой (ЂA4x3ї) Ч слева по базовой линии; с s0.2.2 Ч атрибут FORMAT в этой точке
(setq *sht:FmtText* '("BR" -14.5 -3.75 2.5))

;; јтрибуты: (0 тег 1 подсказка 2 по-умолчанию 3 угол 4 x 5 y 6 высота 7 поворот 8 выравн-гор
;;            9 выравн-верт 10 ширина-€чейки 11 многострочный 12 слой 13 высота-€чейки 14 флаги).
;; ѕор€док Ч пор€док в окне правки атрибутов. ‘лаги: 0 Ч обычный, 1 Ч невидимый.
;; √рафы √ќ—“ – 21.101-2026: 1 SHIFR, 2 OBJECT, 3 BUILDING, 4 TITLE, 6 STAGE, 7 SHEET, 8 SHEETS,
;; 9 ORG, 10-13 ROLE/NAME/(подпись)/DATE, 14-19 изменени€ C1..C4, 20 INV, 22 VZAM.
;; ‘орма 6: SHEET, SHIFR, C1..C2 и невидимый TITLE (наименование Ч дл€ ведомости и окна листа).
;; s0.10: форма 4 Ч OBOZN (графа 1, своЄ обозначение листа), TITLE (графа 5), MATER (23), STAGE, MASS (24),
;; SCALE (25), SHEET, SHEETS, ORG, подписи 1-6, изменени€ C1..C4; форма 5 Ч OBOZN, TITLE (графа 5), STAGE,
;; SHEET, SHEETS, ORG, подписи 1-5, изменени€ C1..C2. Ѕез бокового штампа ("N") Ч нет INV, VZAM, SOGLЕ.
(defun sht:attrs-table (form / b res i y n top ns)
  (setq b (sht:fbase form))
  (cond
    ((= b "6")
     (setq res
       (list
         (list "SHEET" "Ћист (графа 7)" "" "BR" -5.0 4.0 3.5 0.0 1 2 9.0 nil nil 8.0 0)
         (list "TITLE" "Ќаименование листа (дл€ ведомости, не видно)" "" "BR" -65.0 20.0 3.5 0.0 1 2 108.0 nil nil 15.0 1)
         (list "SHIFR" "ќбозначение, шифр (графа 1)" "" "BR" -65.0 7.5 5.0 0.0 1 2 108.0 nil nil 15.0 0))
           n   2
           top 0.0
           ns  0))
    ((= b "4")
     (setq res
       (list
         (list "SHEET" "Ћист (графа 7)" "" "BR" -35.0 17.5 2.5 0.0 1 2 9.0 nil nil 5.0 0)
         (list "TITLE" "Ќаименование издели€, документа (графа 5)" "" "BR" -85.0 27.5 3.5 0.0 1 2 66.0 T nil 25.0 0)
         (list "OBOZN" "ќбозначение документа (графа 1)" "" "BR" -60.0 47.5 5.0 0.0 1 2 116.0 nil nil 15.0 0)
         (list "MATER" "ћатериал детали (графа 23)" "" "BR" -85.0 7.5 3.5 0.0 1 2 66.0 T nil 15.0 0)
         (list "STAGE" "—тади€ (графа 6)" "" "BR" -42.5 27.5 3.5 0.0 1 2 13.0 nil nil 15.0 0)
         (list "MASS" "ћасса (графа 24)" "" "BR" -27.5 27.5 3.5 0.0 1 2 13.0 nil nil 15.0 0)
         (list "SCALE" "ћасштаб (графа 25)" "" "BR" -10.0 27.5 3.5 0.0 1 2 18.0 nil nil 15.0 0)
         (list "ORG" "ќрганизаци€ (графа 9)" "" "BR" -25.0 7.5 3.5 0.0 1 2 46.0 T nil 15.0 0))
           n   4
           top 30.0
           ns  6))
    ((= b "5")
     (setq res
       (list
         (list "SHEET" "Ћист (графа 7)" "" "BR" -27.5 17.5 2.5 0.0 1 2 13.0 nil nil 5.0 0)
         (list "TITLE" "Ќаименование документа (графа 5)" "" "BR" -85.0 12.5 3.5 0.0 1 2 66.0 T nil 25.0 0)
         (list "OBOZN" "ќбозначение документа (графа 1)" "" "BR" -60.0 32.5 5.0 0.0 1 2 116.0 nil nil 15.0 0)
         (list "STAGE" "—тади€ (графа 6)" "" "BR" -42.5 17.5 2.5 0.0 1 2 13.0 nil nil 5.0 0)
         (list "ORG" "ќрганизаци€ (графа 9)" "" "BR" -25.0 7.5 3.5 0.0 1 2 46.0 T nil 15.0 0))
           n   2
           top 25.0
           ns  5))
    (t
     (setq res
       (list
         (list "SHEET" "Ћист (графа 7)" "" "BR" -27.5 20.0 2.5 0.0 1 2 13.0 nil nil 10.0 0)
         (list "TITLE" "Ќаименование изображений (графа 4)" "" "BR" -85.0 7.5 2.5 0.0 1 2 66.0 T nil 15.0 0)
         (list "SHIFR" "ќбозначение, шифр (графа 1)" "" "BR" -60.0 50.0 5.0 0.0 1 2 116.0 nil nil 10.0 0)
         (list "OBJECT" "ќбъект (графа 2)" "" "BR" -60.0 37.5 3.5 0.0 1 2 118.0 T nil 15.0 0)
         (list "BUILDING" "«дание (графа 3)" "" "BR" -85.0 22.5 3.5 0.0 1 2 66.0 T nil 15.0 0)
         (list "STAGE" "—тади€ (графа 6)" "" "BR" -42.5 20.0 2.5 0.0 1 2 13.0 nil nil 10.0 0)
         (list "ORG" "ќрганизаци€ (графа 9)" "" "BR" -25.0 7.5 3.5 0.0 1 2 46.0 T nil 15.0 0))
           n   4
           top 30.0
           ns  6)))
  ;; подписи (формы 3, 4 Ч 6 строк, форма 5 Ч 5): строка i Ч от верхней (y top-5..top) к нижней (y 0..5)
  (if (> ns 0)
    (progn
      (setq i 1)
      (repeat ns
        (setq y (- top (* 5.0 i)))
        (setq res (append res
          (list (list (strcat "ROLE" (itoa i)) (strcat "ƒолжность, строка " (itoa i)) (sht:role-def i)
                      "BR" -184.55 (+ y 1.17) 2.5 0.0 0 0 19.0 nil nil 5.0 0)
                (list (strcat "NAME" (itoa i)) (strcat "‘амили€, строка " (itoa i)) ""
                      "BR" -164.55 (+ y 1.17) 2.5 0.0 0 0 19.0 nil nil 5.0 0)
                (list (strcat "DATE" (itoa i)) (strcat "ƒата, строка " (itoa i)) ""
                      "BR" -125.0 (+ y 2.5) 2.5 0.0 1 2 9.0 nil nil 5.0 0)))
              i (1+ i)))))
  ;; изменени€: C1 Ч нижн€€ строка над шапкой (формы 3, 4: y 35..40, форма 5: y 30..35, форма 6: y 5..10)
  (setq i 1)
  (repeat n
    (setq y (+ top (* 5.0 i)))
    (setq res (append res
      (mapcar '(lambda (c)
                 (list (strcat "C" (itoa i) (car c)) (strcat (cadr c) ", изменение " (itoa i)) ""
                       "BR" (caddr c) (+ y 2.5) 2.5 0.0 1 2 9.0 nil nil 5.0 0))
              '(("IZM" "»зм." -180.0) ("KOL" " ол. уч." -170.0) ("LST" "Ћист («ам., Ќов., -)" -160.0)
                ("DOC" "є док." -150.0) ("DAT" "ƒата" -125.0))))
          i (1+ i)))
  ;; боковой штамп (поле подшивки) Ч если он есть (s0.10)
  (if (sht:fside-p form)
    (setq res (append res
      (list
        (list "INV" "»нв. є подл. (графа 20)" "" "BL" -3.5 12.5 2.5 90.0 1 2 24.0 nil nil 7.0 0)
        (list "VZAM" "¬зам. инв. є (графа 22)" "" "BL" -3.5 72.5 2.5 90.0 1 2 24.0 nil nil 7.0 0)
        (list "SOGL1R" "—огласовано 1: должность" "" "BL" -7.5 95.0 2.5 90.0 1 2 19.0 nil nil 5.0 0)
        (list "SOGL1N" "—огласовано 1: фамили€" "" "BL" -7.5 115.0 2.5 90.0 1 2 19.0 nil nil 5.0 0)
        (list "SOGL1D" "—огласовано 1: дата" "" "BL" -7.5 145.0 2.5 90.0 1 2 9.0 nil nil 5.0 0)
        (list "SOGL2R" "—огласовано 2: должность" "" "BL" -2.5 95.0 2.5 90.0 1 2 19.0 nil nil 5.0 0)
        (list "SOGL2N" "—огласовано 2: фамили€" "" "BL" -2.5 115.0 2.5 90.0 1 2 19.0 nil nil 5.0 0)
        (list "SOGL2D" "—огласовано 2: дата" "" "BL" -2.5 145.0 2.5 90.0 1 2 9.0 nil nil 5.0 0)))))
  (setq res (append res
    (list
      (list "PNUM" "—квозной номер листа (стади€ ѕ)" "" "TR" -5.0 -3.5 3.5 0.0 1 2 9.0 nil "P" 7.0 0)
      ;; s0.2.2: формат и ориентаци€ Ч прав€тс€ в Ђ—войствахї, лист перестраиваетс€ (SHEET_APPLY)
      (list "FORMAT" "‘ормат: A3, A4x3 ... (графа 26; изменить - лист перестроитс€)" ""
            "BR" -14.5 -3.75 2.5 0.0 0 0 19.0 nil nil 5.0 0)
      (list "ORIENT" "ќриентаци€: горизонтальна€ / вертикальна€ (изменить - лист перестроитс€)" ""
            "BR" -14.5 -3.75 2.5 0.0 0 0 19.0 nil nil 5.0 1))))
  (cond
    ((= b "4")
     (setq res (append res
       (list (list "SHEETS" "Ћистов (графа 8, только на 1-м листе)" "" "BR" -9.5 17.5 2.5 0.0 1 2 17.0 nil nil 5.0 0)))))
    ((= b "5")
     (setq res (append res
       (list (list "SHEETS" "Ћистов (графа 8, только на 1-м листе)" "" "BR" -10.0 17.5 2.5 0.0 1 2 18.0 nil nil 5.0 0)))))
    ((/= b "6")
     (setq res (append res
       (list (list "SHEETS" "Ћистов (графа 8, только на 1-м листе)" "" "BR" -10.0 20.0 2.5 0.0 1 2 18.0 nil nil 10.0 0))))))
  res)

;; ƒолжности по умолчанию (решение јртЄма: Ђ–азработалї, Ђѕроверилї, ЂЌ.контр.ї Ч заранее, все прав€тс€)
(defun sht:role-def (i)
  (cond ((= i 1) "–азработал") ((= i 2) "ѕроверил") ((= i 4) "Ќ.контр.") (t "")))

(setq *sht:Attrs*  (sht:attrs-table "3")
      *sht:Attrs6* (sht:attrs-table "6"))
;; s0.10: таблицы атрибутов всех форм (с боковым штампом и без)
(setq *sht:AttrTabs* (mapcar '(lambda (f) (cons f (sht:attrs-table f))) *sht:FormsAll*))

;; ќбщие дл€ комплекта пол€ (окно Ђƒанные комплектаї)
(setq *sht:Common*
  '("SHIFR" "OBJECT" "BUILDING" "STAGE" "ORG"
    "ROLE1" "NAME1" "DATE1" "ROLE2" "NAME2" "DATE2" "ROLE3" "NAME3" "DATE3"
    "ROLE4" "NAME4" "DATE4" "ROLE5" "NAME5" "DATE5" "ROLE6" "NAME6" "DATE6"
    "INV" "VZAM" "SOGL1R" "SOGL1N" "SOGL1D" "SOGL2R" "SOGL2N" "SOGL2D"))
(setq *sht:CommonDef* '(("ROLE1" . "–азработал") ("ROLE2" . "ѕроверил") ("ROLE4" . "Ќ.контр.")
                        ("STAGE" . "–")))
;; s0.11: окна в виде штампа. ѕол€ окна ЂЎтампї (форма 3: изменени€ сверху вниз Ч C4 Е C1,
;; подписи, права€ часть, графы формы 4) и окна ЂЅоковой штампї; пол€ только листа (в Ђƒл€ всех листовї
;; идут лишь в свой лист); пол€ шаблона данных комплекта (без дат).
(setq *sht:StampTags*
  '("C4IZM" "C4KOL" "C4LST" "C4DOC" "C4DAT" "C3IZM" "C3KOL" "C3LST"
    "C3DOC" "C3DAT" "C2IZM" "C2KOL" "C2LST" "C2DOC" "C2DAT" "C1IZM"
    "C1KOL" "C1LST" "C1DOC" "C1DAT" "ROLE1" "NAME1" "DATE1" "ROLE2"
    "NAME2" "DATE2" "ROLE3" "NAME3" "DATE3" "ROLE4" "NAME4" "DATE4"
    "ROLE5" "NAME5" "DATE5" "ROLE6" "NAME6" "DATE6" "SHIFR" "OBJECT"
    "BUILDING" "STAGE" "SHEET" "SHEETS" "TITLE" "ORG" "MASS" "SCALE"
    "MATER"))
(setq *sht:SideTags* '("INV" "VZAM" "SOGL1R" "SOGL1N" "SOGL1D" "SOGL2R" "SOGL2N" "SOGL2D"))
(setq *sht:OneTags* '("SHEET" "SHEETS" "TITLE" "OBOZN" "MASS" "SCALE" "MATER"))
(setq *sht:TplTags*
  '("SHIFR" "OBJECT" "STAGE" "ORG" "ROLE1" "NAME1" "ROLE2" "NAME2"
    "ROLE3" "NAME3" "ROLE4" "NAME4" "ROLE5" "NAME5" "ROLE6" "NAME6"
    "SOGL1R" "SOGL1N" "SOGL2R" "SOGL2N"))
;; ѕоле окна дл€ каждого пол€ штампа (ключи Ч литералом; графа 1 Ч "sht_SHIFR", у форм 4, 5 Ч обозначение)
(setq *sht:FwTiles*
  '(("C4IZM" . "sht_FC4IZM") ("C4KOL" . "sht_FC4KOL") ("C4LST" . "sht_FC4LST") ("C4DOC" . "sht_FC4DOC")
    ("C4DAT" . "sht_FC4DAT") ("C3IZM" . "sht_FC3IZM") ("C3KOL" . "sht_FC3KOL") ("C3LST" . "sht_FC3LST")
    ("C3DOC" . "sht_FC3DOC") ("C3DAT" . "sht_FC3DAT") ("C2IZM" . "sht_FC2IZM") ("C2KOL" . "sht_FC2KOL")
    ("C2LST" . "sht_FC2LST") ("C2DOC" . "sht_FC2DOC") ("C2DAT" . "sht_FC2DAT") ("C1IZM" . "sht_FC1IZM")
    ("C1KOL" . "sht_FC1KOL") ("C1LST" . "sht_FC1LST") ("C1DOC" . "sht_FC1DOC") ("C1DAT" . "sht_FC1DAT")
    ("ROLE1" . "sht_ROLE1") ("NAME1" . "sht_NAME1") ("DATE1" . "sht_DATE1") ("ROLE2" . "sht_ROLE2")
    ("NAME2" . "sht_NAME2") ("DATE2" . "sht_DATE2") ("ROLE3" . "sht_ROLE3") ("NAME3" . "sht_NAME3")
    ("DATE3" . "sht_DATE3") ("ROLE4" . "sht_ROLE4") ("NAME4" . "sht_NAME4") ("DATE4" . "sht_DATE4")
    ("ROLE5" . "sht_ROLE5") ("NAME5" . "sht_NAME5") ("DATE5" . "sht_DATE5") ("ROLE6" . "sht_ROLE6")
    ("NAME6" . "sht_NAME6") ("DATE6" . "sht_DATE6") ("SHIFR" . "sht_SHIFR") ("OBJECT" . "sht_OBJECT")
    ("BUILDING" . "sht_BUILDING") ("STAGE" . "sht_STAGE") ("SHEET" . "sht_FSHEET") ("SHEETS" . "sht_FSHEETS")
    ("TITLE" . "sht_FTITLE") ("ORG" . "sht_ORG") ("MASS" . "sht_FMASS") ("SCALE" . "sht_FSCALE")
    ("MATER" . "sht_FMATER") ("INV" . "sht_INV") ("VZAM" . "sht_VZAM") ("SOGL1R" . "sht_SOGL1R")
    ("SOGL1N" . "sht_SOGL1N") ("SOGL1D" . "sht_SOGL1D") ("SOGL2R" . "sht_SOGL2R") ("SOGL2N" . "sht_SOGL2N")
    ("SOGL2D" . "sht_SOGL2D")))

;; Ќазвани€ полей Ч дл€ сообщений
(setq *sht:CommonNames*
  '(("SHIFR" . "шифр") ("OBJECT" . "объект") ("BUILDING" . "здание") ("STAGE" . "стади€")
    ("ORG" . "организаци€") ("INV" . "инв. є подл.") ("VZAM" . "взам. инв. є")))

;; јлфавиты Ч пор€док букв в номерах листов (1.а, 1.б Е / 1.a, 1.b Е)
(setq *sht:AbcRu* "абвгдеЄжзийклмнопрстуфхцчшщъыьэю€"
      *sht:AbcEn* "abcdefghijklmnopqrstuvwxyz")

;;; --------------------------------------------------------------------------
;;;  2. ”ћќЋ„јЌ»я (последний выбор Ч в реестре, setenv)
;;; --------------------------------------------------------------------------

(defun sht:defaults ( / s)
  (if (not *sht_Fmt*)
    (setq *sht_Fmt* (if (member (setq s (getenv "SHT_Fmt")) *sht:FmtNames*) s "A3")))
  (if (not *sht_Mult*)
    (setq *sht_Mult* (if (and (setq s (getenv "SHT_Mult")) (> (atoi s) 0)) (atoi s) 1)))
  (if (not (sht:fmt-rec *sht_Fmt* *sht_Mult*)) (setq *sht_Mult* 1))
  (if (not *sht_Orient*)
    (setq *sht_Orient* (if (member (setq s (getenv "SHT_Orient")) '("L" "P")) s "L")))
  (if (not *sht_Scale*)
    (setq *sht_Scale* (if (and (setq s (getenv "SHT_Scale")) (distof s 2) (> (distof s 2) 0))
                        (distof s 2) 100.0)))
  (if (sht:portrait-only-p *sht_Fmt* *sht_Mult*) (setq *sht_Orient* "P"))
  (if (not *sht_Form*)
    (setq *sht_Form* (if (member (setq s (getenv "SHT_Form")) *sht:FormsAll*) s "3")))
  (if (not *sht_Title*) (setq *sht_Title* "")))

(defun sht:save-defaults ()
  (setenv "SHT_Fmt" *sht_Fmt*)
  (setenv "SHT_Mult" (itoa *sht_Mult*))
  (setenv "SHT_Orient" *sht_Orient*)
  (setenv "SHT_Scale" (sht:n2s *sht_Scale*))
  (setenv "SHT_Form" *sht_Form*))

;;; --------------------------------------------------------------------------
;;;  3. ”“»Ћ»“џ
;;; --------------------------------------------------------------------------

(defun sht:doc () (vla-get-ActiveDocument (vlax-get-acad-object)))
(defun sht:ms () (vla-get-ModelSpace (sht:doc)))

;; „исло -> строка без лишних нулей: 100.0 -> "100", 2.5 -> "2.5"
(defun sht:n2s (x / s)
  (setq s (rtos x 2 3))
  (if (vl-string-search "." s)
    (setq s (vl-string-right-trim "." (vl-string-right-trim "0" s))))
  s)

(defun sht:trim (s) (if s (vl-string-trim " \t" s) ""))

;; «аменить (или добавить в конец) группу code в списке DXF
(defun sht:dxf-set (ed code val)
  (if (assoc code ed)
    (subst (cons code val) (assoc code ed) ed)
    (append ed (list (cons code val)))))

(defun sht:pt+ (p x y) (list (+ (car p) x) (+ (cadr p) y) 0.0))

;; Ўирина строки s при высоте h (textbox стил€ штампа; запасной Ч 0,7Јh на знак)
(defun sht:str-w (s h / tb)
  (setq tb (vl-catch-all-apply 'textbox (list (list (cons 1 s) (cons 40 h) (cons 7 *sht:Style*)))))
  (if (and tb (not (vl-catch-all-error-p tb)))
    (- (car (cadr tb)) (car (car tb)))
    (* 0.7 h (strlen s))))

;; —троки многострочного текста ("\P" Ч перенос)
(defun sht:split (s sep / i res)
  (while (setq i (vl-string-search sep s))
    (setq res (cons (substr s 1 i) res)
          s   (substr s (+ i 1 (strlen sep)))))
  (reverse (cons s res)))

;;; --------------------------------------------------------------------------
;;;  4. ‘ќ–ћј“џ » ЅЋќ » Ћ»—“ј
;;; --------------------------------------------------------------------------

(defun sht:fmt-rec (name mult / res)
  (foreach r *sht:Formats*
    (if (and (= (car r) name) (= (cadr r) mult)) (setq res r)))
  res)

(defun sht:mults (name / res)
  (foreach r *sht:Formats*
    (if (= (car r) name) (setq res (cons (cadr r) res))))
  (reverse res))

(defun sht:portrait-only-p (name mult)
  (member (cons name mult) *sht:OnlyPortrait*))

;; ЂA4ї, ЂA4x3ї Ч обозначение формата (графа 26)
(defun sht:fmt-label (rec)
  (if (= (cadr rec) 1) (car rec) (strcat (car rec) "x" (itoa (cadr rec)))))

;; Ўирина и высота листа: L Ч длинна€ сторона по горизонтали, P Ч по вертикали
(defun sht:fmt-wh (rec orient)
  (if (= orient "P") (list (caddr rec) (cadddr rec)) (list (cadddr rec) (caddr rec))))

;; »м€ блока: SHT_<формат><L|P>[_<форма>] Ч форма 3 без суффикса; "_4", "_5", "_6" Ч формы 4, 5, 6
;; (s0.2: "_6"); без бокового штампа (s0.10) Ч "N": "_N" (форма 3), "_4N", "_5N", "_6N"
(defun sht:bname (rec orient form)
  (strcat "SHT_" (sht:fmt-label rec) orient
          (cond ((= form "3") "") ((= form "3N") "_N") (t (strcat "_" form)))))

;; »м€ блока -> (запись-формата ориентаци€ форма) или nil:
;; "SHT_A4x3L" -> (("A4" 3 297 630) "L" "3"); "SHT_A3P_6" -> (("A3" 1 297 420) "P" "6");
;; "SHT_A3L_N" -> (Е "L" "3N"); "SHT_A2L_4N" -> (Е "L" "4N")
(defun sht:parse-bname (bn / s o lab i rec form k sfx)
  (setq bn   (strcase bn)
        form "3")
  (if (and (> (strlen bn) 4) (setq k (vl-string-search "_" bn 4)))
    (setq sfx  (substr bn (+ k 2))
          bn   (substr bn 1 k)
          form (cond ((= sfx "N") "3N")
                     ((and (member sfx *sht:FormsAll*) (/= sfx "3") (/= sfx "3N")) sfx))))
  (if (and form (wcmatch bn "SHT_A#*") (> (strlen bn) 6))
    (progn
      (setq s   (substr bn 5)
            o   (substr s (strlen s))
            lab (substr s 1 (1- (strlen s))))
      (if (member o '("L" "P"))
        (progn
          (if (setq i (vl-string-search "X" lab))
            (setq rec (sht:fmt-rec (substr lab 1 i) (atoi (substr lab (+ i 2)))))
            (setq rec (sht:fmt-rec lab 1)))
          (if rec (list rec o form)))))))

;; “аблицы формы штампа (s0.10: формы 4, 5; без бокового штампа Ч без линий, надписей и атрибутов
;; пол€ подшивки: у них угол "BL")
(defun sht:attr-tab (form) (cond ((cdr (assoc form *sht:AttrTabs*))) (*sht:Attrs*)))
(defun sht:side-filter (form lst)
  (if (sht:fside-p form) lst (vl-remove-if '(lambda (x) (= (car x) "BL")) lst)))
(defun sht:lines-of (form / b)
  (setq b (sht:fbase form))
  (append (cond ((= b "6") *sht:Lines6*) ((= b "4") *sht:Lines4*) ((= b "5") *sht:Lines5*) (t *sht:Lines3*))
          (sht:side-filter form *sht:LinesCommon*)))
(defun sht:texts-of (form / b)
  (setq b (sht:fbase form))
  (append (cond ((= b "6") *sht:Texts6*) ((= b "4") *sht:Texts4*) ((= b "5") *sht:Texts5*) (t *sht:Texts3*))
          (sht:side-filter form *sht:TextsCommon*)))

;; ”гол рамки пол€ в мм листа: "BR", "BL", "TR"
(defun sht:anchor (key wh / m)
  (setq m *sht:Margins*)
  (cond ((= key "BR") (list (- (car wh) (caddr m)) (cadr m)))
        ((= key "BL") (list (car m) (cadr m)))
        ((= key "TR") (list (- (car wh) (caddr m)) (- (cadr wh) (cadddr m))))
        (t (list 0.0 0.0))))

(defun sht:lay-of (code) (if (= code "P") *sht:LayFmtP* "0"))
;; —лой атрибута в описании блока (s0.2): слой листа, рамка сквозного номера Ч свой слой
(defun sht:att-lay (code) (if (= code "P") *sht:LayFmtP* *sht:LayFmt*))

;; --- примитивы описани€ блока (entmake внутри BLOCK ... ENDBLK) ---
(defun sht:bd-line (p1 p2 lw lay)
  (entmake (list '(0 . "LINE") (cons 8 lay) (cons 370 lw) (cons 10 p1) (cons 11 p2))))

(defun sht:bd-rect (x1 y1 x2 y2 lw)
  (entmake (list '(0 . "LWPOLYLINE") '(100 . "AcDbEntity") '(8 . "0") (cons 370 lw)
                 '(100 . "AcDbPolyline") '(90 . 4) '(70 . 1)
                 (list 10 x1 y1) (list 10 x2 y1) (list 10 x2 y2) (list 10 x1 y2))))

;; “ексты и атрибуты Ч толщина 0,25 €вно (s0.2: со сло€ 0000_‘ормат брали 0,5 Ч Ђжирныеї)
(defun sht:bd-text (p s h wf rot hj vj)
  (entmake (list '(0 . "TEXT") '(8 . "0") (cons 370 *sht:LwText*) (cons 10 p) (cons 40 h) (cons 1 s)
                 (cons 50 rot) (cons 41 wf) (cons 7 *sht:Style*)
                 (cons 72 hj) (cons 73 vj) (cons 11 p))))

(defun sht:bd-attdef (p tag prompt def h rot hj vj lay flags)
  (entmake (list '(0 . "ATTDEF") '(100 . "AcDbEntity") (cons 8 lay) (cons 370 *sht:LwText*)
                 '(100 . "AcDbText") (cons 10 p) (cons 40 h) (cons 1 def) (cons 50 rot)
                 '(41 . 1.0) (cons 7 *sht:Style*) (cons 72 hj) (cons 11 p)
                 '(100 . "AcDbAttributeDefinition") (cons 3 prompt) (cons 2 tag) (cons 70 flags)
                 (cons 74 vj))))

(defun sht:deg (a) (* pi (/ a 180.0)))

;; ќписание блока листа rec / orient / form (создать или переопределить)
(defun sht:block-def (rec orient form / name wh w h m a l t1 at tab)
  (setq name (sht:bname rec orient form)
        wh   (sht:fmt-wh rec orient)
        w    (car wh)
        h    (cadr wh)
        m    *sht:Margins*
        tab  (sht:attr-tab form))
  (entmake (list '(0 . "BLOCK") (cons 2 name) '(70 . 2) '(10 0.0 0.0 0.0)))
  ;; обрезна€ рамка (тонка€) и рамка пол€
  (sht:bd-rect 0.0 0.0 w h *sht:LwThin*)
  (sht:bd-rect (car m) (cadr m) (- w (caddr m)) (- h (cadddr m)) *sht:LwThick*)
  (foreach l (sht:lines-of form)
    (setq a (sht:anchor (car l) wh))
    (sht:bd-line (sht:pt+ a (nth 1 l) (nth 2 l)) (sht:pt+ a (nth 3 l) (nth 4 l))
                 (nth 5 l) (sht:lay-of (nth 6 l))))
  (foreach t1 (sht:texts-of form)
    (sht:bd-text (sht:pt+ (sht:anchor (car t1) wh) (nth 1 t1) (nth 2 t1))
                 (nth 3 t1) (nth 4 t1) (nth 5 t1) (sht:deg (nth 6 t1)) (nth 7 t1) (nth 8 t1)))
  (foreach at tab
    (sht:bd-attdef (sht:pt+ (sht:anchor (nth 3 at) wh) (nth 4 at) (nth 5 at))
                   (nth 0 at) (nth 1 at) (sht:att-default at rec orient) (nth 6 at) (sht:deg (nth 7 at))
                   (nth 8 at) (nth 9 at) (sht:att-lay (nth 12 at)) (nth 14 at)))
  (entmake '((0 . "ENDBLK")))
  (sht:ml-attdefs name wh tab)
  name)

;; «начение атрибута по умолчанию; FORMAT и ORIENT Ч формат и ориентаци€ этого блока
;; (ATTSYNC добавит их в листы прежних версий уже с верными значени€ми)
(defun sht:att-default (at rec orient)
  (cond ((= (car at) "FORMAT") (sht:fmt-label rec))
        ((= (car at) "ORIENT") (sht:orient-name orient))
        (t (nth 2 at))))

(defun sht:orient-name (o) (if (= o "P") "вертикальна€" "горизонтальна€"))

;; ћногострочные атрибуты (графы 2, 3, 4, 9): через ActiveX Ч свойство MTextAttribute.
;; Ќе вышло Ч атрибут остаЄтс€ однострочным (длинный текст сжимаетс€ по ширине).
(defun sht:ml-attdefs (name wh tab / blk at r n need)
  (setq n    0
        need (vl-some '(lambda (x) (nth 11 x)) tab)
        blk  (vl-catch-all-apply 'vla-Item (list (vla-get-Blocks (sht:doc)) name)))
  (if (and need (not (vl-catch-all-error-p blk)))
    (vlax-for o blk
      (if (and (= (vla-get-ObjectName o) "AcDbAttributeDefinition")
               (setq at (assoc (vla-get-TagString o) tab))
               (nth 11 at))
        (progn
          (setq r (vl-catch-all-apply 'vla-put-MTextAttribute (list o :vlax-true)))
          (if (not (vl-catch-all-error-p r))
            (progn
              (setq n (1+ n))
              (vl-catch-all-apply 'vla-put-MTextBoundaryWidth (list o (nth 10 at)))
              (vl-catch-all-apply 'vla-put-Alignment (list o 10))   ; acAlignmentMiddleCenter
              (vl-catch-all-apply 'vla-put-TextAlignmentPoint
                (list o (vlax-3d-point (sht:pt+ (sht:anchor (nth 3 at) wh) (nth 4 at) (nth 5 at)))))))))))
  (if (and need (= n 0))
    (princ "\n! SHEETS: многострочные атрибуты не созданы - длинный текст будет сжат в одну строку."))
  n)

;; Ѕлок листа есть? Ќет Ч описать.
(defun sht:block-ensure (rec orient form / name)
  (setq name (sht:bname rec orient form))
  (if (not (tblsearch "BLOCK" name))
    (sht:block-def rec orient form))
  name)

;; ¬ерси€ описаний блоков помен€лась Ч переопределить все блоки листов чертежа (ATTSYNC Ч атрибуты),
;; затем вписать тексты всех листов заново (ATTSYNC возвращает высоты и сжатие к описанию)
(defun sht:blocks-refresh (sdat / r p n names ce)
  (setq n 0)
  (if (/= (cdr (assoc "@BLKVER" sdat)) *sht:BlkVer*)
    (progn
      ;; сначала собрать имена, потом переопредел€ть (не трогать таблицу блоков во врем€ перебора)
      (setq r (tblnext "BLOCK" T))
      (while r
        (if (sht:parse-bname (cdr (assoc 2 r)))
          (setq names (cons (cdr (assoc 2 r)) names)))
        (setq r (tblnext "BLOCK")))
      (setq ce (getvar "CMDECHO"))
      (setvar "CMDECHO" 0)
      (foreach bn (reverse names)
        (setq p (sht:parse-bname bn))
        (sht:block-def (car p) (cadr p) (caddr p))
        (command "_.ATTSYNC" "_N" bn)
        (setq n (1+ n)))
      (setvar "CMDECHO" ce)
      (if (> n 0)
        (progn
          (sht:fit-all)
          (sht:watch)
          (princ (strcat "\nSHEETS: описани€ блоков листов обновлены: " (itoa n)))))
      (sht:set-write (sht:alist-put sdat "@BLKVER" *sht:BlkVer*))))
  n)

;;; --------------------------------------------------------------------------
;;;  5. —Ћќ», —“»Ћ№, ƒјЌЌџ≈  ќћѕЋ≈ “ј (словарь чертежа SHT_SET)
;;; --------------------------------------------------------------------------

(defun sht:layer (name / pr en ed)
  (setq pr (cdr (assoc name *sht:LayProps*)))
  (if (not pr) (setq pr (list 7 -3)))
  (if (setq en (tblobjname "LAYER" name))
    ;; слой есть: включить, разблокировать (4); заморозку (1) решает sht:stage-layer
    (progn
      (setq ed (entget en)
            ed (sht:dxf-set ed 70 (logand (cond ((cdr (assoc 70 ed))) (0)) (~ 4))))
      (if (< (cond ((cdr (assoc 62 ed))) (7)) 0)
        (setq ed (sht:dxf-set ed 62 (abs (cdr (assoc 62 ed))))))
      (entmod ed))
    (entmake (list '(0 . "LAYER") '(100 . "AcDbSymbolTableRecord") '(100 . "AcDbLayerTableRecord")
                   (cons 2 name) '(70 . 0) (cons 62 (car pr)) '(6 . "Continuous") (cons 370 (cadr pr))))))

;; —тади€ ѕ Ч рамка сквозного номера видна, иначе слой заморожен
(defun sht:stage-layer (stage / en ed fl old frz)
  (setq frz (/= (strcase (sht:trim stage)) "ѕ"))
  (if (setq en (tblobjname "LAYER" *sht:LayFmtP*))
    (progn
      (setq ed  (entget en)
            old (cond ((cdr (assoc 70 ed))) (0))
            fl  old)
      (if (and frz (/= (strcase (getvar "CLAYER")) (strcase *sht:LayFmtP*)))
        (setq fl (logior fl 1))
        (setq fl (logand fl (~ 1))))
      ;; заморозка помен€лась Ч записать и перерисовать
      (if (/= fl old)
        (progn
          (entmod (sht:dxf-set ed 70 fl))
          (vl-catch-all-apply 'vla-Regen (list (sht:doc) 0))))))   ; 0 Ч acActiveViewport
  (not frz))

(defun sht:style ()
  (if (not (tblsearch "STYLE" *sht:Style*))
    (entmake (list '(0 . "STYLE") '(100 . "AcDbSymbolTableRecord") '(100 . "AcDbTextStyleTableRecord")
                   (cons 2 *sht:Style*) '(70 . 0) '(40 . 0.0) '(41 . 1.0) '(50 . 0.0) '(71 . 0)
                   '(42 . 2.5) (cons 3 *sht:StyleFont*) '(4 . "")))))

;; alist: заменить / добавить пару
(defun sht:alist-put (al key val)
  (if (assoc key al)
    (subst (cons key val) (assoc key al) al)
    (append al (list (cons key val)))))

;; ƒанные комплекта из словар€ чертежа: (("SHIFR" . "Е") Е), ключи "@Е" Ч служебные
(defun sht:set-read ( / d res key)
  (if (setq d (dictsearch (namedobjdict) *sht:SetKey*))
    (foreach g d
      (cond ((= (car g) 300)
             (setq key (cdr g)
                   res (cons (cons key "") res)))
            ((and key (= (car g) 301))
             (setq res (cons (cons key (strcat (cdar res) (cdr g))) (cdr res)))))))
  (reverse res))

;; —трока -> куски по 250 знаков (группы 301)
(defun sht:chunks (s / res)
  (while (> (strlen s) 250)
    (setq res (cons (cons 301 (substr s 1 250)) res)
          s   (substr s 251)))
  (reverse (cons (cons 301 s) res)))

(defun sht:set-write (al / nod lst old xr)
  (setq nod (namedobjdict)
        lst (list '(0 . "XRECORD") '(100 . "AcDbXrecord")))
  (foreach p al
    (setq lst (append lst (list (cons 300 (car p))) (sht:chunks (cdr p)))))
  (if (setq old (dictsearch nod *sht:SetKey*))
    (progn
      (dictremove nod *sht:SetKey*)
      (vl-catch-all-apply 'entdel (list (cdr (assoc -1 old))))))
  (if (setq xr (entmakex lst))
    (dictadd nod *sht:SetKey* xr)))

;; ѕодготовка чертежа: стиль, слои, верси€ блоков. ¬озвращает данные комплекта.
(defun sht:prepare ()
  (sht:style)
  (sht:layer *sht:LayFmt*)
  (sht:layer *sht:LayFmtP*)
  (sht:blocks-refresh (sht:set-read))
  (sht:set-read))

;;; --------------------------------------------------------------------------
;;;  6. Ћ»—“џ „≈–“≈∆ј: поиск, атрибуты, номера
;;; --------------------------------------------------------------------------

;; ¬се листы (вставки SHT_*) в пространстве модели
(defun sht:sheets ( / ss i en ed res)
  (if (setq ss (ssget "_X" '((0 . "INSERT") (2 . "SHT_*"))))
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq en (ssname ss i)
              ed (entget en)
              i  (1+ i))
        (if (and (sht:parse-bname (cdr (assoc 2 ed)))
                 (= (strcase (cond ((cdr (assoc 410 ed))) ("Model"))) "MODEL"))
          (setq res (cons en res))))))
  (reverse res))

(defun sht:att-objs (en / r)
  (setq r (vl-catch-all-apply 'vlax-invoke (list (vlax-ename->vla-object en) 'GetAttributes)))
  (if (vl-catch-all-error-p r) nil r))

;; јтрибуты листа: (("SHEET" . "3") ("TITLE" . "Е") Е)
(defun sht:attrs (en / res)
  (foreach a (sht:att-objs en)
    (setq res (cons (cons (strcase (vla-get-TagString a)) (vla-get-TextString a)) res)))
  (reverse res))



(defun sht:int-p (s) (and (> (atoi s) 0) (= (itoa (atoi s)) s)))

;; √руппа нумерации листа (s0.10): листы форм 4 и 5 нумеруютс€ внутри своего документа (графа 1,
;; OBOZN; без учЄта регистра и пробелов по кра€м), остальные Ч нумерацией основного комплекта
(defun sht:num-group (form obozn)
  (if (sht:fdoc-p form) (strcat "D:" (sht:lc (sht:trim obozn))) "M"))

;; Ќомера листов ens по группам: ((группа . номер) Е), пустые Ч нет
(defun sht:gnums (ens / inf a s res)
  (foreach en ens
    (setq inf (sht:sheet-info en)
          a   (sht:attrs en)
          s   (sht:trim (cdr (assoc "SHEET" a))))
    (if (/= s "")
      (setq res (cons (cons (sht:num-group (caddr inf) (cdr (assoc "OBOZN" a))) s) res))))
  (reverse res))

;; Ќомера группы g из списка sht:gnums
(defun sht:gnums-of (g gnl / res)
  (foreach p gnl (if (= (car p) g) (setq res (cons (cdr p) res))))
  (reverse res))

;; —ледующий свободный номер: наибольший целый + 1
(defun sht:next-num (nums / mx)
  (setq mx 0)
  (foreach s nums
    (if (sht:int-p s) (setq mx (max mx (atoi s)))))
  (itoa (1+ mx)))

;; ≈сть ли номер s среди nums (без учЄта регистра и пробелов)
(defun sht:num-used-p (s nums)
  (setq s (strcase (sht:trim s)))
  (vl-some '(lambda (x) (= (strcase x) s)) nums))

;; ѕор€док номеров листов: 1 < 1.1 < 1.2 < 1.10 < 1.а < 1.б < 2 < 2.1 < 10.
;; „асти через Ђ.ї; в части Ч число, затем буквы (кириллица и латиница Ч по алфавиту).
(defun sht:tok-key (tok / i n c r)
  (setq i 1 n 0)
  (while (and (<= i (strlen tok)) (wcmatch (setq c (substr tok i 1)) "#"))
    (setq n (+ (* n 10) (atoi c))
          i (1+ i)))
  (setq c (strcase (substr tok i 1) T)
        r (cond ((= c "") 0)
                ((setq r (vl-string-search c *sht:AbcRu*)) (1+ r))
                ((setq r (vl-string-search c *sht:AbcEn*)) (+ 101 r))
                (t 200)))
  (if (> i 1) (list 0 n r) (list 1 0 r)))

(defun sht:num-key (s / res)
  (setq s (sht:trim s))
  (if (= s "")
    (list 9)
    (progn
      (foreach tok (sht:split s ".")
        (setq res (append res (sht:tok-key tok))))
      res)))

(defun sht:key< (a b)
  (cond ((null a) (not (null b)))
        ((null b) nil)
        ((< (car a) (car b)) T)
        ((> (car a) (car b)) nil)
        (t (sht:key< (cdr a) (cdr b)))))

(defun sht:num< (a b) (sht:key< (sht:num-key a) (sht:num-key b)))

(defun sht:sort-nums (nums) (vl-sort nums 'sht:num<))

;; —амое частое значение (при равенстве Ч встретившеес€ раньше)
(defun sht:most (vals / cnt best p)
  (foreach v vals
    (if (setq p (assoc v cnt))
      (setq cnt (subst (cons v (1+ (cdr p))) p cnt))
      (setq cnt (append cnt (list (cons v 1))))))
  (setq best (car cnt))
  (foreach p cnt (if (> (cdr p) (cdr best)) (setq best p)))
  (car best))

;; ќбщие пол€ сейчас: на листах Ч самое частое значение; листов нет Ч словарь чертежа,
;; затем умолчани€. ¬озвращает (значени€ разные-пол€).
(defun sht:common-now (attrs sdat) (sht:fw-now *sht:Common* attrs sdat))

;; ќбъект Ч лист SHEETS? (вставка блока SHT_Е)
(defun sht:sheet-p (en / ed)
  (and en
       (setq ed (entget en))
       (= (cdr (assoc 0 ed)) "INSERT")
       (sht:parse-bname (cdr (assoc 2 ed)))))

;; —ведени€ о листе: (запись-формата ориентаци€ форма масштаб точка-вставки)
(defun sht:sheet-info (en / ed p)
  (setq ed (entget en)
        p  (sht:parse-bname (cdr (assoc 2 ed))))
  (if p
    (list (car p) (cadr p) (caddr p) (cond ((cdr (assoc 41 ed))) (1.0)) (cdr (assoc 10 ed)))))

;; јтрибут на слое листа и толщиной 0,25 (s0.2: со сло€ 0000_‘ормат он брал 0,5 Ч Ђжирныйї)
(defun sht:att-norm (a tag)
  (vl-catch-all-apply 'vla-put-Layer (list a (if (= tag "PNUM") *sht:LayFmtP* *sht:LayFmt*)))
  (vl-catch-all-apply 'vla-put-Lineweight (list a *sht:LwText*)))

;; «аписать значение атрибута и вписать его в €чейку (tab Ч таблица атрибутов формы)
(defun sht:att-set (a val sc tab / at)
  (vla-put-TextString a val)
  (if (setq at (assoc (strcase (vla-get-TagString a)) tab))
    (sht:att-fit a at sc)))

;; —колько строк займЄт текст s высотой h в ширину w (перенос по словам, "\P" Ч нова€ строка)
(defun sht:wrap-n (s h w / n line cand)
  (setq n 0)
  (foreach para (sht:split s "\\P")
    (setq line ""
          n    (1+ n))
    (foreach wd (sht:split para " ")
      (setq cand (if (= line "") wd (strcat line " " wd)))
      (if (and (/= line "") (> (sht:str-w cand h) w))
        (setq n    (1+ n)
              line wd)
        (setq line cand))))
  (max n 1))

;; ¬писать атрибут в €чейку (s0.2):
;;  однострочный Ч сжать по ширине до 0,5; не хватило Ч уменьшить высоту (не ниже 1,8 мм листа);
;;  многострочный Ч ширина переноса = ширине €чейки, высота 3,5 -> 2,5 -> 1,8, чтобы строки
;;  поместились в высоту €чейки (с зазором 1 мм).
(defun sht:att-fit (a at sc / s h w ch ml need wf hh done)
  (setq s  (vla-get-TextString a)
        h  (* (nth 6 at) sc)
        w  (* (nth 10 at) sc)
        ch (* (nth 13 at) sc)
        ml (vl-catch-all-apply 'vla-get-MTextAttribute (list a)))
  (setq ml (and (nth 11 at) (not (vl-catch-all-error-p ml)) (= ml :vlax-true)))
  (if ml
    (progn
      (vl-catch-all-apply 'vla-put-MTextBoundaryWidth (list a w))
      (foreach hh (list h (* 2.5 sc) (* *sht:MinH* sc))
        (if (and (not done) (<= hh h)
                 (<= (* hh (+ 1.0 (* *sht:LineSp* (1- (sht:wrap-n s hh w))))) (- ch sc)))
          (setq done hh)))
      (vl-catch-all-apply 'vla-put-Height (list a (cond (done) ((* *sht:MinH* sc)))))
      (vl-catch-all-apply 'vla-put-MTextBoundaryWidth (list a w)))
    (progn
      (setq need (apply 'max (cons 0.0 (mapcar '(lambda (x) (sht:str-w x h)) (sht:split s "\\P"))))
            wf   (if (> need w) (/ w need) 1.0)
            hh   h)
      (if (< wf *sht:MinWf*)
        (setq hh (max (* *sht:MinH* sc) (* h (/ wf *sht:MinWf*)))
              wf *sht:MinWf*))
      (vl-catch-all-apply 'vla-put-Height (list a hh))
      (vl-catch-all-apply 'vla-put-ScaleFactor (list a wf)))))

;; ¬писать все атрибуты листа (и слой, толщина)
(defun sht:fit-sheet (en / inf tab sc tag at)
  (if (setq inf (sht:sheet-info en))
    (progn
      (setq tab (sht:attr-tab (caddr inf))
            sc  (cadddr inf))
      (foreach a (sht:att-objs en)
        (setq tag (strcase (vla-get-TagString a)))
        (sht:att-norm a tag)
        (if (setq at (assoc tag tab))
          (sht:att-fit a at sc))))))

(defun sht:fit-all ( / n)
  (setq n 0)
  (foreach en (sht:sheets)
    (sht:fit-sheet en)
    (setq n (1+ n)))
  n)

;; «аписать изменЄнные общие пол€ во все листы. changed Ч (("SHIFR" . "Е") Е)
(defun sht:apply-common (changed ens / n p inf)
  (setq n 0)
  (if changed
    (foreach en ens
      (setq inf (sht:sheet-info en)
            n   (1+ n))
      (foreach a (sht:att-objs en)
        (if (setq p (assoc (strcase (vla-get-TagString a)) changed))
          (sht:att-set a (cdr p) (cadddr inf) (sht:attr-tab (caddr inf)))))))
  (if (assoc "STAGE" changed) (sht:stage-layer (cdr (assoc "STAGE" changed))))
  n)

;; ¬ставить лист: rec orient form Ч формат и штамп, pt Ч левый нижний угол листа, sc Ч масштаб,
;; vals Ч значени€ атрибутов. ¬озвращает ename вставки.
(defun sht:insert (rec orient form pt sc vals / name ins tag p en)
  (setq vals (sht:alist-put (sht:alist-put vals "FORMAT" (sht:fmt-label rec)) "ORIENT" (sht:orient-name orient))
        name (sht:block-ensure rec orient form)
        ins  (vla-InsertBlock (sht:ms) (vlax-3d-point pt) name sc sc sc 0.0))
  (vla-put-Layer ins *sht:LayFmt*)
  (foreach a (vlax-invoke ins 'GetAttributes)
    (setq tag (strcase (vla-get-TagString a)))
    (if (setq p (assoc tag vals))
      (vla-put-TextString a (cdr p))))
  (setq en (vlax-vla-object->ename ins))
  (sht:fit-sheet en)
  en)

;; «аменить лист другим форматом / ориентацией / штампом / масштабом на том же месте
;; (левый нижний угол). «начени€: vals (общие пол€) <- прежние атрибуты листа <- new (лист, наименование).
(defun sht:replace (en rec orient form sc vals new / inf old)
  (setq inf (sht:sheet-info en)
        old (sht:attrs en))
  (foreach p old (setq vals (sht:alist-put vals (car p) (cdr p))))
  (foreach p new (setq vals (sht:alist-put vals (car p) (cdr p))))
  (setq new (sht:insert rec orient form (nth 4 inf) sc vals))
  (entdel en)
  new)

;;; --------------------------------------------------------------------------
;;;  9. ќ Ќј (DCL)
;;; --------------------------------------------------------------------------

(defun sht:dcl-lines ()
  (list
    "sht_sheet : dialog {"
    (strcat "  label = \"Ћист (SHEETS " *sht:Version* ")\";")
    "  : text { key = \"sht_Info\"; width = 72; }"
    "  : boxed_column {"
    "    label = \"‘ормат\";"
    "    : row {"
    "      : popup_list { key = \"sht_Fmt\"; label = \"‘ормат\"; width = 22; }"
    "      : popup_list { key = \"sht_Mult\"; label = \" ратность\"; width = 24; }"
    "    }"
    "    : radio_row {"
    "      key = \"sht_Or\";"
    "      : radio_button { key = \"sht_OrL\"; label = \"√оризонтальный\"; }"
    "      : radio_button { key = \"sht_OrP\"; label = \"¬ертикальный\"; }"
    "    }"
    "    : popup_list { key = \"sht_Form\"; label = \"Ўтамп\"; width = 66; }"
    "    : toggle { key = \"sht_Side\"; label = \"Ѕоковой штамп (поле подшивки: инв. є подл., подп. и дата, взам. инв. є, согласовано)\"; }"
    "    : text { key = \"sht_Size\"; width = 72; }"
    "  }"
    "  : boxed_column {"
    "    label = \"Ћист\";"
    "    : row {"
    "      : edit_box { key = \"sht_Scale\"; label = \"ћасштаб 1:\"; edit_width = 8; }"
    "      : edit_box { key = \"sht_Sheet\"; label = \"Ћист є\"; edit_width = 8; }"
    "    }"
    "    : edit_box { key = \"sht_Obozn\"; label = \"ќбозначение документа (гр. 1; формы 4 и 5)\"; edit_width = 40; edit_limit = 250; }"
    "    : edit_box { key = \"sht_Title\"; label = \"Ќаименование (гр. 4; у форм 4 и 5 - гр. 5)\"; edit_width = 56; edit_limit = 250; }"
    "  }"
    "  : row {"
    "    : button { key = \"sht_Data\"; label = \"ƒанные комплекта...\"; width = 28; fixed_width = true; }"
    "    : text { key = \"sht_DataInfo\"; width = 44; }"
    "  }"
    "  : row {"
    "    : button { key = \"sht_SideB\"; label = \"ƒанные бокового штампа...\"; width = 28; fixed_width = true; }"
    "    : text { key = \"sht_SideInfo\"; width = 44; }"
    "  }"
    "  : row {"
    "    : button { key = \"sht_Attr\"; label = \"¬се пол€ штампа...\"; width = 28; fixed_width = true; }"
    "    : text { key = \"sht_AttrInfo\"; width = 44; }"
    "  }"
    "  errtile;"
    "  ok_cancel;"
    "}"
    ""
    "sht_data : dialog {"
    "  label = \"Ўтамп - основна€ надпись\";"
    "  : text { key = \"sht_DataNote\"; width = 100; }"
    "  : text { key = \"sht_DataDiff\"; width = 100; }"
    "  : row {"
    "    : column {"
    "      fixed_width = true;"
    "      : row { fixed_width = true; : edit_box { key = \"sht_FC4IZM\"; width = 4; edit_width = 4; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC4KOL\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC4LST\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC4DOC\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_FC4DAT\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "      : row { fixed_width = true; : edit_box { key = \"sht_FC3IZM\"; width = 4; edit_width = 4; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC3KOL\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC3LST\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC3DOC\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_FC3DAT\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "      : row { fixed_width = true; : edit_box { key = \"sht_FC2IZM\"; width = 4; edit_width = 4; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC2KOL\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC2LST\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC2DOC\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_FC2DAT\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "      : row { fixed_width = true; : edit_box { key = \"sht_FC1IZM\"; width = 4; edit_width = 4; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC1KOL\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC1LST\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FC1DOC\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_FC1DAT\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "      : row { fixed_width = true; : text { label = \"»зм.\"; width = 4; fixed_width = true; } : text { label = \" ол.уч.\"; width = 6; fixed_width = true; } : text { label = \"Ћист\"; width = 6; fixed_width = true; } : text { label = \"є док.\"; width = 6; fixed_width = true; } : text { label = \"ѕодп.\"; width = 8; fixed_width = true; } : text { label = \"ƒата\"; width = 6; fixed_width = true; } }"
    "      : row { fixed_width = true; : edit_box { key = \"sht_ROLE1\"; width = 10; edit_width = 10; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_NAME1\"; width = 12; edit_width = 12; fixed_width = true; edit_limit = 60; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_DATE1\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "      : row { fixed_width = true; : edit_box { key = \"sht_ROLE2\"; width = 10; edit_width = 10; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_NAME2\"; width = 12; edit_width = 12; fixed_width = true; edit_limit = 60; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_DATE2\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "      : row { fixed_width = true; : edit_box { key = \"sht_ROLE3\"; width = 10; edit_width = 10; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_NAME3\"; width = 12; edit_width = 12; fixed_width = true; edit_limit = 60; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_DATE3\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "      : row { fixed_width = true; : edit_box { key = \"sht_ROLE4\"; width = 10; edit_width = 10; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_NAME4\"; width = 12; edit_width = 12; fixed_width = true; edit_limit = 60; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_DATE4\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "      : row { fixed_width = true; : edit_box { key = \"sht_ROLE5\"; width = 10; edit_width = 10; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_NAME5\"; width = 12; edit_width = 12; fixed_width = true; edit_limit = 60; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_DATE5\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "      : row { fixed_width = true; : edit_box { key = \"sht_ROLE6\"; width = 10; edit_width = 10; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_NAME6\"; width = 12; edit_width = 12; fixed_width = true; edit_limit = 60; } : edit_box { width = 8; edit_width = 8; fixed_width = true; is_enabled = false; } : edit_box { key = \"sht_DATE6\"; width = 6; edit_width = 6; fixed_width = true; edit_limit = 20; } }"
    "    }"
    "    : column {"
    "      : text { key = \"sht_FG1Tx\"; width = 66; }"
    "      : edit_box { key = \"sht_SHIFR\"; width = 66; edit_width = 66; fixed_width = true; edit_limit = 250; }"
    "      : text { label = \"ќбъект (гр. 2)\"; width = 66; }"
    "      : edit_box { key = \"sht_OBJECT\"; width = 66; edit_width = 66; fixed_width = true; edit_limit = 250; }"
    "      : row {"
    "        : column { : text { label = \"«дание, сооружение (гр. 3)\"; width = 38; fixed_width = true; } : edit_box { key = \"sht_BUILDING\"; width = 38; edit_width = 38; fixed_width = true; edit_limit = 250; } }"
    "        : column {"
    "          : row { fixed_width = true; : text { label = \"—тади€\"; width = 8; fixed_width = true; } : text { label = \"Ћист\"; width = 8; fixed_width = true; } : text { label = \"Ћистов\"; width = 10; fixed_width = true; } }"
    "          : row { fixed_width = true; : edit_box { key = \"sht_STAGE\"; width = 8; edit_width = 8; fixed_width = true; edit_limit = 10; } : edit_box { key = \"sht_FSHEET\"; width = 8; edit_width = 8; fixed_width = true; edit_limit = 20; } : edit_box { key = \"sht_FSHEETS\"; width = 10; edit_width = 10; fixed_width = true; edit_limit = 20; } }"
    "        }"
    "      }"
    "      : row {"
    "        : column { : text { key = \"sht_FTitleTx\"; width = 38; fixed_width = true; } : edit_box { key = \"sht_FTITLE\"; width = 38; edit_width = 38; fixed_width = true; edit_limit = 250; } }"
    "        : column { : text { label = \"ќрганизаци€ (гр. 9)\"; width = 28; fixed_width = true; } : edit_box { key = \"sht_ORG\"; width = 28; edit_width = 28; fixed_width = true; edit_limit = 250; } }"
    "      }"
    "    }"
    "  }"
    "  : boxed_row {"
    "    label = \"“олько у формы 4 (чертежи строительных изделий)\";"
    "    : edit_box { key = \"sht_FMASS\"; label = \"ћасса (гр. 24)\"; edit_width = 8; edit_limit = 20; }"
    "    : edit_box { key = \"sht_FSCALE\"; label = \"ћасштаб (гр. 25)\"; edit_width = 8; edit_limit = 20; }"
    "    : edit_box { key = \"sht_FMATER\"; label = \"ћатериал (гр. 23)\"; edit_width = 30; edit_limit = 250; }"
    "  }"
    "  : text { key = \"sht_FMsg\"; width = 100; }"
    "  errtile;"
    "  : row {"
    "    : button { key = \"sht_TplLoad\"; label = \"¬ыбрать шаблон...\"; width = 20; fixed_width = true; }"
    "    : button { key = \"sht_TplSave\"; label = \"—охранить шаблон...\"; width = 20; fixed_width = true; }"
    "    : spacer { width = 1; }"
    "    : button { key = \"sht_One\"; label = \"ƒл€ этого листа\"; width = 18; fixed_width = true; }"
    "    : button { key = \"accept\"; label = \"ƒл€ всех листов\"; width = 18; fixed_width = true; is_default = true; }"
    "    : button { key = \"cancel\"; label = \"ќтмена\"; width = 12; fixed_width = true; is_cancel = true; }"
    "  }"
    "}"
    ""
    "sht_side : dialog {"
    "  label = \"Ѕоковой штамп - поле подшивки\";"
    "  : text { key = \"sht_DataNote\"; width = 100; }"
    "  : text { key = \"sht_DataDiff\"; width = 100; }"
    "  : boxed_column {"
    "    label = \"—огласовано\";"
    "    : row { fixed_width = true; : text { label = \"ƒолжность\"; width = 16; fixed_width = true; } : text { label = \"‘амили€\"; width = 22; fixed_width = true; } : text { label = \"ƒата\"; width = 9; fixed_width = true; } }"
    "    : row { fixed_width = true; : edit_box { key = \"sht_SOGL1R\"; width = 16; edit_width = 16; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_SOGL1N\"; width = 22; edit_width = 22; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_SOGL1D\"; width = 9; edit_width = 9; fixed_width = true; edit_limit = 20; } }"
    "    : row { fixed_width = true; : edit_box { key = \"sht_SOGL2R\"; width = 16; edit_width = 16; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_SOGL2N\"; width = 22; edit_width = 22; fixed_width = true; edit_limit = 60; } : edit_box { key = \"sht_SOGL2D\"; width = 9; edit_width = 9; fixed_width = true; edit_limit = 20; } }"
    "  }"
    "  : boxed_row {"
    "    label = \"»нвентарные номера\";"
    "    : edit_box { key = \"sht_VZAM\"; label = \"¬зам. инв. є (гр. 22)\"; edit_width = 14; edit_limit = 40; }"
    "    : edit_box { key = \"sht_INV\"; label = \"»нв. є подл. (гр. 20)\"; edit_width = 14; edit_limit = 40; }"
    "  }"
    "  : text { key = \"sht_FMsg\"; width = 100; }"
    "  errtile;"
    "  : row {"
    "    : button { key = \"sht_TplLoad\"; label = \"¬ыбрать шаблон...\"; width = 20; fixed_width = true; }"
    "    : button { key = \"sht_TplSave\"; label = \"—охранить шаблон...\"; width = 20; fixed_width = true; }"
    "    : spacer { width = 1; }"
    "    : button { key = \"sht_One\"; label = \"ƒл€ этого листа\"; width = 18; fixed_width = true; }"
    "    : button { key = \"accept\"; label = \"ƒл€ всех листов\"; width = 18; fixed_width = true; is_default = true; }"
    "    : button { key = \"cancel\"; label = \"ќтмена\"; width = 12; fixed_width = true; is_cancel = true; }"
    "  }"
    "}"
    ""
    "sht_tpl : dialog {"
    "  label = \"Ўаблоны данных комплекта\";"
    "  : text { key = \"sht_TDir\"; width = 80; }"
    "  : list_box { key = \"sht_TList\"; width = 80; height = 10; }"
    "  : edit_box { key = \"sht_TName\"; label = \"»м€ шаблона\"; edit_width = 50; edit_limit = 100; }"
    "  : text { key = \"sht_TInfo\"; width = 80; }"
    "  : text { key = \"sht_TInfo2\"; width = 80; }"
    "  : text { label = \"¬ шаблоне: шифр, объект, стади€, организаци€, должности и фамилии, согласовано (без дат).\"; }"
    "  errtile;"
    "  : row {"
    "    : button { key = \"sht_TDirB\"; label = \"ѕапка...\"; width = 12; fixed_width = true; }"
    "    : button { key = \"sht_TDel\"; label = \"”далить\"; width = 12; fixed_width = true; }"
    "    : spacer { width = 1; }"
    "    : button { key = \"sht_TUse\"; label = \"ѕодставить\"; width = 14; fixed_width = true; is_default = true; }"
    "    : button { key = \"sht_TSave\"; label = \"—охранить\"; width = 14; fixed_width = true; }"
    "    : button { key = \"cancel\"; label = \"ќтмена\"; width = 12; fixed_width = true; is_cancel = true; }"
    "  }"
    "}"
    ""
    "sht_plot : dialog {"
    (strcat "  label = \"ѕечать в PDF (SHEETS " *sht:Version* ")\";")
    "  : boxed_column {"
    "    label = \"Ћисты - по пор€дку номеров (щелчок отмечает / снимает)\";"
    "    : list_box { key = \"sht_PList\"; multiple_select = true; width = 90; height = 16; tabs = \"8 22 31\"; }"
    "    : row {"
    "      : button { key = \"sht_PAll\"; label = \"¬се\"; width = 10; fixed_width = true; }"
    "      : button { key = \"sht_PNone\"; label = \"Ќи одного\"; width = 12; fixed_width = true; }"
    "      : button { key = \"sht_PSel\"; label = \"¬ыбрать в чертеже <\"; width = 22; fixed_width = true; }"
    "      : edit_box { key = \"sht_PNums\"; label = \"Ќомера:\"; edit_width = 16; edit_limit = 250; }"
    "      : button { key = \"sht_PNumsGo\"; label = \"ќтметить\"; width = 12; fixed_width = true; is_default = true; }"
    "    }"
    "    : text { key = \"sht_PCount\"; width = 90; }"
    "    : text { key = \"sht_POff\"; width = 90; }"
    "  }"
    "  : boxed_radio_row {"
    "    key = \"sht_PMode\";"
    "    label = \"¬ывод\";"
    "    : radio_button { key = \"sht_PModeAll\"; label = \"ќдин PDF - весь комплект\"; }"
    "    : radio_button { key = \"sht_PModeOne\"; label = \"ќтдельный PDF на каждый лист\"; }"
    "  }"
    "  : boxed_column {"
    "    label = \" уда\";"
    "    : row {"
    "      : edit_box { key = \"sht_PDir\"; label = \"ѕапка\"; edit_width = 70; edit_limit = 250; }"
    "      : button { key = \"sht_PDirB\"; label = \"...\"; width = 6; fixed_width = true; }"
    "    }"
    "    : text { key = \"sht_PFile\"; width = 90; }"
    "  }"
    "  : popup_list { key = \"sht_PCtb\"; label = \"—тиль печати\"; width = 50; }"
    "  : toggle { key = \"sht_PSave\"; label = \"—охранить чертЄж перед печатью одним PDF\"; }"
    "  : toggle { key = \"sht_POpen\"; label = \"ќткрыть результат после печати\"; }"
    "  errtile;"
    "  : row {"
    "    : button { key = \"accept\"; label = \"ѕечать\"; width = 14; fixed_width = true; }"
    "    cancel_button;"
    "  }"
    "}"
    ""
    "sht_list : dialog {"
    (strcat "  label = \"¬едомость рабочих чертежей (SHEETS " *sht:Version* ")\";")
    "  : boxed_column {"
    "    label = \"—троки ведомости - листы с номером, по пор€дку номеров\";"
    "    : list_box { key = \"sht_LList\"; width = 100; height = 16; tabs = \"8 80\"; }"
    "    : text { key = \"sht_LInfo\"; width = 100; }"
    "    : text { key = \"sht_LOff\"; width = 100; }"
    "  }"
    "  : edit_box { key = \"sht_LTitle\"; label = \"«аголовок\"; edit_width = 64; edit_limit = 250; }"
    "  : toggle { key = \"sht_LCnt\"; label = \"√рафа ЂЋистовї - число листов на первом листе (на остальных пусто)\"; }"
    "  : toggle { key = \"sht_LAuto\"; label = \"ќбновл€ть автоматически (и ведомость спецификаций): при сохранении и печати, после команд SHEETS\"; }"
    "  errtile;"
    "  : row {"
    "    : button { key = \"sht_LIns\"; label = \"¬ставить ведомость <\"; width = 24; fixed_width = true; }"
    "    : button { key = \"accept\"; label = \"ќбновить\"; width = 14; fixed_width = true; is_default = true; }"
    "    cancel_button;"
    "  }"
    "}"
    ""
    "sht_spec : dialog {"
    (strcat "  label = \"¬едомость спецификаций (SHEETS " *sht:Version* ")\";")
    "  : boxed_column {"
    "    label = \"—троки ведомости - таблицы со словом Ђ—пецификаци€ї в заголовке, на листах с номером\";"
    "    : list_box { key = \"sht_SList\"; width = 100; height = 12; tabs = \"8 80\"; }"
    "    : text { key = \"sht_SInfo\"; width = 100; }"
    "  }"
    "  : boxed_column {"
    "    label = \"Ќе войдут: не на листе SHEETS формы 3, на листе без номера, на листе бумаги\";"
    "    : list_box { key = \"sht_SOff\"; width = 100; height = 4; tabs = \"8 80\"; }"
    "  }"
    "  : edit_box { key = \"sht_STitle\"; label = \"«аголовок\"; edit_width = 64; edit_limit = 250; }"
    "  : toggle { key = \"sht_SAuto\"; label = \"ќбновл€ть автоматически (и ведомость листов): при сохранении и печати, после команд SHEETS\"; }"
    "  errtile;"
    "  : row {"
    "    : button { key = \"sht_SIns\"; label = \"¬ставить ведомость <\"; width = 24; fixed_width = true; }"
    "    : button { key = \"accept\"; label = \"ќбновить\"; width = 14; fixed_width = true; is_default = true; }"
    "    cancel_button;"
    "  }"
    "}"
    ""
    "sht_refs : dialog {"
    (strcat "  label = \"¬едомость ссылочных и прилагаемых документов (SHEETS " *sht:Version* ")\";")
    "  : boxed_column {"
    "    label = \"ѕрилагаемые документы - листы формы 4: обозначение (гр. 1), наименование (гр. 5), листов\";"
    "    : list_box { key = \"sht_RAtt\"; width = 100; height = 7; tabs = \"30 90\"; }"
    "    : text { key = \"sht_RInfo\"; width = 100; }"
    "  }"
    "  : boxed_column {"
    "    label = \"—сылочные документы - вписываютс€ здесь (щелчок по строке - исправить)\";"
    "    : list_box { key = \"sht_RRef\"; width = 100; height = 7; tabs = \"30 90\"; }"
    "    : row {"
    "      : edit_box { key = \"sht_RObo\"; label = \"ќбозначение\"; edit_width = 22; edit_limit = 120; }"
    "      : edit_box { key = \"sht_RNam\"; label = \"Ќаименование\"; edit_width = 44; edit_limit = 250; }"
    "    }"
    "    : row {"
    "      : edit_box { key = \"sht_RNote\"; label = \"ѕримечание\"; edit_width = 16; edit_limit = 60; }"
    "      : button { key = \"sht_RAdd\"; label = \"ƒобавить\"; width = 12; fixed_width = true; is_default = true; }"
    "      : button { key = \"sht_RChg\"; label = \"«аменить\"; width = 12; fixed_width = true; }"
    "      : button { key = \"sht_RDel\"; label = \"”далить\"; width = 12; fixed_width = true; }"
    "      : button { key = \"sht_RUp\"; label = \"¬ыше\"; width = 10; fixed_width = true; }"
    "      : button { key = \"sht_RDn\"; label = \"Ќиже\"; width = 10; fixed_width = true; }"
    "    }"
    "  }"
    "  : edit_box { key = \"sht_RTitle\"; label = \"«аголовок\"; edit_width = 64; edit_limit = 250; }"
    "  : toggle { key = \"sht_RAuto\"; label = \"ќбновл€ть автоматически (все ведомости): при сохранении и печати, после команд SHEETS\"; }"
    "  errtile;"
    "  : row {"
    "    : button { key = \"sht_RIns\"; label = \"¬ставить ведомость <\"; width = 24; fixed_width = true; }"
    "    : button { key = \"accept\"; label = \"ќбновить\"; width = 14; fixed_width = true; }"
    "    cancel_button;"
    "  }"
    "}"
    ""
    "sht_sign : dialog {"
    (strcat "  label = \"ѕодписи и логотип (SHEETS " *sht:Version* ")\";")
    "  : boxed_column {"
    "    label = \"ѕодписи - блок в графу Ђѕодп.ї напротив фамилии, на всех листах с основной надписью\";"
    "    : list_box { key = \"sht_GList\"; width = 96; height = 8; tabs = \"34 76\"; }"
    "    : row {"
    "      : popup_list { key = \"sht_GBlk\"; label = \"Ѕлок подписи\"; width = 66; }"
    "      : button { key = \"sht_GFile\"; label = \"»з файла DWG...\"; width = 20; fixed_width = true; }"
    "    }"
    "    : radio_row {"
    "      key = \"sht_GFit\";"
    "      : radio_button { key = \"sht_GFit1\"; label = \"¬писать в графу (15 x 5)\"; }"
    "      : radio_button { key = \"sht_GFit0\"; label = \" ак нарисована (1 ед. блока = 1 мм листа)\"; }"
    "    }"
    "    : text { key = \"sht_GInfo\"; width = 96; }"
    "  }"
    "  : boxed_column {"
    "    label = \"Ћоготип - в графу 9 (организаци€), на всех листах с основной надписью\";"
    "    : radio_row {"
    "      key = \"sht_LgKind\";"
    "      : radio_button { key = \"sht_LgKindN\"; label = \"Ќет\"; }"
    "      : radio_button { key = \"sht_LgKindB\"; label = \"Ѕлок\"; }"
    "      : radio_button { key = \"sht_LgKindI\"; label = \" артинка\"; }"
    "    }"
    "    : row {"
    "      : popup_list { key = \"sht_LgBlk\"; label = \"Ѕлок\"; width = 66; }"
    "      : button { key = \"sht_LgBFile\"; label = \"»з файла DWG...\"; width = 20; fixed_width = true; }"
    "    }"
    "    : row {"
    "      : edit_box { key = \"sht_LgPath\"; label = \" артинка\"; edit_width = 64; edit_limit = 250; }"
    "      : button { key = \"sht_LgBrowse\"; label = \"...\"; width = 6; fixed_width = true; }"
    "    }"
    "    : radio_row {"
    "      key = \"sht_LgFit\";"
    "      : radio_button { key = \"sht_LgFit1\"; label = \"¬писать в графу (50 x 15)\"; }"
    "      : radio_button { key = \"sht_LgFit0\"; label = \" ак нарисован (блок; 1 ед. = 1 мм листа)\"; }"
    "    }"
    "  }"
    "  : text { key = \"sht_GNote\"; width = 96; }"
    "  errtile;"
    "  : row {"
    "    : button { key = \"accept\"; label = \"–асставить\"; width = 14; fixed_width = true; is_default = true; }"
    "    cancel_button;"
    "  }"
    "}"
    "sht_main : dialog {"
    (strcat "  label = \"SHEETS " *sht:Version* " - все команды\";")
    "  : text { key = \"sht_MInfo1\"; width = 100; }"
    "  : text { key = \"sht_MInfo2\"; width = 100; }"
    "  : row {"
    "    : boxed_column {"
    "      label = \"Ћисты\";"
    "      : button { key = \"sht_MNew\"; label = \"Ќовый лист...\"; width = 36; fixed_width = true; }"
    "      : button { key = \"sht_MEdit\"; label = \"»зменить лист <\"; width = 36; fixed_width = true; }"
    "      : button { key = \"sht_MData\"; label = \"ƒанные комплекта...\"; width = 36; fixed_width = true; }"
    "      : button { key = \"sht_MSide\"; label = \"ƒанные бокового штампа...\"; width = 36; fixed_width = true; }"
    "      : button { key = \"sht_MStamp\"; label = \"¬се пол€ штампа <\"; width = 36; fixed_width = true; }"
    "      : button { key = \"sht_MUpd\"; label = \"ќбновить всЄ\"; width = 36; fixed_width = true; }"
    "    }"
    "    : boxed_column {"
    "      label = \"¬едомости, подписи, печать\";"
    "      : button { key = \"sht_MList\"; label = \"¬едомость рабочих чертежей...\"; width = 36; fixed_width = true; }"
    "      : button { key = \"sht_MSpec\"; label = \"¬едомость спецификаций...\"; width = 36; fixed_width = true; }"
    "      : button { key = \"sht_MRefs\"; label = \"¬едомость ссылочных документов...\"; width = 36; fixed_width = true; }"
    "      : button { key = \"sht_MSign\"; label = \"ѕодписи и логотип...\"; width = 36; fixed_width = true; }"
    "      : button { key = \"sht_MPlot\"; label = \"ѕечать в PDF...\"; width = 36; fixed_width = true; }"
    "    }"
    "  }"
    "  : boxed_column {"
    "    label = \"Ќастройка\";"
    "    : row {"
    "      : text { key = \"sht_MDblTx\"; width = 62; }"
    "      : button { key = \"sht_MDbl\"; label = \"¬кл./выкл.\"; width = 14; fixed_width = true; }"
    "    }"
    "    : row {"
    "      : text { key = \"sht_MAutoTx\"; width = 62; }"
    "      : button { key = \"sht_MAuto\"; label = \"¬кл./выкл.\"; width = 14; fixed_width = true; }"
    "    }"
    "    : row {"
    "      : text { label = \"ѕеревести листы —ѕƒ— в SHEETS (старые рамки - на выключенный слой)\"; width = 62; }"
    "      : button { key = \"sht_MSpds\"; label = \"ѕеревести...\"; width = 14; fixed_width = true; }"
    "    }"
    "    : row {"
    "      : text { label = \"–азбор объекта (дл€ перехода с —ѕƒ—)\"; width = 62; }"
    "      : button { key = \"sht_MProbe\"; label = \"–азбор <\"; width = 14; fixed_width = true; }"
    "    }"
    "  }"
    "  : row {"
    "    : spacer { width = 1; }"
    "    : button { key = \"cancel\"; label = \"«акрыть\"; width = 14; fixed_width = true; is_cancel = true; is_default = true; }"
    "  }"
    "}"
))

;; ќткрыть файл на запись с нужной кодировкой (при LISPSYS > 0)
(defun sht:open-w (fn / f sys)
  (setq sys (getvar "LISPSYS"))
  (if (and *sht:DclEncoding* sys (> sys 0))
    (setq f (vl-catch-all-apply 'open (list fn "w" *sht:DclEncoding*))))
  (if (or (null f) (vl-catch-all-error-p f))
    (setq f (open fn "w")))
  f)

(defun sht:write-dcl ( / fn f)
  (setq fn (vl-filename-mktemp "sht" nil ".dcl"))
  (if (setq f (sht:open-w fn))
    (progn
      (foreach s (sht:dcl-lines) (write-line s f))
      (close f)
      fn)))

;; ¬ыгрузить окна и удалить временный файл (dcl_id, dclFile Ч локальные команды)
(defun sht:dlg-cleanup ()
  (if (and dcl_id (> dcl_id 0))
    (vl-catch-all-apply 'unload_dialog (list dcl_id)))
  (setq dcl_id nil)
  (if (and dclFile (findfile dclFile))
    (vl-file-delete dclFile))
  (setq dclFile nil))

;; «агрузить окна: T Ч можно открывать
(defun sht:dlg-load ()
  (cond
    ((not (setq dclFile (sht:write-dcl)))
     (princ "\nSHEETS: не удалось записать временный DCL-файл.") nil)
    ((not (and (setq dcl_id (load_dialog dclFile)) (> dcl_id 0)))
     (princ "\nSHEETS: не удалось загрузить окна.") nil)
    (t T)))

;;; --------------------------------------------------------------------------
;;;  10. Ћќ√» ј ќ ќЌ
;;;  –абочие переменные (локальные в командах, видны динамически):
;;;    sht:mode Ч 'NEW / 'EDIT; sht:fmt sht:mult sht:or sht:form Ч формат и штамп (форма с "N" Ч
;;;    без бокового штампа); sht:sc0 sht:no0 sht:title0 sht:obozn0 Ч масштаб, номер, наименование,
;;;    обозначение (графа 1 форм 4, 5) в начале; sht:sugg Ч предложенный номер нового листа;
;;;    sht:res Ч результат окна ЂЋистї (формат кратность ориентаци€ штамп масштаб номер наименование
;;;    обозначение); sht:cur Ч общие пол€ (alist), sht:diff Ч пол€, разные на листах; sht:pend Ч
;;;    изменЄнные в окне Ђƒанные комплектаї; sht:gnl Ч номера других листов по группам нумерации
;;;    (sht:gnums), sht:nsh Ч листов в чертеже; sht:dres Ч результат окна данных.
;;; --------------------------------------------------------------------------

(defun sht:set-popup (key items idx)
  (start_list key)
  (mapcar 'add_list items)
  (end_list)
  (set_tile key (itoa (if idx idx 0))))

;; „исло из пол€ ввода (зап€та€ допускаетс€) или nil
(defun sht:tile-num (key / s)
  (setq s (sht:trim (vl-string-translate "," "." (get_tile key))))
  (if (/= s "") (distof s 2)))

;; —писок номеров дл€ строки сведений (не длиннее ~60 знаков)
(defun sht:nums-str (nums / s)
  (setq s "")
  (foreach x (sht:sort-nums nums)
    (if (< (strlen s) 60)
      (setq s (strcat s (if (= s "") "" ", ") x))))
  (if (and (> (length nums) 0) (>= (strlen s) 60)) (setq s (strcat s " ...")))
  s)

;; √руппа нумерации и номера других листов этой группы Ч по форме и обозначению в окне (s0.10)
(defun sht:cur-group ()
  (sht:num-group sht:form (if (sht:fdoc-p sht:form) (get_tile "sht_Obozn") "")))
(defun sht:cur-nums () (sht:gnums-of (sht:cur-group) sht:gnl))

(defun sht:new-info ( / nl doc)
  (setq nl  (sht:cur-nums)
        doc (sht:fdoc-p sht:form))
  (set_tile "sht_Info"
    (cond
      ((eq sht:mode 'EDIT)
       (strcat "»зменить лист " (if (= sht:no0 "") "(без номера)" sht:no0)
               (if nl (strcat (if doc ". ƒругие листы документа: " ". ƒругие листы: ") (sht:nums-str nl)) "")))
      ((> (length nl) 0)
       (strcat (if doc "Ќовый лист документа. Ћистов документа: " "Ќовый лист. Ћистов в чертеже: ")
               (itoa (length nl)) ". Ќомера: " (sht:nums-str nl)))
      (doc "Ќовый лист. Ћистов этого документа (графа 1) пока нет.")
      (t "Ќовый лист. Ћистов в чертеже пока нет."))))

(defun sht:data-info ( / s st)
  (setq s  (sht:trim (cdr (assoc "SHIFR" sht:cur)))
        st (sht:trim (cdr (assoc "STAGE" sht:cur))))
  (set_tile "sht_DataInfo"
    (strcat (if (= s "") "Ўифр не задан" (strcat "Ўифр: " s))
            (if (= st "") "" (strcat ", стади€ " st))
            (if sht:pend " (изменено)" ""))))

;; ‘ормат выбран: список кратностей, ориентаци€, размер
(defun sht:on-fmt ( / ms)
  (setq sht:fmt (nth (atoi (get_tile "sht_Fmt")) *sht:FmtNames*)
        ms      (sht:mults sht:fmt))
  (if (not (member sht:mult ms)) (setq sht:mult 1))
  (sht:set-popup "sht_Mult"
    (mapcar '(lambda (m) (if (= m 1) "1 (основной)" (strcat "x" (itoa m)))) ms)
    (vl-position sht:mult ms))
  (sht:on-size))

(defun sht:on-mult ()
  (setq sht:mult (nth (atoi (get_tile "sht_Mult")) (sht:mults sht:fmt)))
  (sht:on-size))

;; Ўтамп, боковой штамп или обозначение изменили (s0.10): форма, поле обозначени€, номер нового листа
;; (у документа формы 4 / 5 Ч сво€ нумераци€: предложенный номер мен€етс€, если его не правили)
(defun sht:on-form ()
  (setq sht:form (sht:fmake (nth (atoi (get_tile "sht_Form")) *sht:Forms*) (= (get_tile "sht_Side") "1")))
  (mode_tile "sht_Obozn" (if (sht:fdoc-p sht:form) 0 1))
  (if (and (eq sht:mode 'NEW) (= (sht:trim (get_tile "sht_Sheet")) sht:sugg))
    (progn
      (setq sht:sugg (sht:next-num (sht:cur-nums)))
      (set_tile "sht_Sheet" sht:sugg)))
  (sht:new-info)
  (sht:on-size))

(defun sht:on-size ( / rec wh)
  (if (sht:portrait-only-p sht:fmt sht:mult)
    (progn (setq sht:or "P") (mode_tile "sht_OrL" 1))
    (progn
      (mode_tile "sht_OrL" 0)
      (setq sht:or (if (= (get_tile "sht_Or") "sht_OrP") "P" "L"))))
  (set_tile "sht_Or" (if (= sht:or "P") "sht_OrP" "sht_OrL"))
  (setq rec (sht:fmt-rec sht:fmt sht:mult)
        wh  (sht:fmt-wh rec sht:or))
  (set_tile "sht_Size"
    (strcat (sht:fmt-label rec) ": " (sht:n2s (car wh)) " x " (sht:n2s (cadr wh)) " мм"
            (if (= sht:mult 1) "" "  (кратный, бумага - из PMP)")
            "   блок " (sht:bname rec sht:or sht:form))))

(defun sht:sheet-init ()
  (set_tile "sht_Obozn" sht:obozn0)
  (sht:set-popup "sht_Fmt" *sht:FmtNames* (vl-position sht:fmt *sht:FmtNames*))
  (sht:set-popup "sht_Form" *sht:FormNames* (vl-position (sht:fbase sht:form) *sht:Forms*))
  (set_tile "sht_Side" (if (sht:fside-p sht:form) "1" "0"))
  (mode_tile "sht_Obozn" (if (sht:fdoc-p sht:form) 0 1))
  (sht:new-info)
  (set_tile "sht_Or" (if (= sht:or "P") "sht_OrP" "sht_OrL"))
  (sht:on-fmt)
  (set_tile "sht_Scale" (sht:n2s sht:sc0))
  (set_tile "sht_Sheet" sht:no0)
  (set_tile "sht_Title" sht:title0)
  (sht:data-info)
  (if (eq sht:mode 'EDIT)
    (progn
      (set_tile "sht_AttrInfo" "записать окно и открыть штамп этого листа")
      (set_tile "sht_SideInfo" "записать окно и открыть боковой штамп листа"))
    (progn
      (mode_tile "sht_Attr" 1)
      (set_tile "sht_AttrInfo" "")
      (set_tile "sht_SideInfo" "дл€ всех листов")))
  (action_tile "sht_Fmt" "(sht:on-fmt)")
  (action_tile "sht_Mult" "(sht:on-mult)")
  (action_tile "sht_Or" "(sht:on-size)")
  (action_tile "sht_Form" "(sht:on-form)")
  (action_tile "sht_Side" "(sht:on-form)")
  (action_tile "sht_Obozn" "(sht:on-form)")
  (action_tile "sht_Data" "(sht:on-data)")
  (action_tile "sht_Attr" "(sht:sheet-read 3)")
  (action_tile "sht_SideB" (if (eq sht:mode 'EDIT) "(sht:sheet-read 4)" "(sht:on-side)"))
  (action_tile "accept" "(sht:sheet-read 1)"))

;; OK (code 1) / Ђ¬се пол€ штампа...ї (code 3) / Ђƒанные бокового штампа...ї (code 4): проверить ввод -> sht:res
(defun sht:sheet-read (code / sc no)
  (setq sc (sht:tile-num "sht_Scale")
        no (sht:trim (get_tile "sht_Sheet")))
  (cond
    ((not (and sc (> sc 0)))
     (set_tile "error" "ћасштаб: введите число больше 0 (1:100 -> 100)."))
    ((sht:num-used-p no (sht:cur-nums))
     (set_tile "error" (strcat "Ћист " no (if (sht:fdoc-p sht:form) " уже есть в этом документе" " уже есть в чертеже")
                               " - укажите другой номер.")))
    (t
     (setq sht:res (list sht:fmt sht:mult sht:or sht:form sc no (sht:trim (get_tile "sht_Title"))
                         (sht:trim (vl-string-translate "|" "/" (get_tile "sht_Obozn")))))
     (done_dialog code))))

;; ќкно ЂЋистї целиком: загрузить, показать, выгрузить. ¬озвращает код закрыти€.
(defun sht:sheet-dialog ( / dcl_id dclFile ret)
  (if (sht:dlg-load)
    (if (new_dialog "sht_sheet" dcl_id)
      (progn
        (sht:sheet-init)
        (setq ret (start_dialog)))
      (princ "\nSHEETS: не удалось открыть окно.")))
  (sht:dlg-cleanup)
  ret)

;;  нопка Ђƒанные комплекта...ї
(defun sht:on-data ( / r)
  (if (setq r (sht:data-dialog sht:cur sht:diff sht:nsh))
    (setq sht:cur  (car r)
          sht:pend (sht:merge-changes sht:pend (cadr r)))
    )
  (sht:data-info))

;;  нопка Ђƒанные бокового штампа...ї нового листа (s0.11) Ч дл€ всех листов
(defun sht:on-side ( / r)
  (if (setq r (sht:kit-dialog 'SIDE sht:cur sht:diff sht:nsh))
    (setq sht:cur  (car r)
          sht:pend (sht:merge-changes sht:pend (cadr r))))
  (sht:data-info))

;; ƒобавить новые изменени€ к прежним (новые важнее)
(defun sht:merge-changes (old new)
  (foreach p new (setq old (sht:alist-put old (car p) (cdr p))))
  old)

;; ќкно Ђƒанные комплектаї (s0.11 Ч в виде штампа): cur Ч значени€, diff Ч пол€, разные на листах,
;; n Ч листов. ¬озвращает (новые-значени€ изменЄнные) или nil (ќтмена).
(defun sht:data-dialog (cur diff n) (sht:kit-dialog 'STAMP cur diff n))

(defun sht:diff-str (diff / s nm)
  (setq s "")
  (foreach tag diff
    (setq nm (cond ((cdr (assoc tag *sht:CommonNames*)))
                   ((wcmatch tag "ROLE#") (strcat "должность " (substr tag 5)))
                   ((wcmatch tag "NAME#") (strcat "фамили€ " (substr tag 5)))
                   ((wcmatch tag "DATE#") (strcat "дата " (substr tag 5)))
                   (t "согласовано")))
    (if (not (vl-string-search nm s))
      (setq s (strcat s (if (= s "") "" ", ") nm))))
  s)

;;; --------------------------------------------------------------------------
;;;  10а. ќ Ќј ¬ ¬»ƒ≈ Ў“јћѕј (s0.11): Ђƒанные комплектаї, Ђƒанные бокового штампаї, Ђ¬се пол€ штампаї
;;;  –абочие переменные окна (локальные в sht:fw-dialog): sht:fw-kind Ч 'STAMP / 'SIDE; sht:fw-form Ч форма
;;;  листа (nil Ч данные комплекта); sht:fw-tl Ч доступные пол€ ((поле . тег) Е); sht:fw-v0 Ч значени€ в начале;
;;;  sht:fw-cur Ч общие пол€ комплекта (дл€ шаблона); sht:fw-gnl Ч номера других листов; sht:fw-res Ч итог.
;;; --------------------------------------------------------------------------

(defun sht:fw-tile (tag) (cdr (assoc tag *sht:FwTiles*)))

;; —троки изменений окна ЂЎтампї (C4IZM Е C1DAT)
(defun sht:chg-tags () (vl-remove-if-not '(lambda (x) (wcmatch x "C#*")) *sht:StampTags*))

;; ƒоступные пол€ окна kind дл€ формы form (nil Ч комплект: без полей листа): ((поле . тег) Е).
;; ѕол€ нет на этой форме Ч его нет в списке (в окне оно серое). √рафа 1 у форм 4, 5 Ч OBOZN.
(defun sht:fw-map (kind form / tab tg res)
  (setq tab (sht:attr-tab (cond (form) ("3"))))
  (foreach tag (if (eq kind 'SIDE) *sht:SideTags* *sht:StampTags*)
    (setq tg (if (and (= tag "SHIFR") (assoc "OBOZN" tab)) "OBOZN" tag))
    (if (and (assoc tg tab) (or form (not (member tg *sht:OneTags*))))
      (setq res (cons (cons (sht:fw-tile tag) tg) res))))
  (reverse res))

;; «начени€ полей tags на листах: самое частое; листов (пол€) нет Ч словарь чертежа, затем умолчани€.
;; ¬озвращает (значени€ разные-пол€).
(defun sht:fw-now (tags attrs sdat / res diff vals p)
  (foreach tag tags
    (setq vals nil)
    (foreach a attrs
      (if (setq p (assoc tag a)) (setq vals (cons (cdr p) vals))))
    (setq vals (reverse vals))
    (if (and vals (vl-some '(lambda (v) (/= v (car vals))) vals))
      (setq diff (cons tag diff)))
    (setq res (cons (cons tag
                          (cond (vals (sht:most vals))
                                ((cdr (assoc tag sdat)))
                                ((cdr (assoc tag *sht:CommonDef*)))
                                ("")))
                    res)))
  (list (reverse res) (reverse diff)))

;; ќкно-штамп kind ('STAMP Ч Ђsht_dataї, 'SIDE Ч Ђsht_sideї). form Ч форма листа (nil Ч данные комплекта:
;; только Ђƒл€ всех листовї), v0 Ч значени€ ((тег . значение) Е), cur Ч общие пол€ комплекта (дл€ шаблона),
;; note / diff Ч строки сведений, gnl Ч номера других листов (проверка номера).
;; ¬озвращает (область новые изменЄнные): 'ONE Ч в этот лист, 'ALL Ч во все листы; nil Ч Ђќтменаї.
(defun sht:fw-dialog (kind form v0 cur note diff gnl / sht:fw-kind sht:fw-form sht:fw-tl sht:fw-v0
                      sht:fw-cur sht:fw-gnl sht:fw-res)
  (setq sht:fw-kind kind
        sht:fw-form form
        sht:fw-v0   v0
        sht:fw-cur  cur
        sht:fw-gnl  gnl
        sht:fw-tl   (sht:fw-map kind form))
  (if (new_dialog (if (eq kind 'SIDE) "sht_side" "sht_data") dcl_id)
    (progn
      (sht:fw-init note diff)
      (start_dialog)))
  sht:fw-res)

(defun sht:fw-init (note diff / k tg g1)
  (foreach tag (if (eq sht:fw-kind 'SIDE) *sht:SideTags* *sht:StampTags*)
    (setq k  (sht:fw-tile tag)
          tg (cdr (assoc k sht:fw-tl)))
    (set_tile k (if tg (cond ((cdr (assoc tg sht:fw-v0))) ("")) ""))
    (if (or (not tg) (= tg "SHEETS")) (mode_tile k 1)))
  (if (eq sht:fw-kind 'STAMP)
    (progn
      (setq g1 (cdr (assoc "sht_SHIFR" sht:fw-tl)))
      (set_tile "sht_FG1Tx" (if (= g1 "OBOZN") "ќбозначение документа (гр. 1)" "ќбозначение, шифр (гр. 1)"))
      (set_tile "sht_FTitleTx"
        (if (and sht:fw-form (sht:fdoc-p sht:fw-form)) "Ќаименование (гр. 5)" "Ќаименование (гр. 4)"))))
  (set_tile "sht_DataNote" note)
  (set_tile "sht_DataDiff" diff)
  (set_tile "sht_FMsg" "")
  (mode_tile "sht_One" (if sht:fw-form 0 1))
  (action_tile "sht_One" "(sht:fw-ok 'ONE)")
  (action_tile "accept" "(sht:fw-ok 'ALL)")
  (action_tile "sht_TplLoad" "(sht:tpl-use)")
  (action_tile "sht_TplSave" "(sht:tpl-save)"))

;; Ђƒл€ этого листаї / Ђƒл€ всех листовї: значени€ доступных полей, изменЄнные (без ЂЋистовї);
;; номер листа провер€етс€ на повтор в своей группе нумерации (комплект / документ)
(defun sht:fw-ok (scope / new chg v v0 no)
  (foreach p sht:fw-tl
    (if (/= (cdr p) "SHEETS")
      (progn
        (setq v (sht:trim (get_tile (car p))))
        (if (= (cdr p) "OBOZN") (setq v (vl-string-translate "|" "/" v)))
        (setq v0  (sht:trim (cond ((cdr (assoc (cdr p) sht:fw-v0))) ("")))
              new (append new (list (cons (cdr p) v))))
        (if (/= v v0) (setq chg (append chg (list (cons (cdr p) v))))))))
  (setq no (cdr (assoc "SHEET" new)))
  (cond
    ((and no (or (assoc "SHEET" chg) (assoc "OBOZN" chg))
          (sht:num-used-p no (sht:gnums-of (sht:num-group sht:fw-form (cond ((cdr (assoc "OBOZN" new))) ("")))
                                           sht:fw-gnl)))
     (set_tile "error" (strcat "Ћист " no (if (sht:fdoc-p sht:fw-form) " уже есть в этом документе" " уже есть в чертеже")
                               " - укажите другой номер.")))
    (t
     (setq sht:fw-res (list scope new chg))
     (done_dialog 1))))

;; ќкно данных комплекта (kind 'STAMP / 'SIDE): cur Ч общие пол€, diff Ч разные на листах, n Ч листов.
;; —троки изменений Ч самое частое на листах (во все листы пойдЄт только исправленное).
;; ¬озвращает (общие-пол€ изменЄнные) или nil (ќтмена).
(defun sht:kit-dialog (kind cur diff n / tags v0 res new)
  (setq tags (if (eq kind 'SIDE) *sht:SideTags* *sht:StampTags*)
        v0   (if (eq kind 'SIDE)
               cur
               (append cur (car (sht:fw-now (sht:chg-tags) (mapcar 'sht:attrs (sht:sheets)) nil))))
        diff (vl-remove-if-not '(lambda (x) (member x tags)) diff))
  (setq res (sht:fw-dialog kind nil v0 cur
              (if (> n 0)
                (strcat "Ћистов в чертеже: " (itoa n) ". „то исправите здесь - запишетс€ во все листы;"
                        " остальное на листах не тронетс€."
                        (if (eq kind 'SIDE) "" " —троки изменений - самое частое на листах."))
                "Ћистов в чертеже пока нет. ƒанные запомн€тс€ в чертеже и пойдут в новые листы.")
              (if diff (strcat "Ќа листах разное (показано самое частое): " (sht:diff-str diff)) "")
              nil))
  (if res
    (progn
      (setq new cur)
      (foreach p (cadr res)
        (if (member (car p) *sht:Common*) (setq new (sht:alist-put new (car p) (cdr p)))))
      (list new (caddr res)))))

;; «аписать итог окна дл€ листа en (s0.11): 'ONE Ч всЄ изменЄнное только в en; 'ALL Ч пол€ листа
;; (*sht:OneTags*) Ч в en, остальное изменЄнное Ч во все листы ens и в словарь чертежа (общие пол€).
;; ¬озвращает (полей-в-лист полей-во-все листов).
(defun sht:fw-commit (scope en chg ens sdat / one all inf n q)
  (if (eq scope 'ONE)
    (setq one chg)
    (foreach p chg
      (if (member (car p) *sht:OneTags*)
        (setq one (append one (list p)))
        (setq all (append all (list p))))))
  (if one
    (progn
      (setq inf (sht:sheet-info en))
      (foreach a (sht:att-objs en)
        (if (setq q (assoc (strcase (vla-get-TagString a)) one))
          (sht:att-set a (cdr q) (cadddr inf) (sht:attr-tab (caddr inf)))))))
  (setq n (if all (sht:apply-common all ens) 0))
  (if all
    (progn
      (foreach p all
        (if (member (car p) *sht:Common*) (setq sdat (sht:alist-put sdat (car p) (cdr p)))))
      (sht:set-write sdat)))
  (list (length one) (length all) n))

;; Ђ¬се пол€ штампаї (kind 'STAMP) / Ђƒанные бокового штампаї ('SIDE) дл€ листа en.
;; ” листа нет бокового штампа Ч окно бокового штампа дл€ всех листов.
(defun sht:fw-edit (en kind / doc sdat ens r inf form a0 no res cr lr sr dcl_id dclFile)
  (setq doc  (sht:doc)
        sdat (sht:prepare)
        ens  (sht:sheets)
        r    (sht:common-now (mapcar 'sht:attrs ens) sdat)
        inf  (sht:sheet-info en)
        form (caddr inf)
        a0   (sht:attrs en)
        no   (sht:trim (cond ((cdr (assoc "SHEET" a0))) (""))))
  (if (and (eq kind 'SIDE) (not (sht:fside-p form)))
    (progn
      (princ "\n” этого листа нет бокового штампа - окно бокового штампа дл€ всех листов.")
      (sht:kit-cmd 'SIDE))
    (progn
      (if (sht:dlg-load)
        (setq res (sht:fw-dialog kind form a0 (car r)
                    (strcat "Ћист " (if (= no "") "без номера" no) " (форма " (sht:fbase form) "). "
                            "Ђƒл€ этого листаї - только в этот лист; Ђƒл€ всех листовї - исправленное во все листы"
                            " (номер, наименование, обозначение - только в этот).")
                    "" (sht:gnums (vl-remove en ens)))))
      (sht:dlg-cleanup)
      (cond
        ((null res) (princ "\nЎтамп листа: без изменений."))
        ((null (caddr res)) (princ "\nЎтамп листа: ничего не изменено."))
        (t
         (vla-StartUndoMark doc)
         (setq cr (sht:fw-commit (car res) en (caddr res) ens sdat))
         (setq sr (sht:sign-auto T))              ; фамилии Ч подписи (s0.7)
         (setq lr (sht:list-auto T))              ; номер, наименование, изменени€ Ч ведомости (s0.5)
         (vla-EndUndoMark doc)
         (princ (strcat "\nЋист " (if (= no "") "(без номера)" no) ": "
                        (if (> (car cr) 0) (strcat "в этот лист полей " (itoa (car cr))) "")
                        (if (and (> (car cr) 0) (> (cadr cr) 0)) "; " "")
                        (if (> (cadr cr) 0)
                          (strcat "во все листы (" (itoa (caddr cr)) ") полей " (itoa (cadr cr)))
                          "")
                        "."))
         (if lr (sht:list-msg lr nil))
         (if sr (sht:sign-msg sr nil))))))
  (princ))

;; ƒанные комплекта (kind 'STAMP) / бокового штампа ('SIDE) Ч окно дл€ всех листов, запись.
(defun sht:kit-cmd (kind / doc sdat ens r dcl_id dclFile res)
  (sht:dblclick-setup)
  (setq doc  (sht:doc)
        sdat (sht:prepare)
        ens  (sht:sheets)
        r    (sht:common-now (mapcar 'sht:attrs ens) sdat))
  (if (sht:dlg-load)
    (setq res (sht:kit-dialog kind (car r) (cadr r) (length ens))))
  (sht:dlg-cleanup)
  (cond
    ((null res) (princ (if (eq kind 'SIDE) "\nЅоковой штамп: без изменений." "\nƒанные комплекта: без изменений.")))
    ((null (cadr res)) (princ (if (eq kind 'SIDE) "\nЅоковой штамп: ничего не изменено." "\nƒанные комплекта: ничего не изменено.")))
    (t (sht:commit-data doc (car res) (cadr res) ens sdat)))
  (princ))

;; --- шаблоны данных комплекта (s0.11): файлы Ђим€.txtї (поле=значение) в папке шаблонов ---

;; ѕапка шаблонов: выбранна€ (Ђѕапка...ї, реестр SHT_TplDir), иначе ЂЎаблоныї р€дом с SHEETS.lsp
;; (если он в пут€х поддержки), иначе Ђƒокументы\SHEETS\Ўаблоныї
(defun sht:tpl-dir ( / d lsp)
  (setq d (sht:dir-norm (cond ((getenv "SHT_TplDir")) (""))))
  (cond
    ((/= d "") d)
    ((setq lsp (findfile "SHEETS.lsp")) (strcat (vl-filename-directory lsp) "\\Ўаблоны"))
    (t (strcat (sht:dir-norm (cond ((getenv "USERPROFILE")) ("C:"))) "\\Documents\\SHEETS\\Ўаблоны"))))

(defun sht:tpl-file (dir nm) (strcat dir "\\" nm ".txt"))

;; »мена шаблонов в папке (по алфавиту)
(defun sht:tpl-names (dir)
  (vl-sort (mapcar 'vl-filename-base (vl-directory-files dir "*.txt" 1))
           '(lambda (a b) (< (sht:lc a) (sht:lc b)))))

;; ѕрочитать шаблон: ((поле . значение) Е) Ч только пол€ шаблона
(defun sht:tpl-read (fn / f s i res)
  (if (and fn (findfile fn) (setq f (open fn "r")))
    (progn
      (while (setq s (read-line f))
        (if (and (/= (substr s 1 1) ";") (setq i (vl-string-search "=" s))
                 (member (strcase (sht:trim (substr s 1 i))) *sht:TplTags*))
          (setq res (sht:alist-put res (strcase (sht:trim (substr s 1 i))) (sht:trim (substr s (+ i 2)))))))
      (close f)))
  res)

;; «аписать шаблон. T Ч записан
(defun sht:tpl-write (fn vals / f)
  (if (setq f (open fn "w"))
    (progn
      (write-line "; SHEETS - шаблон данных комплекта: поле=значение" f)
      (foreach tag *sht:TplTags*
        (write-line (strcat tag "=" (cond ((cdr (assoc tag vals))) (""))) f))
      (close f)
      T)))

;; «начени€ дл€ шаблона из открытого окна-штампа: поле есть в окне Ч из окна, иначе Ч данные комплекта
(defun sht:tpl-vals ( / res k)
  (foreach tag *sht:TplTags*
    (setq k (sht:fw-tile tag))
    (setq res (append res (list (cons tag (if (= (cdr (assoc k sht:fw-tl)) tag)
                                             (sht:trim (get_tile k))
                                             (cond ((cdr (assoc tag sht:fw-cur))) (""))))))))
  res)

;; ѕодставить шаблон в открытое окно-штамп: только пол€ этого окна. ¬озвращает число полей.
(defun sht:tpl-apply (vals / n k)
  (setq n 0)
  (foreach p vals
    (setq k (sht:fw-tile (car p)))
    (if (= (cdr (assoc k sht:fw-tl)) (car p))
      (progn
        (set_tile k (cdr p))
        (setq n (1+ n)))))
  n)

;;  нопки окна-штампа Ђ¬ыбрать шаблон...ї / Ђ—охранить шаблон...ї
(defun sht:tpl-use ( / vals)
  (if (setq vals (sht:tpl-dialog 'USE nil))
    (set_tile "sht_FMsg" (strcat "Ўаблон подставлен, полей: " (itoa (sht:tpl-apply vals))
                                 ". «аписать - кнопкой Ђƒл€ ...ї."))))

(defun sht:tpl-save ( / nm)
  (if (setq nm (sht:tpl-dialog 'SAVE (sht:tpl-vals)))
    (set_tile "sht_FMsg" (strcat "Ўаблон Ђ" nm "ї сохранЄн."))))

;; ќкно ЂЎаблоныї: mode 'USE Ч выбрать и подставить (итог Ч значени€), 'SAVE Ч сохранить vals (итог Ч им€)
(defun sht:tpl-dialog (mode vals / sht:tmode sht:tvals sht:tdir sht:tnames sht:tres sht:tconf)
  (setq sht:tmode mode
        sht:tvals vals
        sht:tdir  (sht:tpl-dir))
  (if (new_dialog "sht_tpl" dcl_id)
    (progn
      (sht:tpl-fill)
      (mode_tile "sht_TName" (if (eq mode 'SAVE) 0 1))
      (mode_tile (if (eq mode 'SAVE) "sht_TUse" "sht_TSave") 1)
      (action_tile "sht_TList" "(sht:tpl-pick)")
      (action_tile "sht_TDirB" "(sht:tpl-browse)")
      (action_tile "sht_TDel" "(sht:tpl-del)")
      (action_tile "sht_TUse" "(sht:tpl-ok)")
      (action_tile "sht_TSave" "(sht:tpl-ok)")
      (start_dialog)))
  sht:tres)

(defun sht:tpl-fill ()
  (setq sht:tnames (sht:tpl-names sht:tdir))
  (start_list "sht_TList")
  (mapcar 'add_list sht:tnames)
  (end_list)
  (set_tile "sht_TDir" (strcat "ѕапка: " sht:tdir))
  (set_tile "sht_TInfo" (if sht:tnames "" "Ўаблонов в этой папке нет."))
  (set_tile "sht_TInfo2" ""))

;; ¬ыбранное им€ в списке или nil
(defun sht:tpl-sel ( / s)
  (setq s (get_tile "sht_TList"))
  (if (/= s "") (nth (atoi s) sht:tnames)))

;; ўелчок по шаблону: им€ в поле, коротко Ч что в нЄм
(defun sht:tpl-pick ( / nm v)
  (if (setq nm (sht:tpl-sel))
    (progn
      (set_tile "sht_TName" nm)
      (setq v (sht:tpl-read (sht:tpl-file sht:tdir nm)))
      (set_tile "sht_TInfo" (strcat "Ўифр: " (cond ((cdr (assoc "SHIFR" v))) ("")) ". ќрганизаци€: "
                                    (cond ((cdr (assoc "ORG" v))) (""))))
      (set_tile "sht_TInfo2" (strcat "‘амилии: "
                                     (sht:join (vl-remove "" (mapcar '(lambda (x) (cond ((cdr (assoc x v))) ("")))
                                                                     '("NAME1" "NAME2" "NAME3" "NAME4" "NAME5" "NAME6")))
                                               ", "))))))

;; Ђѕодставитьї / Ђ—охранитьї
(defun sht:tpl-ok ( / nm fn)
  (set_tile "error" "")
  (if (eq sht:tmode 'USE)
    (if (setq nm (sht:tpl-sel))
      (progn
        (setq sht:tres (sht:tpl-read (sht:tpl-file sht:tdir nm)))
        (done_dialog 1))
      (set_tile "error" "¬ыберите шаблон в списке."))
    (progn
      (setq nm (sht:trim (get_tile "sht_TName"))
            fn (sht:tpl-file sht:tdir nm))
      (cond
        ((= nm "") (set_tile "error" "¬пишите им€ шаблона."))
        ((vl-some '(lambda (c) (vl-string-search c nm)) '("\\" "/" ":" "*" "?" "\"" "<" ">" "|"))
         (set_tile "error" "¬ имени нельз€: \\ / : * ? \" < > |"))
        ((and (findfile fn) (/= sht:tconf nm))
         (setq sht:tconf nm)
         (set_tile "error" (strcat "Ўаблон Ђ" nm "ї уже есть - нажмите Ђ—охранитьї ещЄ раз, чтобы заменить.")))
        ((not (sht:mkdir sht:tdir))
         (set_tile "error" (strcat "Ќе удалось создать папку " sht:tdir " - выберите другую (Ђѕапка...ї).")))
        ((not (sht:tpl-write fn sht:tvals))
         (set_tile "error" (strcat "Ќе удалось записать " fn)))
        (t
         (setq sht:tres nm)
         (done_dialog 1))))))

;; Ђ”далитьї Ч выбранный шаблон (второе нажатие подтверждает)
(defun sht:tpl-del ( / nm)
  (set_tile "error" "")
  (cond
    ((not (setq nm (sht:tpl-sel))) (set_tile "error" "¬ыберите шаблон в списке."))
    ((/= sht:tconf (strcat "-" nm))
     (setq sht:tconf (strcat "-" nm))
     (set_tile "error" (strcat "”далить шаблон Ђ" nm "ї? Ќажмите Ђ”далитьї ещЄ раз.")))
    (t
     (vl-file-delete (sht:tpl-file sht:tdir nm))
     (setq sht:tconf nil)
     (sht:tpl-fill)
     (set_tile "sht_TInfo" (strcat "Ўаблон Ђ" nm "ї удалЄн.")))))

;; Ђѕапка...ї Ч выбрать папку шаблонов (запоминаетс€ в реестре)
(defun sht:tpl-browse ( / app sh hw f it p)
  (setq app (vlax-get-acad-object)
        sh  (vl-catch-all-apply 'vla-GetInterfaceObject (list app "Shell.Application")))
  (if (and sh (not (vl-catch-all-error-p sh)))
    (progn
      (setq hw (vl-catch-all-apply 'vla-get-HWND (list app))
            f  (vl-catch-all-apply 'vlax-invoke-method
                 (list sh 'BrowseForFolder (if (vl-catch-all-error-p hw) 0 hw) "ѕапка шаблонов SHEETS" 64)))
      (if (and f (not (vl-catch-all-error-p f)))
        (progn
          (setq it (vl-catch-all-apply 'vlax-get-property (list f 'Self)))
          (if (not (vl-catch-all-error-p it))
            (setq p (vl-catch-all-apply 'vlax-get-property (list it 'Path))))
          (if (and (= (type p) 'STR) (/= p "") (not (wcmatch p "::*")))
            (progn
              (setq sht:tdir (sht:dir-norm (vl-string-translate "/" "\\" p)))
              (setenv "SHT_TplDir" sht:tdir)
              (sht:tpl-fill)))
          (vl-catch-all-apply 'vlax-release-object (list f))))
      (vl-catch-all-apply 'vlax-release-object (list sh)))
    (set_tile "error" "ќкно выбора папки недоступно.")))

;;; --------------------------------------------------------------------------
;;;  11.  ќћјЌƒџ
;;; --------------------------------------------------------------------------

;; »зменени€ общих полей: во все листы + в словарь чертежа (внутри одной Ђќтменыї)
(defun sht:commit-data (doc cur pend ens sdat / n sr)
  (vla-StartUndoMark doc)
  (setq n (sht:apply-common pend ens))
  (foreach p cur (setq sdat (sht:alist-put sdat (car p) (cdr p))))
  (sht:set-write sdat)
  (setq sr (sht:sign-auto T))                ; s0.7: фамилии помен€лись Ч подписи
  (vla-EndUndoMark doc)
  (princ (strcat "\nƒанные комплекта: изменено полей " (itoa (length pend))
                 (if (> n 0) (strcat ", записано в листов: " (itoa n)) ", листов в чертеже нет")
                 "."))
  (if sr (sht:sign-msg sr nil))
  n)

(defun c:SHEET_NEW ( / doc sdat ens attrs r ret pt rec en lr sr
                       sht:mode sht:fmt sht:mult sht:or sht:form sht:sc0 sht:no0 sht:title0 sht:res
                       sht:cur sht:diff sht:pend sht:gnl sht:nsh sht:obozn0 sht:sugg)
  (setq doc  (sht:doc)
        sdat (sht:prepare))
  (sht:dblclick-setup)
  (sht:defaults)
  (setq ens   (sht:sheets)
        attrs (mapcar 'sht:attrs ens)
        r     (sht:common-now attrs sdat)
        sht:cur    (car r)
        sht:diff   (cadr r)
        sht:gnl    (sht:gnums ens)
        sht:nsh    (length ens)
        sht:mode   'NEW
        sht:fmt    *sht_Fmt*
        sht:mult   *sht_Mult*
        sht:or     *sht_Orient*
        sht:form   *sht_Form*
        sht:sc0    *sht_Scale*
        ;; графа 1 форм 4, 5: прежнее обозначение (в этом сеансе), иначе шифр комплекта (s0.10)
        sht:obozn0 (cond ((and *sht_Obozn* (/= *sht_Obozn* "")) *sht_Obozn*) ((cdr (assoc "SHIFR" sht:cur))) (""))
        sht:no0    (sht:next-num (sht:gnums-of (sht:num-group sht:form sht:obozn0) sht:gnl))
        sht:sugg   sht:no0
        sht:title0 *sht_Title*
        ret        (sht:sheet-dialog))
  ;; Ђƒанные комплектаї подтверждены Ч записать, даже если лист не вставл€етс€
  (if sht:pend
    (setq sdat (progn (sht:commit-data doc sht:cur sht:pend ens sdat) (sht:set-read))))
  (if (= ret 1)
    (progn
      (setq *sht_Fmt*     (nth 0 sht:res)
            *sht_Mult*    (nth 1 sht:res)
            *sht_Orient*  (nth 2 sht:res)
            *sht_Form*    (nth 3 sht:res)
            *sht_Scale*   (nth 4 sht:res)
            *sht_SheetNo* (nth 5 sht:res)
            *sht_Title*   (nth 6 sht:res)
            *sht_Obozn*   (nth 7 sht:res))
      (sht:save-defaults)
      (setq rec (sht:fmt-rec *sht_Fmt* *sht_Mult*))
      (princ (strcat "\nЋист " (sht:fmt-label rec) (if (= *sht_Orient* "P") " вертикальный" " горизонтальный")
                     ", 1:" (sht:n2s *sht_Scale*) ", в модели "
                     (sht:n2s (* *sht_Scale* (car (sht:fmt-wh rec *sht_Orient*)))) " x "
                     (sht:n2s (* *sht_Scale* (cadr (sht:fmt-wh rec *sht_Orient*))))))
      (if (setq pt (getpoint "\nЋевый нижний угол листа (Enter - отмена): "))
        (progn
          (vla-StartUndoMark doc)
          (setq en (sht:insert rec *sht_Orient* *sht_Form* pt *sht_Scale*
                               (append sht:cur sht:pend
                                       (list (cons "SHEET" *sht_SheetNo*) (cons "TITLE" *sht_Title*)
                                             (cons "OBOZN" *sht_Obozn*)))))
          (sht:stage-layer (cdr (assoc "STAGE" sht:cur)))
          ;; данные комплекта запомнить в чертеже (первый лист Ч источник дл€ следующих)
          (foreach p sht:cur (setq sdat (sht:alist-put sdat (car p) (cdr p))))
          (sht:set-write sdat)
          (setq sr (sht:sign-auto T))           ; подписи и логотип (s0.7)
          (setq lr (sht:list-auto T))           ; ведомость листов и ЂЋистовї (s0.5)
          (vla-EndUndoMark doc)
          (princ (strcat "\nЋист " (if (= *sht_SheetNo* "") "(без номера)" *sht_SheetNo*)
                         " вставлен, блок " (sht:bname rec *sht_Orient* *sht_Form*)
                         ". Ћистов в чертеже: " (itoa (length (sht:sheets))) "."))
          (if lr (sht:list-msg lr nil))
          (if sr (sht:sign-msg sr nil)))
        (princ "\nЋист не вставлен."))))
  (sht:watch)
  (princ))

(defun c:SHEET_DATA () (sht:kit-cmd 'STAMP))

;; s0.11: данные бокового штампа Ч дл€ всех листов
(defun c:SHEET_SIDE () (sht:kit-cmd 'SIDE))

;; s0.11: все пол€ штампа листа (выбранного до команды или щелчком)
(defun c:SHEET_STAMP ( / ss en)
  (sht:dblclick-setup)
  (if (and (setq ss (ssget "_I")) (sht:sheet-p (ssname ss 0)))
    (setq en (ssname ss 0)))
  (sssetfirst nil nil)
  (if (not en) (setq en (sht:pick "\n¬ыберите лист - рамку или штамп (Enter - выход): ")))
  (if en (sht:fw-edit en 'STAMP))
  (sht:watch)
  (princ))

;; ¬ыбрать лист щелчком: промах Ч ещЄ раз, не лист Ч сообщение, Enter Ч nil
(defun sht:pick (msg / r e)
  (while (not r)
    (setq e (entsel msg))
    (cond
      (e (if (sht:sheet-p (car e))
           (setq r (car e))
           (princ "\nЁто не лист SHEETS - щЄлкните рамку или штамп листа.")))
      ((= (getvar "ERRNO") 7) (princ "\nѕромах."))
      (t (setq r 'EXIT))))
  (if (eq r 'EXIT) nil r))

;; ќкно ЂЋистї дл€ листа en: формат, кратность, ориентаци€, штамп, масштаб Ч замена блока на месте;
;; номер и наименование Ч в атрибуты; Ђ¬се пол€ штампа...ї / Ђƒанные бокового штампа...ї Ч затем
;; окно-штамп этого листа (s0.11).
;; ¬озвращает ename листа (после замены Ч новый).
(defun sht:edit-sheet (en / doc sdat ens attrs r inf a0 ret rec changed new p lr sr
                          sht:mode sht:fmt sht:mult sht:or sht:form sht:sc0 sht:no0 sht:title0 sht:res
                          sht:cur sht:diff sht:pend sht:gnl sht:nsh sht:obozn0 sht:sugg)
  (setq doc   (sht:doc)
        sdat  (sht:prepare)
        ens   (sht:sheets)
        attrs (mapcar 'sht:attrs ens)
        r     (sht:common-now attrs sdat)
        inf   (sht:sheet-info en)
        a0    (sht:attrs en)
        sht:cur    (car r)
        sht:diff   (cadr r)
        sht:mode   'EDIT
        sht:fmt    (car (car inf))
        sht:mult   (cadr (car inf))
        sht:or     (cadr inf)
        sht:form   (caddr inf)
        sht:sc0    (cadddr inf)
        sht:no0    (sht:trim (cond ((cdr (assoc "SHEET" a0))) ("")))
        sht:title0 (cond ((cdr (assoc "TITLE" a0))) (""))
        sht:obozn0 (cond ((cdr (assoc "OBOZN" a0))) ((cdr (assoc "SHIFR" a0))) ((cdr (assoc "SHIFR" sht:cur))) (""))
        sht:gnl    (sht:gnums (vl-remove en ens))
        sht:nsh    (length ens)
        ret        (sht:sheet-dialog))
  (if sht:pend
    (setq sdat (progn (sht:commit-data doc sht:cur sht:pend ens sdat) (sht:set-read))))
  (if (member ret '(1 3 4))
    (progn
      (setq rec     (sht:fmt-rec (nth 0 sht:res) (nth 1 sht:res))
            changed (or (not (equal rec (car inf)))
                        (/= (nth 2 sht:res) (cadr inf))
                        (/= (nth 3 sht:res) (caddr inf))
                        (> (abs (- (nth 4 sht:res) (cadddr inf))) 1e-9))
            new     (list (cons "SHEET" (nth 5 sht:res)) (cons "TITLE" (nth 6 sht:res))
                          (cons "OBOZN" (nth 7 sht:res))))
      (vla-StartUndoMark doc)
      (if changed
        (setq en (sht:replace en rec (nth 2 sht:res) (nth 3 sht:res) (nth 4 sht:res) sht:cur new))
        (progn
          (foreach a (sht:att-objs en)
            (if (setq p (assoc (strcase (vla-get-TagString a)) new))
              (vla-put-TextString a (cdr p))))
          (sht:fit-sheet en)))
      (setq sr (sht:sign-auto T))               ; подписи и логотип (s0.7)
      (setq lr (sht:list-auto T))               ; ведомость листов и ЂЋистовї (s0.5)
      (vla-EndUndoMark doc)
      (princ (strcat "\nЋист " (if (= (nth 5 sht:res) "") "(без номера)" (nth 5 sht:res))
                     (if changed
                       (strcat ": " (sht:fmt-label rec) (if (= (nth 2 sht:res) "P") " вертикальный" " горизонтальный")
                               ", 1:" (sht:n2s (nth 4 sht:res)) ", блок "
                               (sht:bname rec (nth 2 sht:res) (nth 3 sht:res)) " (заменЄн на том же месте).")
                       ": записано.")))
      (if lr (sht:list-msg lr nil))
      (if sr (sht:sign-msg sr nil))
      (cond                                     ; s0.11: окна в виде штампа дл€ этого листа
        ((= ret 3) (sht:fw-edit en 'STAMP))
        ((= ret 4) (sht:fw-edit en 'SIDE)))))
  en)

(defun c:SHEET_EDIT ( / ss en)
  (sht:dblclick-setup)
  (if (and (setq ss (ssget "_I")) (sht:sheet-p (ssname ss 0)))
    (setq en (ssname ss 0)))
  (sssetfirst nil nil)
  (if (not en) (setq en (sht:pick "\n¬ыберите лист - рамку или штамп (Enter - выход): ")))
  (if en (sht:edit-sheet en))
  (sht:watch)
  (princ))

;; ƒвойной щелчок по листу Ч два пути (s0.2.2), срабатывает тот, что работает у AutoCAD пользовател€:
;;  1) реактор мыши (раздел 12): щелчок по листу Ч гасит обычное действие (DBLCLKEDIT) и запускает
;;     SHEET_DBLEDIT; не зависит от настройки двойного щелчка в CUI;
;;  2) встроенна€ EATTEDIT отключаетс€ (UNDEFINE "_EATTEDIT" Ч английское им€: в русском AutoCAD
;;     "EATTEDIT" без "_" не находилась, s0.2.1), двойной щелчок по блоку с атрибутами вызывает c:EATTEDIT.
;; ќкно открываетс€ один раз: кто первый Ч открывает, второй видит это и молчит.
(defun c:EATTEDIT ( / ss en)
  (sht:dbl-restore)
  (setq ss (ssget "_I"))
  (if ss (setq en (ssname ss 0)))
  (sssetfirst nil nil)
  (cond
    ((and en (sht:sheet-p en))
     (setq *sht:DblEn* nil)                       ; SHEET_DBLEDIT от реактора Ч уже не нужна
     (sht:edit-sheet en)
     (sht:watch)
     (setq *sht:DblDone* (getvar "MILLISECS")))
    (en (command "_.EATTEDIT" en))
    ;; окно по этому двойному щелчку только что открыл реактор Ч не спрашивать блок
    ((and *sht:DblDone* (< (abs (- (getvar "MILLISECS") *sht:DblDone*)) 3000))
     (setq *sht:DblDone* nil))
    (t (command "_.EATTEDIT")))
  (princ))

;; «апускаетс€ реактором мыши: окно ЂЋистї дл€ листа, по которому дважды щЄлкнули
(defun c:SHEET_DBLEDIT ( / en)
  (sht:dbl-restore)
  (sht:dblclick-setup)                               ; s0.14: первый двойной щелчок Ч настройка здесь
  (setq en          *sht:DblEn*
        *sht:DblEn* nil)
  (cond
    ((not (and en (entget en) (sht:sheet-p en))))   ; окно уже открыл c:EATTEDIT
    ((= (getvar "BLOCKEDITOR") 1)
     (princ "\nSHEETS: двойной щелчок открыл редактор блоков - обычное действие не отключилось."))
    (t
     (sssetfirst nil nil)
     (sht:edit-sheet en)
     (sht:watch)
     (setq *sht:DblDone* (getvar "MILLISECS"))))
  (princ))

(defun sht:dblclick-setup ( / ce)
  (sht:react-ensure)
  (if (and (not *sht:DblOn*) (/= (getenv "SHT_DblClick") "0"))
    (progn
      (setq ce (getvar "CMDECHO"))
      (setvar "CMDECHO" 0)
      (command "_.UNDEFINE" "_EATTEDIT")
      (setvar "CMDECHO" ce)
      (setq *sht:DblOn* T)))
  *sht:DblOn*)

;; ¬ключить / выключить окно ЂЋистї по двойному щелчку (запоминаетс€ в реестре)
(defun c:SHEET_DBLCLICK ( / ce)
  (setq ce (getvar "CMDECHO"))
  (setvar "CMDECHO" 0)
  (if (= (getenv "SHT_DblClick") "0")
    (progn
      (setenv "SHT_DblClick" "1")
      (sht:dblclick-setup)
      (princ "\nƒвойной щелчок по листу: окно ЂЋистї (включено)."))
    (progn
      (setenv "SHT_DblClick" "0")
      (command "_.REDEFINE" "_EATTEDIT")
      (setq *sht:DblOn* nil)
      (if *sht:RMouse* (vlr-remove *sht:RMouse*))
      (setq *sht:RMouse* nil)
      (sht:dbl-restore)
      (princ "\nƒвойной щелчок по листу: обычный редактор атрибутов (выключено).")))
  (setvar "CMDECHO" ce)
  (princ))

;; ¬писать тексты всех листов в графы (после правки атрибутов в Ђ—войствахї или редакторе)
(defun c:SHEET_UPDATE ( / doc sdat r n lr sr)
  (setq doc  (sht:doc)
        sdat (sht:prepare))
  (sht:dblclick-setup)
  (vla-StartUndoMark doc)
  (sht:apply-props)
  (setq n (sht:fit-all)
        r (sht:common-now (mapcar 'sht:attrs (sht:sheets)) sdat))
  (sht:stage-layer (cdr (assoc "STAGE" (car r))))
  (setq lr (sht:list-update nil T))          ; ведомость листов и ЂЋистовї (s0.5)
  (setq sr (sht:sign-sync T))                ; подписи и логотип Ч заново (s0.7)
  (vla-EndUndoMark doc)
  (sht:watch)
  (princ (strcat "\nЋистов обновлено: " (itoa n) " (тексты вписаны в графы)."))
  (sht:list-msg lr nil)
  (if sr (sht:sign-msg sr nil))
  (princ))

;; –азбор объекта (дл€ перехода с —ѕƒ—): тип, класс, габарит, DXF-данные, свойства ActiveX
(defun c:SHEET_PROBE ( / e ed o on r mn mx)
  (if (setq e (car (entsel "\nќбъект дл€ разбора (формат —ѕƒ— и т. п.): ")))
    (progn
      (setq ed (entget e)
            o  (vlax-ename->vla-object e)
            on (vl-catch-all-apply 'vla-get-ObjectName (list o)))
      (princ (strcat "\n“ип: " (cdr (assoc 0 ed)) ", слой: " (cdr (assoc 8 ed))
                     (if (= (type on) 'STR) (strcat ", класс: " on) "")))
      (setq r (vl-catch-all-apply 'vla-GetBoundingBox (list o 'mn 'mx)))
      (if (not (vl-catch-all-error-p r))
        (progn
          (setq mn (vlax-safearray->list mn)
                mx (vlax-safearray->list mx))
          (princ (strcat "\n√абарит: " (sht:n2s (- (car mx) (car mn))) " x " (sht:n2s (- (cadr mx) (cadr mn)))
                         ", левый нижний угол " (sht:n2s (car mn)) "," (sht:n2s (cadr mn))))))
      (princ "\n--- DXF (без двоичных данных):")
      (foreach g ed
        (if (not (member (car g) '(310 -1 330 360)))
          (progn (princ "\n") (prin1 g))))
      (princ "\n--- свойства ActiveX:")
      (vl-catch-all-apply 'vlax-dump-object (list o T))
      (textscr)))
  (princ))

;;; --------------------------------------------------------------------------
;;;  12. ‘ќ–ћј“ ¬ Ђ—¬ќ…—“¬ј’ї » –≈ј “ќ–џ (s0.2.2)
;;; --------------------------------------------------------------------------
;; Ћист: атрибут FORMAT (графа 26: ЂA3ї, ЂA4x3ї) и невидимый ORIENT (Ђгоризонтальна€ї / Ђвертикальна€ї)
;; видны в Ђ—войствахї (раздел Ђјтрибутыї). ѕомен€ли Ч реактор на этих атрибутах запускает SHEET_APPLY:
;; лист перестраиваетс€ на месте (как из окна ЂЋистї). ¬ыпадающий список в Ђ—войствахї бывает только
;; у динамических блоков Ч из LISP их не создать, поэтому значение вписываетс€.

;; ‘ормат из записи: "A3", "a4x3", Ђј4х3ї (кириллица), "A0 x 2" -> запись формата или nil
(defun sht:parse-fmt (s / i)
  (setq s (strcase (vl-string-translate "ја’х*" "AaXxx" (sht:trim s))))
  (while (setq i (vl-string-search " " s))
    (setq s (strcat (substr s 1 i) (substr s (+ i 2)))))
  (cond
    ((not (wcmatch s "A#,A#X#")) nil)
    ((setq i (vl-string-search "X" s)) (sht:fmt-rec (substr s 1 i) (atoi (substr s (+ i 2)))))
    (t (sht:fmt-rec s 1))))

;; ќриентаци€ из записи: г / горизонтальна€ / L -> "L"; в / вертикальна€ / P -> "P"; иначе nil
(defun sht:parse-orient (s / c)
  (setq c (substr (sht:trim s) 1 1))
  (cond ((member c '("г" "√" "L" "l" "H" "h")) "L")
        ((member c '("в" "¬" "P" "p" "V" "v")) "P")))

;; ‘ормат / ориентаци€ в атрибутах листа против блока: nil Ч совпадают; (запись ориентаци€) Ч помен€ли;
;; BAD Ч запись не пон€та
(defun sht:props-want (en / inf a f o rec orient)
  (setq inf (sht:sheet-info en)
        a   (sht:attrs en)
        f   (cdr (assoc "FORMAT" a))
        o   (cdr (assoc "ORIENT" a)))
  (if (and inf f o)
    (progn
      (setq rec    (sht:parse-fmt f)
            orient (sht:parse-orient o))
      (if (and rec (sht:portrait-only-p (car rec) (cadr rec))) (setq orient "P"))
      (cond
        ((or (null rec) (null orient)) 'BAD)
        ((and (equal rec (car inf)) (= orient (cadr inf))) nil)
        (t (list rec orient))))))

;; «аписать в FORMAT / ORIENT формат и ориентацию блока (вид ЂA3ї, Ђвертикальна€ї)
(defun sht:props-reset (en inf / tag v)
  (foreach a (sht:att-objs en)
    (setq tag (strcase (vla-get-TagString a))
          v   (cond ((= tag "FORMAT") (sht:fmt-label (car inf)))
                    ((= tag "ORIENT") (sht:orient-name (cadr inf)))))
    (if (and v (/= v (vla-get-TextString a)))
      (vla-put-TextString a v))))

(defun sht:sheet-no (en / s)
  (setq s (sht:trim (cdr (assoc "SHEET" (sht:attrs en)))))
  (if (= s "") "(без номера)" s))

(defun sht:fmt-list-str ( / res)
  (foreach r *sht:Formats* (setq res (cons (sht:fmt-label r) res)))
  (setq res (reverse res))
  (apply 'strcat (cons (car res) (mapcar '(lambda (x) (strcat ", " x)) (cdr res)))))

;; ѕерестроить листы, у которых FORMAT / ORIENT не совпадают с блоком; непон€тна€ запись Ч
;; вернуть прежнюю. ¬озвращает (набор-новых-листов-или-nil число).
(defun sht:apply-props ( / inf a w new sel n)
  (setq sel (ssadd)
        n   0)
  (foreach en (sht:sheets)
    (setq inf (sht:sheet-info en)
          a   (sht:attrs en)
          w   (sht:props-want en))
    (cond
      ((eq w 'BAD)
       (princ (strcat "\nЋист " (sht:sheet-no en) ": не пон€то Ђ" (cond ((cdr (assoc "FORMAT" a))) (""))
                      "ї / Ђ" (cond ((cdr (assoc "ORIENT" a))) ("")) "ї - оставлен " (sht:fmt-label (car inf))
                      ", " (sht:orient-name (cadr inf)) ".\n  ‘орматы: " (sht:fmt-list-str)
                      ".\n  ќриентаци€: горизонтальна€ / вертикальна€ (можно г / в)."))
       (sht:props-reset en inf))
      (w
       (setq new (sht:replace en (car w) (cadr w) (caddr inf) (cadddr inf) nil nil)
             n   (1+ n))
       (ssadd new sel)
       (princ (strcat "\nЋист " (sht:sheet-no new) ": " (sht:fmt-label (car w)) ", " (sht:orient-name (cadr w))
                      " - перестроен на месте, блок " (sht:bname (car w) (cadr w) (caddr inf)) ".")))
      (t (sht:props-reset en inf))))
  (list (if (> n 0) sel) n))

;; ‘ормат / ориентаци€ помен€ли в Ђ—войствахї (или в редакторе атрибутов) Ч перестроить листы.
;; «апускаетс€ сама (реактор), можно и вручную.
(defun c:SHEET_APPLY ( / doc r)
  (setq *sht:ApplyQ* nil
        doc          (sht:doc))
  (sht:prepare)
  (vla-StartUndoMark doc)
  (setq r (sht:apply-props))
  (sht:sign-auto nil)                        ; s0.7
  (vla-EndUndoMark doc)
  (sht:watch)
  (if (car r) (sssetfirst nil (car r)))      ; новые листы Ч выделены, Ђ—войстваї показывают их
  (princ))

;; --- реакторы: метка "SHEETS" (при повторной загрузке файла прежние снимаютс€) ---
(defun sht:react-remove ()
  (foreach grp (vlr-reactors :vlr-mouse-reactor :vlr-editor-reactor :vlr-object-reactor)
    (foreach r (cdr grp)
      (if (= (vlr-data r) "SHEETS") (vlr-remove r))))
  (setq *sht:RMouse* nil *sht:REditor* nil *sht:RAtts* nil *sht:RTbls* nil *sht:TblDirty* nil
        *sht:RSign* nil *sht:SignDirty* nil))

(defun sht:react-ensure ()
  (if (not *sht:REditor*)
    (setq *sht:REditor*
      (vlr-editor-reactor "SHEETS"
        '((:vlr-commandWillStart . sht:r-cmd-start) (:vlr-commandEnded . sht:r-cmd-end)
          (:vlr-commandCancelled . sht:r-cmd-end) (:vlr-commandFailed . sht:r-cmd-end)))))
  (if (and (/= (getenv "SHT_DblClick") "0") (not *sht:RMouse*))
    (setq *sht:RMouse* (vlr-mouse-reactor "SHEETS" '((:vlr-beginDoubleClick . sht:r-dbl)))))
  (if (not *sht:RAtts*) (sht:watch))
  (if (not *sht:RTbls*) (sht:tbl-watch))          ; s0.6.1: таблицы (спецификации)
  T)

;; „исло вставок SHT_* в чертеже (изменилось Ч пересобрать наблюдение)
(defun sht:sheet-count ( / ss)
  (if (setq ss (ssget "_X" '((0 . "INSERT") (2 . "SHT_*")))) (sslength ss) 0))

;; „исло таблиц AutoCAD в чертеже (s0.6: изменилось и есть ведомость спецификаций Ч обновить еЄ)
(defun sht:table-count ( / ss)
  (if (setq ss (ssget "_X" '((0 . "ACAD_TABLE")))) (sslength ss) 0))

;; s0.6.1: наблюдать за всеми таблицами, кроме таблиц SHEETS: изменилась (правка €чейки, перенос, ручки,
;; Ђ—войстваї) Ч флаг *sht:TblDirty*; в конце команды есть флаг и ведомость спецификаций Ч обновить еЄ
;; (sht:watch-check). —ам реактор ничего в чертеже не мен€ет. ¬озвращает число таблиц под наблюдением.
(defun sht:tbl-watch ( / ss i en objs)
  (if *sht:RTbls* (vlr-remove *sht:RTbls*))
  (setq *sht:RTbls*    nil
        *sht:TblDirty* nil)
  (if (setq ss (ssget "_X" '((0 . "ACAD_TABLE"))))
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq en (ssname ss i)
              i  (1+ i))
        (if (not (sht:tbl-mark en))
          (setq objs (cons (vlax-ename->vla-object en) objs))))))
  (if objs
    (setq *sht:RTbls* (vlr-object-reactor objs "SHEETS" '((:vlr-modified . sht:r-tbl-mod)))))
  (length objs))

(defun sht:r-tbl-mod (obj r args)
  (setq *sht:TblDirty* T)
  (princ))

;; Ќаблюдать за атрибутами FORMAT / ORIENT всех листов; запомнить их значени€
(defun sht:watch ( / objs tag)
  (if *sht:RAtts* (vlr-remove *sht:RAtts*))
  (setq *sht:RAtts*     nil
        *sht:WatchVals* nil)
  (foreach en (sht:sheets)
    (foreach a (sht:att-objs en)
      (setq tag (strcase (vla-get-TagString a)))
      (if (member tag '("FORMAT" "ORIENT"))
        (setq objs            (cons a objs)
              *sht:WatchVals* (cons (cons (vla-get-Handle a) (vla-get-TextString a)) *sht:WatchVals*)))))
  (if objs
    (setq *sht:RAtts* (vlr-object-reactor objs "SHEETS" '((:vlr-modified . sht:r-att-mod)))))
  (sht:sign-watch)                               ; s0.7: листы и фамилии Ч дл€ подписей
  (setq *sht:SignDirty* nil
        *sht:WatchCnt* (sht:sheet-count)
        *sht:WatchTbl* (sht:table-count))
  (length objs))

;; јтрибут FORMAT / ORIENT изменЄн: значение другое Ч поставить SHEET_APPLY в очередь (один раз)
(defun sht:r-att-mod (obj r args)
  (vl-catch-all-apply 'sht:on-att-mod (list obj))
  (princ))

(defun sht:on-att-mod (obj / old)
  (if (and (not *sht:ApplyQ*)
           (not (vlax-erased-p obj))
           (setq old (assoc (vla-get-Handle obj) *sht:WatchVals*))
           (/= (cdr old) (vla-get-TextString obj)))
    (progn
      (setq *sht:ApplyQ* T)
      (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SendCommand (list (sht:doc) "_SHEET_APPLY ")))
        (progn
          (setq *sht:ApplyQ* nil)
          (princ "\nSHEETS: формат / ориентаци€ листа изменены - чтобы перестроить лист, введите SHEET_APPLY."))))))

;; Ќачало любой команды Ч вернуть двойной щелчок (DBLCLKEDIT), если гасили;
;; s0.5: перед сохранением и печатью Ч обновить ведомость листов и ЂЋистовї; s0.7: сначала подписи и логотип
(defun sht:r-cmd-start (r args)
  (vl-catch-all-apply 'sht:dbl-restore nil)
  (if (and (= (type (car args)) 'STR) (member (strcase (car args)) *sht:ListCmds*))
    (progn
      (vl-catch-all-apply 'sht:sign-auto (list nil))
      (vl-catch-all-apply 'sht:list-auto (list nil))))
  (princ))

;;  онец команды: копирование, отмена и т. п. Ч пересобрать наблюдение за атрибутами;
;; s0.5.1: листов стало больше / меньше Ч сразу ведомость листов (sht:watch-check)
(defun sht:r-cmd-end (r args)
  (setq *sht:ApplyQ* nil)
  (vl-catch-all-apply 'sht:watch-check (list (car args)))
  (princ))

(defun sht:watch-check (cmd / chg tc chgt dirty undo sdirty)
  (setq cmd   (if (= (type cmd) 'STR) (strcase cmd) "")
        undo  (wcmatch cmd "U,UNDO,REDO,MREDO")
        chg   (/= (sht:sheet-count) *sht:WatchCnt*)
        tc    (sht:table-count)
        chgt  (/= tc *sht:WatchTbl*)
        dirty *sht:TblDirty*
        sdirty *sht:SignDirty*            ; s0.7: лист сдвинули, фамилию помен€ли
        *sht:SignDirty* nil)
  (if (or chg (wcmatch cmd "U,UNDO,REDO,MREDO,OOPS,ATTSYNC,BATTMAN"))
    (sht:watch))
  ;; s0.6.1: таблиц стало больше / меньше, отмена Ч наблюдение за таблицами заново (флаг снимаетс€)
  (if (or chgt undo (= cmd "OOPS"))
    (sht:tbl-watch))
  (setq *sht:WatchTbl* tc
        *sht:TblDirty* nil)
  ;; s0.5.1: число листов изменилось (ERASE, Delete, вырезать, копировать, вставить Е) Ч ведомость сразу.
  ;; s0.6: число таблиц изменилось (спецификацию вставили, удалили) и есть ведомость спецификаций Ч тоже;
  ;; s0.6.1: и когда таблица изменилась (заголовок поправили Ч TABLEDIT, перенесли Ч MOVE, ручки Е).
  ;; ѕосле U / UNDO / REDO Ч нет: сво€ запись Ђќтменыї перепутала бы цепочку; обновитс€ при сохранении.
  ;; s0.7: подписи и логотип Ч листов стало больше / меньше, лист сдвинули, фамилию помен€ли (так же, не после U)
  (if (and (or chg sdirty) (not undo))
    (sht:sign-auto nil))
  (if (and (or chg (and (or chgt dirty) (sht:kind-tables "SPEC")))
           (not undo))
    (sht:list-auto nil))
  ;; s0.13: ведомость перенесли на другое место / лист Ч разрыв по высоте листа
  (if (not undo) (sht:brk-all)))

;; --- двойной щелчок (реактор мыши) ---
(defun sht:dbl-on-p ( / v)
  (setq v (getvar "DBLCLKEDIT"))
  (or (equal v 1) (and (= (type v) 'STR) (= (strcase v) "ON"))))

(defun sht:dbl-set (on / v)
  (setq v (getvar "DBLCLKEDIT"))
  (vl-catch-all-apply 'setvar (list "DBLCLKEDIT" (if (= (type v) 'STR) (if on "ON" "OFF") (if on 1 0)))))

;; ƒвойной щелчок гасили Ч включить (метка в реестре: и после сбо€ AutoCAD)
(defun sht:dbl-restore ()
  (if (= (getenv "SHT_DblOff") "1")
    (progn
      (setenv "SHT_DblOff" "0")
      (sht:dbl-set T))))

;; Ћист под точкой двойного щелчка (рамка, штамп или атрибут) или nil
(defun sht:dbl-target (pt / r e ed ss)
  (setq r (vl-catch-all-apply 'nentselp (list (trans pt 0 1))))
  (cond
    ((vl-catch-all-error-p r)                ; nentselp недоступен Ч лист, выделенный первым щелчком
     (if (and (setq ss (cadr (ssgetfirst))) (= (sslength ss) 1))
       (setq e (ssname ss 0))))
    ((and r (setq ed (entget (car r))))
     (cond
       ((= (cdr (assoc 0 ed)) "ATTRIB") (setq e (cdr (assoc 330 ed))))
       ((and (cadddr r) (listp (cadddr r))) (setq e (last (cadddr r)))))))
  (if (and e (sht:sheet-p e)) e))

(defun sht:r-dbl (r args)
  (vl-catch-all-apply 'sht:on-dbl (list (car args)))
  (princ))

(defun sht:on-dbl (pt / en)
  (sht:dbl-restore)
  (setq *sht:DblDone* nil)
  (if (and (= (getvar "CMDNAMES") "")
           (sht:dbl-on-p)
           (setq en (sht:dbl-target pt)))
    (progn
      (setq *sht:DblEn* en)
      (setenv "SHT_DblOff" "1")
      (sht:dbl-set nil)                      ; обычное действие двойного щелчка Ч на этот раз нет
      (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SendCommand (list (sht:doc) "_SHEET_DBLEDIT ")))
        (progn
          (sht:dbl-restore)
          (setq *sht:DblEn* nil)
          (princ "\nSHEETS: окно листа по двойному щелчку не открылось - используйте SHEET_EDIT."))))))

;;; --------------------------------------------------------------------------
;;;  13. ѕ≈„ј“№ ¬ PDF (s0.3): SHEET_PLOT
;;;  Ћисты Ч по номерам (sht:num<); без номера не печатаютс€ (список Ч в командной строке и в окне).
;;;  Ќа каждый лист Ч временный набор параметров листа модели SHT_PLOT_<врем€>_nnn: DWG To PDF.pc3,
;;;  бумага Ч по размеру листа (кандидаты Ч по двум последним числам канонического имени,
;;;  размер и пол€ Ч у плоттера: GetPaperSize / GetPaperMargins; лучше без полей, затем без поворота),
;;;  окно = лист в модели (в экранных координатах: trans 0 -> 2), масштаб 1:масштаб листа, по центру.
;;;  ќдин PDF Ч -PUBLISH по списку DSD (Type=6, закладки ЂЋист N. Ќаименованиеї);
;;;  отдельные файлы Ч PlotToFile с параметрами листа модели (прежние Ч в SHT_PLOTSAVE, возвращаютс€).
;;;  ¬ременные наборы удал€ютс€ после печати, при ошибке и при следующем запуске (после сбо€).
;;; --------------------------------------------------------------------------

(setq *sht:Pc3*       "DWG To PDF.pc3"
      *sht:PcPrefix*  "SHT_PLOT_"        ; временные наборы параметров листа
      *sht:PcSave*    "SHT_PLOTSAVE"     ; копи€ параметров листа модели на врем€ печати
      *sht:PlotSaved* nil                ; системные переменные до печати: ((им€ . значение) Е)
      *sht:ModelArea* nil)               ; область печати листа модели до печати (s0.3.2)

(defun sht:pcs () (vla-get-PlotConfigurations (sht:doc)))
(defun sht:model-layout () (vla-get-Layout (sht:ms)))

;; Ќабор параметров листа по имени или nil
(defun sht:pc-get (name / r)
  (setq r (vl-catch-all-apply 'vla-Item (list (sht:pcs) name)))
  (if (vl-catch-all-error-p r) nil r))

;; ”далить временные наборы SHT_PLOT_*; осталась копи€ параметров модели (сбой печати) Ч вернуть еЄ.
;; ¬озвращает число удалЄнных наборов.
(defun sht:pc-purge ( / lst sv pc)
  (vlax-for pc (sht:pcs)
    (if (wcmatch (strcase (vla-get-Name pc)) (strcat *sht:PcPrefix* "*"))
      (setq lst (cons pc lst))))
  (foreach pc lst (vl-catch-all-apply 'vla-Delete (list pc)))
  (if (setq sv (sht:pc-get *sht:PcSave*))
    (progn
      (vl-catch-all-apply 'vla-CopyFrom (list (sht:model-layout) sv))
      (if *sht:ModelArea* (sht:model-area-set (sht:model-layout) *sht:ModelArea*))
      (vl-catch-all-apply 'vla-Delete (list sv))))
  (setq *sht:ModelArea* nil)
  (length lst))

;; —истемные переменные на врем€ печати: lst Ч ((им€ . значение) Е); прежние Ч в *sht:PlotSaved*
(defun sht:plot-sv-set (lst / v)
  (foreach p lst
    (setq v (getvar (car p)))
    (if (and v (not (assoc (car p) *sht:PlotSaved*)))
      (setq *sht:PlotSaved* (cons (cons (car p) v) *sht:PlotSaved*)))
    (if (and v (not (equal v (cdr p))))
      (vl-catch-all-apply 'setvar (list (car p) (cdr p))))))

;; ѕосле печати и при ошибке: временные наборы, параметры модели, системные переменные
(defun sht:plot-cleanup ()
  (vl-catch-all-apply 'sht:pc-purge nil)
  (foreach p *sht:PlotSaved*
    (if (not (equal (getvar (car p)) (cdr p)))
      (vl-catch-all-apply 'setvar (list (car p) (cdr p)))))
  (setq *sht:PlotSaved* nil))

;; --- строки, имена файлов, папки -------------------------------------------

;; “екст атрибута без кодов многострочного текста: Ђ\Pї Ч пробел, фигурные скобки убрать
(defun sht:plain (s / i)
  (setq s (if s s ""))
  (while (setq i (vl-string-search "\\P" s))
    (setq s (strcat (substr s 1 i) " " (substr s (+ i 3)))))
  (sht:trim (vl-string-translate "{}" "  " s)))

;; —клеить строки через sep
(defun sht:join (lst sep / s)
  (setq s nil)
  (foreach x lst (setq s (if s (strcat s sep x) x)))
  (if s s ""))

;; »м€ файла: недопустимые знаки \ / : * ? " < > | и табул€ци€ Ч на Ђ_ї; без точек и пробелов в конце
(defun sht:fname (s)
  (vl-string-right-trim ". " (sht:trim (vl-string-translate "\\/:*?\"<>|\t" "__________" s))))

;; —делать им€ уникальным среди used (без учЄта регистра): Ђим€ї, Ђим€ (2)ї, Е
(defun sht:uniq-name (s used / n r up)
  (setq up (mapcar 'strcase used)
        r  s
        n  1)
  (while (member (strcase r) up)
    (setq n (1+ n)
          r (strcat s " (" (itoa n) ")")))
  r)

(defun sht:pad3 (k / s)
  (setq s (itoa k))
  (while (< (strlen s) 3) (setq s (strcat "0" s)))
  s)

;; ÷елые без повторов, по возрастанию; (sht:range 0 3) -> (0 1 2)
(defun sht:uniq-sort (lst / res)
  (foreach x lst (if (not (member x res)) (setq res (cons x res))))
  (vl-sort res '<))

(defun sht:range (a b / res)
  (while (< a b)
    (setq b   (1- b)
          res (cons b res)))
  res)

;; »ндексы списка окна: "0 3 5" <-> (0 3 5)
(defun sht:idx-read (s / res)
  (foreach x (sht:split (sht:trim s) " ")
    (if (/= x "") (setq res (cons (atoi x) res))))
  (reverse res))

(defun sht:idx-str (lst)
  (sht:join (mapcar 'itoa lst) " "))

(defun sht:find-ci (s lst)
  (vl-some '(lambda (x) (if (= (strcase x) (strcase s)) x)) lst))

(defun sht:dir-norm (d) (vl-string-right-trim "\\/ " (sht:trim d)))
(defun sht:plot-dir-default () (strcat (getvar "DWGPREFIX") "PDF"))

;; ѕапка дл€ PDF: выбранна€ дл€ этого чертежа (словарь SHT_SET, ключ @PDFDIR) или подпапка PDF у чертежа
(defun sht:plot-dir-load (sdat / d)
  (setq d (sht:dir-norm (cdr (assoc "@PDFDIR" sdat))))
  (if (= d "") (sht:plot-dir-default) d))

(defun sht:plot-dir-save (dir / sdat old new)
  (setq sdat (sht:set-read)
        old  (cond ((cdr (assoc "@PDFDIR" sdat))) (""))
        new  (if (= (strcase dir) (strcase (sht:plot-dir-default))) "" dir))
  (if (/= old new) (sht:set-write (sht:alist-put sdat "@PDFDIR" new))))

;; —оздать папку (и недостающие выше). T Ч папка есть
(defun sht:mkdir (d / up)
  (cond
    ((vl-file-directory-p d) T)
    ((and (setq up (vl-filename-directory d)) (/= up "") (/= (strcase up) (strcase d)) (sht:mkdir up))
     (vl-mkdir d)
     (vl-file-directory-p d))))

;; ќткрыть файл или папку в Windows (программа просмотра PDF / ѕроводник)
(defun sht:open-path (p / sh r)
  (setq sh (vl-catch-all-apply 'vlax-create-object (list "Shell.Application")))
  (if (and sh (not (vl-catch-all-error-p sh)))
    (progn
      (setq r (vl-catch-all-apply 'vlax-invoke (list sh 'ShellExecute p)))
      (vl-catch-all-apply 'vlax-release-object (list sh)))
    (setq r (vl-catch-all-error-p T)))
  (if (or (null sh) (vl-catch-all-error-p sh) (vl-catch-all-error-p r))
    (vl-catch-all-apply 'startapp (list "explorer.exe" (strcat "\"" p "\"")))))

;; --- листы дл€ печати ---------------------------------------------------------

;; Ћист: (ename номер наименование формат ориентаци€ масштаб точка ширина высота поворот шифр)
(defun sht:plot-item (en / inf a wh ed)
  (setq inf (sht:sheet-info en)
        a   (sht:attrs en)
        wh  (sht:fmt-wh (car inf) (cadr inf))
        ed  (entget en))
  ;; 10 Ч графа 1 (шифр; у форм 4, 5 Ч обозначение документа), 11 Ч 0 основной комплект (форма 3) /
  ;; 1 документы форм 4, 5, 6 (s0.10), 12 Ч форма
  (list en (sht:trim (cdr (assoc "SHEET" a))) (sht:plain (cdr (assoc "TITLE" a)))
        (sht:fmt-label (car inf)) (cadr inf) (cadddr inf) (nth 4 inf) (car wh) (cadr wh)
        (cond ((cdr (assoc 50 ed))) (0.0))
        (sht:plain (cdr (assoc (if (sht:fdoc-p (caddr inf)) "OBOZN" "SHIFR") a)))
        (if (= (sht:fbase (caddr inf)) "3") 0 1)
        (caddr inf)))

;; ≈стественный пор€док строк (s0.10): цифры подр€д Ч числом (Ђ ∆»2ї < Ђ ∆»10ї), прочее Ч по знакам
;; без учЄта регистра
(defun sht:nat-key (s / i n c d res)
  (setq s (sht:lc (sht:trim (if (= (type s) 'STR) s "")))
        i 1
        n (strlen s))
  (while (<= i n)
    (setq c (substr s i 1))
    (if (wcmatch c "#")
      (progn
        (setq d 0.0)
        (while (and (<= i n) (wcmatch (setq c (substr s i 1)) "#"))
          (setq d (+ (* d 10.0) (atoi c))
                i (1+ i)))
        (setq res (cons (list 0 d) res)))
      (setq res (cons (list 1 (ascii c)) res)
            i   (1+ i))))
  (apply 'append (reverse res)))

(defun sht:nat< (a b) (sht:key< (sht:nat-key a) (sht:nat-key b)))

;; ѕор€док печати (s0.10, решение јртЄма): сначала основной комплект (форма 3) по номерам, затем
;; документы форм 4, 5, 6 по обозначению (графа 1), внутри Ч по номерам
(defun sht:plot< (a b)
  (cond
    ((< (nth 11 a) (nth 11 b)) T)
    ((> (nth 11 a) (nth 11 b)) nil)
    ((= (nth 11 a) 0) (sht:item< a b))
    ((sht:nat< (nth 10 a) (nth 10 b)) T)
    ((sht:nat< (nth 10 b) (nth 10 a)) nil)
    (t (sht:item< a b))))

;; Ћист дл€ сообщений: ЂЋист 3ї; у документов форм 4-6 Ч ЂЛобозначениеЫ, лист 2ї / ЂЛобозначениеЫї
(defun sht:plot-sheet (it)
  (cond ((/= (nth 11 it) 1) (strcat "Ћист " (nth 1 it)))
        ((= (nth 1 it) "") (nth 10 it))
        (t (strcat (nth 10 it) ", лист " (nth 1 it)))))

;; ѕор€док: по номеру; одинаковые номера Ч слева направо, затем сверху вниз
(defun sht:item< (a b)
  (cond
    ((sht:num< (nth 1 a) (nth 1 b)) T)
    ((sht:num< (nth 1 b) (nth 1 a)) nil)
    ((< (car (nth 6 a)) (car (nth 6 b))) T)
    ((> (car (nth 6 a)) (car (nth 6 b))) nil)
    (t (> (cadr (nth 6 a)) (cadr (nth 6 b))))))

;; Ћисты модели: (печатаемые-по-пор€дку без-номера). s0.10: лист документа формы 4 / 5 без номера
;; (однолистовой документ) Ч печатаетс€
(defun sht:plot-items ( / it on off)
  (foreach en (sht:sheets)
    (setq it (sht:plot-item en))
    (if (and (= (nth 1 it) "") (not (sht:fdoc-p (nth 12 it))))
      (setq off (cons it off))
      (setq on (cons it on))))
  (list (vl-sort on 'sht:plot<) (reverse off)))

(defun sht:plot-fmt (it)
  (strcat (nth 3 it) (if (= (nth 4 it) "P") " верт." " гор.") " 1:" (sht:n2s (nth 5 it))))

;; —трока списка окна: номер, формат, масштаб, наименование (через табул€цию)
(defun sht:plot-line (it)
  (strcat (if (= (nth 1 it) "") "-" (nth 1 it)) "\t" (nth 3 it) (if (= (nth 4 it) "P") " верт." " гор.")
          "\t1:" (sht:n2s (nth 5 it)) "\t"
          (if (= (nth 11 it) 1) (strcat (nth 10 it) (if (/= (nth 2 it) "") ". " "")) "")
          (nth 2 it)))

;; ќписание листа дл€ сообщений
(defun sht:plot-desc (it)
  (strcat (sht:plot-fmt it) (if (/= (nth 2 it) "") (strcat " Ђ" (nth 2 it) "ї") "")
          ", угол " (sht:n2s (car (nth 6 it))) "," (sht:n2s (cadr (nth 6 it)))))

;; ѕовтор€ющиес€ номера (sht:pitems); у документов форм 4-6 Ч внутри документа (s0.10)
(defun sht:plot-dups ( / seen res k nm)
  (foreach it sht:pitems
    (if (/= (nth 1 it) "")
      (progn
        (setq k  (strcat (if (= (nth 11 it) 1) (strcat (sht:lc (nth 10 it)) "|") "") (strcase (nth 1 it)))
              nm (if (= (nth 11 it) 1) (sht:plot-sheet it) (nth 1 it)))
        (if (member k seen)
          (if (not (member nm res)) (setq res (cons nm res)))
          (setq seen (cons k seen))))))
  (reverse res))

;; Ћисты без номера и повторы номеров Ч в командную строку
(defun sht:plot-warn-off ( / d)
  (if sht:poff
    (progn
      (princ (strcat "\nЋисты без номера - не печатаютс€ (" (itoa (length sht:poff)) "):"))
      (foreach it sht:poff (princ (strcat "\n  " (sht:plot-desc it))))))
  (if (setq d (sht:plot-dups))
    (princ (strcat "\n¬Ќ»ћјЌ»≈: номера листов повтор€ютс€: " (sht:join d ", ") "."))))

;; —трока окна о листах без номера и повторах
(defun sht:plot-off-str ( / s d)
  (setq s "")
  (if sht:poff
    (setq s (strcat "Ѕез номера - не печатаютс€ (" (itoa (length sht:poff)) "): "
                    (sht:join (mapcar 'sht:plot-desc sht:poff) "; "))))
  (if (setq d (sht:plot-dups))
    (setq s (strcat (if (= s "") "" (strcat s ". ")) "ѕовтор€ютс€ номера: " (sht:join d ", "))))
  (if (> (strlen s) 100) (strcat (substr s 1 97) "...") s))

;; ¬ыбранные до команды объекты (ename); выделение сн€ть
(defun sht:plot-presel0 ( / ss i res)
  (if (setq ss (ssget "_I"))
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq res (cons (ssname ss i) res)
              i   (1+ i)))))
  (sssetfirst nil nil)
  res)

;; ќтметка в окне при открытии: выбранные до команды листы, иначе все
(defun sht:plot-presel (ens / k res)
  (setq k 0)
  (foreach it sht:pitems
    (if (member (car it) ens) (setq res (cons k res)))
    (setq k (1+ k)))
  (if res (reverse res) (sht:range 0 (length sht:pitems))))

(defun sht:pick-items (idx)
  (vl-remove nil (mapcar '(lambda (i) (nth i sht:pitems)) idx)))

;; ќтметка по номерам: Ђ1-5, 7, 1.1ї; диапазон Ч по пор€дку номеров (Ђ-5ї Ч от начала, Ђ7-ї Ч до конца).
;; s0.10: только листы основного комплекта (документы форм 4-6 Ч щелчком в списке).
;; ¬озвращает (индексы-в-items ненайденное)
(defun sht:nums-pick (s items / res miss part i a b k ok)
  (foreach p0 (sht:split (vl-string-translate ";" "," s) ",")
    (setq part (sht:trim p0))
    (cond
      ((= part ""))
      ((setq i (vl-string-search "-" part))
       (setq a  (sht:trim (substr part 1 i))
             b  (sht:trim (substr part (+ i 2)))
             k  0
             ok nil)
       (foreach it items
         (if (and (/= (nth 11 it) 1)
                  (or (= a "") (not (sht:num< (nth 1 it) a)))
                  (or (= b "") (not (sht:num< b (nth 1 it)))))
           (setq res (cons k res)
                 ok  T))
         (setq k (1+ k)))
       (if (not ok) (setq miss (cons part miss))))
      (t
       (foreach tok (sht:split part " ")
         (if (/= tok "")
           (progn
             (setq k 0 ok nil)
             (foreach it items
               (if (and (/= (nth 11 it) 1) (= (strcase (nth 1 it)) (strcase tok)))
                 (setq res (cons k res)
                       ok  T))
               (setq k (1+ k)))
             (if (not ok) (setq miss (cons tok miss)))))))))
  (list (sht:uniq-sort res) (reverse miss)))

;; Ўифр дл€ имени файла: самый частый непустой на листах основного комплекта (s0.10), нет Ч на любых;
;; нет и там Ч им€ чертежа без расширени€
(defun sht:plot-shifr (items / v w)
  (foreach it items
    (if (/= (nth 10 it) "")
      (if (/= (nth 11 it) 1) (setq v (cons (nth 10 it) v)) (setq w (cons (nth 10 it) w)))))
  (cond (v (sht:most (reverse v)))
        (w (sht:most (reverse w)))
        (t (vl-filename-base (getvar "DWGNAME")))))

;; ‘айл комплекта: Ђ<шифр>.pdfї; файл листа (без расширени€): Ђ<шифр>_Ћист <N>ї
(defun sht:plot-file-all (items / s)
  (setq s (sht:fname (sht:plot-shifr items)))
  (strcat (if (= s "") " омплект" s) ".pdf"))

;; s0.10: документ формы 4 / 5 Ч ЂЛобозначениеЫ_Ћист Nї, без номера Ч ЂЛобозначениеЫї
(defun sht:plot-file-base (it base)
  (sht:fname (strcat (if (/= (nth 10 it) "") (nth 10 it) base)
                     (if (= (nth 1 it) "") "" (strcat "_Ћист " (nth 1 it))))))

(defun sht:plot-file-one (it base) (strcat (sht:plot-file-base it base) ".pdf"))

;; »м€ листа в PDF (закладка): ЂЋист 3. Ќаименованиеї. «наки, которых AutoCAD может не прин€ть
;; в имени листа (и скобки разделов списка): [ ] \ / : * ? " < > | = -> ( ) - - . x пробел ' ( ) - -
(defun sht:dsd-name (it / s)
  (setq s (vl-string-translate "[]\\/:*?\"<>|=" "()--.x '()--"
                               (strcat (sht:plot-sheet it) (if (/= (nth 2 it) "") (strcat ". " (nth 2 it)) ""))))
  (if (> (strlen s) 120) (strcat (substr s 1 117) "...") s))

;; --- плоттер, бумага, наборы параметров ---------------------------------------

;; —тили печати: CTB (чертЄж в цветозависимом режиме, PSTYLEMODE = 1) или STB (именованный)
(defun sht:ctb-list ( / r res mask)
  (setq mask (if (= (getvar "PSTYLEMODE") 0) "*`.STB" "*`.CTB")
        r    (vl-catch-all-apply 'vlax-invoke (list (sht:model-layout) 'GetPlotStyleTableNames)))
  (if (and r (not (vl-catch-all-error-p r)))
    (foreach s r
      (if (and (= (type s) 'STR) (wcmatch (strcase s) mask) (not (member s res)))
        (setq res (cons s res)))))
  (setq res (vl-sort res '(lambda (a b) (< (strcase a) (strcase b)))))
  (if res res (list (if (= (getvar "PSTYLEMODE") 0) "monochrome.stb" "monochrome.ctb"))))

;; —тиль по умолчанию: прошлый выбор (реестр SHT_PCtb), иначе monochrome, иначе первый
(defun sht:ctb-default (lst / s r)
  (setq s (getenv "SHT_PCtb"))
  (cond
    ((and s (setq r (sht:find-ci s lst))) r)
    ((setq r (sht:find-ci (if (= (getvar "PSTYLEMODE") 0) "monochrome.stb" "monochrome.ctb") lst)) r)
    (t (car lst))))

;; “очка дл€ SetWindowToPlot (массив из двух чисел)
(defun sht:pt2 (x y)
  (vlax-make-variant
    (vlax-safearray-fill (vlax-make-safearray vlax-vbDouble '(0 . 1)) (list (float x) (float y)))))

;; ћассив ActiveX (safearray или variant с ним) -> список; не вышло Ч nil
(defun sht:sa (v / r)
  (if (= (type v) 'VARIANT) (setq v (vlax-variant-value v)))
  (setq r (vl-catch-all-apply 'vlax-safearray->list (list v)))
  (if (vl-catch-all-error-p r) nil r))

;; „исла в строке: "ISO_full_bleed_A3_(420.00_x_297.00_MM)" -> (3.0 420.0 297.0)
(defun sht:str-nums (s / i c tok res)
  (setq i   1
        tok ""
        s   (strcat s " "))
  (while (<= i (strlen s))
    (setq c (substr s i 1)
          i (1+ i))
    (cond
      ((wcmatch c "#") (setq tok (strcat tok c)))
      ((and (= c ".") (/= tok "") (not (vl-string-search "." tok))) (setq tok (strcat tok c)))
      (t
       (if (and (/= tok "") (distof tok 2)) (setq res (cons (distof tok 2) res)))
       (setq tok ""))))
  (reverse res))

;; –азмер (a b) против листа w x h: 0 Ч так же, 1 Ч повЄрнут на 90∞, nil Ч другой
(defun sht:wh-match (a b w h)
  (cond
    ((and (< (abs (- a w)) 0.6) (< (abs (- b h)) 0.6)) 0)
    ((and (< (abs (- a h)) 0.6) (< (abs (- b w)) 0.6)) 1)))

;; Ѕумага плоттера дл€ листа w x h мм у набора pc: (каноническое-им€ поворот пол€) или nil.
;;  андидаты Ч по двум последним числам имени (не нашлось Ч все); размер и пол€ Ч у плоттера.
;; Ћучше: пол€ не больше 0,6 мм (иначе край листа обрежетс€), затем Ч без поворота.
(defun sht:media-find (pc names w h / cand best lst r pw ph ll ur mg rot sc)
  (foreach nm names
    (setq lst (sht:str-nums nm))
    (if (and (>= (length lst) 2) (sht:wh-match (nth (- (length lst) 2) lst) (last lst) w h))
      (setq cand (cons nm cand))))
  (foreach nm (if cand (reverse cand) names)
    (setq pw nil ph nil ll nil ur nil mg 0.0
          r  (vl-catch-all-apply 'vla-put-CanonicalMediaName (list pc nm)))
    (if (not (vl-catch-all-error-p r))
      (setq r (vl-catch-all-apply 'vla-GetPaperSize (list pc 'pw 'ph))))
    (if (and (not (vl-catch-all-error-p r)) (numberp pw) (numberp ph) (setq rot (sht:wh-match pw ph w h)))
      (progn
        (setq r (vl-catch-all-apply 'vla-GetPaperMargins (list pc 'll 'ur)))
        (if (and (not (vl-catch-all-error-p r)) (setq lst (append (sht:sa ll) (sht:sa ur))))
          (setq mg (apply 'max (mapcar 'abs lst))))
        (setq sc (+ (if (> mg 0.6) 1000.0 0.0) (* rot 10.0) mg))
        (if (or (not best) (< sc (car best)))
          (setq best (list sc nm rot mg))))))
  (if best (cdr best)))

;; “о же с запоминанием по размеру (sht:pcache Ч локальна€ переменна€ sht:plot-run)
(defun sht:media-cached (pc names w h / key p)
  (setq key (list w h))
  (if (setq p (assoc key sht:pcache))
    (cdr p)
    (cdar (setq sht:pcache (cons (cons key (sht:media-find pc names w h)) sht:pcache)))))

;; ќбщий набор: плоттер, стиль печати, веса линий
(defun sht:pc-new (name ctb / pc)
  (setq pc (vla-Add (sht:pcs) name :vlax-true))      ; набор дл€ листа модели
  (vla-put-ConfigName pc *sht:Pc3*)
  (vla-RefreshPlotDeviceInfo pc)
  (vla-put-PaperUnits pc 1)                          ; acMillimeters
  (vla-put-PlotRotation pc 0)                        ; ac0degrees
  (vla-put-PlotWithPlotStyles pc :vlax-true)
  (vla-put-StyleSheet pc ctb)
  (vla-put-PlotWithLineweights pc :vlax-true)
  (vla-put-PlotHidden pc :vlax-false)
  (vla-put-CenterPlot pc :vlax-true)
  pc)

;; Ќастроить печать obj Ч параметры листа модели или набор Ч напр€мую (s0.3.2: без CopyFrom Ч у јртЄма
;; в s0.3 окно и масштаб через CopyFrom не доходили до печати): DWG To PDF, бумага m = (им€ поворот пол€),
;; стиль ctb, веса линий, окно = лист it в модели (экранные координаты), 1:масштаб, по центру.
;; ¬озвращает заданное окно ((x1 y1) (x2 y2)) Ч дл€ обратной проверки.
(defun sht:plot-setup (obj it m ctb / p sc p1 p2 a b)
  (setq p  (nth 6 it)
        sc (nth 5 it)
        p1 (trans p 0 2)
        p2 (trans (list (+ (car p) (* sc (nth 7 it))) (+ (cadr p) (* sc (nth 8 it)))
                        (if (caddr p) (caddr p) 0.0))
                  0 2)
        a  (list (min (car p1) (car p2)) (min (cadr p1) (cadr p2)))
        b  (list (max (car p1) (car p2)) (max (cadr p1) (cadr p2))))
  (vla-put-ConfigName obj *sht:Pc3*)
  (vla-RefreshPlotDeviceInfo obj)
  (vla-put-CanonicalMediaName obj (car m))
  (vla-put-PaperUnits obj 1)                         ; acMillimeters
  (vla-put-PlotRotation obj (cadr m))                ; 0 Ч ac0degrees, 1 Ч ac90degrees
  (vla-put-PlotWithPlotStyles obj :vlax-true)
  (vla-put-StyleSheet obj ctb)
  (vla-put-PlotWithLineweights obj :vlax-true)
  (vla-put-PlotHidden obj :vlax-false)
  (vla-SetWindowToPlot obj (sht:pt2 (car a) (cadr a)) (sht:pt2 (car b) (cadr b)))
  (vla-put-PlotType obj 4)                           ; acWindow Ч только после окна
  (vla-put-UseStandardScale obj :vlax-false)
  (vla-SetCustomScale obj 1.0 (float sc))
  (vla-put-CenterPlot obj :vlax-true)
  (list a b))

;; ќбратна€ проверка: что AutoCAD записал в obj. win Ч заданное окно, sc Ч масштаб листа.
;; ¬озвращает (годитс€ строка-дл€-журнала)
(defun sht:plot-readback (obj win sc / ty st a b n d ok r)
  (setq ty (vl-catch-all-apply 'vla-get-PlotType (list obj))
        st (vl-catch-all-apply 'vla-get-UseStandardScale (list obj))
        r  (vl-catch-all-apply 'vla-GetWindowToPlot (list obj 'a 'b)))
  (if (vl-catch-all-error-p r)
    (setq a nil b nil)
    (setq a (sht:sa a)
          b (sht:sa b)))
  (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-GetCustomScale (list obj 'n 'd)))
    (setq n nil d nil))
  (setq ok (and (equal ty 4) (eq st :vlax-false) a b (numberp n) (numberp d) (> n 0)
                (equal (/ d n) sc 1e-6)
                (equal (car a) (car (car win)) 1.0) (equal (cadr a) (cadr (car win)) 1.0)
                (equal (car b) (car (cadr win)) 1.0) (equal (cadr b) (cadr (cadr win)) 1.0)))
  (list ok
        (strcat "записано: "
                (cond ((equal ty 4) "окно") ((equal ty 0) "экран") ((equal ty 1) "границы")
                      ((equal ty 2) "лимиты") ((numberp ty) (itoa ty)) (t "?"))
                (if (and a b) (strcat " " (sht:n2s (car a)) "," (sht:n2s (cadr a)) " - " (sht:n2s (car b)) "," (sht:n2s (cadr b))) "")
                ", масштаб "
                (cond ((eq st :vlax-true) "стандартный (вписать?)")
                      ((and (numberp n) (numberp d) (> n 0)) (strcat "1:" (sht:n2s (/ d n))))
                      (t "?")))))

;; ќбласть печати листа модели (CopyFrom может еЄ не вернуть): (тип низ-лево верх-право стандартный
;; стандартный-масштаб числитель знаменатель) Ч запомнить до печати и вернуть после (*sht:ModelArea*)
(defun sht:model-area-get (lay / a b n d)
  (vl-catch-all-apply 'vla-GetWindowToPlot (list lay 'a 'b))
  (vl-catch-all-apply 'vla-GetCustomScale (list lay 'n 'd))
  (list (vl-catch-all-apply 'vla-get-PlotType (list lay)) (sht:sa a) (sht:sa b)
        (vl-catch-all-apply 'vla-get-UseStandardScale (list lay))
        (vl-catch-all-apply 'vla-get-StandardScale (list lay)) n d))

(defun sht:model-area-set (lay v)
  (if (and (= (length (nth 1 v)) 2) (= (length (nth 2 v)) 2))
    (vl-catch-all-apply 'vla-SetWindowToPlot
      (list lay (sht:pt2 (car (nth 1 v)) (cadr (nth 1 v))) (sht:pt2 (car (nth 2 v)) (cadr (nth 2 v))))))
  (if (numberp (car v)) (vl-catch-all-apply 'vla-put-PlotType (list lay (car v))))
  (if (and (numberp (nth 5 v)) (numberp (nth 6 v)) (> (nth 5 v) 0))
    (vl-catch-all-apply 'vla-SetCustomScale (list lay (nth 5 v) (nth 6 v))))
  (if (numberp (nth 4 v)) (vl-catch-all-apply 'vla-put-StandardScale (list lay (nth 4 v))))
  (if (member (nth 3 v) (list :vlax-true :vlax-false)) (vl-catch-all-apply 'vla-put-UseStandardScale (list lay (nth 3 v)))))

;; «апомнить параметры листа модели: копи€ SHT_PLOTSAVE (вернЄт sht:pc-purge) и область печати
(defun sht:model-save ( / lay sv)
  (setq lay (sht:model-layout))
  (if (not (sht:pc-get *sht:PcSave*))
    (progn
      (setq sv (vla-Add (sht:pcs) *sht:PcSave* :vlax-true))
      (vla-CopyFrom sv lay)
      (setq *sht:ModelArea* (sht:model-area-get lay)))))

;; --- вывод ------------------------------------------------------------------

;; —писок листов дл€ PUBLISH (DSD): один PDF (Type=6). pairs Ч ((им€-листа . набор) Е).
;; enc Ч "ansi" (кодировка Windows) или "utf8-bom". ¬озвращает fn или nil.
(defun sht:dsd-write (fn pairs pdf enc / f dwg lst)
  (setq dwg (strcat (getvar "DWGPREFIX") (getvar "DWGNAME"))
        f   (if (= enc "ansi") (open fn "w") (vl-catch-all-apply 'open (list fn "w" enc))))
  (if (vl-catch-all-error-p f) (setq f nil))
  (if f
    (progn
      (setq lst (list "[DWF6Version]" "Ver=1" "[DWF6MinorVersion]" "MinorVer=1"))
      (foreach p pairs
        (setq lst (append lst (list (strcat "[DWF6Sheet:" (car p) "]") (strcat "DWG=" dwg) "Layout=Model"
                                    (strcat "Setup=" (cdr p)) (strcat "OriginalSheetPath=" dwg)
                                    "Has Plot Port=0" "Has3DDWF=0"))))
      (setq lst (append lst
                  (list "[Target]" "Type=6" (strcat "DWF=" pdf) (strcat "OUT=" (vl-filename-directory pdf) "\\") "PWD="
                        "[PdfOptions]" "IncludeHyperlinks=TRUE" "CreateBookmarks=TRUE" "CaptureFontsInDrawing=TRUE"
                        "ConvertTextToGeometry=FALSE" "VectorResolution=1200" "RasterResolution=400"
                        "[AutoCAD Block Data]" "IncludeBlockInfo=0" "BlockTmplFilePath="
                        "[SheetSet Properties]" "IsSheetSet=FALSE" "IsHomogeneous=FALSE" "SheetSet Name="
                        "NoOfCopies=1" "PlotStampOn=FALSE" "ViewFile=FALSE" "JobID=0" "SelectionSetName="
                        (strcat "AcadProfile=" (if (getvar "CPROFILE") (getvar "CPROFILE") ""))
                        "CategoryName=" "LogFilePath=" "IncludeLayer=FALSE" "LineMerge=FALSE" "CurrentPrecision="
                        "PromptForDwfName=FALSE" "PwdProtectPublishedDWF=FALSE" "PromptForPwd=FALSE"
                        "RepublishingMarkups=FALSE" "DSTPath=" "PublishSheetSetMetadata=FALSE"
                        "PublishSheetMetadata=FALSE" "3DDWFOptions=0 1")))
      (foreach s lst (write-line s f))
      (close f)
      fn)))

;; ќдин PDF через -PUBLISH.  одировка списка листов: сначала та, что сработала в прошлый раз
;; (реестр SHT_DsdEnc), не вышло Ч друга€ (ANSI / UTF-8 с BOM). T Ч файл pdf по€вилс€.
(defun sht:publish-all (pairs pdf / encs enc dsd log ok cnt)
  (setq encs (if (and (numberp (getvar "LISPSYS")) (> (getvar "LISPSYS") 0)) (list "ansi" "utf8-bom") (list "ansi")))
  (if (= (getenv "SHT_DsdEnc") "utf8-bom") (setq encs (reverse encs)))
  (while (and encs (not ok))
    (setq enc  (car encs)
          encs (cdr encs)
          dsd  (vl-filename-mktemp "shtpdf" nil ".dsd")
          log  (strcat (vl-filename-directory dsd) "\\" (vl-filename-base dsd) ".csv"))
    (if (sht:dsd-write dsd pairs pdf enc)
      (progn
        (princ (strcat "\nPUBLISH: листов " (itoa (length pairs)) " -> " pdf))
        (command "_.-PUBLISH" dsd)
        (setq cnt 0)
        (while (and (> (getvar "CMDACTIVE") 0) (< cnt 10))   ; лишние вопросы команды Ч по умолчанию
          (command "")
          (setq cnt (1+ cnt)))
        (if (setq ok (findfile pdf))
          (progn
            (setenv "SHT_DsdEnc" enc)
            (vl-file-delete dsd)
            (if (findfile log) (vl-file-delete log)))
          (princ (strcat "\nPUBLISH не создал PDF (список листов в кодировке " enc "): " dsd
                         (if (findfile log) (strcat "; журнал: " log) "")))))
      (princ (strcat "\nЌе удалось записать список листов " dsd))))
  (if ok T))

;; ќтдельные файлы: на каждый лист Ч параметры листа модели напр€мую (sht:plot-setup), обратна€ проверка,
;; PlotToFile. jobs Ч ((лист бумага файл подпись) Е). ѕрежние параметры модели вернЄт sht:plot-cleanup.
;; ¬озвращает число файлов.
(defun sht:plot-each (jobs / lay plot n r q chk)
  (setq lay  (sht:model-layout)
        plot (vla-get-Plot (sht:doc))
        n    0)
  (sht:model-save)
  (setq q (vl-catch-all-apply 'vla-get-QuietErrorMode (list plot)))
  (vl-catch-all-apply 'vla-put-QuietErrorMode (list plot :vlax-true))
  (foreach j jobs
    (setq chk (sht:plot-readback lay (sht:plot-setup lay (car j) (cadr j) sht:pctb) (nth 5 (car j))))
    (princ (strcat "\n  " (cadddr j) ": " (cadr chk) (if (car chk) "" " - Ќ≈ “ј , как задано!")))
    (setq r (vl-catch-all-apply 'vla-PlotToFile (list plot (caddr j))))
    (if (and (not (vl-catch-all-error-p r)) (findfile (caddr j)))
      (progn
        (setq n (1+ n))
        (princ (strcat " -> " (vl-filename-base (caddr j)) ".pdf")))
      (princ (strcat " - Ќ≈ Ќјѕ≈„ј“јЌ"
                     (if (vl-catch-all-error-p r) (strcat " (" (vl-catch-all-error-message r) ")") "")))))
  (if (not (vl-catch-all-error-p q)) (vl-catch-all-apply 'vla-put-QuietErrorMode (list plot q)))
  n)
;; ѕечать отмеченных в окне листов (переменные окна sht:pЕ). ¬озвращает число напечатанных.
(defun sht:plot-run ( / doc items dir all tag tpl names sht:pcache bad jobs k it m pc pcn chk nm fn used base pdf pairs lock n res)
  (setq doc   (sht:doc)
        items (sht:pick-items sht:psel)
        dir   sht:pdir
        all   (= sht:pmode "1")
        n     0)
  (setenv "SHT_PMode" sht:pmode)
  (setenv "SHT_PCtb" sht:pctb)
  (setenv "SHT_PSave" sht:psave)
  (setenv "SHT_POpen" sht:popen)
  (sht:plot-dir-save dir)
  (cond
    ((not (sht:mkdir dir))
     (alert (strcat "Ќе удалось создать папку дл€ PDF:\n" dir)))
    (t
     ;; FILEDIA = 0: иначе -PUBLISH не берЄт им€ списка листов, а открывает окно выбора файла (s0.3.1)
     (sht:plot-sv-set (list (cons "CMDECHO" 0) (cons "FILEDIA" 0) (cons "BACKGROUNDPLOT" 0) (cons "PUBLISHCOLLATE" 1)
                            (cons "TILEMODE" 1)))
     (if (and (numberp (getvar "VIEWTWIST")) (not (equal (getvar "VIEWTWIST") 0.0 1e-9)))
       (princ "\n¬Ќ»ћјЌ»≈: вид в модели повЄрнут (VIEWTWIST) - окна печати могут не совпасть с листами. ¬ерните вид: _PLAN _World."))
     ;; ведомость листов и ЂЋистовї (s0.5), тексты вписать в графы (как SHEET_UPDATE)
     (vla-StartUndoMark doc)
     (sht:sign-auto nil)                    ; подписи и логотип (s0.7)
     (sht:list-auto nil)
     (sht:fit-all)
     (vla-EndUndoMark doc)
     ;; имена наборов Ч свои у каждой печати (врем€): в сохранЄнном раньше файле таких нет
     (setq tag (strcat *sht:PcPrefix* (rtos (* 1e8 (rem (getvar "CDATE") 1.0)) 2 0) "_")
           tpl (vl-catch-all-apply 'sht:pc-new (list (strcat tag "000") sht:pctb)))
     (cond
       ((vl-catch-all-error-p tpl)
        (alert (strcat "Ќе удалось настроить печать на Ђ" *sht:Pc3* "ї со стилем Ђ" sht:pctb "ї:\n"
                       (vl-catch-all-error-message tpl))))
       (t
        (setq names (vlax-invoke tpl 'GetCanonicalMediaNames))
        ;; бумага каждому листу
        (foreach it items
          (setq m (sht:media-cached tpl names (nth 7 it) (nth 8 it)))
          (cond
            ((not (equal (cos (nth 9 it)) 1.0 1e-9))
             (setq bad (cons (strcat (sht:plot-sheet it) ": повЄрнут - печатаютс€ только неповЄрнутые листы") bad)))
            ((not m)
             (setq bad (cons (strcat (sht:plot-sheet it) " (" (sht:plot-fmt it) "): у Ђ" *sht:Pc3* "ї нет бумаги "
                                     (sht:n2s (nth 7 it)) " x " (sht:n2s (nth 8 it)) " мм")
                             bad)))
            (t (setq jobs (cons (list it m) jobs)))))
        (setq jobs (reverse jobs))
        (cond
          (bad
           (alert (strcat "ѕечать не выполнена:\n" (sht:join (reverse bad) "\n")
                          "\n\n—нимите отметку с этих листов или исправьте их.")))
          (t
           ;; наборы параметров и имена
           (setq k    0
                 base (sht:plot-shifr items)
                 pdf  (strcat dir "\\" (sht:plot-file-all items)))
           (foreach j jobs
             (setq k    (1+ k)
                   it   (car j)
                   m    (cadr j)
                   nm   (sht:uniq-name (sht:dsd-name it) (mapcar 'car pairs))
                   fn   (sht:uniq-name (sht:plot-file-base it base) used)
                   used (cons fn used)
                   pcn  nil)
             (princ (strcat "\n" (sht:plot-sheet it) " (" (sht:plot-fmt it) "): бумага " (car m)
                            (if (= (cadr m) 1) ", поворот 90" "")))
             ;; один PDF Ч свой набор на лист, настроенный напр€мую, с обратной проверкой
             (if all
               (progn
                 (setq pc  (vla-Add (sht:pcs) (strcat tag (sht:pad3 k)) :vlax-true)
                       pcn (vla-get-Name pc)
                       chk (sht:plot-readback pc (sht:plot-setup pc it m sht:pctb) (nth 5 it)))
                 (princ (strcat "; набор " pcn " - " (cadr chk) (if (car chk) "" " - Ќ≈ “ј , как задано!")))))
             (setq pairs (cons (list nm pcn (strcat dir "\\" fn ".pdf") it m) pairs)))
           (setq pairs (reverse pairs))
           ;; прежние файлы Ч удалить (зан€тый программой просмотра Ч не удалитс€)
           (foreach f (if all (list pdf) (mapcar 'caddr pairs))
             (if (findfile f) (vl-file-delete f))
             (if (findfile f) (setq lock (cons f lock))))
           (cond
             (lock
              (alert (strcat "‘айл зан€т (открыт в программе просмотра?) - закройте его и повторите:\n"
                             (sht:join (reverse lock) "\n"))))
             (all
              (if (= sht:psave "1")
                (if (= (getvar "WRITESTAT") 0)
                  (princ "\n„ертЄж открыт только дл€ чтени€ - перед печатью не сохранЄн.")
                  (progn
                    (princ "\n—охранение чертежа перед печатью...")
                    (command "_.QSAVE"))))
              (if (sht:publish-all (mapcar '(lambda (p) (cons (car p) (cadr p))) pairs) pdf)
                (setq n   (length pairs)
                      res pdf)))
             (t
              (setq n   (sht:plot-each (mapcar '(lambda (p) (list (nth 3 p) (nth 4 p) (nth 2 p) (car p))) pairs))
                    res dir)))))))))
  (sht:plot-cleanup)
  (cond
    ((> n 0)
     (princ (strcat "\nЌапечатано листов: " (itoa n) (if all (strcat " -> " res) (strcat ", папка " res))))
     (if (= sht:popen "1") (sht:open-path res)))
    (jobs (princ "\nPDF не получен - см. сообщени€ выше.")))
  (if sht:poff
    (princ (strcat "\nЋисты без номера не напечатаны: " (itoa (length sht:poff)) " (список выше).")))
  n)

;; --- окно Ђѕечать в PDFї --------------------------------------------------------
;; ѕеременные окна (локальные в c:SHEET_PLOT): sht:pitems Ч листы с номером по пор€дку, sht:poff Ч без
;; номера, sht:psel Ч отмеченные (индексы), sht:pmode "1" один PDF / "0" отдельные, sht:pdir Ч папка,
;; sht:pctb / sht:pctbs Ч стиль и список, sht:psave sht:popen Ч "1"/"0", sht:pnums Ч поле ЂЌомераї,
;; sht:pnums-ok Ч номера, по которым отмечено.

(defun sht:plot-init ()
  (start_list "sht_PList")
  (foreach it sht:pitems (add_list (sht:plot-line it)))
  (end_list)
  (set_tile "sht_PList" (sht:idx-str sht:psel))
  (sht:set-popup "sht_PCtb" sht:pctbs (vl-position sht:pctb sht:pctbs))
  (set_tile "sht_PMode" (if (= sht:pmode "0") "sht_PModeOne" "sht_PModeAll"))
  (set_tile "sht_PDir" sht:pdir)
  (set_tile "sht_PSave" sht:psave)
  (set_tile "sht_POpen" sht:popen)
  (set_tile "sht_PNums" sht:pnums)
  (set_tile "sht_POff" (sht:plot-off-str))
  (sht:plot-info)
  (action_tile "sht_PList" "(set_tile \"error\" \"\") (sht:plot-info)")
  (action_tile "sht_PAll" "(sht:plot-mark T)")
  (action_tile "sht_PNone" "(sht:plot-mark nil)")
  (action_tile "sht_PNums" "(if (member $reason '(1 2)) (sht:plot-on-nums))")
  (action_tile "sht_PNumsGo" "(sht:plot-on-nums)")
  (action_tile "sht_PSel" "(sht:plot-keep) (done_dialog 4)")
  (action_tile "sht_PDirB" "(sht:plot-keep) (done_dialog 3)")
  (action_tile "sht_PMode" "(sht:plot-info)")
  (action_tile "accept" "(sht:plot-ok)"))

;; «апомнить состо€ние окна (перед закрытием)
(defun sht:plot-keep ( / i)
  (setq sht:psel  (sht:idx-read (get_tile "sht_PList"))
        sht:pmode (if (= (get_tile "sht_PMode") "sht_PModeOne") "0" "1")
        sht:pdir  (sht:dir-norm (get_tile "sht_PDir"))
        i         (atoi (get_tile "sht_PCtb"))
        sht:pctb  (if (nth i sht:pctbs) (nth i sht:pctbs) (car sht:pctbs))
        sht:psave (get_tile "sht_PSave")
        sht:popen (get_tile "sht_POpen")
        sht:pnums (get_tile "sht_PNums")))

;; —троки окна: сколько отмечено, какое им€ файла получитс€
(defun sht:plot-info ( / sel one)
  (setq sel (sht:idx-read (get_tile "sht_PList"))
        one (= (get_tile "sht_PMode") "sht_PModeOne"))
  (set_tile "sht_PCount" (strcat "ќтмечено листов: " (itoa (length sel)) " из " (itoa (length sht:pitems))))
  (set_tile "sht_PFile"
    (cond
      ((not sel) "")
      (one (strcat "‘айлы: " (sht:plot-file-one (nth (car sel) sht:pitems) (sht:plot-shifr (sht:pick-items sel)))
                   (if (cdr sel) ", ..." "")))
      (t (strcat "‘айл: " (sht:plot-file-all (sht:pick-items sel))))))
  (mode_tile "sht_PSave" (if one 1 0)))

;; Ђ¬сеї / ЂЌи одногої
(defun sht:plot-mark (all)
  (set_tile "sht_PList" (if all (sht:idx-str (sht:range 0 (length sht:pitems))) ""))
  (set_tile "error" "")
  (sht:plot-info))

;; Ђќтметитьї (и Enter в поле ЂЌомераї)
(defun sht:plot-on-nums ( / s r)
  (setq s            (sht:trim (get_tile "sht_PNums"))
        sht:pnums-ok s)
  (if (/= s "")
    (progn
      (setq r (sht:nums-pick s sht:pitems))
      (set_tile "sht_PList" (sht:idx-str (car r)))
      (set_tile "error" (if (cadr r) (strcat "Ќет листов: " (sht:join (cadr r) ", ")) ""))
      (sht:plot-info))))

;; Ђѕечатьї: номера вписаны, но не отмечены Ч сначала отметить и показать
(defun sht:plot-ok ( / s)
  (setq s (sht:trim (get_tile "sht_PNums")))
  (if (and (/= s "") (/= s sht:pnums-ok))
    (progn
      (sht:plot-on-nums)
      (if (= (get_tile "error") "")
        (set_tile "error" "Ћисты отмечены по номерам - проверьте список и нажмите Ђѕечатьї ещЄ раз.")))
    (progn
      (sht:plot-keep)
      (cond
        ((not sht:psel) (set_tile "error" "Ќе отмечено ни одного листа."))
        ((= sht:pdir "") (set_tile "error" "”кажите папку дл€ PDF."))
        ((and (= sht:pmode "1") (= (getvar "DWGTITLED") 0))
         (set_tile "error" "„ертЄж ещЄ не сохранЄн: дл€ одного PDF сохраните его (или выберите отдельные файлы)."))
        (t (done_dialog 1))))))

;; Ђ...ї: выбор папки (окно Windows); отказ или ошибка Ч папка прежн€€
(defun sht:plot-browse ( / app sh hw f it p)
  (setq app (vlax-get-acad-object)
        sh  (vl-catch-all-apply 'vla-GetInterfaceObject (list app "Shell.Application")))
  (if (and sh (not (vl-catch-all-error-p sh)))
    (progn
      (setq hw (vl-catch-all-apply 'vla-get-HWND (list app))
            f  (vl-catch-all-apply 'vlax-invoke-method
                 (list sh 'BrowseForFolder (if (vl-catch-all-error-p hw) 0 hw) "ѕапка дл€ PDF" 64)))
      (if (and f (not (vl-catch-all-error-p f)))
        (progn
          (setq it (vl-catch-all-apply 'vlax-get-property (list f 'Self)))
          (if (not (vl-catch-all-error-p it))
            (setq p (vl-catch-all-apply 'vlax-get-property (list it 'Path))))
          (if (and (= (type p) 'STR) (/= p "") (not (wcmatch p "::*")))
            (setq sht:pdir (sht:dir-norm (vl-string-translate "/" "\\" p))))
          (vl-catch-all-apply 'vlax-release-object (list f))))
      (vl-catch-all-apply 'vlax-release-object (list sh)))
    (princ "\nќкно выбора папки недоступно - впишите путь в поле Ђѕапкаї.")))

;; Ђ¬ыбрать в чертеже <ї
(defun sht:plot-pick ( / ss i en k res)
  (princ "\n¬ыберите листы дл€ печати (рамка или штамп листа), Enter - конец выбора: ")
  (if (setq ss (ssget '((0 . "INSERT") (2 . "SHT_*"))))
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq en (ssname ss i)
              i  (1+ i)
              k  0)
        (foreach it sht:pitems
          (if (eq (car it) en) (setq res (cons k res)))
          (setq k (1+ k))))
      (if res
        (setq sht:psel     (sht:uniq-sort res)
              sht:pnums    ""
              sht:pnums-ok "")
        (princ "\n—реди выбранного нет листов с номером."))))
  (princ))

;; ќкно целиком. 1 Ч печать, 0 Ч отмена; Ђ¬ыбрать в чертеже <ї (4) и Ђ...ї (3) Ч окно открываетс€ снова
(defun sht:plot-dialog ( / dcl_id dclFile ret)
  (setq ret 2)
  (if (sht:dlg-load)
    (while (> ret 1)
      (if (new_dialog "sht_plot" dcl_id)
        (progn
          (sht:plot-init)
          (setq ret (start_dialog))
          (cond
            ((= ret 3) (sht:plot-browse))
            ((= ret 4) (sht:plot-pick))))
        (progn
          (princ "\nSHEETS: не удалось открыть окно.")
          (setq ret 0))))
    (setq ret 0))
  (sht:dlg-cleanup)
  ret)

(defun c:SHEET_PLOT ( / *error* doc sdat r ens
                        sht:pitems sht:poff sht:psel sht:pdir sht:pmode sht:pctb sht:pctbs
                        sht:psave sht:popen sht:pnums sht:pnums-ok)
  (defun *error* (msg)
    (sht:plot-cleanup)
    (if (not (wcmatch (strcase msg) "*CANCEL*,*BREAK*,*ќ“ћ≈Ќ*,*ѕ–≈–¬*"))
      (princ (strcat "\nSHEETS: печать прервана: " msg)))
    (princ))
  (setq doc  (sht:doc)
        sdat (sht:prepare))
  (sht:dblclick-setup)
  (sht:plot-cleanup)                      ; остатки прошлой печати (после сбо€)
  (setq ens (sht:plot-presel0))           ; выбранное до команды
  (vla-StartUndoMark doc)
  (sht:apply-props)                       ; FORMAT / ORIENT из Ђ—войствї Ч до печати
  (vla-EndUndoMark doc)
  (setq r          (sht:plot-items)
        sht:pitems (car r)
        sht:poff   (cadr r))
  (sht:plot-warn-off)
  (cond
    ((not (or sht:pitems sht:poff))
     (princ "\nЋистов SHEETS в модели нет - печатать нечего."))
    ((not sht:pitems)
     (princ "\n” всех листов пустой номер - печатать нечего (номер - в окне листа, двойной щелчок по листу)."))
    (t
     (setq sht:psel     (sht:plot-presel ens)
           sht:pctbs    (sht:ctb-list)
           sht:pctb     (sht:ctb-default sht:pctbs)
           sht:pmode    (if (= (getenv "SHT_PMode") "0") "0" "1")
           sht:psave    (if (= (getenv "SHT_PSave") "0") "0" "1")
           sht:popen    (if (= (getenv "SHT_POpen") "0") "0" "1")
           sht:pdir     (sht:plot-dir-load sdat)
           sht:pnums    ""
           sht:pnums-ok "")
     (if (= (sht:plot-dialog) 1) (sht:plot-run))))
  (sht:watch)
  (princ))

;;; --------------------------------------------------------------------------
;;;  14. ¬≈ƒќћќ—“№ –јЅќ„»’ „≈–“≈∆≈… (s0.5): SHEET_LIST
;;;  “аблица AutoCAD по образцу —ѕƒ— (так же, как спецификации PYLON_BASE): строка 0 Ч заголовок
;;;  над таблицей (без рамки сверху и по бокам), 1 Ч шапка ЂЋист / Ќаименование / ѕримечаниеї,
;;;  дальше Ч листы с номером по пор€дку номеров (как печать). —толбцы 15 / 140 / 30, шапка 15,
;;;  строки 8 (длинное наименование Ч строка сама становитс€ выше), текст 2,5, заголовок 3,5 мм листа;
;;;  рамка, шапка и вертикали 0,7, между строками 0,2. —лой 0000_“аблицы.
;;;  ћетка таблицы Ч XData SHT_TABLE: "LIST" и масштаб. ќбновление Ч на месте: строки добавл€ютс€
;;;  и удал€ютс€, тексты пишутс€, только если помен€лись (чертЄж зр€ не становитс€ ЂизменЄннымї);
;;;  заголовок мен€етс€ только из окна SHEET_LIST (правку заголовка в самой таблице не трогаем).
;;;  Ђѕримечаниеї Ч по последнему изменению в штампе листа (sht:note).
;;;  ЂЋистовї (графа 8) Ч число листов с номером, на первом по пор€дку листе; на остальных Ч пусто.
;;;  ¬ставка (s0.6.2, решение јртЄма) Ч кликом, точка Ч левый верхний угол всей таблицы, верх строки
;;;  заголовка (к рамке листа), как у ведомости спецификаций; до s0.6.2 Ч угол рамки, заголовок над ним.
;;;  јвтообновление (вкл. по умолчанию; в словаре чертежа @LISTAUTO = "0" Ч выкл.): перед сохранением
;;;  и печатью (реактор команд), в конце SHEET_NEW, окна ЂЋистї, SHEET_PLOT; SHEET_UPDATE Ч всегда.
;;; --------------------------------------------------------------------------

(setq *sht:LayTbl*     "0000_“аблицы"     ; слой таблиц (как у PYLON_BASE)
      *sht:ListApp*    "SHT_TABLE"        ; XData-метка таблиц SHEETS
      *sht:ListTitle*  "¬едомость рабочих чертежей основного комплекта"
      *sht:ListHead*   '("Ћист" "Ќаименование" "ѕримечание")
      *sht:ListCols*   '(15.0 140.0 30.0)
      *sht:ListTitleH* 11.25              ; строка заголовка: текст 3,5 по середине Ч низ текста в 3,9
                                          ; над рамкой, как в образце
      *sht:ListHeadH*  15.0
      *sht:ListRowH*   8.0
      *sht:ListTxt*    2.5                ; шапка и строки
      *sht:ListTitTxt* 3.5                ; заголовок
      *sht:ListLwBold* 70                 ; рамка, шапка, вертикали
      *sht:ListLwThin* 20                 ; между строками
      *sht:ListCmds*   '("QSAVE" "SAVE" "SAVEAS" "PLOT" "-PLOT" "PUBLISH" "-PUBLISH" "EXPORTPDF" "ETRANSMIT"))

;; --- Ђѕримечаниеї ----------------------------------------------------------------

;; Ќомер изменени€ из графы Ђ»зм.ї: первые цифры ("2", "»зм.2" -> 2); цифр нет Ч 0
(defun sht:izm-n (s / i n c)
  (setq i 1 n 0)
  (while (and (<= i (strlen s)) (not (wcmatch (substr s i 1) "#")))
    (setq i (1+ i)))
  (while (and (<= i (strlen s)) (wcmatch (setq c (substr s i 1)) "#"))
    (setq n (+ (* n 10) (atoi c))
          i (1+ i)))
  n)

;; Ђѕримечаниеї ведомости по штампу листа (решени€ јртЄма, s0.5): последнее изменение Ч строка
;; с наибольшим є в графе Ђ»зм.ї (равные Ч верхн€€, она позже); запись Ђ»зм.Nї, по графе ЂЋистї:
;; Ђ-ї или пусто Ч без добавки, Ђ«ам.ї -> Ђ»зм.N(зам.)ї, ЂЌов.ї -> Ђ»зм.N(нов.)ї, другое Ч так же,
;; строчными в скобках. a Ч атрибуты листа, n Ч строк изменений в штампе (форма 3 Ч 4, форма 6 Ч 2).
(defun sht:note (a n / i izm z best bz lst)
  (setq i 1)
  (repeat n
    (setq izm (sht:trim (cdr (assoc (strcat "C" (itoa i) "IZM") a))))
    (if (/= izm "")
      (progn
        (setq z (sht:izm-n izm))
        (if (or (not best) (>= z bz))
          (setq best i
                bz   z))))
    (setq i (1+ i)))
  (if best
    (progn
      (setq izm (sht:trim (cdr (assoc (strcat "C" (itoa best) "IZM") a)))
            lst (sht:trim (cdr (assoc (strcat "C" (itoa best) "LST") a))))
      (strcat (if (wcmatch izm "#*") (strcat "»зм." izm) izm)
              (if (member lst '("" "-" "Ц" "Ч")) "" (strcat (chr 40) (strcase lst T) (chr 41)))))
    ""))

;; —трок изменений в штампе формы: 3, 4 Ч 4; 5, 6 Ч 2 (s0.10)
(defun sht:chg-rows (form) (if (member (sht:fbase form) '("3" "4")) 4 2))

;; Ћисты дл€ ведомости: (с-номером-по-пор€дку без-номера). Ћист Ч (ename номер наименование
;; примечание форма масштаб точка): номер и точка Ч на тех же местах, что в sht:plot-item (sht:item<).
;; s0.10 (решение јртЄма): в ведомость листов Ч только листы формы 3.
(defun sht:list-items ( / a inf it on off)
  (foreach en (sht:sheets)
    (setq inf (sht:sheet-info en))
    (if (= (sht:fbase (caddr inf)) "3")
      (progn
        (setq a  (sht:attrs en)
              it (list en (sht:trim (cdr (assoc "SHEET" a))) (sht:plain (cdr (assoc "TITLE" a)))
                       (sht:note a (sht:chg-rows (caddr inf))) (caddr inf) (cadddr inf) (nth 4 inf)))
        (if (= (nth 1 it) "")
          (setq off (cons it off))
          (setq on (cons it on))))))
  (list (vl-sort on 'sht:item<) (reverse off)))

;; ƒокументы форм 4 и 5 (s0.10): ((обозначение (лист Е)) Е) Ч по обозначению (sht:nat<), листы
;; документа Ч по номерам (без номера Ч в конце); лист Ч как у ведомости листов (ename номер
;; наименование примечание форма масштаб точка). ƒокумент Ч листы с одинаковой графой 1 (OBOZN; без
;; учЄта регистра и пробелов по кра€м).
(defun sht:doc-items ( / a inf it key p res)
  (foreach en (sht:sheets)
    (setq inf (sht:sheet-info en))
    (if (sht:fdoc-p (caddr inf))
      (progn
        (setq a   (sht:attrs en)
              it  (list en (sht:trim (cdr (assoc "SHEET" a))) (sht:plain (cdr (assoc "TITLE" a)))
                        "" (caddr inf) (cadddr inf) (nth 4 inf))
              key (sht:plain (cdr (assoc "OBOZN" a))))
        (if (setq p (vl-some '(lambda (d) (if (= (car d) (sht:lc key)) d)) res))
          (setq res (subst (list (car p) (cadr p) (cons it (caddr p))) p res))
          (setq res (cons (list (sht:lc key) key (list it)) res))))))
  (setq res (mapcar '(lambda (d) (list (cadr d) (vl-sort (caddr d) 'sht:item<))) res))
  (vl-sort res '(lambda (x y) (sht:nat< (car x) (car y)))))

;; Ќаименование документа: графа 5 первого по пор€дку листа (пуста€ Ч следующего)
(defun sht:doc-name (d / s)
  (setq s "")
  (foreach it (cadr d) (if (= s "") (setq s (nth 2 it))))
  s)

;; --- таблица AutoCAD: вызовы через vlax-invoke (как PYLON_BASE); ошибка вызова не обрывает работу ---
(defun sht:tbl-do (tbl m args) (vl-catch-all-apply 'vlax-invoke (append (list tbl m) args)))
(defun sht:tbl-put (tbl p v) (vl-catch-all-apply 'vlax-put-property (list tbl p v)))

(defun sht:tbl-get (tbl p / r)
  (setq r (vl-catch-all-apply 'vlax-get (list tbl p)))
  (if (vl-catch-all-error-p r) nil r))

(defun sht:tbl-text (tbl r c / s)
  (setq s (sht:tbl-do tbl 'GetText (list r c)))
  (if (= (type s) 'STR) s ""))

;; ћетка таблицы SHEETS (XData SHT_TABLE): (вид масштаб) или nil
(defun sht:tbl-mark (en / xd)
  (setq xd (cdr (assoc *sht:ListApp* (cdr (assoc -3 (entget en (list *sht:ListApp*)))))))
  (if xd (list (cdr (assoc 1000 xd)) (cdr (assoc 1040 xd)))))

(defun sht:tbl-mark-set (tbl kind sc / en)
  (regapp *sht:ListApp*)
  (vl-catch-all-apply 'vla-SetXData
    (list tbl
          (vlax-make-variant
            (vlax-safearray-fill (vlax-make-safearray vlax-vbInteger '(0 . 2)) '(1001 1000 1040)))
          (vlax-make-variant
            (vlax-safearray-fill (vlax-make-safearray vlax-vbVariant '(0 . 2))
                                 (list *sht:ListApp* kind (float sc))))))
  (setq en (vlax-vla-object->ename tbl))
  (if (not (sht:tbl-mark en))
    (vl-catch-all-apply 'entmod
      (list (list (cons -1 en) (list -3 (list *sht:ListApp* (cons 1000 kind) (cons 1040 (float sc))))))))
  (sht:tbl-mark en))

;; “аблицы SHEETS вида kind в чертеже (модель и листы бумаги; копии Ч тоже):
;; "LIST" Ч ведомость листов, "SPEC" Ч ведомость спецификаций (s0.6), "REFS" Ч ведомость ссылочных
;; и прилагаемых документов (s0.10)
(defun sht:kind-tables (kind / ss i en res)
  (if (setq ss (ssget "_X" (list '(0 . "ACAD_TABLE") (list -3 (list *sht:ListApp*)))))
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq en (ssname ss i)
              i  (1+ i))
        (if (= (car (sht:tbl-mark en)) kind)
          (setq res (cons (vlax-ename->vla-object en) res))))))
  (reverse res))

;; “аблицы ведомости листов
(defun sht:list-tables () (sht:kind-tables "LIST"))

;; ¬ид таблицы SHEETS по метке; столбцы и шапка вида (s0.10: "REFS" Ч ведомость ссылочных
;; и прилагаемых документов 60 / 95 / 30, остальные Ч 15 / 140 / 30)
(defun sht:tbl-kind (tbl) (car (sht:tbl-mark (vlax-vla-object->ename tbl))))
(defun sht:kind-cols (kind) (if (= kind "REFS") *sht:RefCols* *sht:ListCols*))
(defun sht:kind-head (kind) (if (= kind "REFS") *sht:RefHead* *sht:ListHead*))

(defun sht:tbl-scale (tbl / sc)
  (setq sc (cadr (sht:tbl-mark (vlax-vla-object->ename tbl))))
  (if (and (numberp sc) (> sc 0)) sc 1.0))

;; ќформление ведомости в масштабе sc: столбцы, высоты строк, текст, выравнивание, линии
(defun sht:tbl-format (tbl sc / n i nc r bad kind)
  (setq n    (sht:tbl-get tbl 'Rows)
        kind (sht:tbl-kind tbl))
  (sht:tbl-put tbl 'Layer *sht:LayTbl*)
  (sht:tbl-put tbl 'FlowDirection 0)                        ; сверху вниз
  (sht:tbl-put tbl 'TitleSuppressed :vlax-false)
  (sht:tbl-put tbl 'HeaderSuppressed :vlax-false)
  (sht:tbl-put tbl 'HorzCellMargin (* 1.5 sc))              ; наименование Ч в 1,5 мм от линии
  (sht:tbl-put tbl 'VertCellMargin (* 1.0 sc))
  (foreach rt '(1 2 4)                                      ; 1 данные, 2 заголовок, 4 шапка
    (sht:tbl-do tbl 'SetTextStyle (list rt *sht:Style*))
    (sht:tbl-do tbl 'SetAlignment (list rt 5)))             ; 5 Ч по центру
  (sht:tbl-do tbl 'SetTextHeight (list 2 (* *sht:ListTitTxt* sc)))
  (sht:tbl-do tbl 'SetTextHeight (list 4 (* *sht:ListTxt* sc)))
  (sht:tbl-do tbl 'SetTextHeight (list 1 (* *sht:ListTxt* sc)))
  (setq i 0)
  (foreach w (sht:kind-cols kind)
    (sht:tbl-do tbl 'SetColumnWidth (list i (* w sc)))
    (setq i (1+ i)))
  (sht:tbl-do tbl 'SetRowHeight (list 0 (* *sht:ListTitleH* sc)))
  (sht:tbl-do tbl 'SetRowHeight (list 1 (* *sht:ListHeadH* sc)))
  (setq i 2)
  (while (and (numberp n) (< i n))
    (sht:tbl-do tbl 'SetRowHeight (list i (* *sht:ListRowH* sc)))
    (sht:tbl-do tbl 'SetCellAlignment (list i 1 4))         ; наименование Ч влево, по середине
    (if (= kind "REFS")                                     ; s0.10: и обозначение
      (sht:tbl-do tbl 'SetCellAlignment (list i 0 4)))
    (setq i (1+ i)))
  ;; линии: 63 Ч все, 61 Ч все, кроме между строками (2); 0,7 Ч заголовок, шапка, рамка и вертикали
  (sht:tbl-do tbl 'SetGridLineWeight (list 63 2 *sht:ListLwBold*))
  (sht:tbl-do tbl 'SetGridLineWeight (list 63 4 *sht:ListLwBold*))
  (sht:tbl-do tbl 'SetGridLineWeight (list 61 1 *sht:ListLwBold*))
  (sht:tbl-do tbl 'SetGridLineWeight (list 2 1 *sht:ListLwThin*))
  ;; заголовок Ч без линий сверху и по бокам (s0.9).  ак сделал јртЄм вручную (Ђ√раницы €чеекї):
  ;; 1) ЂЅез границї Ч ¬—≈ €чейки строки заголовка (объединЄнные A, B, C), все стороны: 63 = 1 верх
  ;;    + 2 между строками + 4 низ + 8 лево + 16 между столбцами + 32 право;
  ;; 2) Ђ¬се границыї Ч все €чейки шапки: еЄ верх Ч это и есть низ заголовка (лини€ остаЄтс€).
  ;; s0.5.1 выключал только €чейку (0,0) и три стороны Ч рамка над B, C и справа оставалась.
  ;; ѕо типу строк (SetGridVisibility) Ч оставлено, у јртЄма ничего не мен€ло. ќшибки Ч в *sht:GridErr*.
  (sht:tbl-do tbl 'SetGridVisibility (list 57 2 :vlax-false))
  (setq nc (length *sht:ListCols*))
  (foreach rv '((0 . :vlax-false) (1 . :vlax-true))
    (setq i 0)
    (while (< i nc)
      (setq r (sht:tbl-do tbl 'SetGridVisibility2 (list (car rv) i 63 (cdr rv))))
      (if (vl-catch-all-error-p r)
        (progn
          (if (not bad)                                     ; перва€ ошибка
            (setq bad (strcat "SetGridVisibility2 " (itoa (car rv)) "," (itoa i) ": "
                              (vl-catch-all-error-message r))))
          ;; запасной Ч прежний способ по €чейке (15 = все стороны)
          (sht:tbl-do tbl 'SetCellGridVisibility (list (car rv) i 15 (cdr rv)))))
      (setq i (1+ i))))
  ;; проверка: AutoCAD считает верх заголовка над B (0,1) видимым?
  (if (and (not bad) (> nc 0))
    (progn
      (setq r (sht:tbl-do tbl 'GetGridVisibility2 (list 0 1 1)))
      (if (and (not (vl-catch-all-error-p r)) (member r (list :vlax-true -1 T)))
        (setq bad "GetGridVisibility2 0,1: верх заголовка по-прежнему видим"))))
  (if (and bad (not *sht:GridErr*))
    (progn
      (setq *sht:GridErr* bad)
      (princ (strcat "\nSHEETS: рамка заголовка таблицы, возможно, не убрана - " bad
                     " (сообщите разработчику)."))))
  bad)

;; —троки таблицы под заголовком: шапка head, затем листы (номер наименование примечание);
;; листов нет Ч одна пуста€ строка
(defun sht:list-cells (items head / res)
  (foreach it items
    (setq res (cons (list (nth 1 it) (nth 2 it) (nth 3 it)) res)))
  (cons head (if res (reverse res) (list (list "" "" "")))))

;; “ексты таблицы (с 1-й строки) отличаютс€ от cells? s0.10: сравнение без форматировани€ MText
;; (заголовки разделов ведомости ссылочных Ч подчЄркнутые, Ђ\LЕ\lї)
(defun sht:tbl-diff (tbl cells / r c d)
  (setq r 1)
  (foreach row cells
    (setq c 0)
    (foreach s row
      (if (and (not d) (/= (sht:mt-plain (sht:tbl-text tbl r c)) (sht:mt-plain s))) (setq d T))
      (setq c (1+ c)))
    (setq r (1+ r)))
  d)

;; «аписать строки: число строк, оформление, тексты. T Ч строк столько, сколько нужно.
(defun sht:tbl-write (tbl sc cells title / n need r c k m)
  (setq n    (sht:tbl-get tbl 'Rows)
        need (1+ (length cells)))
  (cond
    ((< n need)          ; новые строки Ч перед последней (вставка внутрь таблицы надЄжнее, чем в конец)
     (sht:tbl-do tbl 'InsertRows (list (if (> n 2) (1- n) n) (* *sht:ListRowH* sc) (- need n))))
    ((> n need)
     (sht:tbl-do tbl 'DeleteRows (list need (- n need)))
     ;; s0.5.1: не удалились разом Ч по одной с конца, пока число строк убывает
     (setq k (sht:tbl-get tbl 'Rows))
     (while (and (numberp k) (> k need)
                 (progn
                   (sht:tbl-do tbl 'DeleteRows (list (1- k) 1))
                   (setq m (sht:tbl-get tbl 'Rows))
                   (and (numberp m) (< m k))))
       (setq k m))))
  (sht:tbl-format tbl sc)
  (if title (sht:tbl-do tbl 'SetText (list 0 0 title)))
  (setq r 1)
  (foreach row cells
    (setq c 0)
    (foreach s row
      (sht:tbl-do tbl 'SetText (list r c s))
      (setq c (1+ c)))
    ;; s0.10: заголовок раздела ведомости ссылочных (Ђ\Lѕрилагаемые документы\lї) Ч по центру
    (if (and (> r 1) (= (substr (cadr row) 1 2) "\\L"))
      (sht:tbl-do tbl 'SetCellAlignment (list r 1 5)))
    (setq r (1+ r)))
  (= (sht:tbl-get tbl 'Rows) need))

;; ѕривести таблицу к листам items. title Ч заголовок (nil Ч не трогать), force Ч оформление заново.
;; T Ч таблица мен€лась.
(defun sht:tbl-fill (tbl items title force / sc cells n r ch b)
  (setq sc    (sht:tbl-scale tbl)
        cells (sht:list-cells items (sht:kind-head (sht:tbl-kind tbl)))
        n     (sht:tbl-get tbl 'Rows))
  (setq ch
  (if (or force (not (numberp n)) (/= n (1+ (length cells)))
          (and title (/= (sht:tbl-text tbl 0 0) title))
          (sht:tbl-diff tbl cells))
    (progn
      (sht:tbl-put tbl 'RegenerateTableSuppressed :vlax-true)
      (setq r (vl-catch-all-apply 'sht:tbl-write (list tbl sc cells title)))
      (sht:tbl-put tbl 'RegenerateTableSuppressed :vlax-false)     ; всегда: иначе текст таблицы не виден
      (cond
        ((vl-catch-all-error-p r)
         (princ (strcat "\nSHEETS: ведомость не записана: " (vl-catch-all-error-message r))))
        ((not r)
         (princ "\nSHEETS: в таблице ведомости не то число строк - удалите еЄ и вставьте заново (SHEET_LIST).")))
      T)))
  ;; s0.13: ниже рамки листа Ч разрыв на части
  (setq b (vl-catch-all-apply 'sht:tbl-break (list tbl)))
  (if (vl-catch-all-error-p b)
    (princ (strcat "\nSHEETS: разрыв ведомости не проверен: " (vl-catch-all-error-message b))))
  (or ch (= b T)))

;;; --------------------------------------------------------------------------
;;;  14а. –ј«–џ¬ ¬≈ƒќћќ—“≈… ѕќ ¬џ—ќ“≈ Ћ»—“ј (s0.13)
;;;  “аблица SHEETS (ведомость листов, спецификаций, ссылочных) стоит на листе SHEETS в модели и ниже
;;;  рамки листа не помещаетс€ Ч включаетс€ разрыв таблицы AutoCAD (одна таблица, части): высота части Ч
;;;  от верха таблицы до рамки пол€ (над основной надписью Ч до еЄ верха, если часть заходит на неЄ
;;;  по ширине); части Ч вправо через *sht:BrkGap* мм листа; заголовок и шапка повтор€ютс€ в каждой части;
;;;  части можно двигать ручкой (AllowManualPositions). ѕомещаетс€ снова Ч разрыв снимаетс€.
;;;  —осто€ние Ч XData SHT_BREAK: 1040 высота части (0 Ч без разрыва), 1041 добавка к сумме высот строк
;;;  (строки с переносом, если GetRowHeight их не учитывает), 1070 частей. ѕроверка Ч при каждом
;;;  заполнении таблицы (sht:tbl-fill) и в конце команд (sht:watch-check: ведомость перенесли);
;;;  таблица мен€етс€, только когда мен€етс€ высота части или число частей.
;;; --------------------------------------------------------------------------

(setq *sht:BrkApp* "SHT_BREAK"
      *sht:BrkGap* 10.0                  ; между част€ми, мм листа
      *sht:BrkTol* 0.5                   ; допуск, мм листа
      *sht:StampH* '(("3" . 55.0) ("4" . 55.0) ("5" . 40.0) ("6" . 15.0))
      *sht:BrkErr* nil)

;; —охранЄнное состо€ние разрыва: (высота-части добавка частей); нет Ч (0.0 0.0 1)
(defun sht:brk-get (en / xd)
  (setq xd (cdr (assoc *sht:BrkApp* (cdr (assoc -3 (entget en (list *sht:BrkApp*)))))))
  (list (cond ((cdr (assoc 1040 xd))) (0.0))
        (cond ((cdr (assoc 1041 xd))) (0.0))
        (cond ((cdr (assoc 1070 xd))) (1))))

(defun sht:brk-put (tbl h ex n / en)
  (regapp *sht:BrkApp*)
  (vl-catch-all-apply 'vla-SetXData
    (list tbl
          (vlax-make-variant
            (vlax-safearray-fill (vlax-make-safearray vlax-vbInteger '(0 . 3)) '(1001 1040 1041 1070)))
          (vlax-make-variant
            (vlax-safearray-fill (vlax-make-safearray vlax-vbVariant '(0 . 3))
                                 (list *sht:BrkApp* (float h) (float ex) (vlax-make-variant n vlax-vbInteger))))))
  (setq en (vlax-vla-object->ename tbl))
  (if (not (equal (sht:brk-get en) (list (float h) (float ex) n) 1e-6))
    (vl-catch-all-apply 'entmod
      (list (list (cons -1 en)
                  (list -3 (list *sht:BrkApp* (cons 1040 (float h)) (cons 1041 (float ex)) (cons 1070 n)))))))
  (sht:brk-get en))

;; Ќиз, до которого может идти часть таблицы на листе sh: x Ч левый край части, w Ч еЄ ширина
;; (единицы модели). –амка пол€ снизу; часть заходит по ширине на основную надпись Ч верх надписи.
;; ¬озвращает (низ правый-край-рамки).
(defun sht:brk-floor (sh x w / inf wh sc q right bot)
  (setq inf   (sht:sheet-info sh)
        wh    (sht:fmt-wh (car inf) (cadr inf))
        sc    (cadddr inf)
        q     (nth 4 inf)
        right (+ (car q) (* sc (- (car wh) (caddr *sht:Margins*))))
        bot   (+ (cadr q) (* sc (cadr *sht:Margins*))))
  (if (and (> (+ x w) (+ (- right (* 185.0 sc)) (* *sht:BrkTol* sc)))
           (< x (- right (* *sht:BrkTol* sc))))
    (setq bot (+ bot (* sc (cond ((cdr (assoc (sht:fbase (caddr inf)) *sht:StampH*))) (55.0))))))
  (list bot right))

;; ¬ысоты строк таблицы (GetRowHeight; не отдал Ч заданные программой)
(defun sht:tbl-rowhs (tbl sc / n i h res)
  (setq n (sht:tbl-get tbl 'Rows)
        i 0)
  (while (and (numberp n) (< i n))
    (setq h (sht:tbl-do tbl 'GetRowHeight (list i)))
    (if (not (numberp h))
      (setq h (* sc (cond ((= i 0) *sht:ListTitleH*) ((= i 1) *sht:ListHeadH*) (t *sht:ListRowH*)))))
    (setq res (cons (float h) res)
          i   (1+ i)))
  (reverse res))

;; „асти при высоте части lim: (частей высота-второй-части); hs Ч высоты строк (заголовок, шапка, данные),
;; заголовок и шапка Ч в каждой части, в части не меньше одной строки данных
(defun sht:brk-parts (hs lim tol / lab cur parts h2)
  (setq lab   (+ (car hs) (cadr hs))
        cur   lab
        parts 1)
  (foreach h (cddr hs)
    (if (and (> (+ cur h) (+ lim tol)) (> cur (+ lab 1e-6)))
      (setq parts (1+ parts)
            cur   (+ lab h))
      (setq cur (+ cur h)))
    (if (= parts 2) (setq h2 cur)))
  (list parts h2))

(defun sht:kind-name (kind)
  (cond ((= kind "SPEC") "¬едомость спецификаций")
        ((= kind "REFS") "¬едомость ссылочных и прилагаемых документов")
        (t "¬едомость листов")))

(defun sht:parts-str (n)
  (strcat (itoa n) (if (< n 5) " части" " частей")))

;; ¬ключить (h > 0) / сн€ть разрыв. ќшибка Ч строка (перва€), иначе nil.
(defun sht:brk-apply (tbl h sc / err r)
  (if (> h 0)
    (foreach pv (list (list 'EnableBreak) (cons 'RepeatTopLabels :vlax-true)
                      (cons 'AllowManualPositions :vlax-true) (cons 'TableBreakFlowDirection 1)
                      (cons 'BreakSpacing (* *sht:BrkGap* sc)) (cons 'TableBreakHeight h))
      (setq r (if (= (car pv) 'EnableBreak)
                (sht:tbl-do tbl 'EnableBreak (list :vlax-true))
                (sht:tbl-put tbl (car pv) (cdr pv))))
      (if (and (vl-catch-all-error-p r) (not err))
        (setq err (strcat (vl-symbol-name (car pv)) ": " (vl-catch-all-error-message r)))))
    (progn
      (setq r (sht:tbl-do tbl 'EnableBreak (list :vlax-false)))
      (if (vl-catch-all-error-p r)
        (setq err (strcat "EnableBreak: " (vl-catch-all-error-message r))))))
  err)

;; –азрыв таблицы SHEETS по высоте листа. T Ч разрыв включЄн / сн€т / изменилс€.
(defun sht:tbl-break (tbl / en ed p sh sc w tol old hs sum tot ex fr1 fr2 x2 lim1 lim2 pr parts h2 want
                            on err msg)
  (setq en    (vlax-vla-object->ename tbl)
        ed    (entget en)
        p     (cdr (assoc 10 ed))
        sc    (sht:tbl-scale tbl)
        w     (* sc (apply '+ (sht:kind-cols (sht:tbl-kind tbl))))
        tol   (* *sht:BrkTol* sc)
        old   (sht:brk-get en)
        on    (> (car old) 0)
        ex    (cadr old)
        want  0.0
        parts 1)
  (if (and (= (strcase (cond ((cdr (assoc 410 ed))) ("Model"))) "MODEL")
           (setq sh (car (sht:sheet-at p))))
    (progn
      (setq hs   (sht:tbl-rowhs tbl sc)
            sum  (apply '+ hs)
            fr1  (sht:brk-floor sh (car p) w)
            x2   (+ (car p) w (* *sht:BrkGap* sc))
            fr2  (sht:brk-floor sh x2 w)
            lim1 (- (cadr p) (car fr1))
            lim2 (- (cadr p) (car fr2)))
      ;; без разрыва Ч высота всей таблицы AutoCAD (строки с переносом): добавка к сумме высот строк
      (if (and (not on) (numberp (setq tot (sht:tbl-get tbl 'Height))))
        (setq ex (max 0.0 (- tot sum))))
      (if (and (> (length hs) 2)
               (> (+ sum ex) (+ lim1 tol))
               (>= lim1 (+ (car hs) (cadr hs) (caddr hs))))     ; хоть одна строка в части
        (setq pr    (sht:brk-parts hs lim1 tol)
              parts (max 2 (car pr))
              h2    (cadr pr)
              want  lim1))))
  (if (or (> (abs (- want (car old))) tol) (/= parts (caddr old)))
    (progn
      (if (> (abs (- want (car old))) tol)
        (setq err (sht:brk-apply tbl want sc)))
      (sht:brk-put tbl want ex parts)
      (setq msg (strcat "\nSHEETS: " (sht:kind-name (sht:tbl-kind tbl))))
      (cond
        ((> want 0)
         (princ (strcat msg " ниже рамки листа " (sht:sheet-no sh) " - разделена на "
                        (sht:parts-str parts) " (высота части " (sht:n2s (/ want sc)) " мм листа)."))
         (if (> parts 2)
           (princ "\n  ¬ 2 части не помещаетс€: треть€ и следующие части - тоже вправо, перенесите их ручкой."))
         (if (> (+ x2 w) (+ (cadr fr2) tol))
           (princ "\n  ¬тора€ часть - правее рамки листа: перенесите еЄ ручкой или поставьте ведомость левее."))
         (if (and h2 (> h2 (+ lim2 tol)))
           (princ "\n  ¬тора€ часть заходит на основную надпись - перенесите еЄ ручкой.")))
        (t (princ (strcat msg " помещаетс€ на листе - снова одна часть."))))
      (if err
        (progn
          (princ (strcat "\nSHEETS: разрыв таблицы не настроен - " err " (сообщите разработчику)."))
          (setq *sht:BrkErr* err)))
      T)))

;; –азрыв всех таблиц SHEETS (конец команды: ведомость перенесли). „исло изменЄнных.
(defun sht:brk-all ( / ss i en r n)
  (setq n 0)
  (if (setq ss (ssget "_X" (list '(0 . "ACAD_TABLE") (list -3 (list *sht:ListApp*)))))
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq en (ssname ss i)
              i  (1+ i))
        (if (sht:tbl-mark en)
          (progn
            (setq r (vl-catch-all-apply 'sht:tbl-break (list (vlax-ename->vla-object en))))
            (cond
              ((vl-catch-all-error-p r)
               (princ (strcat "\nSHEETS: разрыв ведомости не проверен: " (vl-catch-all-error-message r))))
              ((= r T) (setq n (1+ n)))))))))
  n)

;; ЂЋистовї (графа 8): на первом по пор€дку листе Ч число листов с номером, на остальных Ч пусто.
;; s0.10: документы форм 4, 5 Ч на первом листе документа число его листов (и без номера), на остальных
;; пусто. ¬озвращает число изменЄнных листов.
(defun sht:list-count (items / en1 v k inf docs)
  (setq en1 (car (car items))
        k   0)
  (foreach d (sht:doc-items)
    (setq docs (cons (cons (car (car (cadr d))) (itoa (length (cadr d)))) docs)))
  (foreach en (sht:sheets)
    (setq v (cond ((equal en en1) (itoa (length items)))
                  ((cdr (assoc en docs)))
                  ("")))
    (foreach a (sht:att-objs en)
      (if (and (= (strcase (vla-get-TagString a)) "SHEETS") (/= (vla-get-TextString a) v))
        (progn
          (setq inf (sht:sheet-info en)
                k   (1+ k))
          (sht:att-set a v (cadddr inf) (sht:attr-tab (caddr inf)))))))
  k)

;; ќбновить все таблицы ведомости и ЂЋистовї. title Ч новый заголовок (nil Ч не трогать),
;; force Ч оформление заново. s0.6: затем Ч ведомость спецификаций (sht:spec-update, заголовок не трогает;
;; еЄ ошибка ведомости листов не мешает). ¬озвращает
;; (таблиц-изменено таблиц-всего листов-с-номером ЂЋистовї-изменено номер-первого-листа спецификации),
;; спецификации Ч итог sht:spec-update (nil Ч таблиц ведомости спецификаций нет).
(defun sht:list-update (title force / sdat items tbls nt nc sr rr)
  (setq sdat  (sht:set-read)
        items (car (sht:list-items))
        tbls  (sht:list-tables)
        nt    0
        nc    0)
  (foreach tbl tbls
    (if (sht:tbl-fill tbl items title force) (setq nt (1+ nt))))
  (if (/= (cdr (assoc "@LISTCNT" sdat)) "0")
    (setq nc (sht:list-count items)))
  (setq sr (vl-catch-all-apply 'sht:spec-update (list nil force)))
  (if (vl-catch-all-error-p sr)
    (progn
      (princ (strcat "\nSHEETS: ведомость спецификаций не обновлена: " (vl-catch-all-error-message sr)))
      (setq sr nil)))
  ;; s0.10: ведомость ссылочных и прилагаемых документов (7-й элемент итога)
  (setq rr (vl-catch-all-apply 'sht:refs-update (list nil force)))
  (if (vl-catch-all-error-p rr)
    (progn
      (princ (strcat "\nSHEETS: ведомость ссылочных документов не обновлена: " (vl-catch-all-error-message rr)))
      (setq rr nil)))
  (list nt (length tbls) (length items) nc (if items (nth 1 (car items))) sr rr))

;; —ообщение об обновлении; all Ч и когда таблицы не мен€лись
(defun sht:list-msg (r all)
  (if (or all (> (car r) 0))
    (princ (strcat "\n¬едомость листов: листов с номером " (itoa (nth 2 r))
                   (cond ((= (cadr r) 0) " - таблицы ведомости в чертеже нет (вставить: SHEET_LIST)")
                         ((> (car r) 0) (strcat ", обновлено таблиц: " (itoa (car r)) " из " (itoa (cadr r))))
                         (t ", таблица без изменений"))
                   ".")))
  (if (> (nth 3 r) 0)
    (princ (strcat "\nЂЋистовї (графа 8): "
                   (if (nth 4 r) (strcat (itoa (nth 2 r)) " - на листе " (nth 4 r)) "пусто")
                   ", изменено листов: " (itoa (nth 3 r)) ".")))
  (if (nth 5 r) (sht:spec-msg (nth 5 r) nil))                   ; s0.6 Ч только если мен€лась
  (if (nth 6 r) (sht:refs-msg (nth 6 r) nil)))                  ; s0.10

;; јвтообновление: в конце команд SHEETS и перед сохранением / печатью (реактор).
;; ќшибка не мешает команде; quiet Ч не писать (сообщение даст вызывающий). ¬озвращает итог или nil.
(defun sht:list-auto (quiet / r)
  (if (and (not *sht:ListBusy*) (/= (cdr (assoc "@LISTAUTO" (sht:set-read))) "0"))
    (progn
      (setq *sht:ListBusy* T
            r              (vl-catch-all-apply 'sht:list-update (list nil nil))
            *sht:ListBusy* nil)
      (cond
        ((vl-catch-all-error-p r)
         (princ (strcat "\nSHEETS: ведомость листов не обновлена: " (vl-catch-all-error-message r)))
         nil)
        (t
         (if (not quiet) (sht:list-msg r nil))
         r)))))

;; --- окно Ђ¬едомость рабочих чертежейї -------------------------------------------
;; ѕеременные окна (локальные в c:SHEET_LIST): sht:litems sht:loff Ч листы с номером / без номера,
;; sht:ltbls Ч таблицы ведомости, sht:ltitle Ч заголовок, sht:lcnt sht:lauto Ч "1" / "0".

(defun sht:list-line (it)
  (strcat (nth 1 it) "\t" (nth 2 it) "\t" (nth 3 it)))

(defun sht:list-dups (items / seen res)
  (foreach it items
    (if (member (strcase (nth 1 it)) seen)
      (if (not (member (nth 1 it) res)) (setq res (cons (nth 1 it) res)))
      (setq seen (cons (strcase (nth 1 it)) seen))))
  (reverse res))

(defun sht:list-info ( / it1)
  (setq it1 (car sht:litems))
  (strcat "Ћистов с номером: " (itoa (length sht:litems))
          " (только листы формы 3). "
          (if sht:ltbls
            (strcat "“аблиц ведомости в чертеже: " (itoa (length sht:ltbls)) " - Ђќбновитьї перепишет их.")
            "“аблицы ведомости в чертеже нет - Ђ¬ставить ведомость <ї.")))

(defun sht:list-off ( / s d)
  (setq s "")
  (if sht:loff
    (setq s (strcat "Ѕез номера - не войдут (" (itoa (length sht:loff)) "): "
                    (sht:join (mapcar '(lambda (it) (if (= (nth 2 it) "") "(без наименовани€)" (strcat "Ђ" (nth 2 it) "ї")))
                                      sht:loff)
                              ", "))))
  (if (setq d (sht:list-dups sht:litems))
    (setq s (strcat (if (= s "") "" (strcat s ". ")) "ѕовтор€ютс€ номера: " (sht:join d ", "))))
  (if (> (strlen s) 100) (strcat (substr s 1 97) "...") s))

(defun sht:list-init ()
  (start_list "sht_LList")
  (foreach it sht:litems (add_list (sht:list-line it)))
  (end_list)
  (set_tile "sht_LInfo" (sht:list-info))
  (set_tile "sht_LOff" (sht:list-off))
  (set_tile "sht_LTitle" sht:ltitle)
  (set_tile "sht_LCnt" sht:lcnt)
  (set_tile "sht_LAuto" sht:lauto)
  (action_tile "sht_LIns" "(sht:list-ok 2)")
  (action_tile "accept" "(sht:list-ok 1)"))

;; Ђќбновитьї (1) / Ђ¬ставить ведомость <ї (2)
(defun sht:list-ok (code)
  (setq sht:ltitle (sht:trim (get_tile "sht_LTitle"))
        sht:lcnt   (get_tile "sht_LCnt")
        sht:lauto  (get_tile "sht_LAuto"))
  (if (= sht:ltitle "")
    (set_tile "error" "¬пишите заголовок ведомости.")
    (done_dialog code)))

(defun sht:list-dialog ( / dcl_id dclFile ret)
  (setq ret 0)
  (if (sht:dlg-load)
    (if (new_dialog "sht_list" dcl_id)
      (progn
        (sht:list-init)
        (setq ret (start_dialog)))
      (princ "\nSHEETS: не удалось открыть окно.")))
  (sht:dlg-cleanup)
  ret)

;; Ќастройки ведомости Ч в словарь чертежа (если помен€лись)
(defun sht:list-save ( / sdat new)
  (setq sdat (sht:set-read)
        new  (sht:alist-put (sht:alist-put (sht:alist-put sdat "@LISTTITLE" sht:ltitle)
                                           "@LISTCNT" sht:lcnt)
                            "@LISTAUTO" sht:lauto))
  (if (not (equal new sdat)) (sht:set-write new)))

;; Ћист SHEETS, на котором точка p (мировые координаты): (ename масштаб) или nil
(defun sht:sheet-at (p / inf wh q res)
  (foreach en (sht:sheets)
    (setq inf (sht:sheet-info en)
          wh  (sht:fmt-wh (car inf) (cadr inf))
          q   (nth 4 inf))
    (if (and (not res)
             (<= (car q) (car p) (+ (car q) (* (cadddr inf) (car wh))))
             (<= (cadr q) (cadr p) (+ (cadr q) (* (cadddr inf) (cadr wh)))))
      (setq res (list en (cadddr inf)))))
  res)

;; “очка не на листе Ч спросить масштаб (по умолчанию Ч как у первого листа)
(defun sht:list-ask-scale ( / d r)
  (setq d (cond ((nth 5 (car sht:litems))) (*sht_Scale*) (100.0)))
  (initget 6)
  (setq r (getreal (strcat "\n“очка не на листе SHEETS. ћасштаб ведомости 1:<" (sht:n2s d) ">: ")))
  (if r r d))

;; Ќова€ таблица ведомости вида kind ("LIST" / "SPEC", s0.6): pt Ч левый верхний угол всей таблицы
;; (верх строки заголовка), sc Ч масштаб
(defun sht:tbl-new (pt sc title kind / tbl)
  (sht:layer *sht:LayTbl*)
  (setq tbl (vlax-invoke (sht:ms) 'AddTable
                         (list (float (car pt)) (float (cadr pt)) 0.0)
                         3 3 (* *sht:ListRowH* sc) (* 20.0 sc)))
  (sht:tbl-mark-set tbl kind sc)
  (sht:tbl-put tbl 'RegenerateTableSuppressed :vlax-true)
  (sht:tbl-do tbl 'MergeCells (list 0 0 0 2))       ; заголовок обычно уже объединЄн стилем Ч ошибка не мешает
  (vl-catch-all-apply 'sht:tbl-format (list tbl sc))
  (sht:tbl-do tbl 'SetText (list 0 0 title))
  (sht:tbl-put tbl 'RegenerateTableSuppressed :vlax-false)
  tbl)

(defun c:SHEET_LIST ( / doc sdat d ret pt hit sc tbl r h
                        sht:litems sht:loff sht:ltbls sht:ltitle sht:lcnt sht:lauto)
  (setq doc  (sht:doc)
        sdat (sht:prepare))
  (sht:dblclick-setup)
  (sht:defaults)
  (setq d          (sht:list-items)
        sht:litems (car d)
        sht:loff   (cadr d)
        sht:ltbls  (sht:list-tables)
        sht:ltitle (cond ((and sht:ltbls (/= (sht:tbl-text (car sht:ltbls) 0 0) ""))
                          (sht:tbl-text (car sht:ltbls) 0 0))
                         ((/= (sht:trim (cdr (assoc "@LISTTITLE" sdat))) "")
                          (cdr (assoc "@LISTTITLE" sdat)))
                         (t *sht:ListTitle*))
        sht:lcnt   (if (= (cdr (assoc "@LISTCNT" sdat)) "0") "0" "1")
        sht:lauto  (if (= (cdr (assoc "@LISTAUTO" sdat)) "0") "0" "1")
        ret        (sht:list-dialog))
  (cond
    ((= ret 1)
     (sht:list-save)
     (vla-StartUndoMark doc)
     (setq r (sht:list-update sht:ltitle T))
     (vla-EndUndoMark doc)
     (sht:list-msg r T))
    ((= ret 2)
     (sht:list-save)
     (if (= (getvar "TILEMODE") 0)
       (progn
         (setvar "TILEMODE" 1)
         (princ "\n¬едомость вставл€етс€ в модель (там листы SHEETS) - включена вкладка Ђћодельї.")))
     (if (setq pt (getpoint "\nЋевый верхний угол ведомости листов - верх заголовка (к рамке листа; Enter - отмена): "))
       (progn
         (setq pt  (trans pt 1 0)
               hit (sht:sheet-at pt)
               sc  (if hit (cadr hit) (sht:list-ask-scale)))
         (vla-StartUndoMark doc)
         ;; s0.6.2: точка Ч верх заголовка (как у ведомости спецификаций)
         (setq tbl (vl-catch-all-apply 'sht:tbl-new (list pt sc sht:ltitle "LIST")))
         (if (vl-catch-all-error-p tbl)
           (princ (strcat "\nSHEETS: таблица не создана: " (vl-catch-all-error-message tbl)))
           (progn
             (setq r (sht:list-update sht:ltitle T)
                   h (+ *sht:ListTitleH* *sht:ListHeadH* (* *sht:ListRowH* (max 1 (nth 2 r)))))
             (princ (strcat "\n¬едомость вставлена, 1:" (sht:n2s sc)
                            (if hit (strcat " (как у листа " (sht:sheet-no (car hit)) ")") "")
                            "; 185 x " (sht:n2s h) " мм листа вместе с заголовком (без переносов строк)."))
             (sht:list-msg r T)))
         (vla-EndUndoMark doc))
       (princ "\n¬едомость не вставлена."))))
  (setq *sht:WatchTbl* (sht:table-count))           ; сво€ таблица Ч не повод обновл€ть (s0.6)
  (princ))

;;; --------------------------------------------------------------------------
;;;  15. ¬≈ƒќћќ—“№ —ѕ≈÷»‘» ј÷»… (s0.6): SHEET_SPEC
;;;  —водна€ ведомость спецификаций Ч та же таблица, что ведомость листов (15 / 140 / 30, шапка
;;;  ЂЋист / Ќаименование / ѕримечаниеї, заголовок над рамкой), метка XData SHT_TABLE "SPEC".
;;;  —пецификации (решени€ јртЄма, s0.6) Ч только таблицы AutoCAD, в заголовке (строка 0) которых есть
;;;  слово Ђ—пецификаци€ї (Ђ—пецификацииї; Ђ¬едомость спецификацийї, Ђ¬едомость деталейї Ч нет);
;;;  таблицы SHEETS не в счЄт. Ћист Ч лист SHEETS в модели, на котором точка вставки таблицы (левый
;;;  верхний угол); на листе без номера, вне листов SHEETS, на листе бумаги Ч не вход€т (окно их
;;;  показывает).  ажда€ спецификаци€ Ч своей строкой: ЂЋистї Ч номер листа, ЂЌаименованиеї Ч заголовок
;;;  таблицы целиком (без форматировани€), Ђѕримечаниеї Ч пусто. ѕор€док Ч по номерам листов (как
;;;  ведомость листов), на одном листе Ч слева направо, затем сверху вниз.
;;;  ¬ставка Ч кликом: точка Ч левый верхний угол всей таблицы, верх строки заголовка (прив€зать
;;;  к рамке листа или к низу ведомости листов). ќбновление Ч вместе с ведомостью листов
;;;  (sht:list-update): при сохранении и печати, после команд SHEETS, SHEET_UPDATE; а также в конце
;;;  команды, после которой таблиц в чертеже стало больше / меньше (sht:watch-check), и s0.6.1 Ч в конце
;;;  команды, во врем€ которой таблица изменилась (заголовок поправили, перенесли: sht:tbl-watch).
;;;  ѕравка в палитре Ђ—войстваї (без команды) Ч в конце следующей команды или при сохранении.
;;; --------------------------------------------------------------------------

(setq *sht:SpecTitle* "¬едомость спецификаций")

;; “екст €чейки без форматировани€ MText: { } и коды \f \F \H \W \Q \T \A \C \c \p Е; Ч убраны,
;; \P и \~ Ч пробел, \SЕ; (дробь) Ч Ђa/bї, \L \l \O \o \K \k \N Ч убраны; прочие Ђ\Еї (\U+Е, \\, \{) Ч
;; как есть (так они и запишутс€ в ведомость). “абул€ци€ Ч пробел, пробелы подр€д Ч один.
(defun sht:mt-plain (s / i n c d k r)
  (setq s (if (= (type s) 'STR) s "")
        i 1
        n (strlen s)
        r "")
  (while (<= i n)
    (setq c (substr s i 1))
    (cond
      ((and (= c "\\") (< i n))
       (setq d (substr s (1+ i) 1))
       (cond
         ((member d '("P" "~"))
          (setq r (strcat r " ")
                i (+ i 2)))
         ((member d '("L" "l" "O" "o" "K" "k" "N"))
          (setq i (+ i 2)))
         ((and (member d '("f" "F" "H" "W" "Q" "T" "A" "C" "c" "p" "S"))
               (setq k (vl-string-search ";" s (1+ i))))
          (if (= d "S")
            (setq r (strcat r (vl-string-translate "^#" "//" (substr s (+ i 2) (- k i 1))))))
          (setq i (+ k 2)))
         (t
          (setq r (strcat r c d)
                i (+ i 2)))))
      ((member c '("{" "}"))
       (setq i (1+ i)))
      (t
       (setq r (strcat r (if (= c "\t") " " c))
             i (1+ i)))))
  (while (setq k (vl-string-search "  " r))
    (setq r (strcat (substr r 1 k) (substr r (+ k 2)))))
  (sht:trim r))

;; ¬ заголовке есть слово Ђ—пецификаци€ї / Ђ—пецификацииї (любыми буквами; Ђспецификацийї Ч нет)
(defun sht:spec-p (s)
  (and (= (type s) 'STR)
       (wcmatch s "*[—с][ѕп][≈е][÷ц][»и][‘ф][»и][ к][ја][÷ц][»и][я€»и]*")))

;; «аголовок таблицы: перва€ непуста€ €чейка строки 0, без форматировани€
(defun sht:tbl-title (tbl / nc c s)
  (setq nc (sht:tbl-get tbl 'Columns)
        c  0
        s  "")
  (while (and (= s "") (numberp nc) (< c nc))
    (setq s (sht:mt-plain (sht:tbl-text tbl 0 c))
          c (1+ c)))
  s)

;; Ћист из списка shs (ename номер точка масштаб ширина высота), на котором точка p, или nil
(defun sht:sheet-hit (shs p / res)
  (foreach q shs
    (if (and (not res)
             (<= (car (nth 2 q)) (car p) (+ (car (nth 2 q)) (* (nth 3 q) (nth 4 q))))
             (<= (cadr (nth 2 q)) (cadr p) (+ (cadr (nth 2 q)) (* (nth 3 q) (nth 5 q)))))
      (setq res q)))
  res)

;; ѕор€док спецификаций: по листам (sht:item<), на одном листе Ч слева направо, затем сверху вниз
(defun sht:spec< (a b)
  (cond
    ((sht:item< a b) T)
    ((sht:item< b a) nil)
    ((< (car (nth 5 a)) (- (car (nth 5 b)) 1e-6)) T)
    ((> (car (nth 5 a)) (+ (car (nth 5 b)) 1e-6)) nil)
    (t (> (cadr (nth 5 a)) (cadr (nth 5 b))))))

;; —пецификации: (на-листах-с-номером-по-пор€дку остальные). —пецификаци€ Ч (ename-таблицы номер-листа
;; заголовок примечание ename-листа точка-таблицы точка-листа); у остальных вместо примечани€ Ч почему
;; не войдут. Ќомер и точка листа Ч на тех же местах, что у листов ведомости (sht:item<).
(defun sht:spec-items ( / shs inf wh ss i en ed tit p ms hit on off)
  (foreach q (sht:sheets)
    (setq inf (sht:sheet-info q)
          wh  (sht:fmt-wh (car inf) (cadr inf))
          shs (cons (list q (sht:trim (cdr (assoc "SHEET" (sht:attrs q)))) (nth 4 inf) (cadddr inf)
                          (car wh) (cadr wh) (caddr inf))
                    shs)))
  (setq shs (reverse shs))
  (if (setq ss (ssget "_X" '((0 . "ACAD_TABLE"))))
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq en (ssname ss i)
              ed (entget en)
              i  (1+ i))
        (if (and (not (sht:tbl-mark en))
                 (sht:spec-p (setq tit (sht:tbl-title (vlax-ename->vla-object en)))))
          (progn
            (setq p   (cdr (assoc 10 ed))
                  ms  (= (strcase (cond ((cdr (assoc 410 ed))) ("Model"))) "MODEL")
                  hit (if ms (sht:sheet-hit shs p)))
            (cond
              ((not ms)
               (setq off (cons (list en "" tit "на листе бумаги" nil p nil) off)))
              ((not hit)
               (setq off (cons (list en "" tit "не на листе SHEETS" nil p nil) off)))
              ((/= (sht:fbase (nth 6 hit)) "3")                  ; s0.10: не основной комплект
               (setq off (cons (list en "" tit (strcat "на листе формы " (sht:fbase (nth 6 hit))
                                                       " (не в ведомости листов)")
                                     (car hit) p (nth 2 hit))
                               off)))
              ((= (nth 1 hit) "")
               (setq off (cons (list en "" tit "на листе без номера" (car hit) p (nth 2 hit)) off)))
              (t
               (setq on (cons (list en (nth 1 hit) tit "" (car hit) p (nth 2 hit)) on)))))))))
  (list (vl-sort on 'sht:spec<) (reverse off)))

;; ќбновить таблицы ведомости спецификаций. title Ч заголовок (nil Ч не трогать), force Ч оформление
;; заново. “аблиц нет Ч nil (спецификации и не ищутс€); иначе (таблиц-изменено таблиц-всего спецификаций).
(defun sht:spec-update (title force / tbls items nt)
  (if (setq tbls (sht:kind-tables "SPEC"))
    (progn
      (setq items (car (sht:spec-items))
            nt    0)
      (foreach tbl tbls
        (if (sht:tbl-fill tbl items title force) (setq nt (1+ nt))))
      (list nt (length tbls) (length items)))))

;; —ообщение об обновлении; all Ч и когда таблицы не мен€лись
(defun sht:spec-msg (r all)
  (if (or all (> (car r) 0))
    (princ (strcat "\n¬едомость спецификаций: спецификаций " (itoa (nth 2 r))
                   (cond ((= (cadr r) 0) " - таблицы ведомости спецификаций в чертеже нет (вставить: SHEET_SPEC)")
                         ((> (car r) 0) (strcat ", обновлено таблиц: " (itoa (car r)) " из " (itoa (cadr r))))
                         (t ", таблица без изменений"))
                   "."))))

;; --- окно Ђ¬едомость спецификацийї -----------------------------------------------
;; ѕеременные окна (локальные в c:SHEET_SPEC): sht:sitems sht:soff Ч спецификации на листах с номером /
;; остальные, sht:stbls Ч таблицы ведомости спецификаций, sht:stitle Ч заголовок, sht:lauto Ч "1" / "0"
;; (автообновление Ч общее с ведомостью листов).

(defun sht:spec-info ()
  (strcat "—пецификаций в ведомости: " (itoa (length sht:sitems)) ". "
          (if sht:stbls
            (strcat "“аблиц ведомости спецификаций в чертеже: " (itoa (length sht:stbls))
                    " - Ђќбновитьї перепишет их.")
            "“аблицы ведомости спецификаций в чертеже нет - Ђ¬ставить ведомость <ї.")))

(defun sht:spec-init ()
  (start_list "sht_SList")
  (foreach it sht:sitems (add_list (sht:list-line it)))
  (end_list)
  (start_list "sht_SOff")
  (foreach it sht:soff (add_list (strcat "-\t" (nth 2 it) "\t" (nth 3 it))))
  (end_list)
  (set_tile "sht_SInfo" (sht:spec-info))
  (set_tile "sht_STitle" sht:stitle)
  (set_tile "sht_SAuto" sht:lauto)
  (action_tile "sht_SIns" "(sht:spec-ok 2)")
  (action_tile "accept" "(sht:spec-ok 1)"))

;; Ђќбновитьї (1) / Ђ¬ставить ведомость <ї (2)
(defun sht:spec-ok (code)
  (setq sht:stitle (sht:trim (get_tile "sht_STitle"))
        sht:lauto  (get_tile "sht_SAuto"))
  (if (= sht:stitle "")
    (set_tile "error" "¬пишите заголовок ведомости.")
    (done_dialog code)))

(defun sht:spec-dialog ( / dcl_id dclFile ret)
  (setq ret 0)
  (if (sht:dlg-load)
    (if (new_dialog "sht_spec" dcl_id)
      (progn
        (sht:spec-init)
        (setq ret (start_dialog)))
      (princ "\nSHEETS: не удалось открыть окно.")))
  (sht:dlg-cleanup)
  ret)

;; Ќастройки Ч в словарь чертежа (если помен€лись)
(defun sht:spec-save ( / sdat new)
  (setq sdat (sht:set-read)
        new  (sht:alist-put (sht:alist-put sdat "@SPECTITLE" sht:stitle) "@LISTAUTO" sht:lauto))
  (if (not (equal new sdat)) (sht:set-write new)))

(defun c:SHEET_SPEC ( / doc sdat d ret pt hit sc tbl r h
                        sht:sitems sht:soff sht:stbls sht:stitle sht:lauto sht:litems)
  (setq doc  (sht:doc)
        sdat (sht:prepare))
  (sht:dblclick-setup)
  (sht:defaults)
  (setq d          (sht:spec-items)
        sht:sitems (car d)
        sht:soff   (cadr d)
        sht:stbls  (sht:kind-tables "SPEC")
        sht:stitle (cond ((and sht:stbls (/= (sht:tbl-text (car sht:stbls) 0 0) ""))
                          (sht:tbl-text (car sht:stbls) 0 0))
                         ((/= (sht:trim (cdr (assoc "@SPECTITLE" sdat))) "")
                          (cdr (assoc "@SPECTITLE" sdat)))
                         (t *sht:SpecTitle*))
        sht:lauto  (if (= (cdr (assoc "@LISTAUTO" sdat)) "0") "0" "1")
        ret        (sht:spec-dialog))
  (cond
    ((= ret 1)
     (sht:spec-save)
     (vla-StartUndoMark doc)
     (setq r (sht:spec-update sht:stitle T))
     (vla-EndUndoMark doc)
     (sht:spec-msg (cond (r) ((list 0 0 (length sht:sitems)))) T))
    ((= ret 2)
     (sht:spec-save)
     (if (= (getvar "TILEMODE") 0)
       (progn
         (setvar "TILEMODE" 1)
         (princ "\n¬едомость вставл€етс€ в модель (там листы SHEETS) - включена вкладка Ђћодельї.")))
     (if (setq pt (getpoint (strcat "\nЋевый верхний угол ведомости спецификаций - верх заголовка "
                                    "(к рамке листа или к низу ведомости листов; Enter - отмена): ")))
       (progn
         (setq pt         (trans pt 1 0)
               hit        (sht:sheet-at pt)
               sht:litems (car (sht:list-items))         ; масштаб по умолчанию Ч как у первого листа
               sc         (if hit (cadr hit) (sht:list-ask-scale)))
         (vla-StartUndoMark doc)
         (setq tbl (vl-catch-all-apply 'sht:tbl-new (list pt sc sht:stitle "SPEC")))
         (if (vl-catch-all-error-p tbl)
           (princ (strcat "\nSHEETS: таблица не создана: " (vl-catch-all-error-message tbl)))
           (progn
             (setq r (cond ((sht:spec-update sht:stitle T)) ((list 0 0 (length sht:sitems))))
                   h (+ *sht:ListTitleH* *sht:ListHeadH* (* *sht:ListRowH* (max 1 (nth 2 r)))))
             (princ (strcat "\n¬едомость спецификаций вставлена, 1:" (sht:n2s sc)
                            (if hit (strcat " (как у листа " (sht:sheet-no (car hit)) ")") "")
                            "; 185 x " (sht:n2s h) " мм листа вместе с заголовком (без переносов строк)."))
             (sht:spec-msg r T)))
         (vla-EndUndoMark doc))
       (princ "\n¬едомость спецификаций не вставлена."))))
  (setq *sht:WatchTbl* (sht:table-count))
  (princ))


;;; --------------------------------------------------------------------------
;;;  15а. ¬≈ƒќћќ—“№ ——џЋќ„Ќџ’ » ѕ–»Ћј√ј≈ћџ’ ƒќ ”ћ≈Ќ“ќ¬ (s0.10): SHEET_REFS
;;;  ќбразец јртЄма (Ђ‘орматы.dxfї): столбцы Ђќбозначение / Ќаименование / ѕримечаниеї 60 / 95 / 30,
;;;  шапка 15, строки 8, заголовок 3,5 над таблицей Ч как у прочих ведомостей (таблица AutoCAD, метка
;;;  XData SHT_TABLE "REFS"); ставитс€ на лист общих данных кликом Ч точка Ч верх заголовка.
;;;  –азделы Ч подчЄркнутый заголовок по центру столбца ЂЌаименованиеї:
;;;  Ђ—сылочные документыї Ч вписываютс€ вручную в окне SHEET_REFS (словарь чертежа: @REF1, @REF2 Е
;;;  = Ђобозначение|наименование|примечаниеї); записей нет Ч раздела нет;
;;;  Ђѕрилагаемые документыї Ч из листов формы 4 (решение јртЄма): листы с одинаковой графой 1 Ч один
;;;  документ, одна строка: Ђќбозначениеї Ч графа 1, ЂЌаименованиеї Ч графа 5 (клетка 70 x 25) первого
;;;  листа, Ђѕримечаниеї Ч пусто. ƒанные форм 5 и 6 ни в какие таблицы не идут.
;;;  ќбновление Ч вместе с ведомостью листов (sht:list-update): при сохранении и печати, после команд
;;;  SHEETS, SHEET_UPDATE.
;;; --------------------------------------------------------------------------

(setq *sht:RefTitle*  "¬едомость ссылочных и прилагаемых документов"
      *sht:RefHead*   '("ќбозначение" "Ќаименование" "ѕримечание")
      *sht:RefCols*   '(60.0 95.0 30.0)
      *sht:RefSecRef* "\\L—сылочные документы\\l"
      *sht:RefSecAtt* "\\Lѕрилагаемые документы\\l")

;; —сылочные документы из данных чертежа: ((обозначение наименование примечание) Е)
(defun sht:refs-load (sdat / i v l res)
  (setq i 1)
  (while (setq v (cdr (assoc (strcat "@REF" (itoa i)) sdat)))
    (setq l   (sht:split v "|")
          res (cons (list (car l) (cond ((cadr l)) ("")) (cond ((caddr l)) (""))) res)
          i   (1+ i)))
  (reverse res))

;; ƒанные чертежа sdat со ссылочными документами refs вместо прежних @REF1, @REF2 Е
(defun sht:refs-put (sdat refs / res i)
  (foreach p sdat
    (if (not (and (> (strlen (car p)) 4) (= (substr (car p) 1 4) "@REF") (wcmatch (substr (car p) 5 1) "#")))
      (setq res (cons p res))))
  (setq res (reverse res)
        i   1)
  (foreach r refs
    (setq res (append res (list (cons (strcat "@REF" (itoa i)) (strcat (car r) "|" (cadr r) "|" (caddr r)))))
          i   (1+ i)))
  res)

;; ƒокументы раздела Ђѕрилагаемые документыї: документы (sht:doc-items), в которых есть лист формы 4
(defun sht:refs-docs ()
  (vl-remove-if-not '(lambda (d) (vl-some '(lambda (it) (= (sht:fbase (nth 4 it)) "4")) (cadr d)))
                    (sht:doc-items)))

;; —троки таблицы под шапкой: разделы с заголовками; строка Ч (nil обозначение наименование примечание),
;; как у листов ведомости (sht:list-cells)
(defun sht:refs-rows (refs docs / res)
  (if refs
    (setq res (cons (list nil "" *sht:RefSecRef* "")
                    (mapcar '(lambda (r) (list nil (car r) (cadr r) (caddr r))) refs))))
  (if docs
    (setq res (append res (list (list nil "" *sht:RefSecAtt* ""))
                      (mapcar '(lambda (d) (list nil (car d) (sht:doc-name d) "")) docs))))
  res)

;; ќбновить таблицы ведомости ссылочных документов. title Ч заголовок (nil Ч не трогать), force Ч
;; оформление заново. “аблиц нет Ч nil; иначе (таблиц-изменено таблиц-всего прилагаемых ссылочных).
(defun sht:refs-update (title force / tbls refs docs rows nt)
  (if (setq tbls (sht:kind-tables "REFS"))
    (progn
      (setq refs (sht:refs-load (sht:set-read))
            docs (sht:refs-docs)
            rows (sht:refs-rows refs docs)
            nt   0)
      (foreach tbl tbls
        (if (sht:tbl-fill tbl rows title force) (setq nt (1+ nt))))
      (list nt (length tbls) (length docs) (length refs)))))

;; —ообщение об обновлении; all Ч и когда таблицы не мен€лись
(defun sht:refs-msg (r all)
  (if (or all (> (car r) 0))
    (princ (strcat "\n¬едомость ссылочных и прилагаемых документов: прилагаемых " (itoa (nth 2 r))
                   ", ссылочных " (itoa (nth 3 r))
                   (cond ((= (cadr r) 0) " - таблицы в чертеже нет (вставить: SHEET_REFS)")
                         ((> (car r) 0) (strcat ", обновлено таблиц: " (itoa (car r)) " из " (itoa (cadr r))))
                         (t ", таблица без изменений"))
                   "."))))

;; --- окно Ђ¬едомость ссылочных и прилагаемых документовї -----------------------------
;; ѕеременные окна (локальные в c:SHEET_REFS): sht:ratt Ч прилагаемые документы (sht:refs-docs),
;; sht:rref Ч ссылочные ((обозначение наименование примечание) Е), sht:rsel Ч выбранна€ строка
;; ссылочных (номер с 0 или nil), sht:rtbls Ч таблицы, sht:rtitle Ч заголовок, sht:lauto Ч "1" / "0"
;; (автообновление Ч общее дл€ всех ведомостей).

;; —писок lst, в котором элемент номер i заменЄн на v (v = nil Ч убран)
(defun sht:nth-set (lst i v / k res)
  (setq k 0)
  (foreach x lst
    (cond ((/= k i) (setq res (cons x res)))
          (v (setq res (cons v res))))
    (setq k (1+ k)))
  (reverse res))

;; ѕомен€ть местами элементы i и i+1
(defun sht:nth-swap (lst i / a b)
  (setq a (nth i lst)
        b (nth (1+ i) lst))
  (sht:nth-set (sht:nth-set lst i b) (1+ i) a))

(defun sht:refs-info ()
  (strcat "ѕрилагаемых документов: " (itoa (length sht:ratt)) ", ссылочных: " (itoa (length sht:rref)) ". "
          (if sht:rtbls
            (strcat "“аблиц ведомости в чертеже: " (itoa (length sht:rtbls)) " - Ђќбновитьї перепишет их.")
            "“аблицы ведомости в чертеже нет - Ђ¬ставить ведомость <ї.")))

;; —писок ссылочных документов в окне
(defun sht:refs-fill ()
  (start_list "sht_RRef")
  (foreach r sht:rref (add_list (strcat (car r) "\t" (cadr r) "\t" (caddr r))))
  (end_list)
  (if (and sht:rsel (< sht:rsel (length sht:rref)))
    (set_tile "sht_RRef" (itoa sht:rsel)))
  (set_tile "sht_RInfo" (sht:refs-info)))

(defun sht:refs-init ()
  (start_list "sht_RAtt")
  (foreach d sht:ratt
    (add_list (strcat (car d) "\t" (sht:doc-name d) "\t" (itoa (length (cadr d))) " л.")))
  (end_list)
  (sht:refs-fill)
  (set_tile "sht_RTitle" sht:rtitle)
  (set_tile "sht_RAuto" sht:lauto)
  (action_tile "sht_RRef" "(sht:refs-pick)")
  (action_tile "sht_RAdd" "(sht:refs-edit 1)")
  (action_tile "sht_RChg" "(sht:refs-edit 2)")
  (action_tile "sht_RDel" "(sht:refs-edit 3)")
  (action_tile "sht_RUp" "(sht:refs-edit 4)")
  (action_tile "sht_RDn" "(sht:refs-edit 5)")
  (action_tile "sht_RIns" "(sht:refs-ok 2)")
  (action_tile "accept" "(sht:refs-ok 1)"))

;; ўелчок по строке ссылочных Ч в пол€ дл€ правки
(defun sht:refs-pick ( / r)
  (setq sht:rsel (atoi (get_tile "sht_RRef"))
        r        (nth sht:rsel sht:rref))
  (if r
    (progn
      (set_tile "sht_RObo" (car r))
      (set_tile "sht_RNam" (cadr r))
      (set_tile "sht_RNote" (caddr r)))))

;;  нопки: 1 Ч добавить, 2 Ч заменить выбранную строку, 3 Ч удалить, 4 Ч выше, 5 Ч ниже.
;; Ђ|ї в тексте Ч Ђ/ї (разделитель записи в данных чертежа).
(defun sht:refs-edit (op / r n)
  (setq r (mapcar '(lambda (k) (sht:trim (vl-string-translate "|" "/" (get_tile k))))
                  '("sht_RObo" "sht_RNam" "sht_RNote"))
        n (length sht:rref))
  (set_tile "error" "")
  (cond
    ((= op 1)
     (if (and (= (car r) "") (= (cadr r) ""))
       (set_tile "error" "¬пишите обозначение или наименование документа.")
       (setq sht:rref (append sht:rref (list r))
             sht:rsel n)))
    ((not (and sht:rsel (< sht:rsel n)))
     (set_tile "error" "¬ыберите строку в списке ссылочных документов."))
    ((= op 2) (setq sht:rref (sht:nth-set sht:rref sht:rsel r)))
    ((= op 3) (setq sht:rref (sht:nth-set sht:rref sht:rsel nil)
                    sht:rsel nil))
    ((and (= op 4) (> sht:rsel 0))
     (setq sht:rref (sht:nth-swap sht:rref (1- sht:rsel))
           sht:rsel (1- sht:rsel)))
    ((and (= op 5) (< sht:rsel (1- n)))
     (setq sht:rref (sht:nth-swap sht:rref sht:rsel)
           sht:rsel (1+ sht:rsel))))
  (sht:refs-fill))

;; Ђќбновитьї (1) / Ђ¬ставить ведомость <ї (2)
(defun sht:refs-ok (code)
  (setq sht:rtitle (sht:trim (get_tile "sht_RTitle"))
        sht:lauto  (get_tile "sht_RAuto"))
  (if (= sht:rtitle "")
    (set_tile "error" "¬пишите заголовок ведомости.")
    (done_dialog code)))

(defun sht:refs-dialog ( / dcl_id dclFile ret)
  (setq ret 0)
  (if (sht:dlg-load)
    (if (new_dialog "sht_refs" dcl_id)
      (progn
        (sht:refs-init)
        (setq ret (start_dialog)))
      (princ "\nSHEETS: не удалось открыть окно.")))
  (sht:dlg-cleanup)
  ret)

;; —сылочные, заголовок, автообновление Ч в данные чертежа (если помен€лись)
(defun sht:refs-save ( / sdat new)
  (setq sdat (sht:set-read)
        new  (sht:alist-put (sht:alist-put (sht:refs-put sdat sht:rref) "@REFTITLE" sht:rtitle)
                            "@LISTAUTO" sht:lauto))
  (if (not (equal new sdat)) (sht:set-write new)))

(defun c:SHEET_REFS ( / doc sdat ret pt hit sc tbl r h
                        sht:ratt sht:rref sht:rsel sht:rtbls sht:rtitle sht:lauto sht:litems)
  (setq doc  (sht:doc)
        sdat (sht:prepare))
  (sht:dblclick-setup)
  (sht:defaults)
  (setq sht:ratt   (sht:refs-docs)
        sht:rref   (sht:refs-load sdat)
        sht:rtbls  (sht:kind-tables "REFS")
        sht:rtitle (cond ((and sht:rtbls (/= (sht:tbl-text (car sht:rtbls) 0 0) ""))
                          (sht:tbl-text (car sht:rtbls) 0 0))
                         ((/= (sht:trim (cdr (assoc "@REFTITLE" sdat))) "")
                          (cdr (assoc "@REFTITLE" sdat)))
                         (t *sht:RefTitle*))
        sht:lauto  (if (= (cdr (assoc "@LISTAUTO" sdat)) "0") "0" "1")
        ret        (sht:refs-dialog))
  (cond
    ((= ret 1)
     (sht:refs-save)
     (vla-StartUndoMark doc)
     (setq r (sht:refs-update sht:rtitle T))
     (vla-EndUndoMark doc)
     (sht:refs-msg (cond (r) ((list 0 0 (length sht:ratt) (length sht:rref)))) T))
    ((= ret 2)
     (sht:refs-save)
     (if (= (getvar "TILEMODE") 0)
       (progn
         (setvar "TILEMODE" 1)
         (princ "\n¬едомость вставл€етс€ в модель (там листы SHEETS) - включена вкладка Ђћодельї.")))
     (if (setq pt (getpoint (strcat "\nЋевый верхний угол ведомости ссылочных и прилагаемых документов - "
                                    "верх заголовка (Enter - отмена): ")))
       (progn
         (setq pt         (trans pt 1 0)
               hit        (sht:sheet-at pt)
               sht:litems (car (sht:list-items))         ; масштаб по умолчанию Ч как у первого листа
               sc         (if hit (cadr hit) (sht:list-ask-scale)))
         (vla-StartUndoMark doc)
         (setq tbl (vl-catch-all-apply 'sht:tbl-new (list pt sc sht:rtitle "REFS")))
         (if (vl-catch-all-error-p tbl)
           (princ (strcat "\nSHEETS: таблица не создана: " (vl-catch-all-error-message tbl)))
           (progn
             (setq r (cond ((sht:refs-update sht:rtitle T)) ((list 0 0 (length sht:ratt) (length sht:rref))))
                   h (+ *sht:ListTitleH* *sht:ListHeadH*
                        (* *sht:ListRowH* (max 1 (length (sht:refs-rows sht:rref sht:ratt))))))
             (princ (strcat "\n¬едомость ссылочных и прилагаемых документов вставлена, 1:" (sht:n2s sc)
                            (if hit (strcat " (как у листа " (sht:sheet-no (car hit)) ")") "")
                            "; 185 x " (sht:n2s h) " мм листа вместе с заголовком (без переносов строк)."))
             (sht:refs-msg r T)))
         (vla-EndUndoMark doc))
       (princ "\n¬едомость ссылочных и прилагаемых документов не вставлена."))))
  (setq *sht:WatchTbl* (sht:table-count))
  (princ))

;;; --------------------------------------------------------------------------
;;;  16. ѕќƒѕ»—» » Ћќ√ќ“»ѕ (s0.7 Ч шаг плана s0.4): SHEET_SIGN
;;;  ѕодпись Ч блок AutoCAD в графе Ђѕодп.ї напротив фамилии (графа 11, строки 1-6 основной надписи,
;;;  форма 3).  акой блок у какой фамилии Ч задаЄтс€ один раз на комплект (окно SHEET_SIGN; словарь
;;;  чертежа: @SIGN:<фамили€> = им€ блока, "" Ч без подписи) и расходитс€ по всем листам: подпись
;;;  стоит везде, где в штампе эта фамили€. Ћоготип Ч блок или картинка (IMAGE) в графе 9 на всех
;;;  листах формы 3 (@LOGO = "B:<блок>" / "I:<файл>"; "" Ч нет).  ороткий штамп (форма 6) Ч без них.
;;;  –азмер: подпись Ч вписать в графу 15 x 5 с зазором 0,5 (@SIGNFIT "1") или как нарисована Ч
;;;  1 ед. блока = 1 мм листа ("0"); логотип-блок Ч вписать в графу 50 x 15 с зазором 1 (@LOGOFIT)
;;;  или как нарисован; картинка Ч всегда вписать. —ередина габарита Ч в середине графы.
;;;  ѕодписи и логотип Ч отдельные объекты в модели: подписи Ч слой 0000_ѕодписи (заморозить Ч
;;;  печать без подписей; программа слой только создаЄт, вкл./выкл. не трогает), логотип Ч слой
;;;  листа 0000_‘ормат. ћетка XData SHT_SIGN: вид ("SIGN" / "LOGO"), handle листа, строка, точка
;;;  вставки в мм листа (x y), масштаб (у картинки Ч ширина, мм листа), источник ("B:Е" / "I:Е").
;;;  —верка (sht:sign-sync): объект у своего листа, на своЄм месте, того же источника Ч остаЄтс€;
;;;  иначе (лист сдвинули без подписей, удалили, скопировали; фамилию помен€ли; блок сменили) Ч
;;;  удал€етс€, недостающие став€тс€ заново. ѕодписи всегда соответствуют фамили€м в штампах.
;;;   огда: SHEET_SIGN Ђ–асставитьї и SHEET_UPDATE Ч всЄ заново (габариты блоков мер€ютс€ заново);
;;;  в конце SHEET_NEW, окна ЂЋистї, SHEET_DATA, SHEET_APPLY, перед печатью SHEET_PLOT, перед
;;;  сохранением (реактор команд) и в конце команды, после которой листов стало больше / меньше
;;;  или лист сдвинули / фамилию в нЄм помен€ли (реактор *sht:RSign* Ч только если подписи или
;;;  логотип заданы; сам реактор только ставит флаг). ѕосле U / UNDO Ч при сохранении.
;;; --------------------------------------------------------------------------

(setq *sht:LaySign*  "0000_ѕодписи"
      *sht:SignApp*  "SHT_SIGN"
      *sht:SignGap*  0.5                  ; зазор вписывани€ подписи, мм листа (с каждой стороны)
      *sht:LogoGap*  1.0                  ; зазор вписывани€ логотипа
      *sht:NameTags* '("NAME1" "NAME2" "NAME3" "NAME4" "NAME5" "NAME6")
      *sht:ImgExt*   "png;jpg;jpeg;bmp;tif;tiff;gif")

;; Ѕез повторов (без учЄта регистра)
(defun sht:uniq-ci (lst / res)
  (foreach x lst
    (if (not (vl-some '(lambda (y) (= (sht:lc y) (sht:lc x))) res)) (setq res (append res (list x)))))
  res)

;; —трочные буквы (латиница и кириллица; strcase дл€ кириллицы не надЄжен)
(defun sht:lc (s)
  (vl-string-translate "ABCDEFGHIJKLMNOPQRSTUVWXYZјЅ¬√ƒ≈®∆«»… ЋћЌќѕ–—“”‘’÷„ЎўЏџ№Ёёя"
                       "abcdefghijklmnopqrstuvwxyzабвгдеЄжзийклмнопрстуфхцчшщъыьэю€" s))

;; Ќастройки из словар€ чертежа: (фамилии вписать-подпись логотип вписать-логотип);
;; фамилии Ч (("»ванов" . "ѕодпись_»ванов") Е), "" Ч без подписи
(defun sht:sign-cfg (sdat / res)
  (foreach p sdat
    (if (and (> (strlen (car p)) 6) (= (substr (car p) 1 6) "@SIGN:"))
      (setq res (cons (cons (substr (car p) 7) (cdr p)) res))))
  (list (reverse res)
        (if (= (cdr (assoc "@SIGNFIT" sdat)) "0") "0" "1")
        (cond ((cdr (assoc "@LOGO" sdat))) (""))
        (if (= (cdr (assoc "@LOGOFIT" sdat)) "0") "0" "1")))

;; ѕодписи или логотип заданы?
(defun sht:sign-on-p (cfg)
  (or (vl-some '(lambda (p) (/= (cdr p) "")) (car cfg))
      (/= (caddr cfg) "")))

;; »м€ блока, как оно в чертеже (без учЄта регистра), или nil; на врем€ сверки Ч запоминаетс€
(defun sht:blk-real (b / c r)
  (if (setq c (assoc b *sht:BlkReal*))
    (cdr c)
    (progn
      (setq r (tblsearch "BLOCK" b)
            r (if r (cdr (assoc 2 r))))
      (setq *sht:BlkReal* (cons (cons b r) *sht:BlkReal*))
      r)))

;; Ќет блока b Ч запомнить дл€ сообщени€
(defun sht:sign-miss (b)
  (if (not (member b *sht:SignMiss*)) (setq *sht:SignMiss* (append *sht:SignMiss* (list b))))
  nil)

;; —троки подписей формы (s0.10): (число верх) Ч формы 3, 4: 6 строк, верх y 30; форма 5: 5 строк,
;; верх y 25 (мм от угла рамки пол€); короткий штамп (форма 6) Ч nil (подписей и логотипа нет)
(defun sht:sign-rows (form / b)
  (setq b (sht:fbase form))
  (cond ((member b '("3" "4")) (list 6 30.0))
        ((= b "5") (list 5 25.0))))

;; „то должно сто€ть на листе (формы 3, 4, 5): ((вид строка источник cx cy ширина высота вписать) Е):
;; источник Ч "B:<блок>" / "I:<файл>"; cx cy Ч середина графы, мм листа от левого нижнего угла листа.
(defun sht:sign-want (inf a cfg / br i nm b bb res lg sr)
  (if (setq sr (sht:sign-rows (caddr inf)))
    (progn
      (setq br (sht:anchor "BR" (sht:fmt-wh (car inf) (cadr inf)))
            i  1)
      ;; подписи: графа Ђѕодп.ї x -145Е-130, строка i Ч y (верх - 5i)Е(верх + 5 - 5i) от угла рамки пол€
      (repeat (car sr)
        (setq nm (sht:trim (cdr (assoc (strcat "NAME" (itoa i)) a))))
        (if (and (/= nm "")
                 (setq b (cdr (assoc nm (car cfg))))
                 (/= b ""))
          (if (setq bb (sht:blk-real b))
            (setq res (cons (list "SIGN" i (strcat "B:" bb) (- (car br) 137.5)
                                  (+ (cadr br) (- (+ (cadr sr) 2.5) (* 5.0 i)))
                                  15.0 5.0 (cadr cfg))
                            res))
            (sht:sign-miss b)))
        (setq i (1+ i)))
      ;; логотип: графа 9 x -50Е0, y 0Е15
      (setq lg (caddr cfg))
      (cond
        ((= lg ""))
        ((= (substr lg 1 2) "I:")
         (setq res (cons (list "LOGO" 0 lg (- (car br) 25.0) (+ (cadr br) 7.5) 50.0 15.0 "1") res)))
        ((setq b (sht:blk-real (substr lg 3)))
         (setq res (cons (list "LOGO" 0 (strcat "B:" b) (- (car br) 25.0) (+ (cadr br) 7.5) 50.0 15.0 (cadddr cfg))
                         res)))
        (t (sht:sign-miss (substr lg 3))))))
  (reverse res))

;; “очка листа (мм от левого нижнего угла, без поворота) -> мирова€; ed Ч entget листа
(defun sht:sheet-pt (ed lx ly / p sc a)
  (setq p  (cdr (assoc 10 ed))
        sc (cond ((cdr (assoc 41 ed))) (1.0))
        a  (cond ((cdr (assoc 50 ed))) (0.0)))
  (list (+ (car p) (* sc (- (* lx (cos a)) (* ly (sin a)))))
        (+ (cadr p) (* sc (+ (* lx (sin a)) (* ly (cos a)))))
        (cond ((caddr p)) (0.0))))

(defun sht:ang-eq (a b / d)
  (setq d (rem (abs (- a b)) (* 2.0 pi)))
  (or (< d 1e-6) (< (- (* 2.0 pi) d) 1e-6)))

;; ѕодписи и логотипы в чертеже: ((ename вид handle-листа строка x y масштаб источник) Е)
(defun sht:sign-objs ( / ss i en xd res)
  (if (setq ss (ssget "_X" (list (list -3 (list *sht:SignApp*)))))
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq en (ssname ss i)
              i  (1+ i)
              xd (mapcar 'cdr (cdr (assoc *sht:SignApp* (cdr (assoc -3 (entget en (list *sht:SignApp*))))))))
        (if (= (length xd) 7)
          (setq res (cons (cons en xd) res))))))
  (reverse res))

(defun sht:sign-xd-set (en kind h row lx ly k src)
  (regapp *sht:SignApp*)
  (entmod (append (entget en)
                  (list (list -3 (list *sht:SignApp* (cons 1000 kind) (cons 1000 h) (cons 1070 row)
                                       (cons 1040 (float lx)) (cons 1040 (float ly)) (cons 1040 (float k))
                                       (cons 1000 src)))))))

;; ќбъект o (из sht:sign-objs) стоит по своим данным у листа ed: точка, поворот, масштаб / ширина
(defun sht:sign-at-p (o ed / oe q sc a tol v r)
  (setq q   (sht:sheet-pt ed (nth 4 o) (nth 5 o))
        sc  (cond ((cdr (assoc 41 ed))) (1.0))
        a   (cond ((cdr (assoc 50 ed))) (0.0))
        tol (* 0.001 sc)
        oe  (entget (car o)))
  (cond
    ((null oe) nil)
    ((= (cdr (assoc 0 oe)) "INSERT")
     (and (< (distance (cdr (assoc 10 oe)) q) tol)
          (equal (cdr (assoc 41 oe)) (* (nth 6 o) sc) (* 1e-6 (abs (* (nth 6 o) sc))))
          (sht:ang-eq (cond ((cdr (assoc 50 oe))) (0.0)) a)
          (= (strcat "B:" (cdr (assoc 2 oe))) (nth 7 o))))
    ((= (cdr (assoc 0 oe)) "IMAGE")
     (setq v (vlax-ename->vla-object (car o))
           r (sht:tbl-get v 'Origin))
     (and r
          (< (distance r q) tol)
          (sht:ang-eq (cond ((sht:tbl-get v 'Rotation)) (0.0)) a)
          (equal (sht:tbl-get v 'ImageWidth) (* (nth 6 o) sc) tol)))))

;; √абарит блока при вставке 1:1 без поворота: (dx dy ширина высота) Ч середина габарита от
;; базовой точки; не измерилс€ Ч nil. ѕо объектам описани€ блока (без определений атрибутов):
;; чертЄж не мен€етс€, временных вставок нет.
(defun sht:blk-box (name / c blk o0 r mn mx x1 y1 x2 y2)
  (if (setq c (assoc name *sht:BoxCache*))
    (cdr c)
    (progn
      (setq blk (vl-catch-all-apply 'vla-Item (list (vla-get-Blocks (sht:doc)) name)))
      (if (not (vl-catch-all-error-p blk))
        (vlax-for o blk
          (if (/= (vla-get-ObjectName o) "AcDbAttributeDefinition")
            (progn
              (setq r (vl-catch-all-apply 'vla-GetBoundingBox (list o 'mn 'mx)))
              (if (not (vl-catch-all-error-p r))
                (setq mn (vlax-safearray->list mn)
                      mx (vlax-safearray->list mx)
                      x1 (if x1 (min x1 (car mn)) (car mn))
                      y1 (if y1 (min y1 (cadr mn)) (cadr mn))
                      x2 (if x2 (max x2 (car mx)) (car mx))
                      y2 (if y2 (max y2 (cadr mx)) (cadr mx))))))))
      ;; базова€ точка блока (BASE) Ч в точку вставки: середина Ч от неЄ
      (setq o0 (if (vl-catch-all-error-p blk) nil (sht:tbl-get blk 'Origin))
            o0 (if (and (listp o0) (numberp (car o0))) o0 (list 0.0 0.0 0.0))
            r  (if x1 (list (- (/ (+ x1 x2) 2.0) (car o0)) (- (/ (+ y1 y2) 2.0) (cadr o0)) (- x2 x1) (- y2 y1))))
      (setq *sht:BoxCache* (cons (cons name r) *sht:BoxCache*))
      r)))

;; ћасштаб вписывани€ габарита bw x bh в графу w x h с зазором g (плоский Ч по другой стороне)
(defun sht:fit-k (bw bh w h g)
  (setq w (- w g g)
        h (- h g g))
  (cond ((and (> bw 1e-9) (> bh 1e-9)) (min (/ w bw) (/ h bh)))
        ((> bw 1e-9) (/ w bw))
        ((> bh 1e-9) (/ h bh))
        (t 1.0)))

;; ѕоставить слот w на лист s (ename entget handle слоты): блок или картинка. ¬озвращает ename.
(defun sht:sign-put (s w)
  (if (= (substr (nth 2 w) 1 2) "I:")
    (sht:sign-put-img s w (substr (nth 2 w) 3))
    (sht:sign-put-blk s w (substr (nth 2 w) 3) (if (= (car w) "SIGN") *sht:LaySign* *sht:LayFmt*))))

(defun sht:sign-put-blk (s w name lay / ed bx k lx ly sc ins en)
  (setq ed (cadr s)
        bx (sht:blk-box name)
        k  (if (and bx (= (nth 7 w) "1"))
             (sht:fit-k (nth 2 bx) (nth 3 bx) (nth 5 w) (nth 6 w)
                        (if (= (car w) "LOGO") *sht:LogoGap* *sht:SignGap*))
             1.0)
        lx (- (nth 3 w) (* k (if bx (car bx) 0.0)))
        ly (- (nth 4 w) (* k (if bx (cadr bx) 0.0)))
        sc (cond ((cdr (assoc 41 ed))) (1.0))
        ins (vla-InsertBlock (sht:ms) (vlax-3d-point (sht:sheet-pt ed lx ly)) name
                             (* k sc) (* k sc) (* k sc) (cond ((cdr (assoc 50 ed))) (0.0))))
  (vla-put-Layer ins lay)
  (setq en (vlax-vla-object->ename ins))
  (sht:sign-xd-set en (car w) (caddr s) (cadr w) lx ly k (strcat "B:" (cdr (assoc 2 (entget en)))))
  en)

;;  артинка-логотип: вписать в графу по сторонам картинки (вставка 1:1 -> ширина и высота -> масштаб)
(defun sht:sign-put-img (s w path / ed sc img iw ih kw hw lx ly en)
  (setq ed  (cadr s)
        sc  (cond ((cdr (assoc 41 ed))) (1.0))
        img (vlax-invoke (sht:ms) 'AddRaster path (sht:sheet-pt ed (nth 3 w) (nth 4 w)) 1.0 0.0)
        en  (vlax-vla-object->ename img)
        iw  (sht:tbl-get img 'ImageWidth)
        ih  (sht:tbl-get img 'ImageHeight))
  (if (not (and (numberp iw) (numberp ih) (> iw 0) (> ih 0)))
    (progn
      (entdel en)
      (setq en nil)
      (princ (strcat "\nSHEETS: у картинки не определилс€ размер: " path)))
    (progn
      (setq kw (min (- (nth 5 w) (* 2.0 *sht:LogoGap*)) (* (- (nth 6 w) (* 2.0 *sht:LogoGap*)) (/ (float iw) ih)))
            hw (* kw (/ (float ih) iw))
            lx (- (nth 3 w) (/ kw 2.0))
            ly (- (nth 4 w) (/ hw 2.0)))
      (sht:tbl-put img 'ScaleFactor (/ (* kw sc) iw))
      (if (not (equal (sht:tbl-get img 'ImageWidth) (* kw sc) (* 1e-6 kw sc)))
        (progn
          (sht:tbl-put img 'ImageWidth (* kw sc))
          (sht:tbl-put img 'ImageHeight (* hw sc))))
      (sht:tbl-put img 'Rotation (cond ((cdr (assoc 50 ed))) (0.0)))
      (sht:tbl-put img 'Origin (vlax-3d-point (sht:sheet-pt ed lx ly)))
      (vla-put-Layer img *sht:LayFmt*)
      (sht:sign-xd-set en "LOGO" (caddr s) 0 lx ly kw (strcat "I:" path))))
  en)

;; —лой подписей: нет Ч создать (есть Ч не трогать: заморозка / выключение Ч выбор пользовател€)
(defun sht:sign-layer ()
  (if (not (tblsearch "LAYER" *sht:LaySign*))
    (entmake (list '(0 . "LAYER") '(100 . "AcDbSymbolTableRecord") '(100 . "AcDbLayerTableRecord")
                   (cons 2 *sht:LaySign*) '(70 . 0) '(62 . 7) '(6 . "Continuous") '(370 . -3)))))

;; —лой заблокирован Ч разблокировать (возвращает им€, чтобы потом заблокировать обратно)
(defun sht:lay-unlock (name / en ed fl)
  (if (and (setq en (tblobjname "LAYER" name))
           (setq ed (entget en))
           (= 4 (logand 4 (setq fl (cond ((cdr (assoc 70 ed))) (0))))))
    (progn
      (entmod (sht:dxf-set ed 70 (logand fl (~ 4))))
      name)))

(defun sht:lay-lock (name / en ed)
  (if (setq en (tblobjname "LAYER" name))
    (progn
      (setq ed (entget en))
      (entmod (sht:dxf-set ed 70 (logior (cond ((cdr (assoc 70 ed))) (0)) 4))))))

;; Ћист дл€ сверки: (ename entget handle слоты)
(defun sht:sign-sheet (en cfg)
  (list en (entget en) (vla-get-Handle (vlax-ename->vla-object en))
        (sht:sign-want (sht:sheet-info en) (sht:attrs en) cfg)))

;; —верить подписи и логотип со штампами всех листов; force Ч всЄ заново.
;; ¬озвращает (поставлено убрано нет-блоков ошибки) или nil (ошибка Ч сообщение уже написано).
(defun sht:sign-sync (force / cfg lk r)
  (setq *sht:BoxCache* nil
        *sht:BlkReal*  nil
        *sht:SignMiss* nil
        cfg            (sht:sign-cfg (sht:set-read)))
  (if (sht:sign-on-p cfg) (sht:sign-layer))
  ;; заблокированные слои подписей, листа и текущий (на нЄм вставка рождаетс€) Ч на врем€ сверки открыть
  (setq lk (vl-remove nil (mapcar 'sht:lay-unlock (sht:uniq-ci (list *sht:LaySign* *sht:LayFmt* (getvar "CLAYER")))))
        r  (vl-catch-all-apply 'sht:sign-sync0 (list force cfg)))
  (foreach l lk (sht:lay-lock l))
  (if (vl-catch-all-error-p r)
    (progn
      (princ (strcat "\nSHEETS: подписи и логотип не сверены: " (vl-catch-all-error-message r)))
      nil)
    r))

(defun sht:sign-sync0 (force cfg / shs s w keep slot made del errs r)
  (setq made 0
        del  0
        shs  (mapcar '(lambda (en) (sht:sign-sheet en cfg)) (sht:sheets)))
  ;; что есть: на своЄм месте у своего листа и нужно листу Ч остаЄтс€ (по одному на графу), иначе Ч удалить
  (foreach o (sht:sign-objs)
    (setq s    (vl-some '(lambda (x) (if (= (caddr x) (nth 2 o)) x)) shs)
          w    (if s (vl-some '(lambda (x) (if (and (= (car x) (nth 1 o)) (= (cadr x) (nth 3 o))
                                                    (= (caddr x) (nth 7 o)))
                                                x))
                              (nth 3 s)))
          slot (if w (list (caddr s) (car w) (cadr w))))
    (if (and (not force) w (not (member slot keep)) (sht:sign-at-p o (cadr s)))
      (setq keep (cons slot keep))
      (if (not (vl-catch-all-error-p (vl-catch-all-apply 'entdel (list (car o)))))
        (setq del (1+ del)))))
  ;; чего нет Ч поставить
  (foreach s shs
    (foreach w (nth 3 s)
      (if (not (member (list (caddr s) (car w) (cadr w)) keep))
        (progn
          (setq r (vl-catch-all-apply 'sht:sign-put (list s w)))
          (cond
            ((vl-catch-all-error-p r)
             (setq r (strcat (if (= (car w) "LOGO") "Ћоготип" (strcat "ѕодпись (строка " (itoa (cadr w)) ")"))
                             " на листе " (sht:sheet-no (car s)) " не поставлен"
                             (if (= (car w) "LOGO") "" "а") ": " (vl-catch-all-error-message r)))
             (if (not (member r errs)) (setq errs (cons r errs))))
            (r (setq made (1+ made))))))))
  (list made del *sht:SignMiss* (reverse errs)))

;; —ообщение: all Ч и когда ничего не мен€лось
(defun sht:sign-msg (r all / chg)
  (setq chg (or (> (car r) 0) (> (cadr r) 0)))
  (if (or all chg)
    (princ (strcat "\nѕодписи и логотип: "
                   (if chg (strcat "поставлено " (itoa (car r)) ", убрано " (itoa (cadr r))) "всЄ на местах")
                   ".")))
  (if (and (caddr r) (or all chg))
    (princ (strcat "\n  Ќет в чертеже блока: " (sht:join (caddr r) ", ") " - не ставитс€ (SHEET_SIGN).")))
  (foreach e (cadddr r) (princ (strcat "\n  " e))))

;; јвтосверка (без ЂвсЄ занової), если подписи или логотип заданы. quiet Ч без сообщени€.
(defun sht:sign-auto (quiet / r)
  (if (and (not *sht:SignBusy*) (sht:sign-on-p (sht:sign-cfg (sht:set-read))))
    (progn
      (setq *sht:SignBusy* T
            r              (vl-catch-all-apply 'sht:sign-sync (list nil))
            *sht:SignBusy* nil)
      (cond
        ((vl-catch-all-error-p r)
         (princ (strcat "\nSHEETS: подписи и логотип не сверены: " (vl-catch-all-error-message r)))
         nil)
        (r
         (if (not quiet) (sht:sign-msg r nil))
         r)))))

;; Ќаблюдать за листами (вставки и фамилии NAME1-6), если подписи или логотип заданы:
;; лист сдвинули, повернули, фамилию помен€ли Ч флаг *sht:SignDirty* (сверка Ч в конце команды)
(defun sht:sign-watch ( / objs)
  (if *sht:RSign* (vlr-remove *sht:RSign*))
  (setq *sht:RSign* nil)
  (if (sht:sign-on-p (sht:sign-cfg (sht:set-read)))
    (foreach en (sht:sheets)
      (setq objs (cons (vlax-ename->vla-object en) objs))
      (foreach a (sht:att-objs en)
        (if (member (strcase (vla-get-TagString a)) *sht:NameTags*)
          (setq objs (cons a objs))))))
  (if objs
    (setq *sht:RSign* (vlr-object-reactor objs "SHEETS" '((:vlr-modified . sht:r-sign-mod)))))
  (length objs))

(defun sht:r-sign-mod (obj r args)
  (setq *sht:SignDirty* T)
  (princ))

;; --- окно Ђѕодписи и логотипї ---------------------------------------------------
;; ѕеременные окна (локальные в c:SHEET_SIGN): sht:gnames Ч (("»ванов" . листов) Е), sht:gmap Ч
;; фамили€ -> блок, sht:gblks Ч блоки дл€ выбора, sht:gfiles Ч (блок . файл) из файлов DWG (загруз€тс€
;; после Ђ–асставитьї), sht:gsel Ч выбранна€ строка, sht:gfit Ч "1" / "0"; логотип: sht:lkind
;; "N" / "B" / "I", sht:lblk, sht:lpath, sht:lfit.

;; ‘амилии на листах форм 3, 4, 5 (графа 11, строки 1-6): (("»ванов" . листов) Е), по строкам, затем по листам
(defun sht:sign-names (ens / al i nm res n out)
  (foreach en ens
    (if (sht:sign-rows (caddr (sht:sheet-info en)))
      (setq al (cons (sht:attrs en) al))))
  (setq al (reverse al)
        i  1)
  (repeat 6
    (foreach a al
      (setq nm (sht:trim (cdr (assoc (strcat "NAME" (itoa i)) a))))
      (if (and (/= nm "") (not (member nm res)))
        (setq res (append res (list nm)))))
    (setq i (1+ i)))
  (foreach nm res
    (setq n 0)
    (foreach a al
      (if (vl-some '(lambda (k) (= (sht:trim (cdr (assoc k a))) nm)) *sht:NameTags*)
        (setq n (1+ n))))
    (setq out (append out (list (cons nm n)))))
  out)

;; Ѕлоки чертежа дл€ выбора: без листов SHT_*, анонимных, внешних ссылок и их блоков, Ђ_Еї
(defun sht:user-blocks ( / r n fl res)
  (setq r (tblnext "BLOCK" T))
  (while r
    (setq n  (cdr (assoc 2 r))
          fl (cond ((cdr (assoc 70 r))) (0)))
    (if (not (or (wcmatch n "`**,_*,SHT_*,*|*") (/= 0 (logand fl 21))))
      (setq res (cons n res)))
    (setq r (tblnext "BLOCK")))
  (vl-sort res '<))

;; Ѕлок дл€ фамилии: в имени блока есть фамили€ (самое длинное слово без точек, без учЄта регистра);
;; несколько Ч с Ђподпї в имени; нет Ч ""
(defun sht:sign-guess (nm blks / w hits)
  (setq w "")
  (foreach x (sht:split (sht:trim nm) " ")
    (if (and (not (vl-string-search "." x)) (> (strlen x) (strlen w))) (setq w x)))
  (setq w (sht:lc w))
  (if (> (strlen w) 1)
    (foreach b blks
      (if (vl-string-search w (sht:lc b)) (setq hits (append hits (list b))))))
  (cond ((null hits) "")
        ((vl-some '(lambda (b) (if (vl-string-search "подп" (sht:lc b)) b)) hits))
        (t (car hits))))

;; Ќомер блока b в списке выбора (0 Ч Ђнетї)
(defun sht:pos1 (b lst / i)
  (if (and b (setq i (vl-position b lst))) (1+ i) 0))

(defun sht:sign-line (p / b)
  (setq b (cond ((cdr (assoc (car p) sht:gmap))) ("")))
  (strcat (car p) "\t" (if (= b "") "(без подписи)" b) (if (assoc b sht:gfiles) " (из файла)" "")
          "\t" (itoa (cdr p)) (if (= (cdr p) 1) " лист" " листов")))

(defun sht:sign-info ( / n)
  (setq n 0)
  (foreach p sht:gnames
    (if (/= (cond ((cdr (assoc (car p) sht:gmap))) ("")) "") (setq n (1+ n))))
  (if sht:gnames
    (strcat "‘амилий в штампах: " (itoa (length sht:gnames)) ", с подписью: " (itoa n)
            ". ¬ыберите фамилию в списке, затем блок подписи.")
    "¬ штампах (графа 11) фамилий нет - впишите их: SHEET_DATA (данные комплекта)."))

;; «аполнить окно по переменным (список, выбор блоков, логотип)
;; s0.14.3: выбранна€ строка списка фамилий (sht:gsel) или nil Ч без nth
(defun sht:sign-cur ( / i r)
  (if (not (numberp sht:gsel)) (setq sht:gsel 0))
  (setq i 0)
  (foreach q sht:gnames
    (if (= i sht:gsel) (setq r q))
    (setq i (1+ i)))
  (if (and r (listp r)) r))

(defun sht:sign-fill ( / p)
  (setq *sht:Step* "окно: список фамилий")
  (start_list "sht_GList")
  (foreach q sht:gnames
    (setq *sht:Step* (strcat "окно: строка списка " (vl-prin1-to-string q)))
    (add_list (sht:sign-line q)))
  (end_list)
  (setq *sht:Step* "окно: выбранна€ фамили€")
  (setq p (sht:sign-cur))
  (setq *sht:Step* "окно: список блоков подписи")
  (sht:set-popup "sht_GBlk" (cons "(без подписи)" sht:gblks)
                 (if p (sht:pos1 (cdr (assoc (car p) sht:gmap)) sht:gblks) 0))
  (setq *sht:Step* "окно: доступность выбора блока")
  (if p (set_tile "sht_GList" (itoa sht:gsel)))
  (mode_tile "sht_GBlk" (if p 0 1))
  (mode_tile "sht_GFile" (if p 0 1))
  (setq *sht:Step* "окно: строка сведений")
  (set_tile "sht_GInfo" (sht:sign-info))
  (setq *sht:Step* "окно: список блоков логотипа")
  (sht:set-popup "sht_LgBlk" (cons "(не выбран)" sht:gblks) (sht:pos1 sht:lblk sht:gblks))
  (setq *sht:Step* "окно: логотип - путь и вид")
  (set_tile "sht_LgPath" sht:lpath)
  (set_tile "sht_LgKind" (cond ((= sht:lkind "B") "sht_LgKindB") ((= sht:lkind "I") "sht_LgKindI") (t "sht_LgKindN")))
  (setq *sht:Step* "окно: доступность полей логотипа")
  (sht:sign-lmodes))

;; ƒоступность полей логотипа по виду
(defun sht:sign-lmodes ()
  (mode_tile "sht_LgBlk" (if (= sht:lkind "B") 0 1))
  (mode_tile "sht_LgBFile" (if (= sht:lkind "B") 0 1))
  (mode_tile "sht_LgFit" (if (= sht:lkind "B") 0 1))
  (mode_tile "sht_LgPath" (if (= sht:lkind "I") 0 1))
  (mode_tile "sht_LgBrowse" (if (= sht:lkind "I") 0 1)))

(defun sht:sign-init ()
  (sht:sign-fill)
  (setq *sht:Step* "окно: переключатели и примечание")
  (set_tile "sht_GFit" (if (= sht:gfit "0") "sht_GFit0" "sht_GFit1"))
  (set_tile "sht_LgFit" (if (= sht:lfit "0") "sht_LgFit0" "sht_LgFit1"))
  (set_tile "sht_GNote" (strcat "ѕодписи - слой " *sht:LaySign* " (заморозить - печать без подписей), логотип - слой "
                                *sht:LayFmt* ". ƒвигаютс€ вместе с листом, мен€ютс€ с фамилией."))
  (setq *sht:Step* "окно: действи€ кнопок")
  (action_tile "sht_GList" "(sht:sign-pick $value)")
  (action_tile "sht_GBlk" "(sht:sign-blk $value)")
  (action_tile "sht_GFile" "(sht:sign-file \"G\")")
  (action_tile "sht_GFit" "(setq sht:gfit (if (= $value \"sht_GFit0\") \"0\" \"1\"))")
  (action_tile "sht_LgKind" "(sht:sign-lkind $value)")
  (action_tile "sht_LgBlk" "(sht:sign-lblk $value)")
  (action_tile "sht_LgBFile" "(sht:sign-file \"L\")")
  (action_tile "sht_LgPath" "(setq sht:lpath (sht:trim $value))")
  (action_tile "sht_LgBrowse" "(sht:sign-browse)")
  (action_tile "sht_LgFit" "(setq sht:lfit (if (= $value \"sht_LgFit0\") \"0\" \"1\"))")
  (action_tile "accept" "(sht:sign-ok)"))

(defun sht:sign-pick (v)
  (setq sht:gsel (atoi v))
  (sht:sign-fill))

(defun sht:sign-blk (v / p i)
  (setq i (atoi v))
  (if (setq p (sht:sign-cur))
    (setq sht:gmap (sht:alist-put sht:gmap (car p) (if (> i 0) (nth (1- i) sht:gblks) ""))))
  (sht:sign-fill))

(defun sht:sign-lkind (v)
  (setq sht:lkind (cond ((= v "sht_LgKindB") "B") ((= v "sht_LgKindI") "I") (t "N")))
  (sht:sign-lmodes))

(defun sht:sign-lblk (v / i)
  (setq i       (atoi v)
        sht:lblk (if (> i 0) (nth (1- i) sht:gblks) "")))

;; Ђ»з файла DWG...ї: блок загрузитс€ из файла после Ђ–асставитьї (им€ блока Ч им€ файла);
;; target "G" Ч подпись выбранной фамилии, "L" Ч логотип
(defun sht:sign-file (target / f b p)
  (setq sht:lpath (sht:trim (get_tile "sht_LgPath"))
        f         (getfiled "Ѕлок из файла DWG" "" "dwg" 0))
  (if f
    (progn
      (setq b (vl-filename-base f))
      (if (not (member b sht:gblks))
        (setq sht:gblks  (vl-sort (cons b sht:gblks) '<)
              sht:gfiles (cons (cons b f) sht:gfiles)))
      (cond
        ((= target "L") (setq sht:lkind "B" sht:lblk b))
        ((setq p (sht:sign-cur))
         (setq sht:gmap (sht:alist-put sht:gmap (car p) b))))
      (sht:sign-fill))))

;; Ђ...ї картинки логотипа
(defun sht:sign-browse ( / f)
  (setq f (getfiled "Ћоготип - картинка" (sht:trim (get_tile "sht_LgPath")) *sht:ImgExt* 0))
  (if f
    (progn
      (setq sht:lpath f
            sht:lkind "I")
      (sht:sign-fill))))

(defun sht:sign-ok ()
  (setq sht:lpath (sht:trim (get_tile "sht_LgPath")))
  (cond
    ((and (= sht:lkind "B") (= sht:lblk ""))
     (set_tile "error" "Ћоготип: выберите блок (или ЂЌетї)."))
    ((and (= sht:lkind "I") (= sht:lpath ""))
     (set_tile "error" "Ћоготип: укажите файл картинки (или ЂЌетї)."))
    ((and (= sht:lkind "I") (not (findfile sht:lpath)))
     (set_tile "error" (strcat "Ќет файла картинки: " sht:lpath)))
    (t (done_dialog 1))))

(defun sht:sign-dialog ( / dcl_id dclFile ret)
  (setq ret 0)
  (setq *sht:Step* "окно: загрузка DCL")
  (if (sht:dlg-load)
    (if (new_dialog "sht_sign" dcl_id)
      (progn
        (setq *sht:Step* "окно: заполнение"
              *sht:SignErr* (vl-catch-all-apply 'sht:sign-init nil))
        (if (vl-catch-all-error-p *sht:SignErr*)
          (progn                                   ; s0.14.2: окно закрыть, ошибку Ч в команду
            (setq *sht:SignErr* (vl-catch-all-error-message *sht:SignErr*))
            (vl-catch-all-apply '(lambda () (done_dialog 0)) nil)
            (vl-catch-all-apply '(lambda () (start_dialog)) nil)
            (setq ret -1))
          (progn
            (setq *sht:SignErr* nil
                  *sht:Step*    "окно открыто")
            (setq ret (start_dialog))
            (setq *sht:Step* "окно закрыто"))))
      (princ "\nSHEETS: не удалось открыть окно.")))
  (sht:dlg-cleanup)
  ret)

;; «агрузить описание блока из файла DWG (им€ Ч им€ файла): -INSERT им€=файл и отмена на точке вставки
;; (в чертеже ничего не вставл€етс€; не вышло Ч ActiveX). Ѕлок с таким именем уже есть Ч вз€ть его.
;; ¬озвращает им€ или nil.
(defun sht:blk-from-file (f / b ce ins)
  (setq b (vl-filename-base f))
  ;; s0.14.3: сначала ActiveX Ч вставка из файла и сразу удалить (остаЄтс€ описание блока)
  (if (not (tblsearch "BLOCK" b))
    (progn
      (setq ins (vl-catch-all-apply 'vla-InsertBlock (list (sht:ms) (vlax-3d-point 0.0 0.0 0.0) f 1.0 1.0 1.0 0.0)))
      (if (not (vl-catch-all-error-p ins))
        (vl-catch-all-apply 'entdel (list (vlax-vla-object->ename ins))))))
  ;; запасной путь Ч -INSERT им€=файл и отмена на точке вставки
  (if (not (tblsearch "BLOCK" b))
    (progn
      (setq ce (getvar "CMDECHO"))
      (setvar "CMDECHO" 0)
      (command "_.-INSERT" (strcat b "=" f))
      (command)
      (setvar "CMDECHO" ce)))
  (if (tblsearch "BLOCK" b)
    b
    (progn
      (princ (strcat "\nSHEETS: блок из файла не загружен: " f))
      nil)))

;; Ќастройки окна Ч в словарь чертежа (если помен€лись). ‘амилии Ч только те, что сейчас в штампах
;; (прежние записи убираютс€: иначе Ђподписи заданыї оставалось бы и без фамилий на листах).
(defun sht:sign-save ( / sdat new)
  (setq sdat (sht:set-read))
  (foreach p sdat
    (if (not (and (> (strlen (car p)) 6) (= (substr (car p) 1 6) "@SIGN:")))
      (setq new (append new (list p)))))
  (foreach p sht:gnames
    (setq new (sht:alist-put new (strcat "@SIGN:" (car p)) (cond ((cdr (assoc (car p) sht:gmap))) ("")))))
  (setq new (sht:alist-put new "@SIGNFIT" sht:gfit)
        new (sht:alist-put new "@LOGO" (cond ((= sht:lkind "B") (strcat "B:" sht:lblk))
                                             ((= sht:lkind "I") (strcat "I:" sht:lpath))
                                             (t "")))
        new (sht:alist-put new "@LOGOFIT" sht:lfit))
  (if (not (equal new sdat)) (sht:set-write new)))

;; ѕодписи и логотип: какой блок у какой фамилии, логотип; Ђ–асставитьї Ч на всех листах заново
;; s0.14.1: команда Ч обЄртка: ошибка перехватываетс€, в строку Ч шаг (*sht:Step*) и текст ошибки,
;; отметка отмены закрываетс€. ѕеременные окна Ч локальные здесь (окно и sht:sign-cmd вид€т их).
(defun c:SHEET_SIGN ( / res sht:undo
                        sht:gnames sht:gmap sht:gblks sht:gfiles sht:gsel sht:gfit
                        sht:lkind sht:lblk sht:lpath sht:lfit)
  (setq *sht:Step* "начало"
        res        (vl-catch-all-apply 'sht:sign-cmd nil))
  (if (vl-catch-all-error-p res)
    (progn
      (if sht:undo (vl-catch-all-apply 'vla-EndUndoMark (list (sht:doc))))
      (princ (strcat "\nSHEETS: SHEET_SIGN - сбой на шаге Ђ" (cond (*sht:Step*) ("?")) "ї: "
                     (vl-catch-all-error-message res) ". ѕришлите эту строку разработчику."))))
  (princ))

(defun sht:sign-cmd ( / doc sdat cfg lg ret r)
  (setq *sht:Step* "подготовка (стиль, слои, блоки листов)")
  (setq doc  (sht:doc)
        sdat (sht:prepare))
  (setq *sht:Step* "двойной щелчок (UNDEFINE EATTEDIT)")
  (sht:dblclick-setup)
  (setq *sht:Step* "настройки подписей из чертежа")
  (setq cfg        (sht:sign-cfg sdat))
  (setq *sht:Step* "фамилии в штампах")
  (setq sht:gnames (sht:sign-names (sht:sheets)))
  (setq *sht:Step* "блоки чертежа")
  (setq sht:gblks  (sht:user-blocks))
  (setq *sht:Step* "разбор настроек")
  (setq sht:gmap   (car cfg)
        sht:gsel   0
        sht:gfit   (cadr cfg)
        sht:lfit   (cadddr cfg)
        lg         (caddr cfg))
  (setq *sht:Step* "угадать блоки подписей")
  ;; фамили€ без записи Ч блок угадать по имени (в окне видно, можно помен€ть)
  (foreach p sht:gnames
    (if (not (assoc (car p) sht:gmap))
      (setq sht:gmap (sht:alist-put sht:gmap (car p) (sht:sign-guess (car p) sht:gblks)))))
  (cond
    ((= (substr lg 1 2) "B:") (setq sht:lkind "B" sht:lblk (substr lg 3) sht:lpath ""))
    ((= (substr lg 1 2) "I:") (setq sht:lkind "I" sht:lblk "" sht:lpath (substr lg 3)))
    (t (setq sht:lkind "N" sht:lblk "" sht:lpath "")))
  (setq *sht:Step* "окно")
  (setq ret (sht:sign-dialog))
  (if (= ret -1)
    (princ (strcat "\nSHEETS: SHEET_SIGN - сбой на шаге Ђ" (cond (*sht:Step*) ("?")) "ї: "
                   (cond (*sht:SignErr*) ("?")) ". ќкно закрыто. ѕришлите эту строку разработчику.")))
  (if (= ret 1)
    (progn
      (setq *sht:Step* "блоки из файлов")
      (vla-StartUndoMark doc)
      (setq sht:undo T)
      ;; блоки из файлов Ч только выбранные
      (foreach f sht:gfiles
        (if (or (vl-some '(lambda (p) (= (cdr p) (car f))) sht:gmap)
                (and (= sht:lkind "B") (= sht:lblk (car f))))
          (sht:blk-from-file (cdr f))))
      (setq *sht:Step* "запись настроек")
      (sht:sign-save)
      (setq *sht:Step* "расстановка на листах")
      (setq r (sht:sign-sync T))
      (vla-EndUndoMark doc)
      (setq sht:undo nil)
      (setq *sht:Step* "сообщение")
      (if r (sht:sign-msg r T)))
    (if (/= ret -1) (princ "\nѕодписи и логотип: без изменений.")))
  (setq *sht:Step* "наблюдение за листами")
  (sht:watch)
  (setq *sht:Step* "готово")
  (princ))


;;; --------------------------------------------------------------------------
;;;  17. ќ Ќќ ¬—≈’  ќћјЌƒ: SHT (s0.8) и ј¬“ќ«ј√–”« ј
;;;   нопка закрывает окно кодом (done_dialog), команда запускаетс€ после закрыти€:
;;;  из открытого окна command и выбор в чертеже нельз€. Ђ¬кл./выкл.ї Ч окно открываетс€ снова.
;;;  јвтозагрузка: строка в acaddoc.lsp (грузитс€ при открытии каждого чертежа):
;;;    (if (and (/= (getenv "SHT_AutoLoad") "0") (findfile "SHEETS.lsp")) (load "SHEETS.lsp" ""))
;;;  + папка SHEETS.lsp Ч в пути поддержки и в доверенных (TRUSTEDPATHS);
;;;  выключение Ч SHT_AutoLoad = "0" (строка в acaddoc.lsp остаЄтс€, ничего не делает).
;;; --------------------------------------------------------------------------

(setq *sht:AlTag* ";; SHEETS autoload (SHT)")

;; ѕапка без Ђ\ї в конце, дл€ сравнени€ Ч строчными
(defun sht:dir-key (d)
  (setq d (sht:trim d))
  (while (and (> (strlen d) 0) (member (substr d (strlen d)) '("\\" "/")))
    (setq d (substr d 1 (1- (strlen d)))))
  (sht:lc (vl-string-translate "/" "\\" d)))

;; ≈сть ли папка d в списке путей Ђa;b;cї
(defun sht:path-has (paths d / k)
  (setq k (sht:dir-key d))
  (vl-some '(lambda (x) (= (sht:dir-key x) k)) (sht:split (cond (paths) ("")) ";")))

;; ƒобавить папку в список путей (если еЄ там нет)
(defun sht:path-add (paths d / s)
  (setq s (sht:trim (cond (paths) (""))))
  (cond
    ((sht:path-has s d) s)
    ((= s "") d)
    ((= (substr s (strlen s)) ";") (strcat s d))
    (t (strcat s ";" d))))

;; ≈сть ли в файле строка автозагрузки SHEETS
(defun sht:al-has (fn / f s r)
  (if (and fn (findfile fn) (setq f (open fn "r")))
    (progn
      (while (and (not r) (setq s (read-line f)))
        (if (vl-string-search "SHEETS autoload" s) (setq r T)))
      (close f)))
  r)

;; —осто€ние автозагрузки: (код файл): 0 Ч не настроена, 1 Ч выключена, 2 Ч включена,
;; 3 Ч включена, но SHEETS.lsp не находитс€ в пут€х поддержки
(defun sht:al-state ( / fn)
  (setq fn (findfile "acaddoc.lsp"))
  (cond
    ((not (sht:al-has fn)) (list 0 fn))
    ((= (getenv "SHT_AutoLoad") "0") (list 1 fn))
    ((not (findfile "SHEETS.lsp")) (list 3 fn))
    (t (list 2 fn))))

(defun sht:al-text ( / st)
  (setq st (sht:al-state))
  (cond
    ((= (car st) 2) (strcat "јвтозагрузка при открытии чертежа: включена (" (cadr st) ")"))
    ((= (car st) 1) "јвтозагрузка при открытии чертежа: выключена")
    ((= (car st) 3) "јвтозагрузка: включена, но SHEETS.lsp не найден в пут€х - включите заново")
    (t "јвтозагрузка при открытии чертежа: не настроена")))

;; ѕуть поддержки AutoCAD (Ќастройка - ‘айлы): прочитать / записать; nil Ч не вышло
(defun sht:support-files ( / r)
  (setq r (vl-catch-all-apply 'vla-get-Files (list (vla-get-Preferences (vlax-get-acad-object)))))
  (if (vl-catch-all-error-p r) nil r))

;; ¬ключить автозагрузку. ¬озвращает T, если всЄ записано.
(defun sht:autoload-on ( / lsp dir nm files sp r tp fn adir f ok)
  (setq lsp (findfile "SHEETS.lsp"))
  (if (not lsp)
    (setq lsp (getfiled "√де лежит SHEETS.lsp (дл€ автозагрузки)" "" "lsp" 0)))
  (cond
    ((not lsp)
     (princ "\nјвтозагрузка: файл SHEETS.lsp не выбран - ничего не изменено.")
     nil)
    (t
     (setq dir (vl-filename-directory lsp)
           nm  (strcat (vl-filename-base lsp) ".lsp"))
     ;; 1. ѕапка Ч в путь поддержки (чтобы (load "SHEETS.lsp") нашЄл файл)
     (if (setq files (sht:support-files))
       (progn
         (setq sp (vl-catch-all-apply 'vla-get-SupportPath (list files)))
         (if (and (not (vl-catch-all-error-p sp)) (not (sht:path-has sp dir)))
           (progn
             (setq r (vl-catch-all-apply 'vla-put-SupportPath (list files (sht:path-add sp dir))))
             (if (vl-catch-all-error-p r)
               (princ (strcat "\nјвтозагрузка: папку не удалось добавить в путь поддержки: " dir))
               (princ (strcat "\nѕапка добавлена в путь поддержки: " dir)))))))
     ;; 2. ‘айл acaddoc.lsp: тот, что AutoCAD уже находит, иначе Ч новый в папке Support пользовател€
     (setq fn (findfile "acaddoc.lsp"))
     (if (not fn)
       (progn
         (setq adir (strcat (cond ((getvar "ROAMABLEROOTPREFIX")) ("")) "Support"))
         (if (not (vl-file-directory-p adir)) (setq adir dir))
         (setq fn (strcat (vl-string-right-trim "\\" adir) "\\acaddoc.lsp"))))
     ;; 3. ќбе папки Ч в доверенные (без вопроса Ђ«агрузить файл?ї при каждом открытии)
     (setq tp (getvar "TRUSTEDPATHS"))
     (foreach d (list dir (vl-filename-directory fn))
       (setq tp (sht:path-add tp d)))
     (if (/= tp (getvar "TRUSTEDPATHS"))
       (if (vl-catch-all-error-p (vl-catch-all-apply 'setvar (list "TRUSTEDPATHS" tp)))
         (princ "\nјвтозагрузка: доверенные папки (TRUSTEDPATHS) не изменены - AutoCAD может спрашивать Ђ«агрузить?ї.")))
     ;; 4. —трока автозагрузки (один раз; только латиница Ч кодировка файла не важна)
     (cond
       ((sht:al-has fn) (setq ok T))
       ((setq f (open fn "a"))
        (write-line "" f)                         ; если последн€€ строка без перевода строки
        (write-line *sht:AlTag* f)
        (write-line (strcat (chr 40) "if " (chr 40) "and " (chr 40) "/= " (chr 40) "getenv \"SHT_AutoLoad\""
                            (chr 41) " \"0\"" (chr 41) " " (chr 40) "findfile \"" nm "\"" (chr 41) (chr 41)
                            " " (chr 40) "load \"" nm "\" \"\"" (chr 41) (chr 41)) f)
        (close f)
        (setq ok T))
       (t (princ (strcat "\nјвтозагрузка: не удалось записать файл " fn))))
     (if ok
       (progn
         (setenv "SHT_AutoLoad" "1")
         (princ (strcat "\nјвтозагрузка включена: " fn
                        " - SHEETS будет загружатьс€ при открытии каждого чертежа (в этой версии AutoCAD)."))))
     ok)))

(defun sht:autoload-off ()
  (setenv "SHT_AutoLoad" "0")
  (princ "\nјвтозагрузка выключена (строка в acaddoc.lsp осталась и ничего не делает; включить - SHT, Ђ¬кл./выкл.ї)."))

(defun sht:autoload-toggle ()
  (if (= (car (sht:al-state)) 2) (sht:autoload-off) (sht:autoload-on)))

;; —ведени€ о чертеже дл€ окна: (строка1 строка2)
(defun sht:main-info (en / shs nn sdat s1 s2)
  (setq shs  (sht:sheets)
        sdat (sht:set-read)
        nn   0)
  (foreach q shs
    (if (= (sht:trim (cdr (assoc "SHEET" (sht:attrs q)))) "") (setq nn (1+ nn))))
  (setq s1 (strcat "Ћистов SHEETS: " (itoa (length shs))
                   (if (> nn 0) (strcat " (без номера: " (itoa nn) ")") "")
                   (if en
                     (strcat ". ¬ыбран лист "
                             (if (= (setq s2 (sht:trim (cdr (assoc "SHEET" (sht:attrs en))))) "") "без номера" s2))
                     ""))
        s2 (strcat "¬едомость листов: " (if (sht:kind-tables "LIST") "есть" "нет")
                   ". ¬едомость спецификаций: " (if (sht:kind-tables "SPEC") "есть" "нет")
                   ". —сылочных: " (if (sht:kind-tables "REFS") "есть" "нет")
                   ". ѕодписи и логотип: " (if (sht:sign-on-p (sht:sign-cfg sdat)) "заданы" "нет") "."))
  (list s1 s2))

(defun sht:main-init (en / inf)
  (setq inf (sht:main-info en))
  (set_tile "sht_MInfo1" (car inf))
  (set_tile "sht_MInfo2" (cadr inf))
  (set_tile "sht_MDblTx" (if (= (getenv "SHT_DblClick") "0")
                           "ƒвойной щелчок по листу: обычный редактор атрибутов"
                           "ƒвойной щелчок по листу: окно ЂЋистї"))
  (set_tile "sht_MAutoTx" (sht:al-text))
  (set_tile "sht_MEdit" (if en "»зменить выбранный лист..." "»зменить лист <"))
  (set_tile "sht_MStamp" (if en "¬се пол€ штампа (выбранный лист)..." "¬се пол€ штампа <"))
  (foreach p '(("sht_MNew" . 2) ("sht_MEdit" . 3) ("sht_MData" . 4) ("sht_MUpd" . 5)
               ("sht_MList" . 6) ("sht_MSpec" . 7) ("sht_MSign" . 8) ("sht_MPlot" . 9)
               ("sht_MDbl" . 10) ("sht_MAuto" . 11) ("sht_MProbe" . 12) ("sht_MRefs" . 13)
               ("sht_MSide" . 14) ("sht_MStamp" . 15) ("sht_MSpds" . 16))
    (action_tile (car p) (strcat (chr 40) "done_dialog " (itoa (cdr p)) (chr 41)))))

(defun sht:main-dialog (en / dcl_id dclFile ret)
  (setq ret 0)
  (if (sht:dlg-load)
    (if (new_dialog "sht_main" dcl_id)
      (progn
        (sht:main-init en)
        (setq ret (start_dialog)))
      (princ "\nSHEETS: не удалось открыть окно.")))
  (sht:dlg-cleanup)
  ret)

;; SHT Ч окно всех команд SHEETS. Ћист, выбранный до команды, Ч дл€ Ђ»зменить листї.
(defun c:SHT ( / ss en ret again)
  (sht:dblclick-setup)
  (if (and (setq ss (ssget "_I")) (sht:sheet-p (ssname ss 0)))
    (setq en (ssname ss 0)))
  (setq again T)
  (while again
    (setq again nil
          ret   (sht:main-dialog (if (and en (entget en)) en)))
    (cond
      ((= ret 2) (c:SHEET_NEW))
      ((= ret 3)
       (if (and en (entget en))
         (progn
           (sssetfirst nil nil)
           (sht:edit-sheet en)
           (sht:watch))
         (c:SHEET_EDIT)))
      ((= ret 4) (c:SHEET_DATA))
      ((= ret 5) (c:SHEET_UPDATE))
      ((= ret 6) (c:SHEET_LIST))
      ((= ret 7) (c:SHEET_SPEC))
      ((= ret 8) (c:SHEET_SIGN))
      ((= ret 9) (c:SHEET_PLOT))
      ((= ret 10) (c:SHEET_DBLCLICK) (setq again T))
      ((= ret 11) (sht:autoload-toggle) (setq again T))
      ((= ret 12) (c:SHEET_PROBE))
      ((= ret 13) (c:SHEET_REFS))
      ((= ret 14) (c:SHEET_SIDE))
      ((= ret 16) (c:SHEET_FROM_SPDS))
      ((= ret 15)
       (if (and en (entget en))
         (progn
           (sssetfirst nil nil)
           (sht:fw-edit en 'STAMP)
           (sht:watch))
         (c:SHEET_STAMP)))))
  (princ))



;;; --------------------------------------------------------------------------
;;;  18. ѕ≈–≈¬ќƒ Ћ»—“ќ¬ —ѕƒ— ¬ SHEETS (s0.12): SHEET_FROM_SPDS
;;;  –амка —ѕƒ— (объект SPDSFORMAT) хранит пол€ парами 301 Ђим€ пол€ї -> 300 / 40 / 90 / 290 Ђзначениеї.
;;;  —оответствие полей Ч по заполненным рамкам јртЄма (формы 3, 4, 5, 6, боковой штамп; 2026-10-06).
;;;  ѕодписи —ѕƒ—: строка 1 Ч нижн€€; у SHEETS ROLE1 Ч верхн€€. »зменени€: у —ѕƒ— и SHEETS 1 Ч нижн€€.
;;;  Ќа месте рамки Ч лист SHEETS той же формы, формата, ориентации и масштаба (левый нижний угол);
;;;  стара€ рамка Ч на выключенный слой *sht:SpdsLay* (решение јртЄма); переведЄнные повторно не берутс€.
;;; --------------------------------------------------------------------------

(setq *sht:SpdsLay* "0000_—ѕƒ—_старые")

;; ѕодписи (формы 3, 4 Ч строки 1-6, форма 5 Ч 1-5): должность, фамили€, дата
(setq *sht:SpdsSign*
  '(("Add.text5" . "ROLE1") ("Author" . "NAME1") ("Author(date)" . "DATE1")
    ("Add.text6" . "ROLE2") ("Control" . "NAME2") ("Control(date)" . "DATE2")
    ("Add.text" . "ROLE3") ("Add.subject" . "NAME3") ("Add.subject(date)" . "DATE3")
    ("Add.text2" . "ROLE4") ("Add.subject2" . "NAME4") ("Add.subject2(date)" . "DATE4")
    ("Add.text3" . "ROLE5") ("Add.subject3" . "NAME5") ("Add.subject3(date)" . "DATE5")
    ("Add.text4" . "ROLE6") ("Add.subject4" . "NAME6") ("Add.subject4(date)" . "DATE6")))

;; Ѕоковой штамп: Ђ—огласованої Ч 4 столбца (должность, фамили€, подпись, дата); подпись (Name 3, 4) Ч нет
(setq *sht:SpdsSide*
  '(("Original#" . "INV") ("Instead#" . "VZAM")
    ("Role1" . "SOGL1R") ("Name 1" . "SOGL1N") ("Name 5" . "SOGL1D")
    ("Role2" . "SOGL2R") ("Name 2" . "SOGL2N") ("Name 6" . "SOGL2D")))

;; ѕол€ по формам (ЂЋистї формы 4 Ч раньше ЂSheetї: пустое значение не затирает непустое)
(setq *sht:SpdsForm*
  '(("3" ("Designation" . "SHIFR") ("ComplexName" . "OBJECT") ("DrawingName1" . "BUILDING")
         ("Drawing type" . "TITLE") ("Stage" . "STAGE") ("Sheet" . "SHEET") ("Enterprise" . "ORG"))
    ("4" ("Designation" . "OBOZN") ("ComplexName" . "TITLE") ("Drawing type" . "MATER") ("Stage" . "STAGE")
         ("ћасса" . "MASS") ("ћасштаб" . "SCALE") ("Ћист" . "SHEET") ("Sheet" . "SHEET") ("Enterprise" . "ORG"))
    ("5" ("Designation" . "OBOZN") ("DrawingName1" . "TITLE") ("Stage" . "STAGE") ("Sheet" . "SHEET")
         ("Enterprise" . "ORG"))
    ("6" ("Designation" . "SHIFR") ("Sheet" . "SHEET"))))

;; —троки изменений: поле —ѕƒ— + номер строки -> C<строка><поле>
(setq *sht:SpdsChg*
  '(("ChangeNr" . "IZM") ("ChangeSector" . "KOL") ("ChangeSheet" . "LST") ("ChangeDoc" . "DOC")
    ("ChangeDate" . "DAT")))

;; ѕол€ —ѕƒ—, которые не перенос€тс€ и не попадают в отчЄт (служебные, подписи, ЂЋистовї Ч сам)
(setq *sht:SpdsSkip*
  '("Name" "Info" "Scale" "Format" "DimScale" "Autonumerated" "First sheet" "Show zones" "Extended view"
    "Zone" "idTemplate" "Orientation" "Multiplicity" "Std version" "GOST2013.5mm" "Text style"
    "ObliqueByStyle" "XScaleByStyle" "PaperBound" "OriginX" "OriginY" "SheetCount"))

(defun sht:spds-skip-p (k)
  (or (member k *sht:SpdsSkip*)
      (vl-string-search "(sign)" k)
      (= (substr k 1 10) "ChangeSign")
      (= (substr k 1 9) "Sign&date")))

;; ѕол€ рамки: (("им€" . значение) Е) в пор€дке записи
(defun sht:spds-data (ed / key res)
  (foreach g ed
    (cond ((= (car g) 301) (setq key (cdr g)))
          ((and key (member (car g) '(1 40 70 90 290 300)))
           (setq res (cons (cons key (cdr g)) res)
                 key nil))))
  (reverse res))

(defun sht:spds-str (v) (if (= (type v) 'STR) v ""))

;; ‘орма листа SHEETS по набору полей рамки; без пол€ Ђ»нв. є подл.ї Ч без бокового штампа ("N")
(defun sht:spds-form (dat / k f)
  (setq k (mapcar 'car dat)
        f (cond ((or (member "ћасса" k) (member "ћасштаб" k)) "4")
                ((not (member "Author" k)) "6")
                ((or (and (member "ChangeNr3" k) (not (member "ChangeNr1" k)))
                     (and (member "Add.text3" k) (not (member "Add.text4" k))))
                 "5")
                (t "3")))
  (if (member "Original#" k) f (strcat f "N")))

;; Ќомера строк изменений рамки по возрастанию (у формы 5 —ѕƒ— Ч 3, 4; у формы 6 Ч 1, 2)
(defun sht:spds-chg-idx (dat / res k s)
  (foreach p dat
    (setq k (car p))
    (foreach c *sht:SpdsChg*
      (if (and (> (strlen k) (strlen (car c)))
               (= (substr k 1 (strlen (car c))) (car c))
               (sht:int-p (setq s (substr k (1+ (strlen (car c))))))
               (not (member (atoi s) res)))
        (setq res (cons (atoi s) res)))))
  (vl-sort res '<))

;; «начени€ атрибутов листа из полей рамки -> (значени€ непереносимые-непустые)
(defun sht:spds-vals (dat form / map vals unk tag v i)
  (setq map (append (cdr (assoc (sht:fbase form) *sht:SpdsForm*))
                    (if (/= (sht:fbase form) "6") *sht:SpdsSign*)
                    (if (sht:fside-p form) *sht:SpdsSide*)
                    '(("PageNumber" . "PNUM")))
        i   0)
  (foreach n (sht:spds-chg-idx dat)
    (setq i (1+ i))
    (if (<= i (sht:chg-rows form))
      (foreach c *sht:SpdsChg*
        (setq map (append map (list (cons (strcat (car c) (itoa n)) (strcat "C" (itoa i) (cdr c)))))))))
  (foreach p dat
    (setq v (sht:spds-str (cdr p)))
    (cond
      ((setq tag (cdr (assoc (car p) map)))
       (if (or (/= (sht:trim v) "") (not (assoc tag vals)))
         (setq vals (sht:alist-put vals tag v))))
      ((sht:spds-skip-p (car p)) nil)
      ((/= (sht:trim v) "") (setq unk (append unk (list (cons (car p) v)))))))
  (list vals unk))

;; ‘ормат, ориентаци€, масштаб и левый нижний угол рамки -> (запись ориентаци€ масштаб точка)
;; или строка Ч причина, почему рамка не переводитс€
(defun sht:spds-geom (en ed dat / fmt mult rec ori sc o r mn mx wh lab tol)
  (setq fmt  (sht:spds-str (cdr (assoc "Format" dat)))
        mult (cdr (assoc "Multiplicity" dat))
        sc   (cdr (assoc "Scale" dat))
        ori  (sht:parse-orient (sht:spds-str (cdr (assoc "Orientation" dat)))))
  (if (not (and (numberp mult) (> mult 0))) (setq mult 1))
  (setq mult (fix mult))
  (if (not (and (numberp sc) (> sc 0))) (setq sc (cdr (assoc 48 ed))))
  (if (not (and (numberp sc) (> sc 0))) (setq sc 1.0))
  (setq lab (if (> mult 1) (strcat fmt "x" (itoa mult)) fmt)
        rec (if (/= fmt "") (sht:parse-fmt lab)))
  (cond
    ((not rec) (strcat "формат Ђ" lab "ї - нет среди форматов SHEETS"))
    ((not ori) "не распознана ориентаци€")
    ((and (= ori "L") (sht:portrait-only-p (car rec) (cadr rec)))
     (strcat (sht:fmt-label rec) " горизонтальный в SHEETS не предусмотрен"))
    (t
     (setq wh (mapcar '(lambda (x) (* x sc)) (sht:fmt-wh rec ori))
           o  (vlax-ename->vla-object en)
           r  (vl-catch-all-apply 'vla-GetBoundingBox (list o 'mn 'mx)))
     (if (vl-catch-all-error-p r)
       ;; габарита нет Ч угол из полей рамки
       (list rec ori sc (list (cond ((cdr (assoc "OriginX" dat))) (0.0))
                              (cond ((cdr (assoc "OriginY" dat))) (0.0)) 0.0))
       (progn
         (setq mn  (vlax-safearray->list mn)
               mx  (vlax-safearray->list mx)
               tol (max 1.0 (* 0.005 (car wh))))
         (if (and (equal (- (car mx) (car mn)) (car wh) tol)
                  (equal (- (cadr mx) (cadr mn)) (cadr wh) tol))
           (list rec ori sc (list (car mn) (cadr mn) 0.0))
           (strcat "размер рамки " (sht:n2s (- (car mx) (car mn))) " x " (sht:n2s (- (cadr mx) (cadr mn)))
                   " не совпадает с форматом " (sht:fmt-label rec) " 1:" (sht:n2s sc) " "
                   (chr 40) (sht:n2s (car wh)) " x " (sht:n2s (cadr wh)) (chr 41)
                   " - рамка повЄрнута?")))))))

;; ѕодпись рамки дл€ отчЄта: Ђрамка 2E8, лист 21ї
(defun sht:spds-label (ed dat / s)
  (setq s (sht:trim (sht:spds-str (cdr (assoc "Sheet" dat)))))
  (if (= s "") (setq s (sht:trim (sht:spds-str (cdr (assoc "Ћист" dat))))))
  (strcat "рамка " (cond ((cdr (assoc 5 ed))) ("?")) (if (= s "") "" (strcat ", лист " s))))

(defun sht:lay-locked-p (lay / r)
  (and (setq r (tblsearch "LAYER" lay))
       (= 4 (logand 4 (cond ((cdr (assoc 70 r))) (0))))))

;; —лой старых рамок: есть Ч выключить, нет Ч создать выключенным
(defun sht:spds-layer ( / en ed)
  (if (setq en (tblobjname "LAYER" *sht:SpdsLay*))
    (progn
      (setq ed (entget en))
      (entmod (sht:dxf-set ed 62 (- (abs (cond ((cdr (assoc 62 ed))) (8)))))))
    (entmake (list '(0 . "LAYER") '(100 . "AcDbSymbolTableRecord") '(100 . "AcDbLayerTableRecord")
                   (cons 2 *sht:SpdsLay*) '(70 . 0) '(62 . -8) '(6 . "Continuous")))))

;; ѕеревести одну рамку -> (T лист форма непереносимые рамка-на-слое) или (nil причина)
(defun sht:spds-one (en / ed dat form g v base new r)
  (setq ed   (entget en)
        dat  (sht:spds-data ed)
        form (sht:spds-form dat)
        g    (sht:spds-geom en ed dat))
  (cond
    ((= (type g) 'STR) (list nil g))
    ((sht:lay-locked-p (cdr (assoc 8 ed)))
     (list nil (strcat "рамка на заблокированном слое Ђ" (cdr (assoc 8 ed)) "ї")))
    (t
     (setq v (sht:spds-vals dat form))
     ;; все пол€ формы Ч €вно (пустые не получат значений по умолчанию, напр. Ђ–азработалї)
     (foreach at (sht:attr-tab form)
       (if (not (member (car at) '("FORMAT" "ORIENT")))
         (setq base (cons (cons (car at) "") base))))
     (setq new (vl-catch-all-apply 'sht:insert
                 (list (car g) (cadr g) form (cadddr g) (caddr g) (append (car v) base))))
     (if (vl-catch-all-error-p new)
       (list nil (strcat "лист не вставлен: " (vl-catch-all-error-message new)))
       (progn
         (setq r (vl-catch-all-apply 'vla-put-Layer (list (vlax-ename->vla-object en) *sht:SpdsLay*)))
         (list T new form (cadr v) (not (vl-catch-all-error-p r))))))))

(defun sht:spds-form-name (f)
  (strcat "форма " (sht:fbase f) (if (sht:fside-p f) "" " без бокового штампа")))

;; ѕовтор€ющиес€ номера листов (в своей группе нумерации) -> ("лист 21 - 2 раза" Е)
(defun sht:spds-dups (ens / gl seen res n)
  (setq gl (sht:gnums ens))
  (foreach p gl
    (if (not (member p seen))
      (progn
        (setq seen (cons p seen)
              n    0)
        (foreach q gl (if (and (= (car q) (car p)) (= (strcase (cdr q)) (strcase (cdr p)))) (setq n (1+ n))))
        (if (> n 1)
          (setq res (append res (list (strcat (if (= (car p) "M") "" (strcat (substr (car p) 3) ", "))
                                              "лист " (cdr p) " - " (itoa n) " раза"))))))))
  res)

(defun sht:spds-cut (s) (if (> (strlen s) 40) (strcat (substr s 1 37) "...") s))

;; SHEET_FROM_SPDS Ч листы —ѕƒ— -> листы SHEETS
(defun c:SHEET_FROM_SPDS ( / doc sdat ens0 kw ss i en ed frames npaper nlay ok bad unk cnt r p s
                             lr sr dups diff nolay)
  (setq doc  (sht:doc)
        sdat (sht:prepare)
        ens0 (sht:sheets))
  (sht:dblclick-setup)
  (initget "¬се ”казать")
  (setq kw (getkword "\nѕеревести рамки —ѕƒ— в листы SHEETS [¬се/”казать] <¬се>: "))
  (setq ss (if (= kw "”казать")
             (progn (princ "\n¬ыберите рамки —ѕƒ—: ") (ssget '((0 . "SPDSFORMAT"))))
             (ssget "_X" '((0 . "SPDSFORMAT"))))
        npaper 0
        nlay   0)
  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq en (ssname ss i)
              ed (entget en)
              i  (1+ i))
        (cond ((/= (strcase (cond ((cdr (assoc 410 ed))) ("Model"))) "MODEL") (setq npaper (1+ npaper)))
              ((= (strcase (cdr (assoc 8 ed))) (strcase *sht:SpdsLay*)) (setq nlay (1+ nlay)))
              (t (setq frames (cons en frames)))))))
  (setq frames (reverse frames))
  (cond
    ((null frames)
     (princ (strcat "\n–амок —ѕƒ— дл€ перевода нет"
                    (if (> nlay 0) (strcat " (переведЄнные раньше - на слое Ђ" *sht:SpdsLay* "ї: " (itoa nlay) ")") "")
                    (if (> npaper 0) (strcat "; в листах (не в модели): " (itoa npaper)) "")
                    ".")))
    (t
     (vla-StartUndoMark doc)
     (sht:spds-layer)
     (foreach en frames
       (setq ed (entget en)
             s  (sht:spds-label ed (sht:spds-data ed))
             r  (sht:spds-one en))
       (if (car r)
         (progn
           (setq ok (append ok (list (cadr r))))
           (if (setq p (assoc (caddr r) cnt))
             (setq cnt (subst (cons (car p) (1+ (cdr p))) p cnt))
             (setq cnt (append cnt (list (cons (caddr r) 1)))))
           (if (cadddr r) (setq unk (append unk (list (cons s (cadddr r))))))
           (if (not (nth 4 r)) (setq nolay (append nolay (list s)))))
         (setq bad (append bad (list (strcat s ": " (cadr r)))))))
     (if ok
       (progn
         (setq r    (sht:common-now (mapcar 'sht:attrs (sht:sheets)) sdat)
               diff (cadr r))
         ;; листов SHEETS до перевода не было Ч данные комплекта берутс€ с переведЄнных листов
         (if (null ens0)
           (progn
             (foreach q (car r) (setq sdat (sht:alist-put sdat (car q) (cdr q))))
             (sht:set-write sdat)))
         (sht:stage-layer (cdr (assoc "STAGE" (car r))))
         (setq sr (sht:sign-auto T)
               lr (sht:list-auto T))))
     (vla-EndUndoMark doc)
     ;; отчЄт
     (princ (strcat "\nѕереведено рамок —ѕƒ—: " (itoa (length ok))
                    (if cnt
                      (strcat " " (chr 40)
                              (apply 'strcat (mapcar '(lambda (q) (strcat (sht:spds-form-name (car q)) " - "
                                                                          (itoa (cdr q)) "; ")) cnt))
                              (chr 41))
                      "")
                    "."))
     (if ok
       (princ (strcat "\n—тарые рамки - на выключенном слое Ђ" *sht:SpdsLay* "ї (включить слой - чтобы сверить).")))
     (foreach q nolay
       (princ (strcat "\n! " q ": рамку не удалось перенести на слой - уберите еЄ вручную.")))
     (if bad
       (progn
         (princ (strcat "\nЌе переведено: " (itoa (length bad))))
         (foreach q bad (princ (strcat "\n  - " q)))))
     (if (> nlay 0)
       (princ (strcat "\nѕереведЄнные раньше (слой Ђ" *sht:SpdsLay* "ї) не тронуты: " (itoa nlay) ".")))
     (if (> npaper 0)
       (princ (strcat "\n–амки в листах (не в модели) не перевод€тс€: " (itoa npaper) ".")))
     (if unk
       (progn
         (princ "\nЌе перенесены непустые пол€ —ѕƒ— (в SHEETS дл€ них нет графы):")
         (foreach q unk
           (princ (strcat "\n  - " (car q) ": "
                          (apply 'strcat (mapcar '(lambda (x) (strcat (car x) " = Ђ" (sht:spds-cut (cdr x)) "ї; "))
                                                 (cdr q))))))))
     (if (setq dups (sht:spds-dups (sht:sheets)))
       (progn
         (princ "\nѕовтор€ютс€ номера листов (исправить - в окне листа):")
         (foreach q dups (princ (strcat "\n  - " q)))))
     (if (and ok diff)
       (princ (strcat "\nЌа листах разные: " (sht:diff-str diff)
                      " - выровн€ть: SHT -> Ђƒанные комплекта...ї.")))
     (if lr (sht:list-msg lr nil))
     (if sr (sht:sign-msg sr nil))
     (if (or bad unk dups nolay) (textscr))))
  (sht:watch)
  (princ))



;; «агрузка: прежние реакторы сн€ть, поставить заново. s0.14: в командную строку при загрузке ничего не
;; отправл€етс€ (на старте AutoCAD из пакета .bundle SendCommand вешал AutoCAD; в separate namespace строка
;; не видит функций sht:). EATTEDIT отключаетс€ в начале команд SHEETS и в SHEET_DBLEDIT (sht:dblclick-setup).
(vl-catch-all-apply 'sht:react-remove nil)
(vl-catch-all-apply 'sht:dbl-restore nil)
(setq *sht:DblOn* nil *sht:DblEn* nil *sht:DblDone* nil *sht:ApplyQ* nil *sht:ListBusy* nil *sht:SignBusy* nil
      *sht:GridErr* nil)
(vl-catch-all-apply 'sht:react-ensure nil)

(princ (strcat "\nSHEETS " *sht:Version* " загружен. ¬се команды - в окне: SHT "
               "(прежние SHEET_NEW, SHEET_EDIT, SHEET_PLOT ... тоже работают)."))
(princ)
