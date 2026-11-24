# FTP Server

The files of the board for a PC on the same WiFi network: the flash and the SD card, or only the
card, or only the apps installed by Copper and Code Studio, with FileZilla, WinSCP, Windows
Explorer, the file manager of Linux or macOS, `curl`, `lftp` or `ftp`. Copy, download, rename,
delete, make and remove folders, resume a broken transfer. For the ESP32-4848S040 (480×480).

The screen shows the address, the user `mpy` and the password, who is connected, the file moving
and its speed, the free space and a log. The password is made at the first start and kept in
`cac_settings.json`, section `ftp`, with the folder the clients see: a client that saved them
connects again after a restart. **New password** makes another one and logs everyone out.

The network is one of those saved by the [Settings](../settings/README.md) example: the app
connects with `cac_settings.connect()` when it starts.

The server (`ftp_server`) is polled from the screen's timer every 20 ms: commands are answered at
once, files move in pieces for 10 ms of each tick, so the screen keeps its pace during a long
copy. Passive (`PASV`, `EPSV`) and active (`PORT`, `EPRT`) data connections, listings as `ls -l`
(`LIST`) and with exact times (`MLSD`), `REST`, `SIZE`, `MDTM`. Up to three clients at once: the
network stack of the ESP32 has few sockets.

**Security.** Plain FTP: the password and the files cross the network in clear. Use it on your
own network, and switch it off when you are done. Three wrong passwords close the connection;
active connections go only to the client's own address.

## Try it

- On the board: save a network with the Settings example, then run this app; the screen shows
  `ftp://` and the address. From the PC: `curl --user mpy:PASSWORD ftp://ADDRESS/` lists the
  files, `curl -T photo.bin --user mpy:PASSWORD ftp://ADDRESS/sd/photos/` sends one.
- In the simulator there is no network: the screen shows made-up clients.

The server is also run by `tests/test_ftp_server_example.py`, in CPython against Python's
`ftplib`. It is ported from the FTP Server example of the author's Linux boards.

| Module | What it does |
|---|---|
| `ftp_server` | the FTP server: sessions, commands, data connections, transfers in pieces |
| `ftp_app` | the screen: address, password, folder, clients, transfer, storage, log |
| `cac_settings` | the shared settings of the examples, as in [Settings](../settings/README.md) |

On the ESP32-4848S040 it can be started from the board's home menu: see [the home menu of the board](../settings/README.md#the-home-menu-of-the-board).
Its screen is in English or Italian, the language chosen on the Display page of Settings; the
log stays in English, as the commands of FTP it shows.
