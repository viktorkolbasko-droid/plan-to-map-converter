# Pack the UnSpot map code into a versioned archive for Google Drive, folder "11 Код карты UnSpot" (core/rules/10 §2, "Хранение";
# decision of the owner 02.10.2026: code in the project for reading, archive on Drive for deploying — п. 139, variant (б)).
#   code/ without *_backup* files and caches -> unspot-code__v<NNN>__<YYYY-MM-DD-HHMM>.zip with code/MANIFEST.json inside
#   (every file: bytes, SHA-256) + unspot-code__v<NNN>__<YYYY-MM-DD-HHMM>__MANIFEST.md next to it (the same list and the
#   SHA-256 of the zip). The zip is reproducible: files sorted, one timestamp.
#   python3 code_release.py <NNN> [out_dir]
#   then: python3 drive_put.py <folder 11 id> <zip> <manifest.md>; write the version, file id and SHA-256 into map/00 §2.
import os, sys, json, hashlib, zipfile, datetime
CODE = os.environ.get('UNS_CODE', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ver = int(sys.argv[1]); out = sys.argv[2] if len(sys.argv) > 2 else '.'
now = datetime.datetime.now(datetime.timezone.utc); stamp = now.strftime('%Y-%m-%d-%H%M')
base = f'unspot-code__v{ver:03d}__{stamp}'
files = []
for root, dirs, fs in os.walk(CODE):
    dirs[:] = sorted(d for d in dirs if d != '__pycache__' and not (root == CODE and d == 'data') and not d.startswith('out'))   # данные кругов и вывод регрессии — не код
    for f in sorted(fs):
        if 'backup' in f or f.endswith('.pyc') or f == 'MANIFEST.json': continue
        p = os.path.join(root, f); rel = os.path.relpath(p, CODE).replace(os.sep, '/')
        b = open(p, 'rb').read(); files.append((rel, len(b), hashlib.sha256(b).hexdigest(), b))
files.sort()
man = dict(version=ver, made_utc=now.strftime('%Y-%m-%d %H:%M'), files={r: dict(bytes=n, sha256=h) for r, n, h, _ in files})
zp = os.path.join(out, base + '.zip'); dt = now.timetuple()[:6]
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for rel, n, h, b in files:
        zi = zipfile.ZipInfo('code/' + rel, date_time=dt); zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = (0o755 if rel.endswith('.sh') else 0o644) << 16
        z.writestr(zi, b)
    zi = zipfile.ZipInfo('code/MANIFEST.json', date_time=dt); zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, json.dumps(man, ensure_ascii=False, indent=1))
zb = open(zp, 'rb').read(); zh = hashlib.sha256(zb).hexdigest()
md = [f'# Код карты UnSpot — версия {ver:03d}, {man["made_utc"]} UTC', '',
      f'Архив — `{base}.zip`, {len(zb)} байт, SHA-256 `{zh}`. Внутри — папка `code/` и `code/MANIFEST.json` с тем же списком.',
      'Развернуть — `code/README.md`, «Развернуть»; адрес текущей версии — `map/00` §2. Новая версия — новым файлом со следующим номером.', '',
      '| Файл | Байт | SHA-256 |', '|---|---|---|'] + [f'| `{r}` | {n} | `{h}` |' for r, n, h, _ in files]
mp = os.path.join(out, base + '__MANIFEST.md'); open(mp, 'w', encoding='utf-8').write('\n'.join(md) + '\n')
print(json.dumps(dict(zip=zp, zip_bytes=len(zb), zip_sha256=zh, manifest=mp, files=len(files)), ensure_ascii=False, indent=1))
