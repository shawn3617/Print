(vl-load-com)

;;; ==========================================================================
;;;  block_export.lsp -- Быстрый нативный экспорт рамок-блоков из AutoCAD в JSON
;;; ==========================================================================

;; Экранирование строк в формат JSON
(defun sht-blk-escape-json (s / i c a res)
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
          ((= a 34) (setq res (strcat res "\\\"")))
          ((= a 10) (setq res (strcat res " ")))
          ((= a 13) (setq res (strcat res " ")))
          ((= a 9)  (setq res (strcat res " ")))
          ((and (> a 0) (< a 32)) (setq res (strcat res " ")))
          (t        (setq res (strcat res c))))
        (setq i (1+ i)))
      res)))

;; Форматирование вещественного числа в строку
(defun sht-blk-num-to-str (n)
  (if (null n)
    "0.0"
    (vl-string-translate "," "." (rtos (float n) 2 4))))

;; Основная функция экспорта рамок-блоков
(defun sht-export-blocks (filepath patterns-str sheet-tags-str title-tags-str / 
                          ss i en ed obj bname eff-name hdl sc
                          sh-num sh-name att-list tag-str val-str
                          mn mx min-pt max-pt r fp first first-att)
  (setq patterns-str (strcase patterns-str))
  (setq sheet-tags-str (strcase sheet-tags-str))
  (setq title-tags-str (strcase title-tags-str))
  (setq ss (ssget "_X" '((0 . "INSERT") (410 . "Model"))))
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
                  obj (vlax-ename->vla-object en)
                  i (1+ i))
            
            ;; Получаем эффективное имя блока (для динамических блоков)
            (setq eff-name
              (cond
                ((vlax-property-available-p obj 'EffectiveName)
                 (vla-get-EffectiveName obj))
                (t (vla-get-Name obj))))
            
            ;; Проверяем соответствие маске имен блоков
            (if (or (wcmatch (strcase eff-name) patterns-str)
                    (wcmatch (strcase (vla-get-Name obj)) patterns-str))
              (progn
                (setq hdl (vla-get-Handle obj))
                
                ;; Масштаб X
                (setq sc 1.0)
                (if (vlax-property-available-p obj 'XScaleFactor)
                  (setq sc (vlax-get-property obj 'XScaleFactor)))
                (if (not (and (numberp sc) (> sc 0))) (setq sc 1.0))
                
                ;; Считывание атрибутов
                (setq sh-num "Unknown"
                      sh-name "Unknown")
                (if (= (vla-get-HasAttributes obj) :vlax-true)
                  (progn
                    (setq att-list (vl-catch-all-apply 'vlax-invoke (list obj 'GetAttributes)))
                    (if (and att-list (not (vl-catch-all-error-p att-list)))
                      (foreach att att-list
                        (setq tag-str (strcase (vla-get-TagString att))
                              val-str (vla-get-TextString att))
                        (if (wcmatch tag-str sheet-tags-str)
                          (if (= sh-num "Unknown")
                            (setq sh-num val-str)))
                        (if (wcmatch tag-str title-tags-str)
                          (if (= sh-name "Unknown")
                            (setq sh-name val-str)
                            (if (> (strlen val-str) 0)
                              (setq sh-name (strcat sh-name " " val-str)))))))))
                
                ;; BoundingBox
                (setq mn nil mx nil)
                (setq r (vl-catch-all-apply 'vla-GetBoundingBox (list obj 'mn 'mx)))
                (if (not (vl-catch-all-error-p r))
                  (progn
                    (setq min-pt (vlax-safearray->list mn)
                          max-pt (vlax-safearray->list mx))
                    
                    (if (not first) (write-line "  ," fp))
                    (setq first nil)
                    
                    (write-line "  {" fp)
                    (write-line (strcat "    \"handle\": \"" (sht-blk-escape-json hdl) "\",") fp)
                    (write-line (strcat "    \"block_name\": \"" (sht-blk-escape-json eff-name) "\",") fp)
                    (write-line (strcat "    \"sheet_number\": \"" (sht-blk-escape-json sh-num) "\",") fp)
                    (write-line (strcat "    \"sheet_name\": \"" (sht-blk-escape-json sh-name) "\",") fp)
                    (write-line (strcat "    \"scale\": " (sht-blk-num-to-str sc) ",") fp)
                    (write-line (strcat "    \"min_x\": " (sht-blk-num-to-str (car min-pt)) ",") fp)
                    (write-line (strcat "    \"min_y\": " (sht-blk-num-to-str (cadr min-pt)) ",") fp)
                    (write-line (strcat "    \"max_x\": " (sht-blk-num-to-str (car max-pt)) ",") fp)
                    (write-line (strcat "    \"max_y\": " (sht-blk-num-to-str (cadr max-pt)) ",") fp)
                    (write-line "    \"attrs\": {" fp)
                    (if (and att-list (not (vl-catch-all-error-p att-list)))
                      (progn
                        (setq first-att T)
                        (foreach att att-list
                          (if (not first-att) (write-line "      ," fp))
                          (setq first-att nil)
                          (write-line (strcat "      \"" (sht-blk-escape-json (vla-get-TagString att)) "\": \""
                                              (sht-blk-escape-json (vla-get-TextString att)) "\"") fp))))
                    (write-line "    }" fp)
                    (write-line "  }" fp)
                  )
                )
              )
            )
          )
        )
      )
      (write-line "]" fp)
      (close fp)
      T
    )
    nil
  )
)
