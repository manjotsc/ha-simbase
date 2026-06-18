# Simbase IoT SIM Management for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/manjotsc/ha-simbase)](https://github.com/manjotsc/ha-simbase/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Monitor and control your [Simbase](https://www.simbase.com/) IoT SIM cards directly from Home Assistant. Track data usage, costs, SMS metrics, and manage SIM activation from your dashboard.

> **Note:** This is an unofficial, community-developed integration and is not affiliated with or endorsed by Simbase.

## Features

| Feature | Description |
|---------|-------------|
| SIM Monitoring | Track data usage, status, costs, and SMS counts |
| Account Overview | View totals across all SIM cards |
| Activation Control | Enable/disable SIMs individually or in bulk |
| SMS Support | Send SMS messages to your SIM cards |
| Configurable | Choose which sensors to enable |
| Automations | Trigger automations based on SIM status |

## Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations** → **Menu** (three dots) → **Custom repositories**
3. Add `https://github.com/manjotsc/ha-simbase` with category **Integration**
4. Search for and install **Simbase**
5. Restart Home Assistant

### Manual

1. Download the [latest release](https://github.com/manjotsc/ha-simbase/releases)
2. Copy `custom_components/simbase` to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Get your API key from [Simbase Dashboard](https://dashboard.simbase.com/) → **Settings** → **API Key**
2. In Home Assistant, go to **Settings** → **Devices & Services**
3. Click **Add Integration** and search for **Simbase**
4. Enter your API key and select your preferred sensors

## Available Entities

### Per-SIM Sensors

| Sensor | Description |
|--------|-------------|
| Data Usage | Current month data consumption |
| Status | SIM state (enabled/disabled) |
| Monthly Cost | Current month costs |
| SMS Sent/Received | Message counts |
| Coverage Plan | Current plan |
| Network Operator | Carrier the SIM is currently connected to (MCC/MNC, country) |
| Session Status | Whether the SIM has an active data session |
| Location | Country and cell location (lat/lon/cell ID when available) |
| Hardware | Device info |
| IMEI | Device identifier |
| MSISDN | Phone number |
| IP Address | Assigned IP |

### Per-SIM Binary Sensors

| Binary Sensor | Description |
|---------------|-------------|
| Online | Whether the SIM is enabled/connected |
| Throttled | Whether the SIM is currently throttled |

### Per-SIM Device Tracker

Each SIM also creates a **device tracker** that places it on the Home Assistant map using the cell-based `latitude`/`longitude`. Coordinates are approximate (derived from the serving cell, not GPS) and may be unavailable when the network doesn't return a position.

### Account Sensors

| Sensor | Description |
|--------|-------------|
| Account Balance | Credit balance |
| Total/Active/Inactive SIMs | SIM counts |
| Total Data Usage | Aggregate data consumption |
| Total Monthly Cost | Sum of all SIM costs |
| Total SMS | Aggregate message counts |

> **Currency:** all monetary sensors (balance, per-SIM Monthly Cost, Total Monthly Cost) use your account's billing currency, reported by the Simbase API (`USD`, `EUR`, `GBP`, `AUD`, `CAD`, …). It falls back to `USD` only if the balance endpoint is unavailable.

### Controls

| Entity | Type | Description |
|--------|------|-------------|
| SIM Activation | Switch | Enable/disable an individual SIM |
| Auto Re-enable Monthly | Switch | Re-enable the SIM at the start of each month (`usage_limits_auto_enable`) |
| Data Limit | Number | Data usage threshold in MB (`usage_limits_data_threshold`) |
| Data Limit Enabled | Switch | Turn the data limit on/off (off clears the threshold) |
| SMS Limit | Number | SMS usage threshold (`usage_limits_sms_threshold`) |
| SMS Limit Enabled | Switch | Turn the SMS limit on/off (off clears the threshold) |
| Auto-disable Date | Date | Date the SIM is automatically disabled |
| Rate Plan | Select | Assign a rate plan (options from `/account/plans`) |
| Reset Connection | Button | Cancel the SIM's current data session |
| Activate All / Deactivate All | Button | Enable/disable all SIMs at once |

> Setting a **Data/SMS Limit** number turns its **Enabled** switch on automatically. Toggle the switch **off** to clear the limit (set it back to "no limit"). To clear the **Auto-disable Date**, call the `simbase.set_autodisable` service with an empty date (a Date entity can't represent an empty value).

### Services

| Service | Description |
|---------|-------------|
| `simbase.activate_sim` | Activate a SIM card |
| `simbase.deactivate_sim` | Deactivate a SIM card |
| `simbase.send_sms` | Send SMS to a SIM card |
| `simbase.read_sms` | Read SMS messages from a SIM card |
| `simbase.reset_connection` | Reset a SIM's connection (cancel the current data session) |
| `simbase.set_autodisable` | Schedule (or clear) an automatic disable date |
| `simbase.set_usage_limits` | Set data/SMS usage thresholds and monthly auto re-enable |
| `simbase.set_rateplan` | Assign a rate plan to a SIM card |

## Known Limitations

The following are **not available** due to Simbase API limitations:

| Sensor | Reason |
|--------|--------|
| Data Limit | Not provided by API |
| Signal Strength | Not provided by API |
| Connection Type | Not provided by API |
| Roaming Status | Not provided by API |

## License

This project is licensed under the [MIT License](LICENSE).

---

**Trademark Notice:** Simbase is a trademark of its respective owner. This project is not affiliated with Simbase.
