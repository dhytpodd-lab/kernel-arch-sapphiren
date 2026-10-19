#!/usr/bin/env python3
import sys
import re

print("Patching drivers/i2c/busses/i2c-qcom-geni.c...")
with open("drivers/i2c/busses/i2c-qcom-geni.c", "r", encoding="utf-8") as f:
    s = f.read()

# 1. Fix clk_get_rate NULL pointer dereference on ACPI
clk_pattern = r"if\s*\(\s*clk_get_rate\s*\(\s*gi2c->se\.clk\s*\)\s*=="
clk_replacement = "if (!IS_ERR_OR_NULL(gi2c->se.clk) && clk_get_rate(gi2c->se.clk) =="
s, count = re.subn(clk_pattern, clk_replacement, s)
assert count >= 1, f"clk_get_rate pattern not found in i2c-qcom-geni.c (count={count})"
print(f"  [+] Patched clk_get_rate check ({count} occurrence)")

# 2. Force FIFO mode on ACPI
if "if (gi2c->dev_data->no_dma_support) {" in s:
    s = s.replace(
        "if (gi2c->dev_data->no_dma_support) {",
        "if (gi2c->dev_data->no_dma_support || has_acpi_companion(gi2c->se.dev)) {"
    )
    print("  [+] Patched no_dma_support check")
elif "fifo_disable = readl_relaxed(gi2c->se.base + GENI_IF_DISABLE_RO) & FIFO_IF_DISABLE;" in s:
    s = s.replace(
        "fifo_disable = readl_relaxed(gi2c->se.base + GENI_IF_DISABLE_RO) & FIFO_IF_DISABLE;",
        "fifo_disable = has_acpi_companion(gi2c->se.dev) ? false : (readl_relaxed(gi2c->se.base + GENI_IF_DISABLE_RO) & FIFO_IF_DISABLE); if (has_acpi_companion(gi2c->se.dev)) gi2c->no_dma = true;"
    )
    print("  [+] Patched fifo_disable check")

# 3. Safe tx_depth fallback
tx_depth_pattern = r"if\s*\(\s*!tx_depth\s*&&\s*gi2c->se\.core_clk\s*\)\s*\n\s*tx_depth\s*=\s*gi2c->dev_data->tx_fifo_depth;"
tx_depth_replacement = "if (!tx_depth)\n\t\t\ttx_depth = gi2c->dev_data->tx_fifo_depth ? : 16;"
s, count = re.subn(tx_depth_pattern, tx_depth_replacement, s)
if count > 0:
    print("  [+] Patched tx_depth check")

# 4. Informative dev_info log
s = s.replace(
    'dev_dbg(dev, "Geni-I2C adaptor successfully added\\n");',
    'dev_info(dev, "Geni-I2C adapter %s successfully added\\n", gi2c->adap.name);'
)
print("  [+] Patched adapter dev_info log")

with open("drivers/i2c/busses/i2c-qcom-geni.c", "w", encoding="utf-8") as f:
    f.write(s)

print("Patching drivers/soc/qcom/qcom-geni-se.c...")
with open("drivers/soc/qcom/qcom-geni-se.c", "r", encoding="utf-8") as f:
    s2 = f.read()

# 5. Fix devm_clk_get in geni_se_resources_init on ACPI
start_marker = 'se->clk = devm_clk_get(se->dev, "se");'
end_marker = '"Failed to get SE clk\\n");'

assert start_marker in s2, "start_marker not found in qcom-geni-se.c"
assert end_marker in s2, "end_marker not found in qcom-geni-se.c"

idx_start = s2.index(start_marker) + len(start_marker)
idx_end = s2.index(end_marker, idx_start) + len(end_marker)

replacement = """
\tif (IS_ERR(se->clk)) {
\t\tif (has_acpi_companion(se->dev))
\t\t\tse->clk = NULL;
\t\telse
\t\t\treturn dev_err_probe(se->dev, PTR_ERR(se->clk),
\t\t\t\t\t     "Failed to get SE clk\\n");
\t}"""

s2 = s2[:idx_start] + replacement + s2[idx_end:]
print("  [+] Patched devm_clk_get error handling via slice")

with open("drivers/soc/qcom/qcom-geni-se.c", "w", encoding="utf-8") as f:
    f.write(s2)

print("ALL GENI I2C ACPI PATCHES APPLIED SUCCESSFULLY!")
