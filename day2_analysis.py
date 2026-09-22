import duckdb

con = duckdb.connect('user_behavior.db')

print('===== 时间戳分布 =====')
print(con.sql("""
SELECT
    CASE
        WHEN timestamp BETWEEN 1511625600 AND 1512403199 THEN '正常'
        ELSE '异常'
    END AS flag,
    COUNT(*) AS cnt
FROM raw_behavior
GROUP BY flag;
""").df())

# 修正时间范围
con.sql("""
CREATE OR REPLACE TABLE valid_behavior AS
SELECT * FROM valid_behavior
WHERE timestamp BETWEEN 1511625600 AND 1512403199;
""")

print('\n===== 修正后漏斗 =====')
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

print('\n===== 分品类 Top 20 =====')
print(con.sql("""
WITH cat AS (
    SELECT
        category_id,
        COUNT(DISTINCT CASE WHEN behavior_type = 'pv' THEN user_id END) AS pv_uv,
        COUNT(DISTINCT CASE WHEN behavior_type IN ('cart','fav') THEN user_id END) AS cart_fav_uv,
        COUNT(DISTINCT CASE WHEN behavior_type = 'buy' THEN user_id END) AS buy_uv
    FROM valid_behavior
    GROUP BY category_id
)
SELECT *,
    ROUND(buy_uv * 100.0 / NULLIF(pv_uv,0), 2) AS buy_rate_pct
FROM cat
WHERE pv_uv >= 100
ORDER BY pv_uv DESC
LIMIT 20;
""").df())

print('\n===== 分时段 =====')
print(con.sql("""
SELECT
    hour,
    SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END) AS pv_cnt,
    SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS buy_cnt,
    ROUND(
        SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) * 100.0 /
        NULLIF(SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END), 0),
    3) AS buy_rate_pct
FROM valid_behavior
GROUP BY hour
ORDER BY hour;
""").df())

con.close()