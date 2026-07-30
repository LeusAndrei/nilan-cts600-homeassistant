# Nilan CTS600 over WiFi — ESP32 Modbus TCP↔RTU Bridge

This guide describes how to connect a **Nilan CTS600** ventilation unit to Home
Assistant **over WiFi**, using an **ESP32** running [ESPHome](https://esphome.io)
as a **Modbus TCP ↔ RTU bridge**. Home Assistant talks Modbus TCP to the ESP32,
and the ESP32 relays it over RS485 to the CTS600.

```
Home Assistant ──(WiFi / Modbus TCP :502)──► ESP32 (ESPHome + modbus_bridge)
                                                  │  UART 19200, 2 stop bits
                                                  ▼
                                            RS485 transceiver
                                                  │  A / B
                                                  ▼
                                          Nilan CTS600 control-panel bus
```

Compared to the direct USB-RS485 method (see the main [README](README.md)), the
ESP32 sits right next to the unit and needs no cable back to the HA server.

> ⚠️ **This bridge replaces the physical control panel.** You cannot use the
> original wall panel and this integration at the same time — disconnect the
> panel from the A/B bus.

---

## 1. Hardware shopping list

| Part | What to get | Notes |
|------|-------------|-------|
| **ESP32 board** | **ESP32-WROOM-32**, 38-pin DevKit (NodeMCU-32S / DevKitC) | Must be **WROOM**, *not* WROVER — see warning below |
| **RS485 transceiver** | TTL↔RS485 module **with automatic flow control** (auto-direction) | No DE/RE pin needed; the config has no `flow_control_pin` |
| **Power (optional)** | DC-DC buck converter **12 V → 5 V** (MP1584 / LM2596) | To power the ESP32 from the Nilan 12 V bus instead of USB |
| Wires | Dupont jumpers, or soldered leads | — |

### ⚠️ ESP32: WROOM, not WROVER

The ESPHome config uses **GPIO16 and GPIO17** for the UART. On **ESP32-WROVER**
modules those two pins are **reserved for the PSRAM** and are not usable — the
bridge will not work. Use a plain **ESP32-WROOM-32** (no PSRAM), which matches
`board: esp32dev` in the config. If you *must* use a WROVER, move the UART to
free pins in `nilan_cts600.yaml`.

### RS485 module — pick an auto-direction one

The config has **no direction-control pin**, so the module must switch
send/receive automatically. Look for "**automatic flow control**" /
"auto-direction" in the description.

* ✅ **Good:** single-chip auto-flow modules (e.g. ARCELI / DollaTek / DSD TECH
  "TTL to RS485, automatic flow control"). Typically 4 TTL pins
  (VCC/GND/TXD/RXD) + A/B terminals, often with a 120 Ω terminating resistor and
  TX/RX indicator LEDs (handy for debugging).
* ❌ **Avoid:** bare MAX485 breakouts with manual **DE/RE** pins — they need
  extra wiring and a `flow_control_pin` in the config.

---

## 2. Wiring

### 2.1 ESP32 ↔ RS485 module

The data lines are **crossed** (TX→RX, RX→TX):

```
ESP32 GPIO17 (TX) ──► RXD  (module)
ESP32 GPIO16 (RX) ──► TXD  (module)
ESP32 3V3         ──► VCC  (module)     ← power the module from 3.3 V
ESP32 GND         ──► GND  (module)
```

> Powering the module from **3.3 V** keeps the TTL logic levels at 3.3 V so they
> are safe for the ESP32 GPIOs.

### 2.2 RS485 module ↔ Nilan

```
Module A ──► Nilan  A
Module B ──► Nilan  B
```

If there is a third RS485 terminal marked with an earth symbol / "接大地"
("connect to earth ground"), it is for the cable shield — **leave it
unconnected** for this short link.

> If you get **no response at all**, the first thing to try is **swapping A and
> B** — guessing the polarity wrong is the most common cause.

### 2.3 Nilan control-panel connector pinout

The unit connects to the control panel with **4 wires**: two carry **12 V power**
and two are the **RS485 A / B** data lines.

![Nilan connector and wiring](docs/esp32-bridge-wiring.jpg)

Green pluggable terminal (as labelled on the housing):

| Terminal | Signal | Connect to |
|----------|--------|------------|
| `+`      | +12 V  | Buck converter input **+** (or leave unused if powering ESP32 by USB) |
| `–`      | 0 V / GND | Buck converter input **–** / common ground |
| `A`      | RS485 A | RS485 module **A** |
| `B`      | RS485 B | RS485 module **B** |

> ⚠️ **Never connect the 12 V wires to the RS485 module.** 12 V goes **only** to
> the buck converter input (Section 3). Feeding 12 V into the RS485 module or the
> ESP32 GPIOs will destroy them.

*(Add your own photo as `docs/esp32-bridge-wiring.jpg` — see the image reference
above. The photo should show the ESP32, buck converter, RS485 module and the
green Nilan connector with its `+ / – / A / B` markings.)*

---

## 3. Powering the ESP32 from the Nilan 12 V (optional)

Instead of a USB supply you can tap the **12 V** on the panel bus and step it
down to **5 V** with a buck converter.

```
Nilan  +12V ──► Buck IN+
Nilan  0V   ──► Buck IN–
Buck OUT+ (5V) ──► ESP32 pin  "5V" / "VIN"      ← NOT the 3V3 pin!
Buck OUT– (GND)──► ESP32 pin  "GND"
```

Rules:

1. Feed **5 V into the `5V` / `VIN` pin** of the ESP32 (its onboard regulator
   makes 3.3 V). **Do not** feed 5 V into the `3V3` pin — that bypasses the
   regulator and can damage the board.
2. If your buck module is **adjustable**, set it to **exactly 5.0 V with a
   multimeter before** connecting the ESP32. A fixed-5 V module avoids this risk.
3. **Don't power the ESP32 from USB and the buck at the same time** (except
   briefly while flashing), to avoid back-feeding.
4. The buck is usually non-isolated, so ESP32 GND becomes common with the Nilan
   GND — this is fine and actually gives RS485 a shared ground reference.
5. Check the 12 V rail can supply the ESP32's WiFi peaks (~150 mA @ 12 V). If the
   ESP32 brown-outs, add a 470–1000 µF capacitor across the 5 V output, or use a
   separate supply.

---

## 4. ESPHome firmware

Use [`nilan_cts600.yaml`](nilan_cts600.yaml) from this repo as the ESPHome device
config. Key points:

* UART: **19200 baud, 2 stop bits**, GPIO17 (TX) / GPIO16 (RX)
* `modbus_bridge`: `tcp_port: 502`, `crc_bytes_swapped: true`
* Status LED on GPIO2 blinks once every 3 s per connected TCP client
* A **"Modbus Bridge Debug"** switch enables verbose byte-level logging

### 4.1 ⚠️ Pin the `modbus_bridge` component version (required!)

The external `modbus_bridge` component **must be pinned** to a commit **before**
response validation was added. Since commit `3d1b5e0`
("Validate RTU responses against active request", v2026.06.1) the bridge drops
any RTU response whose function code does not match the request — and the CTS600
**always** replies with a different function code (it is a *pseudo*-Modbus
protocol: the unit answers with a "random" status update, not a matching reply).

With a newer version you will see, endlessly:

```
[W][modbus_bridge]: RTU response does not match request. Dropping response.
```

The config pins the component to `65caef9` (the parent of `3d1b5e0`, the last
version **without** response matching):

```yaml
external_components:
  - source:
      type: git
      url: https://github.com/rosenrot00/esphome_modbus_bridge
      ref: 65caef9bea567f6e9ce78e703d1c37de31614b0c
    components: [modbus_bridge]
```

Pinning also makes the build **reproducible** — otherwise ESPHome fetches the
latest `main` on every build and can silently break again.

### 4.2 Secrets

`nilan_cts600.yaml` references these in your ESPHome `secrets.yaml`:

```yaml
wifi_ssid: "YourNetwork"
wifi_password: "yourWifiPassword"
ota_password: "any-password-for-ota-updates"   # you choose it
ap_password: "any-password-min-8-chars"        # fallback hotspot password
```

* **`ota_password`** — protects over-the-air firmware updates (you invent it).
* **`ap_password`** — password for the fallback WiFi hotspot the ESP32 raises if
  it can't join your network (you invent it, min 8 chars).

Note: the sample config also sets `min_auth_mode: WPA3` and `domain: .lan` —
remove/adjust those if your router doesn't use WPA3 / `.lan`.

### 4.3 Flash

1. First flash over **USB** (ESPHome dashboard or CLI); afterwards you can use
   **OTA** over WiFi.
2. If you change the pinned `ref` later, run **Clean Build Files** before
   flashing so ESPHome doesn't reuse a cached component version.
3. Find the ESP32's IP (ESPHome logs, your router, or `nilan-cts600.lan`).

### 4.4 Verify the bridge

* `Test-NetConnection <esp32-ip> -Port 502` → `TcpTestSucceeded : True`
* When HA connects, the status LED starts blinking (1 client).
* With the RS485 module's TX/RX LEDs you can see traffic: **TX** blinking =
  requests going out; **RX** blinking = the unit answering.

---

## 5. Home Assistant integration

1. Copy `custom_components/nilan_cts600/` into your HA `config/custom_components/`
   (do **not** copy `__pycache__`; it is regenerated automatically).
2. Restart Home Assistant.
3. **Settings → Devices & Services → + Add Integration → "Nilan CTS600"**.
4. In the wizard:
   * **Connection type:** `Modbus TCP`
   * **Name:** any, e.g. `Loft CTS600`
   * **Host:** the ESP32 IP, e.g. `192.168.1.50`
   * **tcp_port:** `502`
   * **sensor_T15:** a temperature `sensor` / `input_number` that replaces the
     unit's built-in room sensor (see below)
5. Submit — the integration tests the TCP connection and creates the device
   (1 climate entity, temperature/flow sensors, and 6 panel-button entities).

### 5.1 Room temperature (T15) from a template

The `sensor_T15` field only accepts an existing `sensor` or `input_number`
entity — you can't paste a template. To use, say, another climate entity's
temperature, create a template sensor first:

```yaml
template:
  - sensor:
      - name: "Bedroom Temp for Nilan"
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: "{{ state_attr('climate.bedroom', 'current_temperature') }}"
        availability: "{{ state_attr('climate.bedroom', 'current_temperature') is not none }}"
```

Then pick `sensor.bedroom_temp_for_nilan` as `sensor_T15`. Leaving T15 empty
falls back to a fixed 21 °C, so set a real source for correct control.

---

## 6. Troubleshooting

| Symptom | Likely cause / fix |
|---------|-------------------|
| `Modbus timeout: no response (no first byte)` | Nothing received. Swap **A/B**; check the crossed **TX/RX**; confirm the module is powered; confirm the unit is powered and the wall panel is disconnected. |
| `RTU response does not match request. Dropping response.` | `modbus_bridge` too new — **pin `ref: 65caef9…`** and **Clean Build Files** (Section 4.1). |
| `cannot_connect` when adding the integration | ESP32 not reachable: check IP, WiFi, that port 502 answers, and that only 1 TCP client is connected (`tcp_allowed_clients: 1`). |
| Integration not in the Add list | Files not in `config/custom_components/nilan_cts600/`, or HA not restarted. |
| Config dialog "doesn't appear" | Hard-refresh the browser (Ctrl+Shift+R); the wizard opens only after you click the integration in the Add list. |
| Build warnings `Chip rev >= 3.0` / `SRAM1 as IRAM` | Harmless size-optimization hints — safe to ignore. Optionally add `esp32 → framework → advanced → sram1_as_iram: true`. |

---

## Notes about the CTS600 protocol

The CTS600 speaks a *pseudo*-Modbus over RS485 where the wall panel is the master
and the unit answers with "random" status updates (display text or LED state),
**not** with a reply matching the request's function code. The integration
emulates the panel: it "presses" buttons and parses the LCD text. Consequences:

* During init the unit's language is forced to **English** so the display can be
  parsed.
* Temperature precision is limited to whole degrees (what the LCD shows).
* Because responses don't match requests, a standards-enforcing Modbus bridge
  will reject them — hence the required component pin in Section 4.1.
