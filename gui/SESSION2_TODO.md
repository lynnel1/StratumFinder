# Сессия 2 — статус

## Сделано в этой итерации (2A)

1. ✅ **bio_window.py полностью переписан** — иерархический Treeview.
2. ✅ **Data-модель** `_bodies[body_name] = {planet_data, bio_signals, confirmed_genera, species: {...}}`
3. ✅ **4 состояния видов**:
   | State     | Иконка | Тег/цвет   | Триггер                    |
   |-----------|--------|------------|----------------------------|
   | species   | ✅     | `ok`       | ScanOrganic Analyse        |
   | historic  | 📚     | `text_dim` | history за 5 дней          |
   | genus     | ✨     | `warn`     | DSS SAASignalsFound        |
   | predicted | 🔍     | `text_dim` | FSS Scan + FSSBodySignals  |
4. ✅ **Priority merge**: `species > historic > genus > predicted`
5. ✅ **`~` префикс** на цене для predicted/genus.
6. ✅ **Auto-expand** новых planet-узлов + системный узел всегда open.
7. ✅ **Multi-system НЕ поддерживается**: при FSDJump дерево очищается
   (прошлые сборы остаются в inventory).
8. ✅ **Body-узел скрыт** если нет FSS и нет species/historic.
9. ✅ **История за 5 дней**: подтягивается для текущей системы. Виды
   без FSS-планеты остаются в `_pending_historic` до её сканирования.
10. ✅ **Persistence** `realtime_bio.json` v2: полное дерево + expanded.
    Восстанавливается только если игрок в той же системе.
11. ✅ **Died / Sell / Clear** — работают на новой модели.
12. ✅ **Правки в main_window.py**:
    - `_toggle_bio_window`: прокидывает уже накопленные звёзды при
      открытии окна.
    - `on_star_scanned` callback: пробрасывает star_data в bio_window,
      чтобы он мог перегенерировать предсказания при добавлении звезды
      после Scan планет.

## Что осталось на потом

### Сессия 2B — тесты и правки

Проверить на живом journal:
- [ ] Все 4 состояния корректно отображаются.
- [ ] DSS правильно понижает predicted → genus и удаляет виды не из
      подтверждённых родов.
- [ ] Historic-виды с 📚 не теряют иконку после Analyse (баг из Сессии 1).
- [ ] `_current_stars` синхронизируется, если Scan звезды приходит после
      Scan планет.
- [ ] Persistence восстанавливает дерево корректно.
- [ ] Died удаляет только несданные species, historic остаётся.

### Сессия 3 — nebula detection

- Список известных туманностей (~500 из EDSM) для проверки близости.
- Точка отсчёта — координаты системы. Радиус 100 ly для Electricae Radialem.

### Возможно в 2B/2C

- **BodyID в planet_data** (в journal.py добавить одну строчку) — тогда
  сортировка body-узлов будет по BodyID, а не по имени (сейчас "A 10"
  идёт перед "A 2" — строковая).
- **Гео-сигналы** — пользователь сказал что не нужны сейчас.
