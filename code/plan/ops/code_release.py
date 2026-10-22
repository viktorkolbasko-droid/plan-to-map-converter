# Pack the engplan code into a versioned archive for Google Drive, folder "10 Код инженерного плана" (plan/code/90).
#   code/ without *_backup* files and caches -> engplan-code__v<NNN>__<YYYY-MM-DD-HHMM>.zip with MANIFEST.json inside
#   (every file: bytes, SHA-256) + engplan-code__v<NNN>__<YYYY-MM-DD-HHMM>__MANIFEST.md next to it (the same list and
#   the SHA-256 of the zip). The zip is reproducible: files sorted, one timestamp.
#   python3 code_release.py <NNN> [out_dir] [draft label]
#   then: python3 drive_put.py <folder 10 id> <zip> <manifest.md>   and write the version, file id and SHA-256 into
#   plan/code/90 ("Текущая версия"). A new version is a new file: Drive files are never overwritten.
#   A draft label ('черновик-ред3') names a draft that is not a release: engplan-code__v<NNN>-<label>__<stamp>.zip, and
#   MANIFEST.json gets the field 'draft' - it goes to the subfolder "Черновики — не выпущено", not to the root of "10".
# (code 007, п. 239) code/MANIFEST.json of a folder deployed from Drive is not taken into the archive: the archive gets its
#   own MANIFEST.json, and a second one made code_deploy.py refuse the archive (proposals/plan/2026-10-03-выпуск-кода-из-
#   развёрнутой-папки.md).
import os, sys, json, hashlib, zipfile, datetime
CODE = os.environ.get('ENG_CODE', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ver = int(sys.argv[1]); out = sys.argv[2] if len(sys.argv) > 2 else '.'; draft = sys.argv[3] if len(sys.argv) > 3 else ''
now = datetime.datetime.now(datetime.timezone.utc); stamp = now.strftime('%Y-%m-%d-%H%M')
base = f'engplan-code__v{ver:03d}{"-" + draft if draft else ""}__{stamp}'
files = []
for root, dirs, fs in os.walk(CODE):
    dirs[:] = sorted(d for d in dirs if d != '__pycache__')
    for f in sorted(fs):
        if 'backup' in f or f.endswith('.pyc') or (root == CODE and f == 'MANIFEST.json'): continue
        p = os.path.join(root, f); rel = os.path.relpath(p, CODE).replace(os.sep, '/')
        b = open(p, 'rb').read(); files.append((rel, len(b), hashlib.sha256(b).hexdigest(), b))
files.sort()
man = dict(version=ver, **({'draft': draft} if draft else {}), made_utc=now.strftime('%Y-%m-%d %H:%M'), files={r: dict(bytes=n, sha256=h) for r, n, h, _ in files})
zp = os.path.join(out, base + '.zip'); dt = now.timetuple()[:6]
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for rel, n, h, b in files:
        zi = zipfile.ZipInfo('code/' + rel, date_time=dt); zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = (0o755 if rel.endswith('.sh') else 0o644) << 16
        z.writestr(zi, b)
    zi = zipfile.ZipInfo('code/MANIFEST.json', date_time=dt); zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, json.dumps(man, ensure_ascii=False, indent=1))
zb = open(zp, 'rb').read(); zh = hashlib.sha256(zb).hexdigest()
md = [f'# Код инженерного плана — версия {ver:03d}{" — " + draft + ", не выпущено" if draft else ""}, {man["made_utc"]} UTC', '',
      f'Архив — `{base}.zip`, {len(zb)} байт, SHA-256 `{zh}`. Внутри — папка `code/` и `code/MANIFEST.json` с тем же списком.',
      'Развернуть — `plan/code/90`, «Развернуть код». Новая версия — новым файлом со следующим номером.', '',
      '| Файл | Байт | SHA-256 |', '|---|---|---|'] + [f'| `{r}` | {n} | `{h}` |' for r, n, h, _ in files]
mp = os.path.join(out, base + '__MANIFEST.md'); open(mp, 'w', encoding='utf-8').write('\n'.join(md) + '\n')
print(json.dumps(dict(zip=zp, zip_bytes=len(zb), zip_sha256=zh, manifest=mp, files=len(files)), ensure_ascii=False, indent=1))
