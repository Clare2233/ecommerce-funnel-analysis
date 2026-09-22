import duckdb

# 数据库文件会生成在当前目录
con = duckdb.connect('user_behavior.db')

# =========================
# 1. 从 CSV 建原始表（只在第一次运行时需要）
# =========================
print('开始读取 CSV，请等待 ...')

con.sql("""
CREATE OR REPLACE TABLE raw_behavior AS
SELECT *
FROM read_csv(
    'D:/用户行为数据集/UserBehavior.csv',
    header = false,
    columns = {
        'user_id': 'BIGINT',
        'item_id': 'BIGINT',
        'category_id': 'BIGINT',
        'behavior_type': 'VARCHAR',
        'timestamp': 'BIGINT'
    }
);
""")

print('原始表行数：', con.sql("SELECT COUNT(*) FROM raw_behavior").fetchone()[0])

# =========================
# 2. 按用户采样 5 万
# =========================
con.sql("""
CREATE OR REPLACE TABLE sample_users AS
SELECT user_id
FROM (SELECT DISTINCT user_id FROM raw_behavior)
USING SAMPLE 50000 ROWS (reservoir, 42);
""")

print('采样用户数：', con.sql("SELECT COUNT(*) FROM sample_users").fetchone()[0])

# =========================
# 3. 保留这些用户的全部行为 + 清洗
# =========================
con.sql("""
CREATE OR REPLACE TABLE clean_behavior AS
SELECT
    user_id,
    item_id,
    category_id,
    behavior_type,
    timestamp,
    to_timestamp(timestamp) + INTERVAL 8 HOUR AS datetime,
    (to_timestamp(timestamp) + INTERVAL 8 HOUR)::DATE AS date,
    EXTRACT(HOUR FROM to_timestamp(timestamp) + INTERVAL 8 HOUR) AS hour
FROM raw_behavior
WHERE user_id IN (SELECT user_id FROM sample_users);
""")

con.sql("CREATE OR REPLACE TABLE clean_behavior AS SELECT DISTINCT * FROM clean_behavior;")
print('去重后行数：', con.sql("SELECT COUNT(*) FROM clean_behavior").fetchone()[0])

# =========================
# 4. 过滤行为数 < 5 的用户
# =========================
con.sql("""
CREATE OR REPLACE TABLE valid_behavior AS
SELECT *
FROM clean_behavior
WHERE user_id IN (
    SELECT user_id FROM clean_behavior
    GROUP BY user_id
    HAVING COUNT(*) >= 5
);
""")

print('过滤后行数：', con.sql("SELECT COUNT(*) FROM valid_behavior").fetchone()[0])
print('过滤后用户数：', con.sql("SELECT COUNT(DISTINCT user_id) FROM valid_behavior").fetchone()[0])

# =========================
# 5. 检查
# =========================
print('\n===== 行为类型分布 =====')
print(con.sql("""
SELECT behavior_type, COUNT(*) AS cnt
FROM valid_behavior
GROUP BY behavior_type
ORDER BY cnt DESC
""").df())

print('\n===== 时间范围 =====')
print(con.sql("SELECT MIN(datetime), MAX(datetime) FROM valid_behavior").df())

# =========================
# 6. Day 2：整体漏斗
# =========================
print('\n===== 整体漏斗 =====')
print(con.sql("""
WITH u AS (
    SELECT
        user_id,
        MAX(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END) AS has_pv,
        MAX(CASE WHEN behavior_type IN ('cart','fav') THEN 1 ELSE 0 END) AS has_cart_fav,
        MAX(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS has_buy
    FROM valid_behavior
    GROUP BY user_id
)
SELECT
    SUM(has_pv) AS pv_uv,
    SUM(has_cart_fav) AS cart_fav_uv,
    SUM(has_buy) AS buy_uv,
    ROUND(SUM(has_cart_fav) * 100.0 / NULLIF(SUM(has_pv),0), 2) AS pv_to_cart_pct,
    ROUND(SUM(has_buy) * 100.0 / NULLIF(SUM(has_cart_fav),0), 2) AS cart_to_buy_pct,
    ROUND(SUM(has_buy) * 100.0 / NULLIF(SUM(has_pv),0), 2) AS pv_to_buy_pct
FROM u;
""").df())

con.close()
print('\n完成。数据库已保存为 user_behavior.db')