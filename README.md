## GeoCorrection

使用 Excel 中的卫星地理高度数据与 TLE 轨道进行对比的小工具。

### 安装依赖

在项目根目录执行：

```bash
pip install -r requirements.txt
```

### 配置与使用

1. 将观测数据文件放在 `data/Beijing/ZTMK011-卫星地理高度.xlsx`（或按需修改路径）。
2. 打开 `src/correct.py`，根据实际表头修改：
   - `TIME_COLUMN`：时间列列名
   - `HEIGHT_COLUMN`：高度列列名（单位假定为米）
3. 在 `TLE_LINE1` / `TLE_LINE2` 中填入要对比的 TLE 两行字符串。
4. 在项目根目录执行：

```bash
python src/correct.py
```

脚本会在同一目录下生成一个带有 TLE 高度与高度差的 Excel 文件，文件名类似：

- `ZTMK011-卫星地理高度_tle对比结果.xlsx`

