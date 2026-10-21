# kernel-arch-sapphiren

Arch Linux ARM mainline kernel with full ACPI hardware support for **Xiaomi Redmi Note 13 4G / NFC (`sapphiren` / `sapphire`)** running Qualcomm Snapdragon 685 (SM6225 / Bengal / Khaje) under Project Silicium UEFI.

---

## 🚀 Included Hardware Fixes & Features

1. **UFS Storage (QCOM UFS)**:
   - Fixed ACPI reset controller initialization (`rcdev.dev = dev`).
   - Bypassed Device Tree interconnect dependencies under ACPI (`ufs_qcom_icc_init`).
   - Bypassed platform PHY power-up sequence under ACPI (`ufs_qcom_power_up_sequence`).
   - *Patch: `0006-ufs-qcom-fix-acpi-boot.patch`*

2. **USB Controller (DWC3 QCOM Host Mode)**:
   - Restored Qualcomm DWC3 ACPI driver binding on SM6225.
   - Released umbrella ACPI memory resource reservation to avoid `-EBUSY` conflict with child core.
   - Forced Host mode (`dr_mode = "host"`) under ACPI with VBUS override.
   - Clamped max speed to High-Speed (480 Mbps) and selected UTMI clock source (fixes USB transfer error `-71`).
   - Tuned Femto PHY registers (HS swing, pre-emphasis, and output impedance) for hardware signal stability.
   - *Patch: `0007-dwc3-qcom-restore-acpi-support.patch`*

3. **GENI I2C Serial Engine (ACPI QCOM0220)**:
   - Prevented kernel panic on ACPI due to missing `se` clock lookup.
   - Dynamically ungates GCC QUP0 AHB, Core, and SE2 clocks via memory-mapped registers.
   - Enforced safe FIFO mode on ACPI where GSI/GPI DMA engines are unavailable.
   - Prevented NULL pointer dereference in `geni_se_get_qup_hw_version`.
   - *Patch: `patch_geni_i2c.py`*

4. **Built-in Drivers (`config`)**:
   - `CONFIG_SCSI_UFS_QCOM=y` (internal UFS storage)
   - `CONFIG_USB_DWC3=y`, `CONFIG_USB_DWC3_QCOM=y` (USB controller)
   - `CONFIG_USB_NET_DRIVERS=y`, `CONFIG_USB_RNDIS_HOST=y`, `CONFIG_USB_NET_CDCETHER=y` (USB tethering network)
   - `CONFIG_DRM_SIMPLEDRM=y` (continuous splash display output)
   - `CONFIG_I2C_CHARDEV=y` (`/dev/i2c-0` access)
   - `CONFIG_TOUCHSCREEN_EDT_FT5X06=y`, `CONFIG_TOUCHSCREEN_GOODIX=y` (touchscreen support)

---

## 🛠️ Generic Partitioning & Installation Guide

The UEFI boot manager (BDS) and this kernel are **completely independent of fixed partition numbers** (such as `/dev/sda19` or `/dev/sda20`). Any user can create partitions of their desired size and order.

### 1. Disk Partitioning

You can use `parted` or `gdisk` (from TWRP/recovery or an existing Linux environment) to create two partitions on the internal storage:

1. **ESP / Boot Partition**:
   - Recommended size: 512 MB – 1 GB.
   - Filesystem: FAT32.
   - Label: `ARCH_BOOT`
   ```bash
   mkfs.vfat -F 32 -n ARCH_BOOT /dev/sdaX
   ```
   *(replace `sdaX` with your chosen partition, e.g. `sda19`)*

2. **Root Partition**:
   - Recommended size: 10 GB or more.
   - Filesystem: ext4.
   - Label: `ARCH_ROOT`
   ```bash
   mkfs.ext4 -L ARCH_ROOT /dev/sdaY
   ```
   *(replace `sdaY` with your chosen partition, e.g. `sda20`)*

---

### 2. Installing Arch Linux ARM

Mount the partitions using their labels:

```bash
mkdir -p /mnt/arch
mount /dev/disk/by-label/ARCH_ROOT /mnt/arch
mkdir -p /mnt/arch/boot
mount /dev/disk/by-label/ARCH_BOOT /mnt/arch/boot

# Extract Arch Linux ARM rootfs
cd /mnt/arch
tar -xpf /path/to/ArchLinuxARM-aarch64-latest.tar.gz

# Configure /etc/fstab using labels (independent of partition numbers!)
cat << 'EOF' > /mnt/arch/etc/fstab
# <file system>        <dir>  <type>  <options>         <dump> <pass>
LABEL=ARCH_ROOT        /      ext4    defaults,noatime  0      1
LABEL=ARCH_BOOT        /boot  vfat    defaults          0      2
EOF
```

---

### 3. Installing Kernel & Boot Files

Copy `vmlinuz-linux` (from GitHub Releases) and your generated `initramfs-linux.img` directly to the boot partition:

```bash
cp vmlinuz-linux /mnt/arch/boot/
cp initramfs-linux.img /mnt/arch/boot/
```

---

### 4. Boot Options (`cmdline.txt`)

UEFI automatically searches for `cmdline.txt` on the boot partition:

- **Automatic Default (no file required)**:
  If `cmdline.txt` is omitted, UEFI automatically boots with:
  ```text
  console=tty0 earlycon=efifb,ram keep_bootcon root=LABEL=ARCH_ROOT rw rootwait acpi=force clk_ignore_unused pd_ignore_unused ignore_loglevel systemd.journald.forward_to_console=1
  ```
  *(Any root partition labeled `ARCH_ROOT` will boot automatically without any configuration!)*

- **Custom Configuration**:
  If you want to use custom kernel flags, UUIDs, or different root locations, simply create `/boot/cmdline.txt`:
  ```text
  console=tty0 earlycon=efifb,ram keep_bootcon root=LABEL=ARCH_ROOT rw rootwait acpi=force clk_ignore_unused pd_ignore_unused ignore_loglevel systemd.journald.forward_to_console=1
  ```
  *(Both ASCII/UTF-8 and UTF-16 text encodings are supported).*

---

## 📦 Building from Source

This repository builds the kernel via GitHub Actions on every push to `main`. Artifacts are published under **Releases**.

To build locally with Arch Linux `makepkg`:
```bash
makepkg -s
```
