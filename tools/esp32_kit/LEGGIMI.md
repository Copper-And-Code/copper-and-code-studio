# Il kit della ESP32-4848S040

Tutto quello che serve alla ESP32-4848S040 (uno schermo touch da 4" 480×480 con un ESP32-S3) per
fare da stazione meteo, orologio, cornice per le foto e qualche gioco, senza PC una volta
preparata. Fatto con [Copper and Code Studio](https://github.com/Copper-And-Code/copper-and-code-studio);
il firmware viene da [copper-and-code-mcu-boards](https://github.com/Copper-And-Code/copper-and-code-mcu-boards).
In inglese: [README.md](README.md). Come si usa la board una volta preparata: [GUIDA.md](GUIDA.md).

| Cartella | Cos'è | Dove va |
|---|---|---|
| `firmware/` | MicroPython 1.29 con LVGL 9.5 per questa board | nella flash della board, con `esptool` |
| `flash/` | `main.py`, che avvia la home della scheda; `boot.py` e `cac_settings.py`, per il WiFi e le impostazioni; la shell, per una board senza scheda | nella flash della board, con `mpremote` |
| `sd/` | la home e il suo menu, le app, i giochi, una cartella `photos` vuota | una scheda microSD, FAT32 |

Serve un computer con Python 3 e un cavo USB-C che porti i dati. La board si vede come porta
seriale: `/dev/ttyUSB0` su Linux, `COM3` o simile su Windows (Gestione dispositivi, "Porte"),
`/dev/cu.usbserial-…` su Mac. Qui sotto è `PORTA`.

## 1. Il firmware

Una volta per ogni board. Cancella tutto quello che c'è nella flash, anche le reti WiFi salvate.

```bash
pip install esptool
esptool.py --chip esp32s3 -p PORTA erase_flash
esptool.py --chip esp32s3 -p PORTA -b 460800 write_flash 0x0 firmware/ESP32_4848S040-v0.1.8.bin
```

(Con un esptool recente il comando è `esptool` e i sottocomandi `erase-flash` e `write-flash`.)
Senza Python, [ESP Tool](https://espressif.github.io/esptool-js/) di Espressif fa lo stesso da
Chrome o Edge: Connect, Erase Flash, poi il file all'indirizzo `0x0`.

## 2. I file della flash

```bash
pip install mpremote
cd flash
mpremote connect PORTA cp main.py boot.py cac_settings.py shell.py ansiterm.py ansifont.py OFL.txt :
mpremote connect PORTA reset
```

Si può fare anche con [Thonny](https://thonny.org/): interprete "MicroPython (ESP32)" su quella
porta, poi ogni file con **Upload to /**.

## 3. La scheda SD

Una microSD fino a 32 GB, formattata FAT32. Copia **il contenuto** di `sd/` nella cartella
principale della scheda, non la cartella stessa: in cima alla scheda devono esserci `home.json`,
`apps/`, `bin/`, `lib/` e `photos/`. Inseriscila con la board staccata.

## 4. L'accensione

Collega la board: parte il Meteo. Poi, sulla board, l'app Impostazioni (dito giù dal bordo in
alto, casetta, Settings): **WiFi** per la rete, **Schermo** per la lingua, inglese o italiano,
**Avvio** per l'app che parte all'accensione. Vedi [GUIDA.md](GUIDA.md).

## Aggiornare

Con un kit più nuovo: copia il contenuto del suo `sd/` sulla scheda, sostituendo i file. Foto e
impostazioni restano: le foto stanno in `photos/`, che il kit non riempie, e le impostazioni
nella flash. Firmware e file della flash vanno riscritti solo quando le note della release lo
dicono.

Chi ha i repository può fare lo stesso con `tools/esp32_sd.py` di Copper and Code Studio, che
scrive solo quello che è cambiato, anche dalla porta seriale con la scheda nella board.
