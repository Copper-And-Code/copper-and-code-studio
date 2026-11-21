# C64 Keyboard

A touch keyboard with the layout of the Commodore 64, for the STM32H7_CORE V1.3 at 1024×600. Each
key press and release is one byte on a UART, as a row and a column of the C64's keyboard matrix,
for a C64 emulator or a real machine behind an adapter that reads them. **Setup** chooses the
UART, baud rate, parity and stop bits, saves them on the board and sends a test byte; the page
explains the protocol.

In the simulator there is no UART: the bytes go to the console as `TX` lines.

Open `project.json` and press F5. It was checked in the simulator, not on a board.
Commodore 64 is a trademark of its owner; this project is not affiliated with it.
