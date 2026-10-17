# Required feature: stock firmware backup before first install

Status: **not implemented**. The user requires reading the firmware actually
installed on an untouched RD-6 before writing any custom firmware. Neither a
copy of a supplied SysEx file nor a readback command added by custom firmware
meets that first-install requirement.

## Evidence checked on2026-10-16

- Stock application1.0.5 SysEx command dispatch was inspected. Its known
  responses provide identity/version, settings and patterns; no generic
  firmware/flash-read command was identified.
- The pattern response validates two banks and16 patterns and serializes22
  bytes of pattern data. It is not a flash dump.
- The verified update handshake and0A/0B transactions write firmware. An ACK
  or version reply is not firmware readback.
- Available stock update files omit the first0x2800 flash bytes, which contain
  the bootloader. Its command handling cannot be audited from those files.
- Windows records RD-6 USB IDs1397:122C and1397:122D. Cached interface metadata
  for both uses audio class01/subclass01 with the usbaudio driver; no separate
  standard DFU interface was found in that metadata. This does not prove that
  undocumented readback is impossible or exhaust all USB configurations.

## What is still needed

A documented or independently verified stock bootloader read command, or a
verified hardware-debug readout path. Hardware debugging requires physical
access and checking protection state; it is not a browser-only solution.
Do not run a protection-removal/unlock operation as a backup method: such an
operation may erase data. No such operation was performed here.

No firmware was written, no guessed SysEx commands were sent and the unit
was not put into update mode during this investigation. The attached unit
still runs TEST12, and is not an untouched-stock first-install test unit.

The current save/open controls handle supplied files only. Automatic stock
readback must not be advertised as available until actual bytes can be read,
verified, saved and shown to form a usable restore image.

## Next investigation step

A private TEST13 diagnostic has been built for the already-custom test unit.
It adds a stopped-only fixed-range read of the untouched10KB bootloader, with
chunk echoes, checksums and a host-side comparison of two full reads. The
purpose is to obtain the missing bootloader code for analysis of its stock
USB commands. The diagnostic itself does not solve first-install backup:
installing it would change the application first. Physical installation/read
remain pending. TEST12 is kept as the known working restore target. Neither
the diagnostic full image nor any bootloader dump is published here.
