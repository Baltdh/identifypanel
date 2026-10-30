# ROCKNIX pre-kernel recovery: evidence and safe design

Status: engineering note; no bootloader or boot files are modified by IdentifyPanel.

## Confirmed ROCKNIX behavior (documented for related RK3326 devices)

The ROCKNIX guide for the unbranded R35S/R36S family documents placing the selected panel overlay at `overlays/mipi-panel.dtbo` on the ROCKNIX boot partition. It also documents remounting `/flash` read-write, creating the overlays directory, generating an overlay with `/usr/libexec/generic-dsi/importpanel.py`, syncing, and remounting read-only.

This is evidence for the documented R35S/R36S workflow only. It does not certify that an R36S profile, a device-tree base, the partition layout, or the same bootloader commands apply to every R36H revision. IdentifyPanel must inspect the actual card before proposing any boot-script change.

## Important correction: bootcount is not a complete rollback implementation

U-Boot's bootcount facility is conditional on the bootloader build/configuration and its selected persistence backend. The documented behavior is that the counter increments across boot attempts and, when the configured limit is exceeded, U-Boot selects `altbootcmd` instead of the normal `bootcmd`. Linux-side software is normally responsible for clearing the counter after a successful boot.

That mechanism alone does not restore a file on the FAT boot partition. An `altbootcmd` that merely runs `fatload` and `fdt apply` changes the in-memory device tree for that boot; it does not replace `overlays/mipi-panel.dtbo` on disk. A true persistent rollback would need a proven write path (for example, a supported `fatwrite` command with the correct MMC device/partition and a valid backup loaded into RAM), followed by a safe continuation of the normal boot sequence. The exact U-Boot commands, addresses, environment storage, and boot flow are device-image-specific.

Do not deploy a generic `altbootcmd`, `saveenv`, `bootcount`, `fatwrite`, or replacement `boot.scr` based only on command names found in a text file. A textual reference is not proof that the running U-Boot was compiled with that command or that environment writes persist.

## Visual confirmation is a separate condition

A Linux userspace service starting is not proof that the LCD displays a usable image. A candidate can allow the kernel and userspace to boot while the panel remains black. Therefore IdentifyPanel must never clear a trial counter or mark a panel confirmed merely because Linux started.

Confirmation remains an explicit user action after visually checking the LCD. If the display is black but Linux is otherwise running, a visual confirmation interface may be inaccessible; this is one reason to design recovery around a physical reset and a bootloader-controlled fallback, but only after the actual bootloader and filesystem write path are proven.

## Candidate recovery architecture (not enabled)

1. Preserve the original boot partition and current `mipi-panel.dtbo` byte-for-byte.
2. Stage one candidate and write a durable trial record before changing the active overlay.
3. Configure a one-attempt boot counter only if the actual U-Boot supports the required counter, persistent environment backend, and tested semantics.
4. On a subsequent reset without manual visual confirmation, the bootloader fallback must restore the backup file on the boot filesystem, not merely apply the backup in RAM.
5. The fallback must then continue through the original boot path with the restored overlay.
6. Only an explicit visual confirmation clears the pending trial state.
7. If any prerequisite is absent, retain the current manual rollback path and provide PC-based recovery from a copy of the boot partition.

This architecture is a design target, not a claim that the user's R36H bootloader supports it.

## Required evidence from the exact R36H card

Before implementing pre-kernel recovery, collect:

- Full listing and filesystem type/label of all SD partitions.
- Complete boot configuration and scripts, including `extlinux.conf`, `boot.ini`, `boot.scr`, `uEnv.txt`, if present.
- Exact active DTB path/name and overlay path/name.
- The actual boot command path and MMC device/partition numbering.
- U-Boot version and environment location/backend, if safely readable.
- Whether `bootcount`, `bootlimit`, `altbootcmd`, `saveenv`, `fatload`, `fatwrite` (or equivalent filesystem write command) are actually available and persistent.
- A complete backup image of the SD card before any experiment.

The current `boot-info` command is read-only and only scans known text boot files for useful references. Its output is an inventory aid, not a capability test.

## Safe next step

Run the current read-only diagnostic against the mounted ROCKNIX boot partition:

```sh
python3 identifypanel.py boot-info --boot /CAMINHO/DA/PARTICAO-ROCKNIX
```

Also provide the full directory listing of the partition root and the contents of any boot configuration files it reports. Do not run any command that edits `boot.ini`, `boot.scr`, `extlinux.conf`, the DTB, or U-Boot environment yet.

## References

- ROCKNIX, Game Console R35S/R36S: https://rocknix.org/devices/unbranded/game-console-r35s-r36s/
- U-Boot, Boot Count Limit: https://docs.u-boot.org/en/v2026.04/api/bootcount.html
- ROCKNIX X35S notes on `extlinux.conf` and `FDTOVERLAYS` (a different device; useful only as an example of a boot configuration): https://rocknix.org/devices/powkiddy/x35s/
