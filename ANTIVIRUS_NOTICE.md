# ⚠️ Antivirus warning? Read this first / Антивирус ругается? Прочитайте

## 🇬🇧 English

### Why does my antivirus flag StratumFinder.exe?

Your antivirus may show a warning like **"Win64:Malware-gen"** when you
download or run StratumFinder. **This is a false positive — the app is
safe.**

**Why it happens:** the app is built with a tool called PyInstaller,
which packs Python programs into a single .exe. Antivirus software often
flags ALL PyInstaller apps with a generic heuristic warning, because the
packing method superficially resembles how some malware is built. It is
NOT detecting actual malicious code — there is none.

### Is it really safe?

Yes:
- The app only reads public game data from spansh.co.uk and edsm.net.
- It does not touch your system files, registry, or other programs.
- It does not collect or send any personal information.
- The full source code is open and viewable on GitHub: https://github.com/lynnel1/StratumFinder

You can verify it yourself by uploading the file to
https://www.virustotal.com — you'll see only generic heuristic flags
from a few engines, not real malware detections.

### How to run it anyway

**Windows Defender / SmartScreen:**
1. If you see "Windows protected your PC", click **More info**.
2. Click **Run anyway**.

**To stop the warnings permanently — add an exclusion:**

*Windows Defender:*
1. Open **Windows Security** → **Virus & threat protection**
2. **Manage settings** → **Add or remove exclusions**
3. **Add an exclusion** → **Folder** → select the StratumFinder folder

*AVG / Avast:*
1. Open AVG → **Menu** → **Settings**
2. **General** → **Exceptions** → **Add Exception**
3. Browse to the StratumFinder folder → **Add**

After adding the exclusion, the warning won't appear again.

═══════════════════════════════════════════════════════════════════

## 🇷🇺 Русский

### Почему антивирус ругается на StratumFinder.exe?

Антивирус может показать предупреждение вроде **"Win64:Malware-gen"**
при скачивании или запуске StratumFinder. **Это ложное срабатывание —
приложение безопасно.**

**Почему так происходит:** приложение собрано инструментом PyInstaller,
который упаковывает Python-программы в один .exe. Антивирусы часто
помечают ВСЕ приложения на PyInstaller общим эвристическим
предупреждением, потому что метод упаковки внешне похож на то, как
устроены некоторые вирусы. Это НЕ обнаружение реального вредоносного
кода — его там нет.

### Это действительно безопасно?

Да:
- Приложение только читает публичные игровые данные с spansh.co.uk
  и edsm.net.
- Не трогает системные файлы, реестр или другие программы.
- Не собирает и не отправляет никакую личную информацию.
- Полный исходный код открыт и доступен на GitHub:
  https://github.com/lynnel1/stratum-finder

Можете проверить сами, загрузив файл на https://www.virustotal.com —
увидите только общие эвристические флаги от пары движков, а не
реальные обнаружения вирусов, да и у вас на руках открытый исходный код приложения.

### Как всё-таки запустить

**Windows Defender / SmartScreen:**
1. Если видите "Система Windows защитила ваш компьютер", нажмите
   **Подробнее**.
2. Нажмите **Выполнить в любом случае**.

**Чтобы убрать предупреждения навсегда — добавьте исключение:**

*Windows Defender:*
1. Откройте **Безопасность Windows** → **Защита от вирусов и угроз**
2. **Управление настройками** → **Добавление или удаление исключений**
3. **Добавить исключение** → **Папка** → выберите папку StratumFinder

*AVG / Avast:*
1. Откройте AVG → **Меню** → **Настройки**
2. **Общее** → **Исключения** → **Добавить исключение**
3. Укажите папку StratumFinder → **Добавить**

После добавления исключения предупреждение больше не появится.

