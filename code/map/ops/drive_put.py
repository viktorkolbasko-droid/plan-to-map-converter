# Upload files to a Drive folder and check each one: download it back and compare SHA-256 with the local file
# (core/rules/10-запись-и-хранение.md, §2 "Хранение на Google Диске", п. 4). A file whose name is already in the folder is NOT uploaded -
# Drive files are never overwritten; a new version is a new file name.
#   python3 drive_put.py <folder id> file1 [file2 ...]
# Prints id, link, bytes and both hashes per file; exit 0 only when every file was uploaded and matched.
# Limit: about 0.9 MB per file - larger ones go as zip or 700 KB parts (core/code/21-сохранение-на-диск.md).
import json, base64, os, sys, hashlib, mimetypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drive_q import call, download
if __name__ == '__main__':
    parent = sys.argv[1]; files = sys.argv[2:]; out = []; ok = True
    for path in files:
        name = os.path.basename(path); data = open(path, 'rb').read(); h = hashlib.sha256(data).hexdigest()
        # (Т6-9) Drive's search is not strict - in folder "05" it returned three folders with other names: only a file whose
        #   title is exactly this name is a repeat; the quote and the backslash of the name are escaped in the query
        qn = name.replace('\\', '\\\\').replace("'", "\\'")
        ex = call("search_files", {"query": f"parentId = '{parent}' and title = '{qn}'", "excludeContentSnippets": True, "pageSize": 50}).get("files", [])
        ex = [f for f in ex if f.get('title') == name]
        if ex:
            out.append(dict(file=name, status='exists - not uploaded', ids=[f['id'] for f in ex])); ok = False; continue
        mime = 'text/markdown' if name.endswith('.md') else (mimetypes.guess_type(name)[0] or 'application/octet-stream')
        f = call("create_file", {"title": name, "parentId": parent, "base64Content": base64.b64encode(data).decode(),
                                 "contentMimeType": mime, "disableConversionToGoogleType": True})
        back, d = download(f["id"]); hb = hashlib.sha256(back).hexdigest() if back else None
        out.append(dict(file=name, status='uploaded', id=f['id'], url=f.get('viewUrl'), bytes=len(data), sha256_local=h,
                        sha256_drive=hb, match=hb == h))
        ok = ok and hb == h
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)
