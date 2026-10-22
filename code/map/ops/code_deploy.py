# Deploy the UnSpot map code from Google Drive (folder "11 Код карты UnSpot") into a work folder (map/00 §2): download the archive through the Drive MCP
# endpoint (the session proxy adds the auth), check its SHA-256, unpack, check every file against code/MANIFEST.json.
# Stops on any mismatch - nothing half-deployed is left to run silently.
#   python3 code_deploy.py <zip file id> <zip sha256> [dest, default .]      -> dest/code/...
# The same script, pasted from map/00 §2, is the bootstrap in a fresh session.
import json, subprocess, base64, hashlib, sys, zipfile, io, os, tempfile
URL = "https://drivemcp.googleapis.com/mcp/v1"
fid, sha = sys.argv[1], sys.argv[2]; dest = sys.argv[3] if len(sys.argv) > 3 else '.'
body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "download_file_content", "arguments": {"fileId": fid}}})
fd, p = tempfile.mkstemp(); os.write(fd, body.encode()); os.close(fd)
r = subprocess.run(["curl", "-sS", "-X", "POST", URL, "-H", "Content-Type: application/json",
                    "-H", "Accept: application/json, text/event-stream", "--data-binary", "@" + p], capture_output=True, text=True)
os.remove(p); t = r.stdout.strip()
if 'data:' in t[:20]: t = '\n'.join(l[5:].strip() for l in t.splitlines() if l.startswith('data:'))
res = json.loads(t)
if 'error' in res or res['result'].get('isError'): sys.exit('download failed: ' + t[:300])
d = res['result'].get('structuredContent') or json.loads(res['result']['content'][0]['text'])
b = base64.b64decode(d.get('content') or d.get('base64Content') or '')
h = hashlib.sha256(b).hexdigest()
if h != sha: sys.exit(f'archive SHA-256 {h} != {sha} - not deployed')
z = zipfile.ZipFile(io.BytesIO(b)); man = json.loads(z.read('code/MANIFEST.json'))
bad = [n for n, m in man['files'].items() if hashlib.sha256(z.read('code/' + n)).hexdigest() != m['sha256']]
if bad: sys.exit(f'files differ from MANIFEST: {bad[:10]} - not deployed')
z.extractall(dest)
for n in man['files']:
    if n.endswith('.sh'): os.chmod(os.path.join(dest, 'code', n), 0o755)
print(f"deployed UnSpot map code v{man['version']:03d} ({man['made_utc']} UTC): {len(man['files'])} files, archive and files SHA-256 OK -> {os.path.join(dest, 'code')}")
