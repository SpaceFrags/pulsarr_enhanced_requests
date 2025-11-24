---
name: Pulsarr Enhanced Requests
default_values:
  config_flow:
    host: "192.168.1.10"
    port: 3003
    api_key: "YourPulsarrAPIKey"
---

The **Pulsarr Enhanced Requests** integration provides a single sensor entity in Home Assistant to manage pending media approval requests from your Pulsarr instance. 

It fetches aggregated request details, including rich TMDB metadata (poster, ratings, etc.), and exposes a dedicated service (`pulsarr_enhanced_requests.process_request`) to approve or reject requests directly from your dashboard or automations.

This integration is designed to work with the companion Lovelace card: [Pulsarr Requests Card](https://github.com/SpaceFrags/pulsarr_requests_card).

**Setup Requirements:**
1. Your Pulsarr instance's Host and Port.
2. A valid Pulsarr API Key.
