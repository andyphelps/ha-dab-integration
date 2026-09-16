# ha-dab-integration

A Home Assistant custom component (`custom_components/dab_radio/`) that
creates a `media_player.dab_radio` entity and a Media Browser source, both
backed by the `ha-dab-addon` controller's REST API (see
`../ha-dab-addon/README.md`). Confirmed working end-to-end against a real
HAOS instance: scanning 10B/11A/11D/12B found 27 real stations across two
ensembles (Somerset and BBC National DAB).

## What it gives you

- `media_player.dab_radio`, with `source_list` populated from the last scan
  (station labels). Selecting a source, or calling
  `media_player.play_media` with a station label or service id, tunes the
  receiver.
- `media_content_id` is set to the currently-tuned station's stream URL, so
  the entity works as a `media_player.play_media` *target* too -- e.g. cast
  it to a real speaker:
  ```yaml
  service: media_player.play_media
  target:
    entity_id: media_player.living_room_speaker
  data:
    media_content_id: "{{ state_attr('media_player.dab_radio', 'media_content_id') }}"
    media_content_type: music
  ```
- A `dab_radio.scan` service to (re)scan the configured channels on demand.
- A **Media Browser** source (`media_source.py`): stations show up under
  *Media -> DAB Radio* in the sidebar, grouped by ensemble (e.g. "Somerset",
  "BBC National DAB") -- deliberately **not** by the underlying DAB
  channel/multiplex code (10B, 12B, ...), since that's internal plumbing
  nobody browsing for a station cares about. Picking a station there tunes
  the receiver and lets you "Play on" any real speaker directly from the
  browse UI, the same flow as the built-in Radio Browser integration.

There's deliberately no signal-strength/SNR sensor yet -- easy to add later
(the add-on's `/status` could pass through welle-cli's own `/mux.json` SNR
field) but not in scope for a first working version.

## Installing

HAOS ships with neither SSH nor Samba by default, so getting this folder
onto the HAOS host needs one of those installed first from the official
Add-on store (*Settings -> Add-ons -> Add-on Store*), or use
[HACS](https://hacs.xyz/) with this repo added as a custom integration
repository. Whichever path: the end result needs to be
`/config/custom_components/dab_radio/` on the HAOS host containing the
files from this repo's `custom_components/dab_radio/`.

1. Copy `custom_components/dab_radio/` into `/config/custom_components/` on
   the HAOS host.
2. Restart Home Assistant (Settings -> System -> Restart).
3. *Settings -> Devices & Services -> Add Integration -> DAB Radio*. Enter
   the add-on's host/IP and controller port (9000 by default).
4. Call `dab_radio.scan` (Developer Tools -> Actions) to populate the
   station list -- takes 30-90s. `media_player.dab_radio`'s `source_list`
   attribute fills in once it completes.

## Design note: one entity, one tuner

There's a single RTL-SDR dongle behind all of this, so `media_player.dab_radio`
represents *the receiver*, not a speaker -- selecting a source retunes the
shared hardware for everyone, the same way changing the channel on a
physical radio does. This is why tuning is modeled as
`select_source`/`play_media` on our own entity (which then exposes a stream
URL) rather than trying to make our entity itself "play" audio anywhere --
actual playback happens on whatever real `media_player` you point at that
URL.
