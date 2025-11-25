# Pulsarr Enhanced Requests

## 🧑‍💻 Streamline Media Approval Requests from Home Assistant

***

## Overview

The **Pulsarr Enhanced Requests** integration provides a single, powerful sensor entity in Home Assistant designed to streamline your media approval workflow from jamcalli's [Pulsarr](https://jamcalli.github.io/Pulsarr/) Real-time Plex watchlist monitoring and content acquisition tool, which Seamlessly sync Plex watchlists with Sonarr and Radarr.

This integration is built for efficiency, aggregating detailed information from multiple Pulsarr API endpoints into one central sensor. This allows you to view, manage, and act on pending requests directly from your Home Assistant dashboard without complex manual lookups.

### Key Features

* **Aggregated Data:** Fetches all requests awaiting approval, including the requesting user, content type, title, and the essential `contentGuids`.
* **Enhanced Metadata:** Automatically performs secondary API calls to Pulsarr to fetch rich TMDB metadata (poster, backdrop, ratings, etc.) for each requested item. This makes your dashboard card visually informative and provides context for quick decision-making.
* **Actionable Service:** Provides a native Home Assistant service (`pulsarr_enhanced_requests.process_request`) to approve or reject requests with a single button click, instantly updating Pulsarr.

This integration is specifically designed to work with the official-unofficial Home Assistant custom card: [**Pulsarr Requests Card**](https://github.com/SpaceFrags/pulsarr-requests-card).

<img width="517" height="564" alt="image" src="https://github.com/user-attachments/assets/294aedbc-7814-4b3a-94fa-6c8b68322326" />

***

## Installation

The installation process is similar to other custom Home Assistant integrations.

### 1. Installation via HACS My Home Assistant (Recommended)

The easiest way to install the Pulsarr Enhanced Requests integration is via HACS.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=SpaceFrags&repository=pulsarr_enhanced_requests&category=integration)

### 2. Installation via HACS Manually

HACS (Home Assistant Community Store) makes installation and updates simple. Since this is a new custom component, you must first add the repository to HACS.

1.  In Home Assistant, navigate to **HACS**.
2.  Go to the **Integrations** tab.
3.  Click the three dots **(⋮)** in the top right corner and select **Custom repositories**.
4.  Enter the URL: `https://github.com/SpaceFrags/pulsarr_enhanced_requests`
5.  Select **Integration** as the Category.
6.  Click **ADD**.
7.  After the repository is added, search for **"Pulsarr"** in the HACS Integrations section and click **Download**.
8.  **Restart Home Assistant** to load the new integration.

### 3. Manual Installation

1.  Download the latest release zip file from the [GitHub releases page](https://github.com/SpaceFrags/pulsarr_enhanced_requests/releases).
2.  Extract the contents. You should find a folder named `pulsarr_enhanced_requests`.
3.  Copy the entire `pulsarr_enhanced_requests` folder into your Home Assistant configuration directory under `custom_components/`.
    * **Resulting Path:** `config/custom_components/pulsarr_enhanced_requests/`
4.  **Restart Home Assistant** to load the new integration.

***

## Configuration

The configuration is handled entirely through the Home Assistant UI, requiring your Pulsarr connection details.

### Home Assistant Setup

1.  In Home Assistant, navigate to **Settings** > **Devices & Services**.
2.  Click the **+ ADD INTEGRATION** button.
3.  Search for **"Pulsarr Enhanced Requests"**.
4.  You will be prompted to enter the following mandatory details:
    * **Host:** The IP address or hostname of your Pulsarr instance (e.g., `192.168.1.10` or `pulsarr.local`).
    * **Port:** The port Pulsarr is running on (default is `3003`).
    * **API Key:** Your Pulsarr API key.
5.  Click **SUBMIT**. If successful, a new device and one sensor will be created under the name you provided.

### Sensor Entity

A single sensor entity is created: `sensor.pulsarr_enhanced_requests`.

| State Value | Description |
| :--- | :--- |
| `native_value` | The total count of pending approval requests. |

The most valuable data is stored in the state attributes, specifically `pending_requests_details`, which is a JSON list containing the full information for each pending request, including the enriched TMDB metadata needed for display by the custom card.

| Attribute | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| `pending_requests_details` | `list` | `[{"id": "...", "contentTitle": "...", "tmdb_metadata": {...}}]` | The complete list of requests ready for approval/rejection. |

***

## Automation & Services

This integration provides a service that can be called via automations, scripts, or—most importantly—by your custom Lovelace card.

### Service: `pulsarr_enhanced_requests.process_request`

This service allows you to approve or reject a pending request programmatically.

| Field | Required | Description |
| :--- | :--- | :--- |
| `request_id` | Yes | The unique ID of the request to process (found in the `pending_requests_details` attribute). |
| `action` | Yes | The action to perform: `approve` or `reject`. |

**Example YAML Service Call (for use in automations or scripts):**

```yaml
service: pulsarr_enhanced_requests.process_request
data:
  request_id: YOUR_REQUEST_ID_HERE # This ID is dynamically pulled by the custom card
  action: approve # Can be 'approve' or 'reject'
