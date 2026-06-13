# Submitting StratumFinder to antivirus vendors (false-positive whitelist)

PyInstaller executables get flagged as `Win64:Malware-gen` and similar.
This is a FALSE POSITIVE. Submitting your built EXE to each vendor gets
it added to their whitelist, usually within 1-7 days, for ALL their users.

Build the EXE first, then submit the SAME file to every vendor below.
Re-submit after each new build (the file hash changes every build).

═══════════════════════════════════════════════════════════════════
SUBMISSION LINKS
═══════════════════════════════════════════════════════════════════

AVG / Avast (same engine):
  https://www.avast.com/false-positive-file-form.php

Microsoft Defender:
  https://www.microsoft.com/en-us/wdsi/filesubmission

Kaspersky:
  https://opentip.kaspersky.com/

Bitdefender:
  https://www.bitdefender.com/submit/

ESET:
  https://support.eset.com/en/kb141 (samples@eset.com)

Malwarebytes:
  https://www.malwarebytes.com/false-positive

McAfee:
  https://www.mcafee.com/enterprise/en-us/threat-center/threat-library/false-positive.html

Norton / Symantec:
  https://submit.norton.com/

VirusTotal (CHECK detections, not a vendor):
  https://www.virustotal.com/

═══════════════════════════════════════════════════════════════════
READY-TO-PASTE SUBMISSION TEXT (English)
═══════════════════════════════════════════════════════════════════

Subject: False positive on legitimate open-source application

Body:

Hello,

Your product is flagging the file "StratumFinder.exe" as malware
(detection name: Win64:Malware-gen or similar). This is a FALSE POSITIVE.

This file is a legitimate, open-source desktop application for the
video game Elite Dangerous. It is written in Python and packaged with
PyInstaller, which is known to cause generic heuristic false positives.

- The application only makes read-only HTTPS requests to two public
  game-data APIs (spansh.co.uk and edsm.net).
- It does not modify system files, registry, or other processes.
- It does not collect or transmit personal data.
- Full source code is publicly available at:
  https://github.com/YOUR_USERNAME/stratum-finder

Please review and whitelist this file. I am happy to provide any
additional information needed.

Thank you,
[Your name]

═══════════════════════════════════════════════════════════════════
READY-TO-PASTE SUBMISSION TEXT (Русский)
═══════════════════════════════════════════════════════════════════

Тема: Ложное срабатывание на легитимном приложении

Текст:

Здравствуйте,

Ваш продукт помечает файл "StratumFinder.exe" как вредоносный
(имя детекта: Win64:Malware-gen или похожее). Это ЛОЖНОЕ
СРАБАТЫВАНИЕ.

Это легитимное приложение с открытым исходным кодом для игры
Elite Dangerous. Написано на Python и упаковано через PyInstaller,
который известен генерацией эвристических ложных срабатываний.

- Приложение делает только HTTPS-запросы на чтение к двум публичным
  игровым API (spansh.co.uk и edsm.net).
- Не изменяет системные файлы, реестр или другие процессы.
- Не собирает и не передаёт персональные данные.
- Полный исходный код доступен публично:
  https://github.com/YOUR_USERNAME/stratum-finder

Прошу проверить файл и добавить в белый список. Готов предоставить
любую дополнительную информацию.

Спасибо,
[Ваше имя]

═══════════════════════════════════════════════════════════════════
TIPS
═══════════════════════════════════════════════════════════════════

- Submit the EXACT file you distribute (same hash).
- AVG/Avast usually respond fastest (1-3 days).
- After whitelisting, that specific file hash is trusted for all users.
- IMPORTANT: every time you rebuild, the hash changes -> re-submit.
- Replace YOUR_USERNAME with your real GitHub username.
- Hosting source on GitHub greatly increases approval chances.
