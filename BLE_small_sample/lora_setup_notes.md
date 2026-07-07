# LoRa setup — DX-LR02-433T22D (one-way relay)

Master: **Arduino Nano Every** (or Nano 33 BLE) with [lora_master/lora_master.ino](lora_master/lora_master.ino)  
Remote: **Nano Every** with [lora_remote/lora_remote.ino](lora_remote/lora_remote.ino)

## Data flow

```
PC scoreboard app (USB serial) -> Master (lora_master.ino) -> LoRa TX --433 MHz--> LoRa RX -> Remote (lora_remote.ino)
```

The master runs **lora_master.ino**: USB serial in, local display/buzzer via `handleScoreboardCommand()`, and the same command forwarded over LoRa. Remotes run **lora_remote.ino** and mirror the command on their display.

Commands are plain text (`TEST`, `BUZZER`, `42`, etc.) with a newline delimiter.

## Wiring (each board + module)

| LoRa pin | Connect to |
|----------|------------|
| VCC | 3.3V |
| GND | GND |
| TX | Arduino pin **0** (RX1) |
| RX | Arduino pin **1** (TX1) |
| M0 | GND (run mode) or see modes below |
| M1 | GND (transparent) or HIGH (config) |
| AUX | Optional — master sketch supports `LORA_AUX_PIN` if wired |

Attach the 433 MHz antenna before transmitting.

Scoreboard segment pins match the original sketch (digits on 2–9, tens on A0–A7, buzzer on 10).

## M0 / M1 modes

| M0 | M1 | Mode |
|----|-----|------|
| LOW | LOW | Transparent transmission (normal run) |
| LOW | HIGH | AT command / configuration |
| HIGH | LOW | WOR (wake-on-radio) |
| HIGH | HIGH | Deep sleep |

## Phase 1 — Gather parts and decide the config path

Use one of these two methods to configure each LoRa module:

1. **Recommended:** USB-TTL adapter at 3.3V logic
2. **Fallback:** Arduino passthrough sketch [lora_config_helper/lora_config_helper.ino](lora_config_helper/lora_config_helper.ino)

### What you need

- 2 x DX-LR02-433T22D modules
- 2 x antennas
- 1 x Nano 33 BLE for the master
- 1 x Nano Every for the remote
- USB cable(s)
- Jumper wires
- Optional but recommended: a breadboard
- Optional but recommended: a **3.3V USB-TTL adapter**

### Why the helper sketch exists

`lora_config_helper.ino` turns an Arduino into a simple serial bridge:

- PC USB serial ↔ Arduino `Serial`
- Arduino `Serial1` ↔ LoRa module UART

That lets you send AT commands from the Arduino IDE Serial Monitor directly into the LoRa module.

## Phase 2 — Load `lora_config_helper`

Use this phase when you do **not** have a separate USB-TTL adapter, or if you want to do the setup through the Arduino IDE.

### Step 2.1 — Choose the board to use for config

Pick one Arduino to temporarily act as the setup bridge:

- `Nano 33 BLE`
- `Nano Every`

Either one is fine for this helper sketch.

### Step 2.2 — Open the sketch

Open:

`BLE_small_sample/lora_config_helper/lora_config_helper.ino`

This sketch is a passthrough. It does not configure the LoRa module by itself; it just forwards bytes between USB serial and `Serial1`.

### Step 2.3 — Verify the sketch behavior

The helper sketch expects:

- PC Serial Monitor speed: **9600**
- LoRa module UART speed: **9600**
- LoRa wired to Arduino `Serial1`

Current behavior from the sketch:

- Anything typed into Serial Monitor is sent to the LoRa module
- Any response from the LoRa module is printed back into Serial Monitor

### Step 2.4 — Select the correct board in Arduino IDE

In Arduino IDE:

1. Connect the temporary setup board over USB
2. Go to `Tools > Board`
3. Select the actual board you connected:
   - `Arduino Nano 33 BLE`, or
   - `Arduino Nano Every`
4. Go to `Tools > Port`
5. Select the COM port for that board

### Step 2.5 — Upload the helper sketch

1. Click **Verify** first
2. Click **Upload**
3. Wait for the upload to finish
4. Do **not** open the Serial Monitor yet if the LoRa wiring is not connected

## Phase 3 — Wire one LoRa module to the helper board

Configure **one module at a time**. Do not wire both LoRa modules to the same helper board during AT setup.

### Step 3.1 — Power and UART wiring

Wire the LoRa module to the helper Arduino like this:

| LoRa pin | Arduino connection |
|----------|--------------------|
| VCC | 3.3V |
| GND | GND |
| TX | pin `0` (`RX1`) |
| RX | pin `1` (`TX1`) |

### Step 3.2 — Put the module into AT/config mode

For configuration mode:

- `M0 = LOW`
- `M1 = HIGH`

You can do that by:

- tying `M0` to `GND`
- tying `M1` to `3.3V`

Keep those levels in place **before powering the module** and while issuing AT commands.

### Step 3.3 — Antenna guidance

For simple AT configuration, the antenna is usually not critical if you are only reading or writing settings.

For any over-the-air testing afterward, attach the antenna first.

## Phase 4 — Talk to the module through Serial Monitor

### Step 4.1 — Open Serial Monitor with the right settings

In Arduino IDE Serial Monitor:

- Baud: **9600**
- Line ending: **Both NL & CR** or **CR+LF**

Those settings should match the helper sketch and typical module defaults.

### Step 4.2 — Confirm the helper sketch started

You should see:

```text
LoRa config passthrough ready (9600)
```

If you do not see that:

- check the selected COM port
- close and reopen Serial Monitor
- press the board reset button once

### Step 4.3 — Send a simple AT probe

Start with a simple AT command from the module guide, such as:

```text
AT
```

or the vendor's equivalent basic query command if plain `AT` does not respond.

Because DX-LR02 firmware variants differ, use the module's **DX-Smart serial application guide** as the source of truth for exact commands.

### Step 4.4 — If there is no response

Check these in order:

1. `M0` and `M1` are really in config mode (`LOW/HIGH`)
2. `TX` and `RX` are crossed correctly
3. `GND` is common
4. Module is powered from **3.3V**
5. Serial Monitor is at **9600**
6. Line ending is **CR+LF**
7. The board you uploaded to matches the board selected in Arduino IDE

## Phase 5 — Configure module A

Using the DX-Smart guide, configure the first LoRa module with your desired settings.

### Target settings

Set module A to:

- UART baud: **9600**
- Same RF channel/frequency plan you will use on module B
- Same air data rate/level you will use on module B
- Transparent transmission mode
- Any address/network settings required by your firmware so both modules match

### Suggested order

1. Read current settings
2. Change UART baud if needed
3. Set RF channel/frequency
4. Set air rate / speed level
5. Confirm transparent mode behavior
6. Save settings to flash using the vendor save command
7. Read the settings back again and write them down

### Record what you used

Write down the exact values for:

- channel
- air rate / level
- UART baud
- any address fields
- any mode or switch settings

You will need to apply the same compatible settings to module B.

## Phase 6 — Configure module B

Repeat the exact same process for the second LoRa module.

The two modules must match on the settings that control communication.

At minimum, keep these the same:

- UART baud
- RF channel / frequency
- air rate / speed level
- transmission mode
- any addressing mode required for transparent link operation

## Phase 7 — Return both modules to run mode

After both modules are configured:

- `M0 = LOW`
- `M1 = LOW`

That is the normal transparent transmission mode used by the scoreboard sketches.

Do this on both modules before moving on to over-the-air testing.

## Phase 8 — Bench test the LoRa link before flashing scoreboard firmware

This is the safest way to confirm the radio link works before involving BLE and the scoreboard logic.

### Option A — Best test

Use two serial bridges:

- two USB-TTL adapters, or
- one adapter and one Arduino helper board, or
- two Arduino helper boards

Open a serial terminal for each module and verify:

- text typed into module A appears on module B
- text typed into module B appears on module A

### Option B — Minimal test

If you only have one helper board:

1. Configure module A
2. Configure module B
3. Move each to run mode (`LOW/LOW`)
4. Flash the actual master and remote scoreboard sketches
5. Test with live commands

## Phase 9 — Flash firmware

| Board | Sketch | IDE board setting |
|-------|--------|-------------------|
| Master | `BLE_small_sample/lora_master/lora_master.ino` | Arduino Nano Every (or Nano 33 BLE) |
| Remote | `BLE_small_sample/lora_remote/lora_remote.ino` | Arduino Nano Every |
| LoRa AT setup | `BLE_small_sample/lora_config_helper/lora_config_helper.ino` | Same as board used for config |

**Arduino IDE:** Each sketch must live in its own folder with a matching `.ino` name. The BLE-only board uses `BLE_small_sample/BLE_small_sample.ino`. The LoRa master uses `BLE_small_sample/lora_master/lora_master.ino` — do not put extra `.ino` files in the same folder or the IDE merges them and the build fails.

**Note:** `scoreboard_commands.h` exists in `BLE_small_sample/` and `lora_remote/`. If you change command logic, update both copies.

## Phase 10 — Test sequence

1. **LoRa only:** With both boards powered, open master Serial Monitor; connect BLE and send `42` — both displays should show 42.
2. **Buzzer:** Send `BUZZER` — both buzzers (remote may lag ~100–500 ms).
3. **Range:** Move remote to pool-deck position; repeat digit and `CHANGE` commands.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Remote silent | M0/M1 not transparent; mismatched channel or air rate |
| Garbled text | Baud not 9600 on module and `Serial1` |
| Master OK, no RF | Antenna missing; modules not paired settings |
| Partial commands | Increase `Serial1.setTimeout` on remote |

## Shared command reference

| Command | Master + remote action |
|---------|------------------------|
| `TEST` | Short beep, DP on |
| `BUZZER` | 500 ms beep |
| `CHANGE` | 1 s beep, clear display |
| `END` | 1 s beep, clear display |
| `exit` | Clear display |
| `0` | Clear display |
| `1`–`99` | Show two-digit score |

BLE notify acks (`BUZZER`, `CHANGE`, etc.) are sent only from the master to the phone — not over LoRa.
