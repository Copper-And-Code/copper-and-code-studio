# Copper and Code Studio

**Copper and Code Studio** — a visual GUI builder for MicroPython and LVGL. Formerly LVGL MPY Studio.

Copper and Code Studio is a desktop IDE for building graphical interfaces with LVGL 9.5 and MicroPython. Design pages visually, write event handlers in Python, and run the application in a simulator that uses the real LVGL library.

The same project can be uploaded to a supported board, exported as portable C sources, built as a standalone application, or published in the browser through WebAssembly. AI agents can perform the complete workflow through the MCP server.

On the PC the same MicroPython is a program of the operating system: an application can run commands, read and write files, open sockets and call C libraries. See [Files, commands and the network on the PC](pc-programs.md).

**The whole IDE in the browser** is a work in progress, experimental but already usable: [open it](https://copper-and-code.github.io/copper-and-code-studio-web/), nothing to install. It is built in [a repository of its own](https://github.com/Copper-And-Code/copper-and-code-studio-web) that reuses the core of this one.

![The IDE with an industrial monitor running in its simulator, and the Files panel](images/ide-simulator.png)

> **Status: 0.8.0 ([download](https://github.com/Copper-And-Code/copper-and-code-studio/releases/latest)).** The automated tests are many and human testing is scarce: much has been written and checked by machine, and little has been used by people. [What is verified, and how](status.md) describes each area.

<div class="home-grid" markdown>
<div class="home-card" markdown>

## Documentation

Install the IDE, create the first project, and learn how to publish it.

[Getting started](getting-started.md){ .md-button .md-button--primary }
[User manual](manual.md){ .md-button }

</div>
<div class="home-card" markdown>

## Browser demos

Try applications and games built with Copper and Code Studio, running on a shared WebAssembly runtime.

[Open the gallery](demos.md){ .md-button .md-button--primary }

</div>
<div class="home-card" markdown>

## Project evaluation

Examine the architecture, development method, recorded decisions, and current verification limits.

[The stack](stack.md){ .md-button .md-button--primary }
[What is verified](status.md){ .md-button }

</div>
</div>
