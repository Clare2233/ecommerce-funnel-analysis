import matplotlib
matplotlib.use('Agg')  # 关键：不弹窗，直接存图

import duckdb
import matplotlib.pyplot as plt

matplotlib.rcParams['font.sans-serif'] = ['SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

con = duckdb.connect('user_behavior.db')

# =========================
# 图1：漏斗图（梯形）
# =========================
funnel = con.sql("""
WITH u AS (
    SELECT
        user_id,
        MAX(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END) AS has_pv,
        MAX(CASE WHEN behavior_type IN ('cart','fav') THEN 1 ELSE 0 END) AS has_cart_fav,
        MAX(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS has_buy
    FROM valid_behavior
    GROUP BY user_id
)
SELECT SUM(has_pv) AS pv_uv,
       SUM(has_cart_fav) AS cart_fav_uv,
       SUM(has_buy) AS buy_uv
FROM u;
""").df()

stages = ['浏览', '加购/收藏', '购买']
values = [funnel['pv_uv'][0], funnel['cart_fav_uv'][0], funnel['buy_uv'][0]]
colors = ['#3498db', '#f39c12', '#2ecc71']
max_v = values[0]

fig, ax = plt.subplots(figsize=(8, 6))
for i, (s, v, c) in enumerate(zip(stages, values, colors)):
    w = v / max_v
    ax.fill_between([-w/2, w/2], i, i+1, color=c, edgecolor='white', linewidth=2)
    ax.text(0, i+0.5, f'{s}\n{int(v):,}',
            ha='center', va='center', color='white',
            fontsize=13, fontweight='bold')
    if i > 0:
        rate = v / values[i-1] * 100
        ax.text(0.6, i+0.5, f'{rate:.1f}%', va='center', fontsize=11, color='#333')

ax.set_xlim(-0.7, 0.9)
ax.set_ylim(0, 3)
ax.invert_yaxis()
ax.axis('off')
ax.set_title('用户行为漏斗（UV）', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('chart1_funnel.png', dpi=150)
plt.close()

# =========================
# 图2：品类转化率
# =========================
cat_df = con.sql("""
WITH cat AS (
    SELECT
        category_id,
        COUNT(DISTINCT CASE WHEN behavior_type = 'pv' THEN user_id END) AS pv_uv,
        COUNT(DISTINCT CASE WHEN behavior_type = 'buy' THEN user_id END) AS buy_uv
    FROM valid_behavior
    GROUP BY category_id
)
SELECT category_id, pv_uv,
       ROUND(buy_uv * 100.0 / NULLIF(pv_uv,0), 2) AS buy_rate_pct
FROM cat
WHERE pv_uv >= 100
ORDER BY pv_uv DESC
LIMIT 20;
""").df()

plt.figure(figsize=(12, 6))
colors = ['#e74c3c' if r < 3 else '#2ecc71' for r in cat_df['buy_rate_pct']]
plt.bar(cat_df['category_id'].astype(str), cat_df['buy_rate_pct'], color=colors)
plt.axhline(y=3, color='gray', linestyle='--', linewidth=1, label='3% 基准线')
plt.title('Top 20 品类购买转化率（红色为高流量低转化）')
plt.xlabel('品类 ID')
plt.ylabel('购买转化率 (%)')
plt.xticks(rotation=45)
plt.legend()
plt.tight_layout()
plt.savefig('chart2_category.png', dpi=150)
plt.close()

# =========================
# 图3：时段转化率
# =========================
hour_df = con.sql("""
SELECT
    hour,
    ROUND(
        SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) * 100.0 /
        NULLIF(SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END), 0),
    3) AS buy_rate_pct
FROM valid_behavior
GROUP BY hour
ORDER BY hour;
""").df()

plt.figure(figsize=(10, 5))
plt.plot(hour_df['hour'], hour_df['buy_rate_pct'], marker='o', color='#3498db')
plt.axvspan(18, 23, alpha=0.15, color='green', label='转化高峰')
plt.axvspan(9, 15, alpha=0.15, color='red', label='转化低谷')
plt.title('各时段购买转化率')
plt.xlabel('小时')
plt.ylabel('购买转化率 (%)')
plt.xticks(range(0, 24))
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig('chart3_hour.png', dpi=150)
plt.close()

con.close()
print('已保存 3 张图：chart1_funnel.png, chart2_category.png, chart3_hour.png')