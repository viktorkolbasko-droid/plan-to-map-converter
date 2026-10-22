# Small Google Drive client over the Drive MCP endpoint (the session proxy adds the auth; no keys in code).
# Storage rules - core/rules/10-запись-и-хранение.md, §2 "Хранение на Google Диске": never overwrite, a new version is a new file.
#   python3 drive_q.py ls <folder id>            id | title | mime | bytes | time
#   python3 drive_q.py find "<query>"            e.g. "title contains 'state_2026-09-30'"
#   python3 drive_q.py get <file id> <local>     download to a file (content is never printed)
import json, subprocess, base64, os, sys, tempfile
URL = "https://drivemcp.googleapis.com/mcp/v1"
def call(name, args):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})
    fd, p = tempfile.mkstemp(); os.write(fd, body.encode()); os.close(fd)
    r = subprocess.run(["curl", "-sS", "-X", "POST", URL, "-H", "Content-Type: application/json",
                        "-H", "Accept: application/json, text/event-stream", "--data-binary", "@" + p], capture_output=True, text=True)
    os.remove(p); txt = r.stdout.strip()
    if 'data:' in txt[:20]: txt = '\n'.join(l[5:].strip() for l in txt.splitlines() if l.startswith('data:'))
    res = json.loads(txt)
    if 'error' in res: raise RuntimeError(str(res['error'])[:300])
    res = res["result"]
    if res.get("isError"): raise RuntimeError(res["content"][0]["text"][:300])
    return res.get("structuredContent") or json.loads(res["content"][0]["text"])
def search(q, n=100):
    out = []; tok = None
    while True:
        a = {"query": q, "excludeContentSnippets": True, "pageSize": n}
        if tok: a["pageToken"] = tok
        d = call("search_files", a); out += d.get("files", []); tok = d.get("nextPageToken")
        if not tok: return out
def download(fid):
    d = call("download_file_content", {"fileId": fid})
    b64 = d.get('content') or d.get('base64Content') or d.get('data') or ''
    if isinstance(b64, dict): b64 = b64.get('data', '')
    return base64.b64decode(b64) if b64 else b'', d
if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == 'ls':
        for f in search(f"parentId = '{sys.argv[2]}'"): print(f.get('id'), '|', f.get('title'), '|', f.get('mimeType'), '|', f.get('fileSize'), '|', f.get('modifiedTime', f.get('createdTime')))
    elif cmd == 'find':
        for f in search(sys.argv[2]): print(f.get('id'), '|', f.get('title'), '|', f.get('parentId', ''), '|', f.get('fileSize'))
    elif cmd == 'get':
        b, d = download(sys.argv[2]); open(sys.argv[3], 'wb').write(b); print(len(b), d.get('title'))
