(vl-load-com)

;;; ==========================================================================
;;;  spds_export.lsp -- экспорт рамок —ѕƒ— (SPDSFORMAT) чертежа в JSON
;;;  ѕол€ рамки —ѕƒ— Ч по SHEETS.lsp (SHEET_FROM_SPDS, *sht:SpdsForm*):
;;;    форма 3: Sheet Ч лист, Drawing type Ч наименование (графа 4),
;;;             Designation Ч шифр, DrawingName1 Ч здание (графа 3!), ComplexName Ч объект;
;;;    форма 4: Ћист (или Sheet) Ч лист, DrawingName1 (иначе ComplexName, Drawing type) Ч наименование,
;;             Designation Ч обозначение;
;;;    форма 5: Sheet Ч лист, DrawingName1 Ч наименование, Designation Ч обозначение;
;;;    форма 6: Sheet Ч лист, наименовани€ в штампе нет.
;;;  ¬ј∆Ќќ: файл хранить в кодировке Windows-1251 (ANSI), как SHEETS.lsp, Ч
;;;  иначе ключи ЂЋистї, Ђћассаї, Ђћасштабї не совпадут с пол€ми рамки.
;;;  ¬ JSON добавлены "form" и "fields" (все пол€ рамки как есть) Ч дл€ отладки в Python.
;;; ==========================================================================

;; ѕол€ рамки: (("им€" . значение) Е) Ч пары 301 Ђим€ї -> значение (1 40 70 90 290 300)
(defun sht-spds-data (ed / key res)
  (foreach g ed
    (cond ((= (car g) 301) (setq key (cdr g)))
          ((and key (member (car g) '(1 40 70 90 290 300)))
           (setq res (cons (cons key (cdr g)) res)
                 key nil))))
  (reverse res))

;; «начение -> строка: 3.0 -> "3", 2.5 -> "2.5"; коды MText \P -> пробел; пробелы по кра€м убраны
(defun sht-val-str (v / s i)
  (setq s (cond ((= (type v) 'STR) v)
                ((= (type v) 'INT) (itoa v))
                ((and (numberp v) (< (abs v) 1e9) (equal v (fix v) 1e-9)) (itoa (fix v)))   ; fix от огромного числа Ч ошибка
                ((numberp v) (rtos v 2 4))
                ((null v) "")
                (t (vl-princ-to-string v))))
  (while (setq i (vl-string-search "\\P" s))
    (setq s (strcat (substr s 1 i) " " (substr s (+ i 3)))))
  (vl-string-trim " \t\r\n" s))

;; Ќепустое значение пол€ k (точное им€) или nil
(defun sht-get-val (k dat / p s)
  (if (and (setq p (assoc k dat))
           (/= (setq s (sht-val-str (cdr p))) ""))
    s))

;; ѕервое непустое из списка полей
(defun sht-find-first (keys dat / res)
  (while (and keys (null res))
    (setq res  (sht-get-val (car keys) dat)
          keys (cdr keys)))
  res)

;; ≈сть ли в строке не-латинские знаки (кириллица в любой кодировке)
(defun sht-nonascii-p (s / i r)
  (setq i 1)
  (while (and (not r) (<= i (strlen s)))
    (if (> (ascii (substr s i 1)) 127) (setq r T))
    (setq i (1+ i)))
  r)

;; ѕол€ рамки с не-латинскими именами (ЂЋистї, Ђћассаї, Ђћасштабї у формы 4)
(defun sht-ru-keys (dat / res)
  (foreach p dat
    (if (and (sht-nonascii-p (car p)) (not (member (car p) res)))
      (setq res (cons (car p) res))))
  (reverse res))

;; ѕоле ЂЋистї формы 4: точное им€; кодировка не совпала Ч самое короткое кириллическое им€
;; (ЂЋистї короче Ђћассаї и Ђћасштабї в любой кодировке)
(defun sht-f4-sheet-key (dat / ks best)
  (if (assoc "Ћист" dat)
    "Ћист"
    (progn
      (foreach k (sht-ru-keys dat)
        (if (or (null best) (< (strlen k) (strlen best))) (setq best k)))
      best)))

;; ‘орма штампа (как sht:spds-form в SHEETS.lsp): "3" "4" "5" "6".
;; ‘орма 4 Ч по пол€м Ђћассаї / Ђћасштабї; не совпала кодировка Ч по любому кириллическому имени пол€
;; (у форм 3, 5, 6 —ѕƒ— имена полей латинские)
(defun sht-spds-form (dat / k)
  (setq k (mapcar 'car dat))
  (cond ((or (member "ћасса" k) (member "ћасштаб" k) (sht-ru-keys dat)) "4")
        ((not (member "Author" k)) "6")
        ((or (and (member "ChangeNr3" k) (not (member "ChangeNr1" k)))
             (and (member "Add.text3" k) (not (member "Add.text4" k))))
         "5")
        (t "3")))

;; Ёкранирование строк дл€ JSON
(defun sht-escape-json (s / i c a res)
  (if (/= (type s) 'STR)
    ""
    (progn
      (setq res "" i 1)
      (while (<= i (strlen s))
        (setq c (substr s i 1)
              a (ascii c))
        (cond
          ((= a 92) (setq res (strcat res "\\\\")))
          ((= a 34) (setq res (strcat res "\\\"")))   ; было "\\"" Ч ломало разбор всего файла
          ((and (> a 0) (< a 32)) (setq res (strcat res " ")))
          (t (setq res (strcat res c))))
        (setq i (1+ i)))
      res)))

(defun sht-num-to-str (n)
  (if (numberp n) (vl-string-translate "," "." (rtos (float n) 2 4)) "0.0"))

;; ќсновна€ функци€ экспорта
(defun sht-export-spds (filepath / ss i en ed dat form hdl sh-num sh-name shifr fmt mult sc ori
                        o r mn mx min-pt max-pt ox oy fp first k)
  (setq ss (ssget "_X" '((0 . "SPDSFORMAT")))
        fp (open filepath "w"))
  (if fp
    (progn
      (write-line "[" fp)
      (setq first T)
      (if ss
        (progn
          (setq i 0)
          (while (< i (sslength ss))
            (setq en (ssname ss i)
                  ed (entget en)
                  i  (1+ i))
            (if (= (strcase (cond ((cdr (assoc 410 ed))) ("MODEL"))) "MODEL")
              (progn
                (setq dat  (sht-spds-data ed)
                      form (sht-spds-form dat)
                      hdl  (cond ((cdr (assoc 5 ed))) ("")))

                ;; 1. Ќомер листа: у формы 4 Ч ЂЋистї, у остальных Ч ЂSheetї.
                ;;    PageNumber Ч сквозной номер (стади€ ѕ), только если своего нет.
                (setq sh-num (sht-find-first
                               (if (= form "4")
                                 (vl-remove nil (list (sht-f4-sheet-key dat) "Sheet" "PageNumber"))
                                 '("Sheet" "PageNumber"))
                               dat))
                (if (null sh-num) (setq sh-num "Unknown"))

                ;; 2. Ќаименование листа Ч по форме (DrawingName1 у формы 3 Ч это здание, не лист;
                ;;    ЂName 1ї, ЂName 2ї Ч фамилии в Ђ—огласованої)
                (setq sh-name
                  (cond
                    ((= form "3") (sht-find-first '("Drawing type") dat))
                    ((= form "4") (sht-find-first '("DrawingName1" "ComplexName" "Drawing type") dat))
                    ((= form "5") (sht-find-first '("DrawingName1") dat))
                    (t nil)))
                (if (null sh-name) (setq sh-name ""))

                ;; 3. Ўифр / обозначение (графа 1)
                (setq shifr (cond ((sht-get-val "Designation" dat)) ("")))

                ;; 4-7. ‘ормат, кратность, масштаб, ориентаци€
                (setq fmt  (cond ((sht-get-val "Format" dat)) (""))
                      mult (cdr (assoc "Multiplicity" dat))
                      mult (cond ((= (type mult) 'INT) mult)
                                 ((and (numberp mult) (< (abs mult) 1000)) (fix mult))
                                 ((= (type mult) 'STR) (atoi mult))
                                 (t 1))
                      sc   (cdr (assoc "Scale" dat))
                      sc   (cond ((numberp sc) (float sc)) ((= (type sc) 'STR) (distof sc)) (t nil))
                      ori  (cond ((sht-get-val "Orientation" dat)) ("")))
                (if (< mult 1) (setq mult 1))
                (if (not (and (numberp sc) (> sc 0))) (setq sc (cdr (assoc 48 ed))))
                (if (not (and (numberp sc) (> sc 0))) (setq sc 1.0))

                ;; 8. √абарит
                (setq o (vlax-ename->vla-object en)
                      r (vl-catch-all-apply 'vla-GetBoundingBox (list o 'mn 'mx)))
                (if (vl-catch-all-error-p r)
                  (setq ox     (cdr (assoc "OriginX" dat))
                        oy     (cdr (assoc "OriginY" dat))
                        ox     (if (numberp ox) (float ox) 0.0)
                        oy     (if (numberp oy) (float oy) 0.0)
                        min-pt (list ox oy 0.0)
                        max-pt (list ox oy 0.0))
                  (setq min-pt (vlax-safearray->list mn)
                        max-pt (vlax-safearray->list mx)))

                (if (not first) (write-line "  ," fp))
                (setq first nil)
                (setq layout-name (cdr (assoc 410 ed)))
                (if (null layout-name) (setq layout-name "Model"))
                (write-line "  {" fp)
                (write-line (strcat "    \"handle\": \"" (sht-escape-json hdl) "\",") fp)
                (write-line (strcat "    \"layout\": \"" (sht-escape-json layout-name) "\",") fp)
                (write-line (strcat "    \"form\": \"" form "\",") fp)
                (write-line (strcat "    \"sheet_number\": \"" (sht-escape-json sh-num) "\",") fp)
                (write-line (strcat "    \"sheet_name\": \"" (sht-escape-json sh-name) "\",") fp)
                (write-line (strcat "    \"shifr\": \"" (sht-escape-json shifr) "\",") fp)
                (write-line (strcat "    \"format\": \"" (sht-escape-json fmt) "\",") fp)
                (write-line (strcat "    \"multiplicity\": " (itoa mult) ",") fp)
                (write-line (strcat "    \"scale\": " (sht-num-to-str sc) ",") fp)
                (write-line (strcat "    \"orientation\": \"" (sht-escape-json ori) "\",") fp)
                (write-line (strcat "    \"min_x\": " (sht-num-to-str (car min-pt)) ",") fp)
                (write-line (strcat "    \"min_y\": " (sht-num-to-str (cadr min-pt)) ",") fp)
                (write-line (strcat "    \"max_x\": " (sht-num-to-str (car max-pt)) ",") fp)
                (write-line (strcat "    \"max_y\": " (sht-num-to-str (cadr max-pt)) ",") fp)
                ;; все пол€ рамки Ч дл€ отладки (повтор€ющиес€ имена Ч первое)
                (write-line "    \"fields\": {" fp)
                (setq k nil)
                (foreach p dat
                  (if (not (member (car p) k))
                    (progn
                      (write-line (strcat (if k "      ," "      ")
                                          "\"" (sht-escape-json (car p)) "\": \""
                                          (sht-escape-json (sht-val-str (cdr p))) "\"")
                                  fp)
                      (setq k (cons (car p) k)))))
                (write-line "    }" fp)
                (write-line "  }" fp))))))
      (write-line "]" fp)
      (close fp)
      (princ "\n[SPDS EXPORT SUCCESS]")
      T)
    (progn
      (princ "\n[SPDS EXPORT ERROR: Cannot open file]")
      nil)))

(princ)
