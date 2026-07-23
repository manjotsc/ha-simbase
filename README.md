<div align="center">
  <img src="custom_components/simbase/brand/logo.png" alt="Simbase" width="320">

  <h1>Simbase for Home Assistant</h1>

  <p><strong>Monitor and control your <a href="https://www.simbase.com/">Simbase</a> IoT SIM cards from Home Assistant.</strong><br>
  Data usage, costs, SMS, location and full activation control — one device per SIM.</p>

  <p>
    <a href="https://github.com/hacs/integration"><img alt="HACS Custom" src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square"></a>
    <a href="https://github.com/manjotsc/ha-simbase/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/manjotsc/ha-simbase?style=flat-square"></a>
    <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2024.1%2B-41BDF5.svg?style=flat-square">
    <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square"></a>
  </p>
</div>

> [!NOTE]
> Unofficial, community-developed integration. Not affiliated with or endorsed by Simbase.

---

## Highlights

| | |
|---|---|
| 📊 **Usage & cost tracking** | Data, SMS and spend per SIM and across the account, in your billing currency |
| 🎛️ **Full control** | Activate SIMs, set data/SMS limits, assign rate plans, schedule auto-disable |
| 🔒 **Theft protection** | Toggle the IMEI lock so a stolen SIM stops working in another device |
| 📍 **Map presence** | Each SIM becomes a device tracker using its cell location |
| 💬 **SMS** | Send and read messages straight from automations |
| ⚙️ **Pick your entities** | Every sensor and control group can be switched off during setup |

## Installation

### HACS (recommended)

1. **HACS** → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/manjotsc/ha-simbase` with category **Integration**
3. Search for **Simbase**, install, and restart Home Assistant

<details>
<summary><b>Manual installation</b></summary>

1. Download the [latest release](https://github.com/manjotsc/ha-simbase/releases)
2. Copy `custom_components/simbase` into your `config/custom_components/` directory
3. Restart Home Assistant

</details>

## Setup

1. Grab an API key from the [Simbase Dashboard](https://dashboard.simbase.com/) → **Settings** → **API Key**
2. **Settings** → **Devices & Services** → **Add Integration** → **Simbase**
3. Paste the key, then tick the sensors and control groups you want

Everything you choose here can be changed later via **Configure** on the integration entry, including the polling interval (60–3600 s, default 5 minutes).

## Entities

Each SIM card becomes its own device, named after its Simbase label (or `SIM ...1234` as a fallback). Account-wide totals live on a separate device.

### Controls

| Entity | Type | What it does |
|---|---|---|
| **SIM Activation** | Switch | Enable/disable an individual SIM |
| **Theft Protection** | Switch | IMEI lock — Simbase disables the SIM if it's moved to another device |
| **Data Limit** | Number | Data threshold in MB |
| **Data Limit Enabled** | Switch | Turn the data limit on/off (off clears the threshold) |
| **SMS Limit** | Number | SMS threshold, in messages |
| **SMS Limit Enabled** | Switch | Turn the SMS limit on/off |
| **Auto Re-enable Monthly** | Switch | Re-enable the SIM at the start of each month |
| **Auto-disable Date** | Date | Date the SIM is automatically disabled |
| **Rate Plan** | Select | Assign a rate plan (options come from your account) |
| **Reset Connection** | Button | Cancel the SIM's current data session |
| **Activate All / Deactivate All** | Button | Enable/disable every SIM at once |

> [!TIP]
> Setting a **Data/SMS Limit** turns its **Enabled** switch on automatically. Toggle that switch **off** to clear the limit entirely. To clear the **Auto-disable Date**, call `simbase.set_autodisable` with an empty date — a Date entity can't represent "none".

> [!WARNING]
> Turning on **Theft Protection** locks the SIM to whichever device it's in *right now*. Make sure it's in the right one first.

<details>
<summary><b>Per-SIM sensors</b></summary>

| Sensor | Description |
|---|---|
| Data Usage | Current month data consumption |
| Status | SIM state (enabled/disabled) |
| Monthly Cost | Current month costs |
| SMS Sent / Received / Total | Message counts |
| Coverage Plan | Current plan |
| Network Operator | Carrier the SIM is connected to (MCC/MNC, country) |
| Session Status | Whether the SIM has an active data session |
| Location | Country and cell location (lat/lon/cell ID when available) |
| Hardware | Device info |
| ICCID / IMEI / MSISDN | Identifiers |
| IP Address | Assigned IP |

**Binary sensors:** `Online` (enabled/connected) and `Throttled`.

**Device tracker:** places the SIM on the Home Assistant map using its cell-derived `latitude`/`longitude`. Coordinates are approximate — they come from the serving cell, not GPS — and may be unavailable when the network returns no position.

</details>

<details>
<summary><b>Account sensors</b></summary>

| Sensor | Description |
|---|---|
| Account Balance | Credit balance |
| Total / Active / Inactive SIMs | SIM counts |
| Total Data Usage | Aggregate data consumption |
| Total Monthly Cost | Sum of all SIM costs |
| Total SMS | Aggregate message counts |

</details>

> **Units.** Data is reported in decimal megabytes (1 MB = 1,000,000 bytes), matching both the Simbase dashboard and Home Assistant's `MB` unit — a 10 MB limit set here is exactly 10 MB there.
>
> **Currency.** All monetary sensors use your account's billing currency as reported by the API (`USD`, `EUR`, `GBP`, `AUD`, `CAD`, …), falling back to `USD` only if the balance endpoint is unavailable.

## Services

| Service | Description |
|---|---|
| `simbase.activate_sim` | Activate a SIM card |
| `simbase.deactivate_sim` | Deactivate a SIM card |
| `simbase.send_sms` | Send an SMS to a SIM card |
| `simbase.read_sms` | Read SMS messages (returns a response) |
| `simbase.reset_connection` | Cancel the SIM's current data session |
| `simbase.set_autodisable` | Schedule or clear an automatic disable date |
| `simbase.set_usage_limits` | Set data/SMS thresholds and monthly auto re-enable |
| `simbase.set_rateplan` | Assign a rate plan |

All services target a SIM by `device_id`, so they work with the device picker in the UI.

## Automation recipes

<details open>
<summary><b>Alert when a SIM burns through its data</b></summary>

```yaml
automation:
  - alias: "Tracker SIM data warning"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.tracker_sim_data_usage
        above: 800          # MB
    actions:
      - action: notify.mobile_app
        data:
          message: >-
            Tracker SIM has used {{ states('sensor.tracker_sim_data_usage') }} MB this month.
```

</details>

<details>
<summary><b>Cut a SIM off when it goes over budget</b></summary>

```yaml
automation:
  - alias: "Kill switch on runaway usage"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.tracker_sim_monthly_cost
        above: 25
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.tracker_sim_active
```

Prefer letting Simbase enforce it? Set **Data Limit** instead and turn on **Auto Re-enable Monthly** so the SIM comes back by itself next month.

</details>

<details>
<summary><b>Notice when a SIM drops offline</b></summary>

```yaml
automation:
  - alias: "SIM offline for 30 minutes"
    triggers:
      - trigger: state
        entity_id: binary_sensor.tracker_sim_online
        to: "off"
        for: "00:30:00"
    actions:
      - action: notify.mobile_app
        data:
          message: "Tracker SIM has been offline for 30 minutes."
```

</details>

<details>
<summary><b>Send an SMS to a device</b></summary>

```yaml
script:
  reboot_via_sms:
    sequence:
      - action: simbase.send_sms
        data:
          device_id: !input sim_device
          message: "REBOOT"
```

</details>

## Not available

These are missing because the Simbase API doesn't expose them: **signal strength**, **connection type**, and **roaming status**.

## Contributing

Issues and pull requests are welcome at [manjotsc/ha-simbase](https://github.com/manjotsc/ha-simbase). Bug reports are much easier to act on with the integration's **Download diagnostics** output attached (identifiers are redacted automatically).

## License

[MIT](LICENSE) · **Trademark notice:** Simbase is a trademark of its respective owner. This project is not affiliated with Simbase.
