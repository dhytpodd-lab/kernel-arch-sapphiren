#!/usr/bin/env python3
import sys
import re
import subprocess

print("=== Starting GENI I2C ACPI Patcher ===")

# ---------------------------------------------------------------------------
# Patch drivers/i2c/busses/i2c-qcom-geni.c
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

print("\n=== All patches applied! Running git diff ===")
try:
    diff_out = subprocess.check_output(["git", "diff", path_i2c]).decode("utf-8")
    print(diff_out)
except Exception as e:
    print("Could not run git diff:", e)

print("=== Patching complete! ===")
