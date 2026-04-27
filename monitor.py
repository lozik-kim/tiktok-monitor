import requests
import json
import os
import xml.etree.ElementTree as ET

ACCOUNTS = ["drop_kr", "grainy.fm", "kpopssed1"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
STATE_FILE = "state.json"

RSSHUB_INSTANCES = [
    "https://rsshub.app",
    "https://rss.shab.fun",
    "https://rsshub.rssforever.com",
]


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
    for base in RSSHUB_INSTANCES:
        url = f"{base}/tiktok/user/@{username}"
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                continue

            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            # RSS 2.0
            items = root.findall(".//item")
            if items:
                item = items[0]
                title = item.findtext("title") or ""
                link = item.findtext("link") or ""
                guid = item.findtext("guid") or link
                video_id = guid.rstrip("/").split("/")[-1]
                print(f"[{username}] RSS OK ({base}): {title[:50]}")
                return {"id": video_id, "desc": title, "url": link}

            # Atom
            entries = root.findall("atom:entry", ns)
            if entries:
                entry = entries[0]
                title = entry.findtext("atom:title", namespaces=ns) or ""
                link_el = entry.find("atom:link", ns)
                link = link_el.attrib.get("href", "") if link_el is not None else ""
                video_id = link.rstrip("/").split("/")[-1]
                print(f"[{username}] Atom OK ({base}): {title[:50]}")
                return {"id": video_id, "desc": title, "url": link}

        except Exception as e:
            print(f"[{username}] {base} 실패: {e}")
            continue

    print(f"[{username}] 모든 RSS 인스턴스 실패")
    return None


def send_slack(username, video):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL이 설정되지 않았습니다")
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
