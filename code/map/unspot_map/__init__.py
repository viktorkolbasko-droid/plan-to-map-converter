"""unspot_map - reusable pieces of the client C v2 pipeline (UnSpot office map, raster/PDF source).

Not a library for any plan: the geometry model of a building is always plan-specific. What is reusable:
source assembly from a PDF page (pdf_source), measuring by profiles (profiles), the wall graph (wall_graph),
the canonical SVG (svg_map), doors (doors), stair flights (stairs), furniture (furniture), badges (icons),
artifact 3 variant C (workplaces), acceptance checks (checks) and review crops (compare).
v005: chairs of the sheet apart from the desk search (chairs, for Ch-31); micro_ortho of short oblique edges (ortho, Ch-32).
v007: artifact 3 - the seat number in white over the desk fill (owner row 181), spots counted on the fill mask before the numbers;
svg_map.DOOR_EXTRA - the door depth overhang shared with acceptance Ch-19 (OPENING_EXTRA).
v008: inputs of the acceptance from the vector sheet - doors, glass, seat numbers (sheet, Ch-36..Ch-38); the wall-body mask by the fixed
recipe wm1 (wall_mask, Ch-10: massif - a band t_m at the face); room type by the sheet furniture (room_types, owner rows 176-177);
places - numbers to chairs one to one over the floor, no chair behind another desk (workplaces), desk-fill exclusion and joined pieces (chairs).
v012: мост, приёмка — двери листа по дугам-ломаным и кускам дуги, формат номера места — настройка клиента (sheet, КМ-8, КМ-13).
v012: места, PNG, полигоны — места по объектам плана (places_plan) и по линиям (desks_lines), to_png ≈ 4 000 px, полигоны зон (zones).
v012, выпуск 14.10.2026: zones — «проходов A-922 нет» и счёт пропущенных сущностей (ПК6-К3); to_png — «меньше 1×» и «пропорции» (ПК6-К4).
v013 (16.10.2026): draft 25 / 50 / 100 (workplaces.render_draft, replaces render_variant_c), to_png about 4 000 px, place record fields room and gaze_deg (workplaces.finish_records), acceptance Ch-10 / Ch-21 / Ch-22 / Ch-29 and the checks without a Ch number (meeting-room table), glyphs - cache of badge glyphs (dinner = fork and knife, food = cup; glyphs.BADGES, badge_svg).
Constants of drawing (colours, thicknesses, badge size) are NOT defined here: take them from the stage canon, map/00 §10."""
