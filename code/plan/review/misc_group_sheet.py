# Puts the tiles of misc_group_view.py on sheets for the owner: misc_group_sheet.py tiles_dir out_prefix first last [per_sheet=5]
import sys, os
from PIL import Image
d, pref, a, b = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]); K = int(sys.argv[5]) if len(sys.argv) > 5 else 5
nums = [n for n in range(a, b + 1) if os.path.exists(os.path.join(d, f'tile_{n:02d}.png'))]
for s in range(0, len(nums), K):
    ims = [Image.open(os.path.join(d, f'tile_{n:02d}.png')) for n in nums[s:s + K]]
    W = max(i.width for i in ims); H = sum(i.height + 10 for i in ims)
    sh = Image.new('RGB', (W, H), (235, 235, 235)); y = 0
    for i in ims: sh.paste(i, (0, y)); y += i.height + 10
    out = f'{pref}_{nums[s]}-{nums[min(s + K, len(nums)) - 1]}.png'; sh.save(out); print(out, sh.size)
