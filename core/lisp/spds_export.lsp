(vl-load-com)

;;; ==========================================================================
;;;  spds_export.lsp -- Быстрый экспорт СПДС рамок чертежа в JSON
;;;  Основано на алгоритмах SHEETS.lsp (c:SHEET_FROM_SPDS / sht:spds-data)
;;;  Поддерживает различные типы СПДС-штампов (ГОСТ 21.101-97, 21.101-2020,
;;;  формы 3, 4, 5, 6, многострочные наименования DrawingName1..N, Name 1..N и т.д.)
;;; ==========================================================================

;; Чтение и парсинг ассоциативного списка DXF (группы 301 + значение)
(defun sht-spds-data (ed / key res)
  (foreach g ed
    (cond ((= (car g) 301) (setq key (cdr g)))
          ((and key (member (car g) '(1 40 70 90 290 300)))
           (setq res (cons (cons key (cdr g)) res)
                 key nil))))
  (reverse res))

;; Проверка значения на непустоту (не nil, не пустая строка, не пробелы)
(defun sht-nonempty-str (v / s)
  (if (null v)
    nil
    (progn
      (setq s (vl-princ-to-string v))
      (setq s (vl-string-trim " \t\r\n" s))
      (if (and (/= s "") (/= s "nil"))
        s
        nil))))

;; Поиск значения по ключу в alist без учета регистра
(defun sht-get-val (target-key alist / t-up found val)
  (setq t-up (strcase target-key)
        found nil)
  (foreach pair alist
    (if (and (null found)
             (or (= (car pair) target-key)
                 (= (car pair) t-up)
                 (= (strcase (car pair)) t-up)))
      (progn
        (setq val (sht-nonempty-str (cdr pair)))
        (if val (setq found val)))))
  found)

;; Поиск первого непустого значения по списку ключей
(defun sht-find-first (keys alist / res k)
  (setq res nil)
  (while (and keys (null res))
    (setq k (car keys)
          keys (cdr keys)
          res (sht-get-val k alist)))
  res)

;; Сборка многострочного текста по префиксам (например DrawingName1..N, Name 1..N)
(defun sht-collect-multiline (prefix-list max-lines alist / full p i k val)
  (setq full "")
  (foreach p prefix-list
    (if (= full "")
      (progn
        (setq i 1)
        (while (<= i max-lines)
          (setq k (strcat p (itoa i)))
          (setq val (sht-get-val k alist))
          (if val
            (if (= full "")
              (setq full val)
              (setq full (strcat full " " val))))
          (setq i (1+ i))))))
  (if (/= full "") full nil))

;; Экранирование строк в формат JSON
(defun sht-escape-json (s / i c a res)
  (if (/= (type s) 'STR)
    ""
    (progn
      (setq res "")
      (setq i 1)
      (while (<= i (strlen s))
        (setq c (substr s i 1)
              a (ascii c))
        (cond
          ((= a 92) (setq res (strcat res "\\\\")))
          ((= a 34) (setq res (strcat res "\\"")))
          ((= a 10) (setq res (strcat res " ")))
          ((= a 13) (setq res (strcat res " ")))
          ((= a 9)  (setq res (strcat res " ")))
          ((and (> a 0) (< a 32)) (setq res (strcat res " ")))
          (t        (setq res (strcat res c))))
        (setq i (1+ i)))
      res)))

;; Форматирование вещественного числа с точкой
(defun sht-num-to-str (n)
  (if (null n)
    "0.0"
    (vl-string-translate "," "." (rtos (float n) 2 4))))

;; Основная функция экспорта СПДС-рамок в JSON файл
(defun sht-export-spds (filepath / ss i en ed dat hdl sh-num sh-name shifr fmt mult sc ori min-pt max-pt o r mn mx ox oy fp first)
  (setq ss (ssget "_X" '((0 . "SPDSFORMAT,*MCS*,*SPDB*"))))
  (setq fp (open filepath "w"))
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
            ;; Только пространство модели
            (if (= (strcase (cond ((cdr (assoc 410 ed))) ("MODEL"))) "MODEL")
              (progn
                (setq dat (sht-spds-data ed))
                (setq hdl (cond ((cdr (assoc 5 ed))) ("")))
                
                ;; 1. Номер листа (проверяем все варианты названий полей)
                (setq sh-num (sht-find-first
                               '("Лист" "Sheet" "PageNumber" "Page" "Номер листа" "НомерЛиста" "SH_NUM" "NUM" "Number" "Лист1" "Sheet1")
                               dat))
                (if (null sh-num) (setq sh-num "Unknown"))
                
                ;; 2. Наименование листа (сначала многострочные поля, затем одиночные)
                (setq sh-name (sht-collect-multiline
                                '("DrawingName" "Name " "Name" "Наименование " "Наименование" "Название " "Название")
                                9
                                dat))
                (if (null sh-name)
                  (setq sh-name (sht-find-first
                                  '("Drawing type" "DrawingName" "ComplexName" "TITLE" "Title" "Наименование" "Название" "Name" "Description" "Subject")
                                  dat)))
                (if (null sh-name) (setq sh-name ""))
                
                ;; 3. Обозначение / Шифр
                (setq shifr (sht-find-first '("Designation" "Обозначение" "Шифр" "Code" "DocCode") dat))
                (if (null shifr) (setq shifr ""))
                
                ;; 4. Формат
                (setq fmt (sht-find-first '("Format" "Формат") dat))
                (if (null fmt) (setq fmt ""))
                
                ;; 5. Кратность
                (setq mult (sht-find-first '("Multiplicity" "Кратность") dat))
                (cond
                  ((null mult) (setq mult 1))
                  ((numberp mult) (setq mult (fix mult)))
                  ((= (type mult) 'STR) (setq mult (atoi mult)))
                  (t (setq mult 1)))
                (if (< mult 1) (setq mult 1))
                
                ;; 6. Масштаб
                (setq sc (sht-find-first '("Scale" "Масштаб") dat))
                (cond
                  ((null sc) (setq sc (cdr (assoc 48 ed))))
                  ((numberp sc) (setq sc (float sc)))
                  ((= (type sc) 'STR) (setq sc (distof sc)))
                  (t (setq sc 1.0)))
                (if (not (and (numberp sc) (> sc 0))) (setq sc 1.0))
                
                ;; 7. Ориентация
                (setq ori (sht-find-first '("Orientation" "Ориентация") dat))
                (if (null ori) (setq ori ""))
                
                ;; 8. Габариты (BoundingBox)
                (setq o (vlax-ename->vla-object en)
                      min-pt '(0.0 0.0 0.0)
                      max-pt '(0.0 0.0 0.0)
                      r (vl-catch-all-apply 'vla-GetBoundingBox (list o 'mn 'mx)))
                (if (vl-catch-all-error-p r)
                  (progn
                    (setq ox (sht-find-first '("OriginX") dat)
                          oy (sht-find-first '("OriginY") dat))
                    (if (numberp ox) (setq ox (float ox)) (if ox (setq ox (distof (vl-princ-to-string ox)))))
                    (if (numberp oy) (setq oy (float oy)) (if oy (setq oy (distof (vl-princ-to-string oy)))))
                    (if (null ox) (setq ox 0.0))
                    (if (null oy) (setq oy 0.0))
                    (setq min-pt (list ox oy 0.0)
                          max-pt (list ox oy 0.0)))
                  (setq min-pt (vlax-safearray->list mn)
                        max-pt (vlax-safearray->list mx)))
                
                (if (not first) (write-line "  ," fp))
                (setq first nil)
                
                (write-line "  {" fp)
                (write-line (strcat "    \"handle\": \"" (sht-escape-json hdl) "\",") fp)
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
                (write-line (strcat "    \"max_y\": " (sht-num-to-str (cadr max-pt))) fp)
                (write-line "  }" fp)
              )
            )
          )
        )
      )
      (write-line "]" fp)
      (close fp)
      (princ "\n[SPDS EXPORT SUCCESS]")
      T
    )
    (progn
      (princ "\n[SPDS EXPORT ERROR: Cannot open file]")
      nil
    )
  )
)
(princ)
