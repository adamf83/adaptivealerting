# Adaptive Alerting

A Home Assistant custom integration that learns the normal range of a sensor and
raises an alert when it drifts outside that range, using z-score anomaly
detection. No automations, no manually-typed entity IDs — just pick a sensor
from a dropdown and it takes care of the rest.

## What it does

- Sensor is **selected from a dropdown** in the HA UI — no entity IDs typed manually
- Learns the sensor's normal range over a configurable window
- Exposes a `binary_sensor` that turns `on` when the value is anomalous
- Exposes a `sensor` with the current z-score
- Fires a HA event `adaptive_alerting_anomaly` when triggered
- Persists the learned baseline across restarts
- Has a `reset_baseline` service

## Installation

1. Copy the `custom_components/adaptive_alerting/` folder into your Home
   Assistant `config/custom_components/` directory.
2. Restart Home Assistant fully (not just reload).
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for **Adaptive Alerting**.
5. The setup form appears:
   - **Sensor to monitor** — click the field and search by room or device name
     (e.g. type "humidity" to see all humidity sensors)
   - **Learning window** — how many days of history to use (default 14)
   - **Sensitivity** — drag the slider (default 2.5σ; lower = triggers more easily)
6. Click **Submit**.

The integration seeds its baseline immediately from your recorder history for
the chosen window, so it won't need to wait days before it has data to work
with.

## What you get

| Entity | Description |
|---|---|
| `binary_sensor.alerting_x_anomaly` | `on` when current value is anomalous |
| `sensor.alerting_x_z_score` | Live z-score in σ units |

**Attributes on the binary sensor:**

| Attribute | Description |
|---|---|
| `z_score` | How many standard deviations from the mean |
| `mean` | The learned average |
| `std_dev` | The learned spread |
| `model_ready` | `false` until 30+ samples collected |
| `monitored_entity` | Which sensor is being watched |

## Services

`adaptive_alerting.reset_baseline` wipes the learned baseline for one (or all)
monitored sensors and starts relearning from scratch. Pick a sensor from the
**Entry** dropdown, or leave it blank to reset every monitored sensor.

## Testing it quickly

Once installed, go to **Developer Tools → States**, find your monitored
sensor, and manually set its state to an extreme value (e.g. set
`sensor.dining_room_humidity` to `99`). If the model has 30+ samples (check
the `model_ready` attribute), the binary sensor will flip to `on` within
seconds.

To check sample count, look at the HA logs for the seed message:

```
Seeded baseline for sensor.dining_room_humidity with 847 historical samples
```

If you see 0 samples, your recorder may not have history for that sensor
yet — let it run for a day and it will build up naturally.

## What's missing (v1.1 ideas)

- Time-of-day segmentation (separate baselines per hour of day)
- CUSUM detector for slow sustained drift
- `mark_as_normal` service to feed false positives back into the model
- Options flow to adjust sensitivity without re-adding the integration
- Multiple sensors per config entry
- HACS `hacs.json` packaging for public release

## Running the tests

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements_test.txt
pytest tests/
```
