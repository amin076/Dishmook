# Kaggle GPU: first Qwen conjecture campaign

Run these cells in a Kaggle notebook with a GPU accelerator enabled.

```sh
!git clone --branch experiment/qwen-conjecture-agent https://github.com/amin076/Dishmook.git
%cd Dishmook
!pip install -q -e ".[qwen]"
!python experiments/qwen_conjectures_100.py --per-parent 20 --output /kaggle/working/qwen_conjectures_100.jsonl
```

Then inspect the file before any Gareen integration:

```python
import json
p="/kaggle/working/qwen_conjectures_100.jsonl"
rows=[json.loads(x) for x in open(p,encoding="utf-8")]
print("count",len(rows))
for r in rows[:20]:
    print(r["parent_id"], r["statement"], r["mutation_kind"], r["claimed_distance"])
```

Download `qwen_conjectures_100.jsonl` from Kaggle output. These records are
unverified model suggestions only. Do not treat them as theorems.
