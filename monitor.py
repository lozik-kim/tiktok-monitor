import requests
import json
import re
import os

ACCOUNTS = ["drop_kr", "grainy.fm", "kpopssed1"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
STATE_FILE = "state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def fetch_latest_video(username):
    url = f"https://www.tiktok.com/@{username}"
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{username}] 要請 失敗: {e}")
        return None

    html = resp.text

    for pattern in [
        r'<script id="SIGI_STATE"[^>]*>(.*?)<\/script>',
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)<\/script>',
    ]:
        m = re.search(pattern, html, re.DOTALL)
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue

        items = data.get("ItemModule", {})
        if items:
            sorted_items = sorted(
                items.values(),
                key=lambda x: int(x.get("createTime", 0)),
                reverse=True,
            )
            if sorted_items:
                v = sorted_items[0]
                return {
                    "id": v.get("id", ""),
                    "desc": v.get("desc", ""),
                    "url": f"https://www.tiktok.com/@{username}/video/{v.get('id', '')}",
                }

        scope = data.get("__DEFAULT_SCOPE__", {})
        item_list = scope.get("webapp.user-post", {}).get("itemList", [])
        if item_list:
            v = item_list[0]
            return {
                "id": v.get("id", ""),
                "desc": v.get("desc", ""),
                "url": f"https://www.tiktok.com/@{username}/video/{v.get('id', '')}",
            }

    print(f"[{username}] 小数 欠些數據")
    return None


def send_slack(username, video):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set")
        return

    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"🎵 *새 TikTok 영상 업로드!*\n"
                        f"*계정:* <https://www.tiktok.com/@{username}|@{username}>\n"
                        f"*설명:* {video['desc'] or '(없음)'}\n"
                        f"*링크:* {video['url']}"
                    ),
                },
            }
        ]
    }

    try:
        r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"[{username}] Slack 알림 전송 완료 ✅")
        else:
            print(f"[{username}] Slack 오류: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[{username}] Slack 전송 실패: {e}")


def main():
    state = load_state()
    new_state = dict(state)

    for username in ACCOUNTS:
        print(f"\n🔍 @{username} 확인 중...")
        video = fetch_latest_video(username)

        if video is None:
            print(f"[{username}] 조회 실패, 건너뜀")
            continue

        print(f"[{username}] 최신 영상: {video['id']} — {video['desc'][:60]}")

        last_id = state.get(username, {}).get("last_id")

        if last_id is None:
            print(f"[{username}] 첫 실행 — 기준값 저장")
        elif last_id != video["id"]:
            print(f"[{username}] 🆕 새 영상 발견!")
            send_slack(username, video)
        else:
            print(f"[{username}] 새 영상 없음")

        new_state[username] = {"last_id": video["id"]}

    save_state(new_state)
    print("\n✅ 완료")


if __name__ == "__main__":
    main()
