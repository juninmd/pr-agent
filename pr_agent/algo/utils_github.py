from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime

import requests
from starlette_context import context

from pr_agent.config_loader import get_settings, global_settings
from pr_agent.log import get_logger

def get_rate_limit_status(github_token) -> dict:
    GITHUB_API_URL = get_settings(use_context=False).get("GITHUB.BASE_URL", "https://api.github.com").rstrip("/")
    RATE_LIMIT_URL = f"{GITHUB_API_URL}/rate_limit"
    HEADERS = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {github_token}"
    }

    response = requests.get(RATE_LIMIT_URL, headers=HEADERS)
    try:
        rate_limit_info = response.json()
        if rate_limit_info.get('message') == 'Rate limiting is not enabled.':  # for github enterprise
            return {'resources': {}}
        response.raise_for_status()  # Check for HTTP errors
    except:  # retry
        time.sleep(0.1)
        response = requests.get(RATE_LIMIT_URL, headers=HEADERS)
        return response.json()
    return rate_limit_info


def validate_rate_limit_github(github_token, installation_id=None, threshold=0.1) -> bool:
    try:
        rate_limit_status = get_rate_limit_status(github_token)
        if installation_id:
            get_logger().debug(f"installation_id: {installation_id}, Rate limit status: {rate_limit_status['rate']}")
    # validate that the rate limit is not exceeded
        for key, value in rate_limit_status['resources'].items():
            if value['remaining'] < value['limit'] * threshold:
                get_logger().error(f"key: {key}, value: {value}")
                return False
        return True
    except Exception as e:
        get_logger().error(f"Error in rate limit {e}",
                           artifact={"traceback": traceback.format_exc()})
        return True


def validate_and_await_rate_limit(github_token):
    try:
        rate_limit_status = get_rate_limit_status(github_token)
        # validate that the rate limit is not exceeded
        for key, value in rate_limit_status['resources'].items():
            if value['remaining'] < value['limit'] // 80:
                get_logger().error(f"key: {key}, value: {value}")
                sleep_time_sec = value['reset'] - datetime.now().timestamp()
                sleep_time_hour = sleep_time_sec / 3600.0
                get_logger().error(f"Rate limit exceeded. Sleeping for {sleep_time_hour} hours")
                if sleep_time_sec > 0:
                    time.sleep(sleep_time_sec + 1)
                rate_limit_status = get_rate_limit_status(github_token)
        return rate_limit_status
    except:
        get_logger().error("Error in rate limit")
        return None


def github_action_output(output_data: dict, key_name: str):
    try:
        if not get_settings().get('github_action_config.enable_output', False):
            return

        key_data = output_data.get(key_name, {})
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            print(f"{key_name}={json.dumps(key_data, indent=None, ensure_ascii=False)}", file=fh)
    except Exception as e:
        get_logger().error(f"Failed to write to GitHub Action output: {e}")
    return
