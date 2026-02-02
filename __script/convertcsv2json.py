import pandas as pd
import json
import os

# 读取你上传的 CSV
df = pd.read_csv('__script/08 エンジニア技術能力表.csv')

# 清洗数据：填充合并单元格导致的空值
df['類別'] = df['類別'].ffill()
df['能力（中国語）'] = df['能力（中国語）'].ffill()

# 难度映射逻辑
level_map = {'簡単': 2, '普通': 1, '困難': 0}

skills_list = []
paths_list = []
for _, row in df.dropna(subset=['子能力（中国語）']).iterrows():
    skills_list.append({
        "path": f"{row['類別']}.{row['能力（中国語）']}",
        "name": row['子能力（中国語）'],
        "proficiency": 5,   # 固定为 5
        "priority": 2,  # 默认设为 2 
        "memo": row['分類']
    })
# for _, row in df.dropna(subset=['子能力（中国語）']).iterrows():
#     skills_list.append({
#         "id": int(row['番号']),
#         "category": row['類別'],
#         "path": f"{row['類別']}.{row['能力（中国語）']}",
#         "name": row['子能力（中国語）'],
#         "name_jp": row['サブ能力（日本語）'],
#         "proficiency": level_map.get(row['レベル'], 1),
#         "priority": 2, # 默认设为 2
#         "tags": [row['分類']]
#     })

for _, row in df.dropna(subset=['子能力（中国語）']).iterrows():
    current_data = f"{row['類別']}.{row['能力（中国語）']}"
    if current_data not in paths_list:
        paths_list.append(current_data)


# 写入文件
with open('__script/skills.json', 'w', encoding='utf-8') as f:
    json.dump(skills_list, f, indent=4, ensure_ascii=False)

with open('__script/paths.json', 'w', encoding='utf-8') as f:
    json.dump(paths_list, f, indent=4, ensure_ascii=False)

print("✅ 已成功将 164 条能力项转换")