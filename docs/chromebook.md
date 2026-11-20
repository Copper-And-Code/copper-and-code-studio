# Running on a Chromebook

A Chromebook can run the Linux AppImage of Copper and Code Studio inside the Linux development
environment of ChromeOS. No change to ChromeOS itself is needed.

## What is needed

- A Chromebook with an **Intel or AMD processor**: the AppImage is built for x86-64 and does not
  run on ARM Chromebooks.
- The **Linux development environment** turned on, with a container on **Debian 13 (trixie)** or
  newer. The AppImage needs glibc 2.38 or later, and Debian 12 has 2.36.

## Steps

1. Turn on Linux: **Settings → About ChromeOS → Developers → Linux development environment →
   Set up**. ChromeOS opens a terminal when it is ready.
2. Check the version of the container, in that terminal:

   ```bash
   grep PRETTY /etc/os-release; ldd --version | head -1
   ```

   It should say Debian 13 and glibc 2.38 or later. On Debian 12, upgrade the container to
   Debian 13 first, or run the IDE [from the sources](https://github.com/Copper-And-Code/copper-and-code-studio/blob/main/docs/development.md) with Python 3.12.
3. Download `Copper_and_Code_Studio-x86_64.AppImage` from the
   [latest release](https://github.com/Copper-And-Code/copper-and-code-studio/releases/latest) and, in the
   Files app, move it from **Downloads** to **Linux files**.
4. Make it executable and start it, in the terminal:

   ```bash
   chmod +x Copper_and_Code_Studio-x86_64.AppImage
   ./Copper_and_Code_Studio-x86_64.AppImage
   ```

   If it stops with an error about `libfuse.so.2`, either install FUSE 2 with
   `sudo apt install libfuse2t64`, or start it without FUSE:
   `./Copper_and_Code_Studio-x86_64.AppImage --appimage-extract-and-run`.
5. To check the installation, run the self-test: the IDE drives itself and ends with
   `RESULT: PASSED`.

   ```bash
   ./Copper_and_Code_Studio-x86_64.AppImage selftest
   ```

## A board over USB

The Linux container does not see USB devices until ChromeOS shares them: plug in the board, then
**Settings → About ChromeOS → Developers → Linux development environment → Manage USB devices**,
and turn on the board. The serial port then appears in the IDE, usually as `/dev/ttyACM0` or
`/dev/ttyUSB0`. The sharing lasts while the board stays plugged in.

If the IDE cannot open the port, the Linux user has no permission on it. Add the user to the
`dialout` group once:

```bash
sudo usermod -aG dialout $USER
```

then restart Linux from the shelf menu of the terminal (**Shut down Linux**) and open the terminal
again. For a quick try without restarting, `sudo chmod a+rw /dev/ttyACM0` opens the port until the
board is unplugged.

## What has been verified

On 14 November 2026 the author installed the AppImage of 0.7.0 on a Chromebook, in the Linux
development environment on Debian 13 (trixie), glibc 2.41, and used it: the simulator with touch
and sound, and a board over USB, shared with Linux and opened both after `chmod` on the port
and through the `dialout` group. The self-test passed.
[What is verified](status.md) is kept up to date.
