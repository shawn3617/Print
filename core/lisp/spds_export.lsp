(vl-load-com)

;;; ==========================================================================
;;;  spds_export.lsp -- быстрый экспорт СПДС рамок чертежа в JSON
;;;  Основан на алгоритмах SHEETS.lsp (c:SHEET_FROM_SPDS / sht:spds-data)
;;; ==========================================================================

;; Чтение полей СПДС из ассоциативного списка DXF (группа 301 + значение)
(defun sht-spds-data (ed / key res)
  (foreach g ed
    (cond ((= (car g) 301) (setq key (cdr g)))
          ((and key (member (car g) '(1 40 70 90 290 300)))
           (setq res (cons (cons key (cdr g)) res)
                 key nil))))
  (reverse res))

;; Экранирование строк для формата JSON по ASCII кодам
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
          ((= a 92) (setq res (strcat res (chr 92) (chr 92))))  ;; Backslash
          ((= a 34) (setq res (strcat res (chr 92) (chr 34))))  ;; Quote
          ((= a 10) (setq res (strcat res " ")))              ;; Newline
          ((= a 13) (setq res (strcat res " ")))              ;; Carriage return
          ((= a 9)  (setq res (strcat res " ")))              ;; Tab
          ((< a 32) (setq res (strcat res " ")))              ;; Control chars
          (t        (setq res (strcat res c))))
        (setq i (1+ i)))
      res)))

;; Форматирование вещественного числа с точкой
(defun sht-num-to-str (n)
  (vl-string-translate "," "." (rtos (float n) 2 4)))

;; Основная функция экспорта всех СПДС-рамок в JSON файл
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
                
                ;; Номер листа
                (setq sh-num (cond ((cdr (assoc "Sheet" dat)))
                                   ((cdr (assoc "Лист" dat)))
                                   ("Unknown")))
                (if (numberp sh-num) (setq sh-num (itoa (fix sh-num))))
                
                ;; Название листа
                (setq sh-name (cond ((cdr (assoc "Drawing type" dat)))
                                    ((cdr (assoc "DrawingName1" dat)))
                                    ((cdr (assoc "ComplexName" dat)))
                                    ((cdr (assoc "TITLE" dat)))
                                    ("")))
                (if (numberp sh-name) (setq sh-name (vl-princ-to-string sh-name)))
                
                ;; Обозначение / Шифр
                (setq shifr (cond ((cdr (assoc "Designation" dat))) ("")))
                (if (numberp shifr) (setq shifr (vl-princ-to-string shifr)))
                
                ;; Формат
                (setq fmt (cond ((cdr (assoc "Format" dat))) ("")))
                (if (numberp fmt) (setq fmt (vl-princ-to-string fmt)))
                
                ;; Кратность
                (setq mult (cdr (assoc "Multiplicity" dat)))
                (cond
                  ((null mult) (setq mult 1))
                  ((numberp mult) (setq mult (fix mult)))
                  ((= (type mult) 'STR) (setq mult (atoi mult)))
                  (t (setq mult 1)))
                (if (< mult 1) (setq mult 1))
                
                ;; Масштаб
                (setq sc (cdr (assoc "Scale" dat)))
                (cond
                  ((null sc) (setq sc (cdr (assoc 48 ed))))
                  ((numberp sc) (setq sc (float sc)))
                  ((= (type sc) 'STR) (setq sc (distof sc)))
                  (t (setq sc 1.0)))
                (if (not (and (numberp sc) (> sc 0))) (setq sc 1.0))
                
                ;; Ориентация
                (setq ori (cond ((cdr (assoc "Orientation" dat))) ("")))
                (if (numberp ori) (setq ori (vl-princ-to-string ori)))
                
                ;; Габариты (BoundingBox)
                (setq o (vlax-ename->vla-object en)
                      min-pt '(0.0 0.0 0.0)
                      max-pt '(0.0 0.0 0.0)
                      r (vl-catch-all-apply 'vla-GetBoundingBox (list o 'mn 'mx)))
                (if (vl-catch-all-error-p r)
                  (progn
                    (setq ox (cond ((cdr (assoc "OriginX" dat))) (0.0))
                          oy (cond ((cdr (assoc "OriginY" dat))) (0.0)))
                    (if (numberp ox) (setq ox (float ox)) (setq ox (distof (vl-princ-to-string ox))))
                    (if (numberp oy) (setq oy (float oy)) (setq oy (distof (vl-princ-to-string oy))))
                    (if (null ox) (setq ox 0.0))
                    (if (null oy) (setq oy 0.0))
                    (setq min-pt (list ox oy 0.0)
                          max-pt (list ox oy 0.0)))
                  (setq min-pt (vlax-safearray->list mn)
                        max-pt (vlax-safearray->list mx)))
                
                (if (not first) (write-line "  ," fp))
                (setq first nil)
                
                (write-line "  {" fp)
                (write-line (strcat "    "handle": "" (sht-escape-json hdl) "",") fp)
                (write-line (strcat "    "sheet_number": "" (sht-escape-json sh-num) "",") fp)
                (write-line (strcat "    "sheet_name": "" (sht-escape-json sh-name) "",") fp)
                (write-line (strcat "    "shifr": "" (sht-escape-json shifr) "",") fp)
                (write-line (strcat "    "format": "" (sht-escape-json fmt) "",") fp)
                (write-line (strcat "    "multiplicity": " (itoa mult) ",") fp)
                (write-line (strcat "    "scale": " (sht-num-to-str sc) ",") fp)
                (write-line (strcat "    "orientation": "" (sht-escape-json ori) "",") fp)
                (write-line (strcat "    "min_x": " (sht-num-to-str (car min-pt)) ",") fp)
                (write-line (strcat "    "min_y": " (sht-num-to-str (cadr min-pt)) ",") fp)
                (write-line (strcat "    "max_x": " (sht-num-to-str (car max-pt)) ",") fp)
                (write-line (strcat "    "max_y": " (sht-num-to-str (cadr max-pt))) fp)
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
