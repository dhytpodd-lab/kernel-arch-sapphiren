#!/usr/bin/env python3
import sys
import re
import subprocess

print("=== Starting GENI I2C ACPI Patcher ===")

# ---------------------------------------------------------------------------
# 1. Patch drivers/i2c/busses/i2c-qcom-geni.c
# ---------------------------------------------------------------------------
path_i2c = "drivers/i2c/busses/i2c-qcom-geni.c"
print(f"Patching {path_i2c}...")
with open(path_i2c, "r", encoding="utf-8") as f:
    s = f.read()

# 1. Fix clk_get_rate NULL pointer dereference on ACPI
clk_pattern = r"if\s*\(\s*clk_get_rate\s*\(\s*gi2c->se\.clk\s*\)\s*=="
clk_replacement = "if (!IS_ERR_OR_NULL(gi2c->se.clk) && clk_get_rate(gi2c->se.clk) =="
s, count = re.subn(clk_pattern, clk_replacement, s)
assert count >= 1, f"clk_get_rate pattern not found in {path_i2c}"
print(f"  [+] Patched clk_get_rate check ({count} occurrence)")

# 2. Fix devm_clk_get error check on ACPI (set gi2c->se.clk = NULL instead of leaving ERR_PTR)
clk_err_pattern = r'(gi2c->se\.clk\s*=\s*devm_clk_get\s*\([^;]+;\s*if\s*\(\s*IS_ERR\s*\(\s*gi2c->se\.clk\s*\)\s*&&\s*!has_acpi_companion\s*\([^)]+\)\s*\)\s*return\s+PTR_ERR\s*\(\s*gi2c->se\.clk\s*\)\s*;)'
m = re.search(clk_err_pattern, s)
if m:
    replacement = """gi2c->se.clk = devm_clk_get(dev, "se");
\tif (IS_ERR(gi2c->se.clk)) {
\t\tif (has_acpi_companion(dev))
\t\t\tgi2c->se.clk = NULL;
\t\telse
\t\t\treturn PTR_ERR(gi2c->se.clk);
\t}"""
    s = s[:m.start()] + replacement + s[m.end():]
    print("  [+] Patched devm_clk_get error handling on ACPI")
else:
    print("  [!] clk_err_pattern not found via regex, trying literal replace...")
    orig_clk = '\tgi2c->se.clk = devm_clk_get(dev, "se");\n\tif (IS_ERR(gi2c->se.clk) && !has_acpi_companion(dev))\n\t\treturn PTR_ERR(gi2c->se.clk);'
    new_clk = '\tgi2c->se.clk = devm_clk_get(dev, "se");\n\tif (IS_ERR(gi2c->se.clk)) {\n\t\tif (has_acpi_companion(dev))\n\t\t\tgi2c->se.clk = NULL;\n\t\telse\n\t\t\treturn PTR_ERR(gi2c->se.clk);\n\t}'
    assert orig_clk in s, "devm_clk_get pattern not found in i2c-qcom-geni.c"
    s = s.replace(orig_clk, new_clk)
    print("  [+] Patched devm_clk_get error handling via literal match")

# 3. Force FIFO mode on ACPI
if "if (desc && desc->no_dma_support) {" in s:
    s = s.replace(
        "if (desc && desc->no_dma_support) {",
        "if (has_acpi_companion(dev) || (desc && desc->no_dma_support)) {"
    )
    print("  [+] Patched FIFO mode check (desc && desc->no_dma_support)")
elif "if (gi2c->dev_data->no_dma_support) {" in s:
    s = s.replace(
        "if (gi2c->dev_data->no_dma_support) {",
        "if (has_acpi_companion(dev) || gi2c->dev_data->no_dma_support) {"
    )
    print("  [+] Patched FIFO mode check (dev_data->no_dma_support)")
else:
    print("  [!] Could not find FIFO mode check condition!")

# 4. Safe tx_depth fallback
tx_depth_pattern = r"if\s*\(\s*!tx_depth\s*&&\s*desc\s*\)\s*\n\s*tx_depth\s*=\s*desc->tx_fifo_depth;"
tx_depth_replacement = "if (!tx_depth)\n\t\t\ttx_depth = desc ? desc->tx_fifo_depth : 16;"
s, count = re.subn(tx_depth_pattern, tx_depth_replacement, s)
if count > 0:
    print("  [+] Patched tx_depth check (desc)")
else:
    tx_depth_pattern2 = r"if\s*\(\s*!tx_depth\s*&&\s*gi2c->se\.core_clk\s*\)\s*\n\s*tx_depth\s*=\s*gi2c->dev_data->tx_fifo_depth;"
    tx_depth_replacement2 = "if (!tx_depth)\n\t\t\ttx_depth = gi2c->dev_data->tx_fifo_depth ? : 16;"
    s, count = re.subn(tx_depth_pattern2, tx_depth_replacement2, s)
    if count > 0:
        print("  [+] Patched tx_depth check (dev_data)")

# 5. Informative dev_info log
s = s.replace(
    'dev_dbg(dev, "Geni-I2C adaptor successfully added\\n");',
    'dev_info(dev, "Geni-I2C adapter %s successfully added\\n", gi2c->adap.name);'
)
print("  [+] Patched adapter dev_info log")

with open(path_i2c, "w", encoding="utf-8") as f:
    f.write(s)

# ---------------------------------------------------------------------------
# 2. Patch drivers/soc/qcom/qcom-geni-se.c
# ---------------------------------------------------------------------------
path_se = "drivers/soc/qcom/qcom-geni-se.c"
print(f"\nPatching {path_se}...")
with open(path_se, "r", encoding="utf-8") as f:
    s2 = f.read()

# 6. Fix geni_se_get_qup_hw_version NULL pointer dereference on ACPI (where se->wrapper is NULL)
orig_hw_ver = """u32 geni_se_get_qup_hw_version(struct geni_se *se)
{
\tstruct geni_wrapper *wrapper = se->wrapper;

\treturn readl_relaxed(wrapper->base + QUPV3_HW_VER_REG);
}"""

new_hw_ver = """u32 geni_se_get_qup_hw_version(struct geni_se *se)
{
\tstruct geni_wrapper *wrapper = se->wrapper;

\tif (!wrapper || !wrapper->base)
\t\treturn 0;

\treturn readl_relaxed(wrapper->base + QUPV3_HW_VER_REG);
}"""

assert orig_hw_ver in s2, f"geni_se_get_qup_hw_version pattern not found in {path_se}"
s2 = s2.replace(orig_hw_ver, new_hw_ver)
print("  [+] Patched geni_se_get_qup_hw_version wrapper null check")

# 7. Safe DMA unprep wrappers
orig_tx_dma = """void geni_se_tx_dma_unprep(struct geni_se *se, dma_addr_t iova, size_t len)
{
\tstruct geni_wrapper *wrapper = se->wrapper;

\tif (!dma_mapping_error(wrapper->dev, iova))"""

new_tx_dma = """void geni_se_tx_dma_unprep(struct geni_se *se, dma_addr_t iova, size_t len)
{
\tstruct geni_wrapper *wrapper = se->wrapper;

\tif (!wrapper || !wrapper->dev)
\t\treturn;

\tif (!dma_mapping_error(wrapper->dev, iova))"""

if orig_tx_dma in s2:
    s2 = s2.replace(orig_tx_dma, new_tx_dma)
    print("  [+] Patched geni_se_tx_dma_unprep wrapper null check")

orig_rx_dma = """void geni_se_rx_dma_unprep(struct geni_se *se, dma_addr_t iova, size_t len)
{
\tstruct geni_wrapper *wrapper = se->wrapper;

\tif (!dma_mapping_error(wrapper->dev, iova))"""

new_rx_dma = """void geni_se_rx_dma_unprep(struct geni_se *se, dma_addr_t iova, size_t len)
{
\tstruct geni_wrapper *wrapper = se->wrapper;

\tif (!wrapper || !wrapper->dev)
\t\treturn;

\tif (!dma_mapping_error(wrapper->dev, iova))"""

if orig_rx_dma in s2:
    s2 = s2.replace(orig_rx_dma, new_rx_dma)
    print("  [+] Patched geni_se_rx_dma_unprep wrapper null check")

with open(path_se, "w", encoding="utf-8") as f:
    f.write(s2)

print("\n=== All patches applied! Running git diff ===")
try:
    diff_out = subprocess.check_output(["git", "diff", path_i2c, path_se]).decode("utf-8")
    print(diff_out)
except Exception as e:
    print("Could not run git diff:", e)

print("=== Patching complete! ===")
